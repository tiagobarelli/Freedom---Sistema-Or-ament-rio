"""Consultas e helpers da área de lançamentos.

Leitura sai sempre de `vw_despesas` (que já traz categoria e essencialidade
efetiva); INSERT, UPDATE e DELETE vão em `tb_despesas`.
"""

from datetime import date

from flask import request

from freedom.db import query_all, query_one
from freedom.util import escapar_like

ESSENCIAL = "Essencial"
NAO_ESSENCIAL = "Não Essencial"

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


# --------------------------------------------------------------------------
# Opções dos selects
# --------------------------------------------------------------------------

def subcategorias_ativas():
    """Só subcategorias ativas de categorias ativas, ordenadas para o optgroup."""
    return query_all(
        """
        SELECT s.id, s.nome, s.essencialidade,
               c.id AS categoria_id, c.nome AS categoria_nome
          FROM tb_subcategorias s
          JOIN tb_categorias    c ON c.id = s.categoria_id
         WHERE s.ativo = TRUE AND c.ativo = TRUE
         ORDER BY c.nome, s.nome
        """
    )


def agrupar_por_categoria(linhas):
    """[(nome_categoria, [(id, nome), ...]), ...] preservando a ordem do SELECT."""
    grupos, atual, nome_atual = [], None, None
    for linha in linhas:
        if linha["categoria_nome"] != nome_atual:
            nome_atual = linha["categoria_nome"]
            atual = []
            grupos.append((nome_atual, atual))
        atual.append((linha["id"], linha["nome"]))
    return grupos


def contas_ativas():
    return query_all(
        "SELECT id, nome FROM tb_contas WHERE ativa = TRUE ORDER BY nome"
    )


def pessoas_ativas():
    return query_all(
        "SELECT id, nome FROM tb_pessoas WHERE ativo = TRUE ORDER BY nome"
    )


def subcategoria(subcategoria_id):
    """Subcategoria com a categoria, sem exigir que estejam ativas.

    Usada na edição e na rota de classificação: uma despesa antiga pode
    apontar para subcategoria que foi desativada depois.
    """
    if not subcategoria_id:
        return None
    return query_one(
        """
        SELECT s.id, s.nome, s.essencialidade, s.ativo,
               c.nome AS categoria_nome
          FROM tb_subcategorias s
          JOIN tb_categorias    c ON c.id = s.categoria_id
         WHERE s.id = %s
        """,
        (subcategoria_id,),
    )


# --------------------------------------------------------------------------
# Essencialidade efetiva
# --------------------------------------------------------------------------

def essencialidade_efetiva(override, sub):
    """COALESCE(despesa.essencialidade, subcategoria.essencialidade).

    Mesma regra da vw_despesas, repetida aqui porque o formulário precisa
    dela antes de existir linha no banco.
    """
    if override:
        return override
    if sub:
        return sub["essencialidade"]
    return None


# --------------------------------------------------------------------------
# Lista e totais
# --------------------------------------------------------------------------

# vw_despesas não traz nome de conta nem de pessoa (decisão registrada no
# schema); o JOIN é feito aqui.
_SELECT_LISTA = """
    SELECT v.id, v.data, v.ano_mes, v.descricao, v.valor,
           v.subcategoria, v.categoria, v.essencialidade, v.prioridade,
           v.integra_ipca, v.observacoes, v.criado_em, v.atualizado_em,
           v.conta_id, v.pessoa_id, v.usuario_id,
           ct.nome AS conta_nome,
           p.nome  AS pessoa_nome
      FROM vw_despesas v
      JOIN tb_contas  ct ON ct.id = v.conta_id
      JOIN tb_pessoas p  ON p.id  = v.pessoa_id
"""


def recentes(limite=15):
    """As mais recentes por criado_em. Sistema doméstico: mostra de todos."""
    return query_all(
        _SELECT_LISTA + " ORDER BY v.criado_em DESC, v.id DESC LIMIT %s",
        (limite,),
    )


def linha(despesa_id):
    return query_one(_SELECT_LISTA + " WHERE v.id = %s", (despesa_id,))


def despesa_para_edicao(despesa_id):
    """Lê de tb_despesas: a edição precisa do override cru, não do efetivo."""
    return query_one(
        """
        SELECT id, data, descricao, valor, subcategoria_id, conta_id,
               pessoa_id, usuario_id, essencialidade, prioridade,
               integra_ipca, observacoes
          FROM tb_despesas
         WHERE id = %s
        """,
        (despesa_id,),
    )


def total_do_mes(referencia):
    """Soma das despesas do mês da data informada, com o nome do mês."""
    ano_mes = referencia.year * 100 + referencia.month
    linha_total = query_one(
        "SELECT COALESCE(SUM(valor), 0) AS total, count(*) AS quantidade "
        "FROM vw_despesas WHERE ano_mes = %s",
        (ano_mes,),
    )
    return {
        "total": linha_total["total"],
        "quantidade": linha_total["quantidade"],
        "rotulo": f"{MESES[referencia.month - 1]} de {referencia.year}",
    }


