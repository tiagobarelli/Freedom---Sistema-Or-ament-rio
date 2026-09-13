"""Acompanhamento do orçamento: o que se planejou contra o que se gastou.

Módulo separado de `servico.py` de propósito. Lá mora a MONTAGEM do plano —
criar o mês, sugerir linhas, editar, encerrar. Aqui mora a LEITURA do plano
contra a realidade, que não escreve nada e tem regras próprias (faixas de cor,
período acumulado, o que ficou fora do orçamento).

Duas coisas que valem por todo o módulo:

- **O realizado nunca é gravado.** Sai de `vw_despesas` e `vw_receitas` a cada
  exibição, sempre por intervalo de `data`. Gravá-lo criaria um segundo número
  sobre os mesmos lançamentos, que envelheceria assim que alguém corrigisse
  uma despesa do período.
- **A cor é decidida aqui, não no Jinja.** `situacao()` devolve `ok`, `alerta`
  ou `estouro`, e célula, barra, subtotal, rodapé e card usam a mesma resposta.
  Espalhar `{% if pct > 100 %}` pelo template daria cinco lugares para a regra
  divergir.
"""

from decimal import Decimal

from freedom.db import query_all, query_one
from freedom.orcamento.servico import ZERO, _intervalo, meses_com_orcamento
from freedom.util import chave_alfabetica, fracao, nome_do_periodo

# Modos da tela e períodos do acompanhamento. Texto fora da lista cai no
# padrão, sem erro, como todo seletor deste projeto.
MONTAGEM = "montagem"
ACOMPANHAMENTO = "acompanhamento"
MODOS = (MONTAGEM, ACOMPANHAMENTO)

MES = "mes"
ACUMULADO = "acumulado"
PERIODOS = (MES, ACUMULADO)

# Faixas do percentual consumido. 90 é o aviso ("está acabando"), 100 é o
# estouro. Ficam aqui, e não no CSS, porque são regra de negócio: o CSS só
# sabe pintar o que estas três palavras mandam.
ALERTA = Decimal(90)
ESTOURO = Decimal(100)

OK, EM_ALERTA, ESTOUROU = "ok", "alerta", "estouro"


# --------------------------------------------------------------------------
# Estado da tela
# --------------------------------------------------------------------------

def modo_valido(texto):
    return texto if texto in MODOS else None


def periodo_valido(texto):
    return texto if texto in PERIODOS else MES


def tem_despesa(ano_mes):
    """Houve algum lançamento no mês? Decide o modo padrão da tela."""
    inicio, fim = _intervalo(ano_mes)
    return bool(query_one(
        "SELECT 1 AS ha FROM vw_despesas WHERE data >= %s AND data < %s LIMIT 1",
        (inicio, fim)))


def modo_padrao(ano_mes, cabecalho):
    """Com que modo a tela abre quando a URL não diz.

    Mês encerrado não se monta mais, então abre no acompanhamento. Mês aberto
    abre no acompanhamento se já houver despesa — quem lançou quer ver como
    está indo — e na montagem enquanto o mês estiver vazio, que é quando o
    plano ainda é a única coisa a olhar.
    """
    if cabecalho["encerrado_em"] is not None:
        return ACOMPANHAMENTO
    return ACOMPANHAMENTO if tem_despesa(ano_mes) else MONTAGEM


def meses_considerados(ano_mes, periodo):
    """Os meses que entram na conta, em ordem.

    No período `mes`, só o escolhido. No `acumulado`, os meses **do mesmo ano
    que têm orçamento**, do primeiro até o escolhido: mês sem orçamento no meio
    da sequência não entra em nada, nem no planejado nem no realizado, porque
    somar o gasto de um mês que ninguém planejou compararia coisas diferentes.
    """
    if periodo != ACUMULADO:
        return [ano_mes]
    return sorted(m for m in meses_com_orcamento()
                  if m.year == ano_mes.year and m <= ano_mes)


# --------------------------------------------------------------------------
# Consultas
# --------------------------------------------------------------------------

def _where_dos_meses(meses, coluna="v.data"):
    """(trecho SQL, params) com um intervalo de `data` por mês considerado.

    OR de intervalos, e não `date_trunc(data) = ANY(...)`: a coluna derivada
    mataria o índice, e um BitmapOr sobre `ix_despesas_data` resolve os no
    máximo doze intervalos sem esforço. Só a QUANTIDADE de trechos é dinâmica;
    as datas continuam sendo parâmetros.
    """
    trechos, params = [], []
    for m in meses:
        inicio, fim = _intervalo(m)
        trechos.append(f"({coluna} >= %s AND {coluna} < %s)")
        params.extend([inicio, fim])
    return "(" + " OR ".join(trechos) + ")", params


