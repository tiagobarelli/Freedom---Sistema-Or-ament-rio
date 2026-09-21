"""Página de backup (`/configuracoes/backup`): exporta o banco inteiro.

Um assunto, um módulo — a mesma divisão de `cadastros/resumos_anuais.py`.
Fica no grupo Configurações porque é o que é: manutenção do sistema, e não
lançamento nem cadastro.

**Só exporta.** Não há restauração pela interface, e não há por quê: restaurar
é derrubar o banco que está no ar e pôr outro no lugar, coisa que se faz no
terminal, com o servidor à mão e sabendo o que se está apagando. A tela
mostra o comando; quem o roda é o dono.

Não há histórico de backup — nem tabela, nem log, nem "último backup em". O
arquivo sai pelo navegador e passa a ser do sistema de arquivos do dono; o
sistema não teria como saber se ele ainda existe, e um "último backup em"
que mente é pior que nenhum.

O dump é gerado pelo `pg_dump` da própria máquina onde o Flask roda, falando
com o banco por TCP: host, porta, usuário e banco saem do `DATABASE_URL`, e
de nenhum outro lugar. Em produção quem tem o `pg_dump` é a própria imagem que
serve o app; no desenvolvimento é o Windows do dono, e é para ele que existe a
variável `PG_DUMP` — ver `_executavel`.

Assim o mecanismo é um só nos dois lugares, e o processo do Flask não precisa
de nada além do banco a que já se conecta.

Três cuidados que valem mais que o código que os implementa:

- **Nada de streamar.** O dump é bufferizado inteiro e só vira resposta se o
  `pg_dump` terminou bem. Streamar o stdout daria 200 antes de saber o
  desfecho, e uma falha no meio deixaria o dono com um `.sql` truncado
  acreditando que tem backup.
- **Nada em disco do servidor.** Os bytes vão da memória para a resposta. Não
  há pasta temporária, então não há arquivo esquecido com senha_hash dentro.
- **Nada de credencial na linha de comando.** Ver `_comando` abaixo.
"""

import os
import subprocess
from datetime import datetime

from flask import Response, current_app, flash, redirect, render_template, url_for
from flask_login import login_required
from psycopg.conninfo import conninfo_to_dict

from freedom.configuracoes import bp

# Executável usado quando `PG_DUMP` não está no ambiente: o que estiver no
# PATH. É o caso da imagem de produção, que instala o `postgresql-client`.
PADRAO_PG_DUMP = "pg_dump"

# Teto da geração inteira. O dump de hoje sai em menos de um segundo; 120 s
# cobrem um acervo muitas vezes maior e ainda param bem antes de o navegador
# desistir sozinho.
TEMPO_LIMITE = 120

# Quantas linhas do stderr do pg_dump a mensagem de erro carrega. As últimas,
# e não as primeiras: quando o Postgres recusa, o motivo está no fim.
LINHAS_DE_ERRO = 3


class ErroBackup(Exception):
    """Falha que a tela sabe mostrar. A mensagem já vai pronta em português."""


def _identificacao():
    """Host, porta, usuário, banco e senha saem do `DATABASE_URL`, e de mais
    nenhum lugar.

    `conninfo_to_dict` entende tanto a URL quanto o formato chave=valor, então
    não importa em qual das duas formas o `.env` está escrito. A senha agora é
    devolvida junto — o `pg_dump` por TCP precisa dela —, mas não chega perto
    da linha de comando: quem a usa é `_ambiente`, e o `_comando` não a vê.

    Porta e senha podem faltar numa conninfo legítima (conexão local no porto
    padrão, autenticação sem senha). Faltando, cada uma vira o que o `pg_dump`
    faria sozinho: 5432 e nenhuma senha.
    """
    info = conninfo_to_dict(current_app.config["DATABASE_URL"])
    return (
        info["host"],
        info.get("port") or "5432",
        info["user"],
        info["dbname"],
        info.get("password") or "",
    )


def _executavel():
    """Qual `pg_dump` chamar.

    Na imagem de produção é o do PATH, instalado pelo `postgresql-client`. No
    Windows do desenvolvimento não há PATH que ajude: os binários do Postgres
    ficam onde o dono os pôs, e `PG_DUMP` recebe o caminho do `.exe`.
    """
    return os.environ.get("PG_DUMP") or PADRAO_PG_DUMP


def _comando(host, porta, usuario, banco):
    """A linha do `pg_dump`, como lista: `shell=False`, sem interpolação.

    **Nenhuma credencial aqui.** A senha vai por `PGPASSWORD` no ambiente do
    subprocesso, e não num argumento, porque argumento aparece para qualquer
    um que liste os processos da máquina — e o `pg_dump` nem sequer aceita
    senha por argumento, justamente por isso.

    `--no-password` existe para o erro não virar espera: sem ele, um banco que
    pede senha e não a recebe faz o `pg_dump` PERGUNTAR no terminal, e o
    processo do Flask ficaria parado até o `TEMPO_LIMITE` estourar — a tela
    diria "tempo esgotado" onde o que houve foi credencial errada.

    `--no-owner` e `--no-privileges` deixam o dump reaplicável por outro
    usuário: no servidor quem restaura é o dono do banco de lá, que não
    precisa ser o mesmo nome de cá.
    """
    return [
        _executavel(),
        "--host", host,
        "--port", str(porta),
        "--username", usuario,
        "--dbname", banco,
        "--no-password",
        "--no-owner", "--no-privileges", "--encoding=UTF8",
    ]


