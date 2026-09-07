"""Comandos de linha de comando do app."""

import sys

import click
from flask.cli import with_appcontext
from psycopg import errors
from werkzeug.security import generate_password_hash

from freedom.db import get_connection


def register_cli(app):
    app.cli.add_command(create_user)
    app.cli.add_command(set_password)


@click.command("create-user")
@click.option("--login", required=True, help="Nome de acesso do usuario.")
@click.option("--pessoa", required=True, help="Nome do membro da familia.")
@with_appcontext
def create_user(login, pessoa):
    """Cria um usuario em tb_usuarios e, se preciso, a pessoa em tb_pessoas.

    A senha e pedida de forma interativa e nunca aparece na linha de comando
    nem no historico do shell.
    """
    login = login.strip()
    pessoa = pessoa.strip()
    if not login or not pessoa:
        raise click.ClickException("Login e pessoa nao podem ser vazios.")

    # Checagem antecipada so para dar mensagem boa antes de pedir a senha; a
    # garantia real e o UNIQUE de tb_usuarios.login, tratado abaixo.
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM tb_usuarios WHERE login = %s", (login,))
        if cur.fetchone() is not None:
            raise click.ClickException(
                f"Ja existe um usuario com o login '{login}'."
            )

    senha = click.prompt(
        "Senha", hide_input=True, confirmation_prompt="Repita a senha"
    )
    if not senha:
        raise click.ClickException("A senha nao pode ser vazia.")

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
            f"Ja existe um usuario com o login '{login}'."
        ) from None

    if pessoa_criada:
        click.echo(f"Pessoa '{pessoa}' criada (id {pessoa_id}).")
    else:
        click.echo(f"Pessoa '{pessoa}' ja existia (id {pessoa_id}).")
    click.echo(f"Usuario '{login}' criado (id {usuario_id}).")


@click.command("set-password")
@click.option("--login", required=True, help="Login do usuario que troca a senha.")
@with_appcontext
def set_password(login):
    """Troca a senha de um usuario existente.

    A senha e pedida sem eco, com confirmacao, e so o hash chega ao banco.
    """
    login = login.strip()
    if not login:
        raise click.ClickException("Informe o login.")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, ativo FROM tb_usuarios WHERE login = %s", (login,)
        )
        usuario = cur.fetchone()

    if usuario is None:
        raise click.ClickException(f"Nao existe usuario com o login '{login}'.")

    senha = click.prompt(
        "Nova senha", hide_input=True, confirmation_prompt="Repita a nova senha"
    )
    if not senha:
        raise click.ClickException("A senha nao pode ser vazia.")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE tb_usuarios SET senha_hash = %s WHERE id = %s",
            (generate_password_hash(senha), usuario["id"]),
        )

    click.echo(f"Senha do usuario '{login}' atualizada.")
    if not usuario["ativo"]:
        click.echo(
            "Atencao: este usuario esta inativo e segue sem conseguir entrar."
        )