def realizado_por_subcategoria(meses):
    """{subcategoria_id: {subcategoria, categoria, realizado}} no período.

    A view já traz os dois nomes, então não há JOIN a fazer aqui. Traz TODAS
    as subcategorias com despesa, inclusive as que não estão no orçamento — é
    delas que sai o bloco "Fora do orçamento".
    """
    onde, params = _where_dos_meses(meses)
    return {l["subcategoria_id"]: l for l in query_all(
        "SELECT v.subcategoria_id, v.subcategoria, v.categoria,"
        "       SUM(v.valor) AS realizado"
        "  FROM vw_despesas v"
        f" WHERE {onde}"
        " GROUP BY v.subcategoria_id, v.subcategoria, v.categoria",
        params)}


def receita_realizada(meses):
    onde, params = _where_dos_meses(meses)
    return query_one(
        "SELECT COALESCE(SUM(v.valor), 0) AS total"
        "  FROM vw_receitas v"
        f" WHERE {onde}",
        params)["total"]


def planejado_por_subcategoria(meses):
    """{subcategoria_id: {subcategoria, categoria, planejado}} somando os meses.

    Uma subcategoria que tem linha em alguns dos meses e não em outros soma só
    o planejado que existe — e é justamente isso que a diferença contra o
    realizado de todos os meses mostra.
    """
    return {l["subcategoria_id"]: l for l in query_all(
        "SELECT o.subcategoria_id, s.nome AS subcategoria, c.nome AS categoria,"
        "       SUM(o.valor_planejado) AS planejado"
        "  FROM tb_orcamentos    o"
        "  JOIN tb_subcategorias s ON s.id = o.subcategoria_id"
        "  JOIN tb_categorias    c ON c.id = s.categoria_id"
        " WHERE o.ano_mes = ANY(%s)"
        " GROUP BY o.subcategoria_id, s.nome, c.nome",
        (list(meses),))}


def receita_planejada(meses):
    return query_one(
        "SELECT COALESCE(SUM(receita_planejada), 0) AS total"
        "  FROM tb_orcamento_meses WHERE ano_mes = ANY(%s)",
        (list(meses),))["total"]


# --------------------------------------------------------------------------
# A regra de cor, num lugar só
# --------------------------------------------------------------------------

def situacao(planejado, realizado):
    """`ok`, `alerta` ou `estouro`. É a única decisão de cor do módulo.

    Planejado zero é caso à parte: sem denominador não há percentual, mas
    gastar onde não se planejou nada é estouro do mesmo jeito — e não gastar
    é normal.
    """
    if planejado > 0:
        pct = realizado / planejado * ESTOURO
        if pct > ESTOURO:
            return ESTOUROU
        return EM_ALERTA if pct >= ALERTA else OK
    return ESTOUROU if realizado > 0 else OK


def consumo(planejado, realizado):
    """O que a tela precisa saber sobre uma comparação planejado × realizado.

    `pct` é None quando não há denominador, e a tela mostra travessão; `barra`
    nunca passa de 100, porque uma barra de 143% não cabe na caixa e não diria
    mais do que a cheia já diz — o número ao lado é que mostra o excesso.
    """
    estado = situacao(planejado, realizado)
    if planejado > 0:
        pct = realizado / planejado * ESTOURO
        return {"pct": pct, "barra": min(pct, ESTOURO), "situacao": estado}
    # Sem planejado: barra cheia se gastou, vazia se não gastou.
    return {"pct": None,
            "barra": ESTOURO if realizado > 0 else ZERO,
            "situacao": estado}


def _diferenca(planejado, realizado):
    """Sobra (positiva) ou estouro (negativo). Nome do sinal, não do módulo."""
    return planejado - realizado


# --------------------------------------------------------------------------
# Composição da tela
# --------------------------------------------------------------------------

def _linha(dados, planejado, realizado):
    return dict(dados, planejado=planejado, realizado=realizado,
                diferenca=_diferenca(planejado, realizado),
                consumo=consumo(planejado, realizado))


def _agrupar(itens):
    """Linhas -> grupos por categoria, com subtotal. Ordem alfabética pt-BR."""
    por_categoria = {}
    for item in itens:
        por_categoria.setdefault(item["categoria"], []).append(item)

    grupos = []
    for categoria in sorted(por_categoria, key=chave_alfabetica):
        linhas = sorted(por_categoria[categoria],
                        key=lambda i: chave_alfabetica(i["subcategoria"]))
        planejado = sum((l["planejado"] for l in linhas), ZERO)
        realizado = sum((l["realizado"] for l in linhas), ZERO)
        grupos.append({
            "categoria": categoria,
            "linhas": linhas,
            "planejado": planejado,
            "realizado": realizado,
            "diferenca": _diferenca(planejado, realizado),
            "consumo": consumo(planejado, realizado),
        })
    return grupos


