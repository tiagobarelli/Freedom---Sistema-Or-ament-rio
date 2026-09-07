"""Peças compartilhadas pelas cinco telas de cadastro.

Cada entidade tem seu módulo, mas alternar ativo/inativo, traduzir violação de
UNIQUE e montar a lista são a mesma coisa em todas — ficam aqui.
"""

from psycopg import errors

from freedom.db import get_connection

# As tabelas de referência têm coluna `ativo`, menos tb_contas, que usa `ativa`.
# O nome vem sempre daqui, nunca de string interpolada em runtime.
_ENTIDADES = {
    "categorias": {
        "tabela": "tb_categorias",
        "coluna_ativo": "ativo",
        "rotulo": "Categoria",
    },
    "subcategorias": {
        "tabela": "tb_subcategorias",
        "coluna_ativo": "ativo",
        "rotulo": "Subcategoria",
    },
    "contas": {
        "tabela": "tb_contas",
        "coluna_ativo": "ativa",
        "rotulo": "Conta",
    },
    "pessoas": {
        "tabela": "tb_pessoas",
        "coluna_ativo": "ativo",
        "rotulo": "Pessoa",
    },
    "ref_receitas": {
        "tabela": "tb_ref_receitas",
        "coluna_ativo": "ativo",
        "rotulo": "Fonte de receita",
    },
}

# Constraint UNIQUE do banco -> (campo do formulário, mensagem para o usuário).
# O nome da constraint vem de pg_constraint; ver db/init/01_schema.sql.
MENSAGENS_UNIQUE = {
    "tb_categorias_nome_key": (
        "nome", "Já existe uma categoria com esse nome."),
    "uq_subcategorias_categoria_nome": (
        "nome", "Já existe uma subcategoria com esse nome nesta categoria."),
    "tb_contas_nome_key": (
        "nome", "Já existe uma conta com esse nome."),
    "tb_pessoas_nome_key": (
        "nome", "Já existe uma pessoa com esse nome."),
    "uq_ref_receitas_categoria_subcategoria": (
        "subcategoria",
        "Já existe uma fonte de receita com essa categoria e subcategoria."),
}


class NomeDuplicado(Exception):
    """UniqueViolation traduzida para algo que o formulário sabe exibir."""

    def __init__(self, campo, mensagem):
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


def traduzir_unique(exc):
    """Converte psycopg UniqueViolation em NomeDuplicado com texto legível.

    Sem isso, um nome repetido viraria página 500.
    """
    nome_constraint = getattr(exc.diag, "constraint_name", None)
    campo, mensagem = MENSAGENS_UNIQUE.get(
        nome_constraint, (None, "Já existe um registro com esses dados.")
    )
    return NomeDuplicado(campo, mensagem)


def aplicar_erro_duplicado(form, exc):
    """Pendura a mensagem no campo certo do formulário (ou no formulário todo).

    Devolve sempre False, para uso direto no fluxo da rota.
    """
    erro = traduzir_unique(exc)
    campo = getattr(form, erro.campo, None) if erro.campo else None
    if campo is not None:
        campo.errors = list(campo.errors) + [erro.mensagem]
    else:
        form.form_errors = list(getattr(form, "form_errors", [])) + [erro.mensagem]
    return False


def executar(sql, params=(), retornar=False):
    """Roda INSERT/UPDATE numa transação. Commit ao sair, rollback em erro."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if retornar:
            return cur.fetchone()
    return None


def alternar_ativo(entidade, registro_id):
    """Inverte a coluna de situação e devolve a linha já atualizada.

    Nada é apagado no sistema: desativar é o substituto de excluir. A troca é
    feita em um único UPDATE ... RETURNING para não haver leitura intermediária.
    """
    config = _ENTIDADES[entidade]
    coluna = config["coluna_ativo"]
    # tabela e coluna vêm do dicionário acima, nunca do request.
    sql = (
        f"UPDATE {config['tabela']} "
        f"   SET {coluna} = NOT {coluna} "
        f" WHERE id = %s "
        f"RETURNING id, {coluna} AS ativo"
    )
    return executar(sql, (registro_id,), retornar=True)


def rotulo(entidade):
    return _ENTIDADES[entidade]["rotulo"]
