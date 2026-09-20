"""Comandos de linha de comando do app."""

import sys

import click
from flask.cli import with_appcontext
from psycopg import errors
from werkzeug.security import generate_password_hash

from freedom import ipca
from freedom.auth.servico import trocar_senha
from freedom.db import get_connection
from freedom.util import formatar_numero


def register_cli(app):
    app.cli.add_command(create_user)
    app.cli.add_command(set_password)
    app.cli.add_command(carregar_ipca)


@click.command("create-user")
@click.option("--login", required=True, help="Nome de acesso do usuário.")
@click.option("--pessoa", required=True, help="Nome do membro da família.")
@with_appcontext
def create_user(login, pessoa):
    """Cria um usuário em tb_usuarios e, se preciso, a pessoa em tb_pessoas.

    A senha é pedida de forma interativa e nunca aparece na linha de comando
    nem no histórico do shell.
    """
    login = login.strip()
    pessoa = pessoa.strip()
    if not login or not pessoa:
        raise click.ClickException("Login e pessoa não podem ser vazios.")

    # Checagem antecipada so para dar mensagem boa antes de pedir a senha; a
    # garantia real e o UNIQUE de tb_usuarios.login, tratado abaixo.
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM tb_usuarios WHERE login = %s", (login,))
        if cur.fetchone() is not None:
            raise click.ClickException(
                f"Já existe um usuário com o login '{login}'."
            )

    senha = click.prompt(
        "Senha", hide_input=True, confirmation_prompt="Repita a senha"
    )
    if not senha:
        raise click.ClickException("A senha não pode ser vazia.")

    senha_hash = generate_password_hash(senha)

    try:
        # Uma transacao so: ou nasce pessoa + usuario, ou nada.
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT id FROM tb_pessoas WHERE nome = %s", (pessoa,))
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO tb_pessoas (nome) VALUES (%s) RETURNING id",
                    (pessoa,),
                )
                pessoa_id = cur.fetchone()["id"]
                pessoa_criada = True
            else:
                pessoa_id = row["id"]
                pessoa_criada = False

            cur.execute(
                """
                INSERT INTO tb_usuarios (login, senha_hash, pessoa_id)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (login, senha_hash, pessoa_id),
            )
            usuario_id = cur.fetchone()["id"]
    except errors.UniqueViolation:
        # Corrida entre a checagem acima e o INSERT.
        raise click.ClickException(
            f"Já existe um usuário com o login '{login}'."
        ) from None

    if pessoa_criada:
        click.echo(f"Pessoa '{pessoa}' criada (id {pessoa_id}).")
    else:
        click.echo(f"Pessoa '{pessoa}' já existia (id {pessoa_id}).")
    click.echo(f"Usuário '{login}' criado (id {usuario_id}).")


@click.command("set-password")
@click.option("--login", required=True, help="Login do usuário que troca a senha.")
@with_appcontext
def set_password(login):
    """Troca a senha de um usuário existente.

    A senha é pedida sem eco, com confirmação, e só o hash chega ao banco.
    """
    login = login.strip()
    if not login:
        raise click.ClickException("Informe o login.")

    with get_connection() as conn, conn.cursor() as cur:
        # `ativo` porque o aviso do fim depende dele; o id nao e mais
        # preciso desde que a gravacao passou a ser por login.
        cur.execute("SELECT ativo FROM tb_usuarios WHERE login = %s", (login,))
        usuario = cur.fetchone()

    if usuario is None:
        raise click.ClickException(f"Não existe usuário com o login '{login}'.")

    senha = click.prompt(
        "Nova senha", hide_input=True, confirmation_prompt="Repita a nova senha"
    )
    if not senha:
        raise click.ClickException("A senha não pode ser vazia.")

    # A gravação é a mesma da tela /conta/senha, e é uma função só: o hash
    # nasce em um lugar no sistema inteiro.
    trocar_senha(login, senha)

    click.echo(f"Senha do usuário '{login}' atualizada.")
    if not usuario["ativo"]:
        click.echo(
            "Atenção: este usuário está inativo e segue sem conseguir entrar."
        )


@click.command("carregar-ipca")
@with_appcontext
def carregar_ipca():
    """Baixa a série do IPCA no SIDRA (IBGE) e grava em tb_ipca.

    Rode depois do dia 10 de cada mês, quando o IBGE publica o índice do mês
    anterior. Rodar de novo não faz mal: mês que já está igual não é tocado e
    nenhuma linha é apagada.
    """
    try:
        r = ipca.carregar()
    except ipca.ErroIpca as erro:
        # ClickException imprime só a mensagem e sai com código 1: o
        # traceback não diz nada a quem só quer saber se o mês novo entrou.
        raise click.ClickException(str(erro)) from None

    variacao = (
        f"{formatar_numero(r['variacao_ultimo'], 2)}%"
        if r["variacao_ultimo"] is not None
        else "não publicada"
    )

    click.echo("Série do IPCA lida do SIDRA (IBGE), tabela 1737.")
    click.echo(
        f"Período coberto: {r['primeiro']:%Y-%m} a {r['ultimo']:%Y-%m} "
        f"({r['meses']} meses)."
    )
    click.echo(
        f"Número-índice com {r['casas']} casas decimais na resposta da API."
    )
    click.echo(
        f"Inseridos: {r['inseridos']}. "
        f"Atualizados: {r['atualizados']}. "
        f"Já iguais: {r['iguais']}."
    )

    # A mesma frase que a faixa da tela mostra, do mesmo lugar: mês sem
    # variação publicada é legítimo, mas é o tipo de buraco que se descobre
    # tarde, quando um gráfico some.
    nulas = ipca.texto_das_nulas(r["meses_nulos"])
    if nulas:
        click.echo(nulas)

    click.echo(
        f"Último mês: {r['ultimo']:%Y-%m} — número-índice "
        f"{formatar_numero(r['indice_ultimo'], 2)}, variação {variacao}."
    )