def _card(rotulo, valor, planejado, negativo=False, texto=None,
          texto_planejado=None, consumo_=None):
    """Um card do acompanhamento: realizado em cima, planejado no apoio.

    Formato próprio, e não o `card` da Visão Anual: aqui todo card tem DOIS
    números (o que aconteceu e o que estava previsto), e importar o helper de
    outro blueprint seria pior que estas seis linhas.
    """
    # O planejado tambem pode ser negativo (poupanca prevista de um mes que
    # planeja gastar mais do que recebe), e um menos sem cor passa batido.
    previsto = planejado if planejado is not None else texto_planejado
    return {"rotulo": rotulo, "valor": valor, "texto": texto,
            "planejado": planejado, "texto_planejado": texto_planejado,
            "negativo": negativo, "consumo": consumo_,
            "negativo_planejado": previsto is not None and previsto < 0}


def _cards(receita, receita_prevista, despesa, despesa_prevista, consumo_):
    poupanca = receita - despesa
    poupanca_prevista = receita_prevista - despesa_prevista
    taxa = fracao(poupanca, receita)
    taxa_prevista = fracao(poupanca_prevista, receita_prevista)
    return [
        _card("Receitas", receita, receita_prevista),
        _card("Despesas", despesa, despesa_prevista, consumo_=consumo_),
        _card("Poupança", poupanca, poupanca_prevista, negativo=poupanca < 0),
        # O vermelho acompanha o percentual, não o saldo: com receita zero o
        # card mostra travessão, e travessão vermelho não quer dizer nada.
        _card("Taxa de poupança", None, None,
              texto=taxa, texto_planejado=taxa_prevista,
              negativo=taxa is not None and taxa < 0),
    ]


def painel(ano_mes, periodo):
    """Cards, tabela, fora do orçamento e totais — em quatro consultas.

    A composição é em Python sobre conjunto pequeno e completo: as linhas
    orçadas do período e as subcategorias com despesa nele. Subtotal, rodapé e
    cards leem da MESMA lista, então "a soma dos subtotais mais o fora do
    orçamento dá o rodapé" é estrutural, não coincidência.
    """
    meses = meses_considerados(ano_mes, periodo)
    planejadas = planejado_por_subcategoria(meses)
    realizadas = realizado_por_subcategoria(meses)

    orcadas = [
        _linha(dados, dados["planejado"],
               realizadas[sub]["realizado"] if sub in realizadas else ZERO)
        for sub, dados in planejadas.items()
    ]
    # Fora do orçamento: teve despesa e não tem linha em NENHUM dos meses
    # considerados. Não é erro — é o que o plano não previu, e some quando
    # alguém acrescenta a linha na montagem.
    fora = [
        _linha(dados, ZERO, dados["realizado"])
        for sub, dados in realizadas.items() if sub not in planejadas
    ]

    planejado = sum((l["planejado"] for l in orcadas), ZERO)
    realizado_orcado = sum((l["realizado"] for l in orcadas), ZERO)
    realizado_fora = sum((l["realizado"] for l in fora), ZERO)
    # O total realizado é o do PERÍODO, não o do que estava orçado: é ele que
    # tem de bater com o card Despesas da Visão Mensal.
    realizado = realizado_orcado + realizado_fora

    receita = receita_realizada(meses)
    prevista = receita_planejada(meses)
    total = {
        "planejado": planejado,
        "realizado": realizado,
        "realizado_orcado": realizado_orcado,
        "realizado_fora": realizado_fora,
        "diferenca": _diferenca(planejado, realizado),
        "consumo": consumo(planejado, realizado),
    }

    return {
        "periodo_tipo": periodo,
        "meses": meses,
        "rotulo_periodo": _rotulo(meses, periodo),
        "grupos": _agrupar(orcadas),
        "fora": {"grupos": _agrupar(fora), "total": realizado_fora},
        "total": total,
        "cards": _cards(receita, prevista, realizado, planejado,
                        total["consumo"]),
    }


def _rotulo(meses, periodo):
    """O que a tela escreve sobre o período considerado.

    No acumulado o texto diz quais meses entraram: sem isso, um acumulado que
    pula um mês sem orçamento pareceria erro de conta.
    """
    if periodo != ACUMULADO or len(meses) <= 1:
        return nome_do_periodo(meses[-1])
    return (f"{len(meses)} meses orçados de {meses[0].year}: "
            f"{nome_do_periodo(meses[0]).split(' de ')[0]} a "
            f"{nome_do_periodo(meses[-1]).split(' de ')[0]}")