def ultimo_lancamento_do_usuario(usuario_id):
    """Conta e pessoa do último lançamento do usuário, para pré-preencher."""
    return query_one(
        "SELECT conta_id, pessoa_id FROM tb_despesas "
        "WHERE usuario_id = %s ORDER BY criado_em DESC, id DESC LIMIT 1",
        (usuario_id,),
    )


# --------------------------------------------------------------------------
# Consulta com filtros
#
# O WHERE e montado como lista de condicoes + lista de parametros. Nenhum
# valor vindo do request entra em f-string de SQL: o unico trecho de SQL
# escolhido dinamicamente e a ordenacao, e vem de um dicionario fechado.
# --------------------------------------------------------------------------

POR_PAGINA = 50

# Whitelist de ordenacao. A chave vem do request; o valor, nunca.
ORDENS = {
    "data": "v.data DESC, v.id DESC",
    "valor": "v.valor DESC, v.id DESC",
}


# --------------------------------------------------------------------------
# Estado da tela vindo do request
#
# As tres funcoes abaixo nasceram privadas em consulta.py e passaram a ser
# importadas por receitas.py. Subiram para ca, sem underscore: sao a regra
# comum das duas telas de lista, e cada copia extra seria um lugar a mais
# para elas divergirem.
# --------------------------------------------------------------------------

def id_valido(args, chave, existentes):
    """Id de filtro que nao existe cai no padrao (sem filtro), nao em erro."""
    valor = args.get(chave, type=int)
    if valor and any(o["id"] == valor for o in existentes):
        return valor
    return None


def pagina_pedida(args):
    pagina = args.get("pagina", type=int)
    return pagina if pagina and pagina >= 1 else 1


def so_fragmento():
    """True quando o HTMX quer apenas o bloco de resultados.

    A excecao e a restauracao de historico: quando o cache do HTMX nao tem a
    tela, ele refaz o GET com HX-History-Restore-Request e espera a pagina
    inteira de volta. Devolver o fragmento ali quebraria o botao voltar.
    """
    return bool(
        request.headers.get("HX-Request")
        and not request.headers.get("HX-History-Restore-Request")
    )


def mes_valido(ano_mes):
    """AAAAMM -> (ano, mes) se fizer sentido como mes de calendario."""
    try:
        n = int(ano_mes)
    except (TypeError, ValueError):
        return None
    ano, mes = divmod(n, 100)
    if 1900 <= ano <= 2999 and 1 <= mes <= 12:
        return ano, mes
    return None


def mes_corrente():
    hoje = date.today()
    return hoje.year * 100 + hoje.month