def _ambiente(senha):
    """O ambiente do subprocesso: o do processo mais `PGPASSWORD`.

    Copiado, e não substituído: o `pg_dump` do Windows precisa do PATH e do
    SystemRoot para carregar as próprias DLLs. `PGPASSWORD` vazio sairia da
    cópia em vez de ficar lá como string vazia, que o Postgres trataria como
    senha errada.
    """
    ambiente = dict(os.environ)
    if senha:
        ambiente["PGPASSWORD"] = senha
    else:
        ambiente.pop("PGPASSWORD", None)
    return ambiente


def _ultimas_linhas(bruto):
    """stderr do pg_dump -> uma linha só com o fim do que ele reclamou."""
    linhas = [l.strip() for l in bruto.decode("utf-8", "replace").splitlines()
              if l.strip()]
    return " | ".join(linhas[-LINHAS_DE_ERRO:])


def nome_do_arquivo(agora):
    """`freedom_AAAAMMDD-HHMM.sql`, na data e hora locais da geração.

    Recebe o instante em vez de o ler: separa a função pura do relógio, como
    `ipca.mes_esperado`. Minuto basta — dois backups no mesmo minuto são a
    pessoa clicando duas vezes, e o navegador resolve isso sozinho
    acrescentando "(1)".
    """
    return f"freedom_{agora:%Y%m%d-%H%M}.sql"


def gerar_dump():
    """Roda o pg_dump e devolve (bytes, nome do arquivo).

    Levanta `ErroBackup` em qualquer falha, com mensagem pronta para a tela.
    Fora das rotas para o que é execução não se misturar com o que é HTTP.
    """
    host, porta, usuario, banco, senha = _identificacao()
    try:
        processo = subprocess.run(
            _comando(host, porta, usuario, banco),
            capture_output=True,
            timeout=TEMPO_LIMITE,
            env=_ambiente(senha),
        )
    except FileNotFoundError:
        # O executável não existe. Na imagem de produção não acontece — ela
        # instala o cliente Postgres. No Windows acontece: é o caso de
        # `PG_DUMP` apontando para um caminho que mudou de lugar.
        raise ErroBackup(
            f"Não encontrei o pg_dump ({_executavel()}). Instale o cliente do "
            "PostgreSQL ou aponte a variável PG_DUMP para o executável."
        ) from None
    except subprocess.TimeoutExpired:
        raise ErroBackup(
            f"O pg_dump passou de {TEMPO_LIMITE} segundos e foi interrompido. "
            "Nenhum arquivo foi gerado."
        ) from None

    if processo.returncode != 0:
        detalhe = _ultimas_linhas(processo.stderr)
        raise ErroBackup(
            f"O pg_dump falhou (código {processo.returncode})."
            + (f" {detalhe}" if detalhe else "")
        )

    # Código 0 com stdout vazio não existe em pg_dump são, mas se existir é
    # um arquivo de zero byte com cara de backup — pior que erro nenhum.
    if not processo.stdout:
        raise ErroBackup(
            "O pg_dump terminou sem erro mas não devolveu nada. "
            "Nenhum arquivo foi gerado."
        )

    return processo.stdout, nome_do_arquivo(datetime.now())


# --------------------------------------------------------------------------
# Rotas
# --------------------------------------------------------------------------

@bp.route("/backup")
@login_required
def backup_tela():
    return render_template("configuracoes/backup.html")


@bp.route("/backup/confirmar")
@login_required
def backup_confirmar():
    """Segundo passo: troca o botão pela pergunta. Só troca DOM, nada roda."""
    return render_template("configuracoes/_backup_confirmar.html")


@bp.route("/backup/acao")
@login_required
def backup_acao():
    """Cancelar: devolve o botão de partida. Nenhum dump foi gerado."""
    return render_template("configuracoes/_backup_botao.html")


@bp.route("/backup/executar", methods=["POST"])
@login_required
def backup_executar():
    """Gera o dump e o entrega como anexo. Em falha, volta à tela com o erro.

    POST de formulário comum, **sem HTMX**, e é o único ponto do sistema em
    que o padrão do projeto não se aplica: o HTMX troca DOM, não dispara
    download. Uma resposta com `Content-Disposition` chegando por `hx-post`
    seria engolida pelo swap e o arquivo nunca apareceria.

    Por ser POST comum, a falha também segue o caminho comum: `flash` mais
    redirect para a própria tela — e não um fragmento com status de erro,
    que aqui não teria onde encaixar.
    """
    try:
        dados, nome = gerar_dump()
    except ErroBackup as erro:
        flash(f"Backup não realizado. {erro}", "erro")
        return redirect(url_for("configuracoes.backup_tela"))

    return Response(
        dados,
        headers={
            "Content-Type": "application/sql; charset=utf-8",
            "Content-Length": str(len(dados)),
            "Content-Disposition": f'attachment; filename="{nome}"',
        },
    )
