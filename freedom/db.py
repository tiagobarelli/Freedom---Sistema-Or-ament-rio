"""Acesso ao PostgreSQL via psycopg 3 + pool de conexoes.

O pool e criado uma vez na inicializacao do app e guardado em app.extensions.
Todas as queries devem ser parametrizadas (%s), nunca formatadas em string.
"""

from contextlib import contextmanager

from flask import current_app
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def init_app(app):
    """Cria o ConnectionPool e registra o fechamento no teardown do app."""
    pool = ConnectionPool(
        conninfo=app.config["DATABASE_URL"],
        min_size=app.config["DB_POOL_MIN"],
        max_size=app.config["DB_POOL_MAX"],
        kwargs={"row_factory": dict_row},
        open=False,
        name="freedom",
    )
    pool.open()
    # Falha cedo e com mensagem clara se o banco nao estiver no ar.
    pool.wait(timeout=10)

    app.extensions["db_pool"] = pool

    @app.teardown_appcontext
    def _close_pool_on_shutdown(exception=None):  # noqa: ARG001
        # Chamado a cada request; o pool em si so fecha no shutdown do processo.
        return None

    import atexit

    atexit.register(pool.close)


def get_pool():
    return current_app.extensions["db_pool"]


@contextmanager
def get_connection():
    """Devolve uma conexao do pool dentro de uma transacao.

    Commit automatico ao sair sem erro, rollback se houver excecao. A conexao
    volta para o pool no fim do bloco.

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...", (param,))
    """
    with get_pool().connection() as conn:
        yield conn


def query_one(sql, params=None):
    """Executa um SELECT e devolve a primeira linha como dict, ou None."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def query_all(sql, params=None):
    """Executa um SELECT e devolve todas as linhas como lista de dicts."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()
