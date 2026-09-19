"""Página de backup (`/configuracoes/backup`): exporta o banco inteiro.

Um assunto, um módulo — a mesma divisão de `cadastros/resumos_anuais.py`.
Fica no grupo Configurações porque é o que é: manutenção do sistema, e não
lançamento nem cadastro.

**Só exporta.** Não há restauração pela interface, e não há por quê: restaurar
é derrubar o banco que está no ar e pôr outro no lugar, coisa que se faz no
terminal, com o container à mão e sabendo o que se está apagando. A tela
mostra o comando; quem o roda é o dono.

Não há histórico de backup — nem tabela, nem log, nem "último backup em". O
arquivo sai pelo navegador e passa a ser do sistema de arquivos do dono; o
sistema não teria como saber se ele ainda existe, e um "último backup em"
que mente é pior que nenhum.

O dump é gerado DENTRO do container, por `docker exec`. Assim o `pg_dump` é o
da mesma versão do servidor (o binário da imagem `postgres:16`) e o host não
precisa ter cliente Postgres instalado — hoje não tem.

Três cuidados que valem mais que o código que os implementa:

- **Nada de streamar.** O dump é bufferizado inteiro e só vira resposta se o
  `pg_dump` terminou bem. Streamar o stdout daria 200 antes de saber o
  desfecho, e uma falha no meio deixaria o dono com um `.sql` truncado
  acreditando que tem backup.
- **Nada em disco do servidor.** Os bytes vão da memória para a resposta. Não
  há pasta temporária, então não há arquivo esquecido com senha_hash dentro.
- **Nada de credencial na linha de comando.** Ver `_comando` abaixo.
"""

import subprocess
from datetime import datetime

from flask import Response, current_app, flash, redirect, render_template, url_for
from flask_login import login_required
from psycopg.conninfo import conninfo_to_dict

from freedom.configuracoes import bp

# `container_name` do serviço `postgres` no docker-compose.yml, onde é
# literal (não vem do .env): o container sobe sempre com este nome.
CONTAINER = "freedom_postgres"

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
    """Usuário e banco saem do `DATABASE_URL`, e de nenhum outro lugar.

    `conninfo_to_dict` entende tanto a URL quanto o formato chave=valor, então
    não importa em qual das duas formas o `.env` está escrito. A senha que vem
    junto no dicionário é ignorada de propósito — ver `_comando`.
    """
    info = conninfo_to_dict(current_app.config["DATABASE_URL"])
    return info["user"], info["dbname"]


def _comando(usuario, banco):
    """A linha do `docker exec`, como lista: `shell=False`, sem interpolação.

    Sem senha nenhuma. Dentro do container a conexão do `pg_dump` é pelo
    socket local, e o `pg_hba.conf` que a imagem oficial do Postgres gera
    trata conexão local como `trust` — medido nesta rodada: o comando sai em
    0,2 s e não pergunta nada.

    Se um dia ele passar a pedir senha, o jeito seria `-e PGPASSWORD=...` no
    `docker exec`, lendo do `DATABASE_URL`. Isso não está escrito aqui porque
    tem um preço que hoje não precisa ser pago: o valor apareceria na linha de
    comando do processo no host, visível a qualquer um que liste processos.
    """
    return [
        "docker", "exec", CONTAINER,
        "pg_dump", "-U", usuario, "-d", banco,
        "--no-owner", "--no-privileges", "--encoding=UTF8",
    ]


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
    """Roda o pg_dump no container e devolve (bytes, nome do arquivo).

    Levanta `ErroBackup` em qualquer falha, com mensagem pronta para a tela.
    Fora das rotas para o que é execução não se misturar com o que é HTTP.
    """
    usuario, banco = _identificacao()
    try:
        processo = subprocess.run(
            _comando(usuario, banco),
            capture_output=True,
            timeout=TEMPO_LIMITE,
        )
    except FileNotFoundError:
        # Docker fora do PATH do processo do Flask. Acontece de verdade: o
        # serviço pode estar no ar e o `docker` não estar visível para quem
        # subiu o servidor.
        raise ErroBackup(
            "Não encontrei o comando docker. Confira se o Docker Desktop está "
            "no ar e se o `docker` está no PATH de quem roda o servidor."
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