def deslocar_mes(ano_mes, passos):
    """Mes anterior/seguinte em AAAAMM, sem depender de biblioteca de datas."""
    ano, mes = divmod(int(ano_mes), 100)
    total = (ano * 12 + (mes - 1)) + passos
    return (total // 12) * 100 + (total % 12) + 1


def rotulo_mes(ano_mes):
    ano, mes = divmod(int(ano_mes), 100)
    return f"{MESES[mes - 1]} de {ano}"


def intervalo_do_mes(ano_mes):
    """AAAAMM -> (primeiro dia do mes, primeiro dia do mes seguinte)."""
    ano, mes = divmod(int(ano_mes), 100)
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return inicio, fim


def _where(filtros):
    """Devolve (trecho_where, params) a partir dos filtros ja validados.

    O mes entra como intervalo de datas, e nao como `ano_mes = %s`: ano_mes e
    coluna derivada da view, e comparar com ela obriga o Postgres a calcular a
    expressao linha a linha (Seq Scan). Com `data >= inicio AND data < fim` o
    ix_despesas_data existente e usado, sem precisar de indice novo.
    """
    inicio, fim = intervalo_do_mes(filtros["mes"])
    condicoes = ["v.data >= %s", "v.data < %s"]
    params = [inicio, fim]

    if filtros["pessoa_id"]:
        condicoes.append("v.pessoa_id = %s")
        params.append(filtros["pessoa_id"])
    if filtros["categoria_id"]:
        condicoes.append("v.categoria_id = %s")
        params.append(filtros["categoria_id"])
    if filtros["conta_id"]:
        condicoes.append("v.conta_id = %s")
        params.append(filtros["conta_id"])
    if filtros["essencialidade"]:
        # Coluna efetiva da view (COALESCE ja aplicado), nunca a crua.
        condicoes.append("v.essencialidade = %s")
        params.append(filtros["essencialidade"])
    if filtros["q"]:
        # ILIKE sem unaccent: 'cafe' nao acha 'café'. Instalar a extensao
        # esta fora do escopo desta rodada.
        condicoes.append("v.descricao ILIKE '%%' || %s || '%%' ESCAPE '\\'")
        params.append(escapar_like(filtros["q"]))

    return " WHERE " + " AND ".join(condicoes), params


def totais_do_filtro(filtros):
    """Uma linha com total, contagem e a divisao essencial x nao essencial.

    Agregacao no banco sobre o filtro inteiro: nunca somando as linhas da
    pagina em Python, que dariam so o total da pagina visivel.
    """
    where, params = _where(filtros)
    linha = query_one(
        "SELECT count(*) AS quantidade, "
        "       COALESCE(SUM(v.valor), 0) AS total, "
        "       COALESCE(SUM(v.valor) FILTER "
        "                (WHERE v.essencialidade = 'Essencial'), 0) AS essencial, "
        "       COALESCE(SUM(v.valor) FILTER "
        "                (WHERE v.essencialidade <> 'Essencial'), 0) "
        "           AS nao_essencial, "
        "       count(*) FILTER (WHERE v.essencialidade = 'Essencial') "
        "           AS qtd_essencial "
        "  FROM vw_despesas v" + where,
        params,
    )
    total = linha["total"] or 0
    linha["pct_essencial"] = (
        float(linha["essencial"]) * 100 / float(total) if total else 0.0
    )
    linha["pct_nao_essencial"] = (
        float(linha["nao_essencial"]) * 100 / float(total) if total else 0.0
    )
    return linha


def resumo_por_categoria(filtros):
    """Valor e percentual por categoria, do maior para o menor."""
    where, params = _where(filtros)
    linhas = query_all(
        "SELECT v.categoria, count(*) AS quantidade, SUM(v.valor) AS total "
        "  FROM vw_despesas v" + where +
        " GROUP BY v.categoria ORDER BY SUM(v.valor) DESC, v.categoria",
        params,
    )
    total_geral = sum(l["total"] for l in linhas) or 0
    for l in linhas:
        l["pct"] = float(l["total"]) * 100 / float(total_geral) if total_geral else 0.0
    return linhas


def pagina_de_despesas(filtros, pagina):
    """Uma pagina de resultados, ja com nome de conta e de pessoa."""
    where, params = _where(filtros)
    ordem = ORDENS[filtros["ordem"]]      # chave validada; valor da whitelist
    return query_all(
        _SELECT_LISTA + where + f" ORDER BY {ordem} LIMIT %s OFFSET %s",
        params + [POR_PAGINA, (pagina - 1) * POR_PAGINA],
    )


def meses_com_lancamento(incluir=None):
    """Meses que tem despesa, do mais recente para o mais antigo.

    `incluir` garante que o mes selecionado apareca no seletor mesmo sem
    lancamento nenhum (a navegacao por setas pode chegar num mes vazio).
    """
    meses = [l["ano_mes"] for l in query_all(
        "SELECT DISTINCT ano_mes FROM vw_despesas ORDER BY ano_mes DESC"
    )]
    for extra in filter(None, (incluir, mes_corrente())):
        if extra not in meses:
            meses.append(extra)
    return sorted(set(meses), reverse=True)


def opcoes_de_filtro():
    """Pessoas, categorias e contas: TODAS, inclusive inativas.

    O historico precisa continuar consultavel depois que algo e desativado.
    """
    return {
        "pessoas": query_all(
            "SELECT id, nome, ativo FROM tb_pessoas ORDER BY nome"),
        "categorias": query_all(
            "SELECT id, nome, ativo FROM tb_categorias ORDER BY nome"),
        "contas": query_all(
            "SELECT id, nome, ativa AS ativo FROM tb_contas ORDER BY nome"),
    }


# --------------------------------------------------------------------------
# Autocomplete de descricao
# --------------------------------------------------------------------------

MIN_SUGESTAO = 2      # so busca a partir de dois caracteres
MAX_SUGESTOES = 6


def sugestoes_de_descricao(termo):
    """Descricoes ja usadas que contem `termo`, com o contexto do ultimo uso.

    Uma consulta so. As funcoes de janela agrupam por lower(descricao) para
    contar usos e escolher a linha mais recente de cada grupo; dai saem a
    grafia exibida e os ids que o formulario vai preencher. Fazer uma consulta
    por sugestao seria seis idas ao banco por tecla digitada.

    Ordem: mais usadas primeiro; empate desfeito pela mais recente. Descricao
    usada uma unica vez continua aparecendo, atras das demais.
    """
    termo = (termo or "").strip()
    if len(termo) < MIN_SUGESTAO:
        return []

    return query_all(
        """
        WITH achadas AS (
            SELECT v.descricao,
                   v.data,
                   v.valor,
                   v.subcategoria_id,
                   v.subcategoria,
                   v.categoria,
                   v.conta_id,
                   v.pessoa_id,
                   count(*)    OVER (PARTITION BY lower(v.descricao)) AS usos,
                   max(v.data) OVER (PARTITION BY lower(v.descricao)) AS ultima,
                   row_number() OVER (PARTITION BY lower(v.descricao)
                                      ORDER BY v.data DESC, v.id DESC) AS recencia
              FROM vw_despesas v
             WHERE v.descricao ILIKE '%%' || %s || '%%' ESCAPE '\\'
        )
        SELECT descricao, valor, subcategoria_id, subcategoria, categoria,
               conta_id, pessoa_id, usos, ultima
          FROM achadas
         WHERE recencia = 1
         ORDER BY usos DESC, ultima DESC, descricao
         LIMIT %s
        """,
        (escapar_like(termo), MAX_SUGESTOES),
    )
