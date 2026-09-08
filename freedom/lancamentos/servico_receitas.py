"""Consultas da tela de receitas.

Toda leitura sai de `vw_receitas` (que já traz categoria, subcategoria e a
situação da fonte); INSERT, UPDATE e DELETE vão em `tb_receitas`.

Os helpers de mês, a paginação e o parser de valor não são reimplementados
aqui: vêm de `servico.py` e de `freedom/util.py`, os mesmos que a consulta de
despesas usa.
"""

from freedom.db import query_all, query_one
from freedom.lancamentos.servico import intervalo_do_mes, mes_corrente
from freedom.util import escapar_like

# Separador do rótulo da fonte, uma vez só: aparece no select, na lista e no
# resumo, e mudar de ideia aqui muda em todos.
SEPARADOR_FONTE = " › "


# --------------------------------------------------------------------------
# Opções dos selects
# --------------------------------------------------------------------------

_SELECT_FONTE = """
    SELECT id, categoria, subcategoria, ativo,
           categoria || %s || subcategoria AS rotulo
      FROM tb_ref_receitas
"""


def fontes_ativas():
    """Fontes que podem receber lançamento novo, na ordem do select."""
    return query_all(
        _SELECT_FONTE + " WHERE ativo = TRUE ORDER BY categoria, subcategoria",
        (SEPARADOR_FONTE,),
    )


def fonte(ref_receita_id):
    """Uma fonte, ativa ou não.

    A edição precisa dela mesmo desativada: senão a receita perderia a
    classificação que já tinha gravada.
    """
    if not ref_receita_id:
        return None
    return query_one(_SELECT_FONTE + " WHERE id = %s",
                     (SEPARADOR_FONTE, ref_receita_id))


def opcoes_de_filtro():
    """Pessoas e fontes: TODAS, inclusive inativas.

    O histórico precisa continuar consultável depois que algo é desativado.
    """
    return {
        "pessoas": query_all(
            "SELECT id, nome, ativo FROM tb_pessoas ORDER BY nome"),
        "fontes": query_all(
            _SELECT_FONTE + " ORDER BY categoria, subcategoria",
            (SEPARADOR_FONTE,)),
    }


# --------------------------------------------------------------------------
# Lista, totais e resumo
#
# O WHERE é montado como lista de condições + lista de parâmetros. Nenhum
# valor vindo do request entra em f-string de SQL.
# --------------------------------------------------------------------------

POR_PAGINA = 50

# vw_receitas não traz nome de pessoa (mesma decisão da vw_despesas); o JOIN
# é feito aqui.
_SELECT_LISTA = """
    SELECT v.id, v.data, v.ano_mes, v.descricao, v.valor,
           v.ref_receita_id, v.categoria, v.subcategoria, v.ref_receita_ativo,
           v.pessoa_id, v.usuario_id, v.anotacoes, v.criado_em, v.atualizado_em,
           p.nome AS pessoa_nome
      FROM vw_receitas v
      JOIN tb_pessoas  p ON p.id = v.pessoa_id
"""

# Data decrescente e, no mesmo dia, o lançamento mais recente em cima. O id
# desempata o que empatar até em criado_em, para a paginação ser estável.
ORDEM = "v.data DESC, v.criado_em DESC, v.id DESC"


def _where(filtros):
    """Devolve (trecho_where, params) a partir dos filtros já validados.

    O mês entra como intervalo de datas, e não como `ano_mes = %s`: ano_mes é
    coluna derivada da view, e comparar com ela obriga o Postgres a calcular a
    expressão linha a linha. Com `data >= inicio AND data < fim` o
    ix_receitas_data existente pode ser usado, sem precisar de índice novo.
    """
    inicio, fim = intervalo_do_mes(filtros["mes"])
    condicoes = ["v.data >= %s", "v.data < %s"]
    params = [inicio, fim]

    if filtros["pessoa"]:
        condicoes.append("v.pessoa_id = %s")
        params.append(filtros["pessoa"])
    if filtros["fonte"]:
        condicoes.append("v.ref_receita_id = %s")
        params.append(filtros["fonte"])
    if filtros["q"]:
        # ILIKE sem unaccent: 'salario' não acha 'salário'. Instalar a
        # extensão está fora do escopo desta rodada.
        condicoes.append("v.descricao ILIKE '%%' || %s || '%%' ESCAPE '\\'")
        params.append(escapar_like(filtros["q"]))

    return " WHERE " + " AND ".join(condicoes), params


def totais_do_filtro(filtros):
    """Total e contagem do filtro inteiro, agregados no banco.

    Nunca somando as linhas da página em Python, que dariam só o total da
    página visível.
    """
    where, params = _where(filtros)
    return query_one(
        "SELECT count(*) AS quantidade, "
        "       COALESCE(SUM(v.valor), 0) AS total "
        "  FROM vw_receitas v" + where,
        params,
    )


def resumo_por_categoria(filtros):
    """Valor e percentual por categoria de receita, do maior para o menor."""
    where, params = _where(filtros)
    linhas = query_all(
        "SELECT v.categoria, count(*) AS quantidade, SUM(v.valor) AS total "
        "  FROM vw_receitas v" + where +
        " GROUP BY v.categoria ORDER BY SUM(v.valor) DESC, v.categoria",
        params,
    )
    total_geral = sum(l["total"] for l in linhas) or 0
    for l in linhas:
        l["pct"] = float(l["total"]) * 100 / float(total_geral) if total_geral else 0.0
    return linhas


def pagina_de_receitas(filtros, pagina):
    """Uma página de resultados, já com o nome da pessoa."""
    where, params = _where(filtros)
    return query_all(
        _SELECT_LISTA + where + f" ORDER BY {ORDEM} LIMIT %s OFFSET %s",
        params + [POR_PAGINA, (pagina - 1) * POR_PAGINA],
    )


def meses_com_lancamento(incluir=None):
    """Meses que têm receita, do mais recente para o mais antigo.

    `incluir` garante que o mês selecionado apareça no seletor mesmo sem
    lançamento nenhum (a navegação por setas pode chegar num mês vazio).
    """
    meses = [l["ano_mes"] for l in query_all(
        "SELECT DISTINCT ano_mes FROM vw_receitas ORDER BY ano_mes DESC"
    )]
    for extra in filter(None, (incluir, mes_corrente())):
        if extra not in meses:
            meses.append(extra)
    return sorted(set(meses), reverse=True)


# --------------------------------------------------------------------------
# Registro isolado
# --------------------------------------------------------------------------

def receita_para_edicao(receita_id):
    """Lê de tb_receitas: a edição escreve nas colunas da tabela, não da view."""
    return query_one(
        """
        SELECT id, data, descricao, valor, ref_receita_id, pessoa_id,
               usuario_id, anotacoes
          FROM tb_receitas
         WHERE id = %s
        """,
        (receita_id,),
    )


def pessoa(pessoa_id):
    """Uma pessoa, ativa ou não.

    Mesma razão de `fonte`: a edição precisa manter quem recebeu, mesmo que
    a pessoa tenha sido desativada depois.
    """
    if not pessoa_id:
        return None
    return query_one(
        "SELECT id, nome, ativo FROM tb_pessoas WHERE id = %s", (pessoa_id,)
    )
