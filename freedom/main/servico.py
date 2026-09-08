"""Leituras e composição da Visão Anual.

A tela é um painel de treze cards mais quatro gráficos sobre um ano inteiro,
e são quatro consultas: despesas agregadas por mês, receitas agregadas por mês,
o maior lançamento individual do ano e — só para o gráfico de prioridades — as
não essenciais agrupadas por mês e prioridade. Nenhuma delas devolve mais que
doze linhas por mês.

Cards e gráficos saem das MESMAS linhas mensais: `painel_do_ano` lê uma vez e
compõe os dois. É a única soma que a aplicação faz fora do banco, e existe
porque somar doze números já lidos custa menos que uma ida ao banco por número
— o agrupamento por mês, que é o trabalho pesado, continua no SQL.

O filtro é sempre por intervalo de `data` (`>= 1º de janeiro` e `< 1º de
janeiro do ano seguinte`), nunca por `ano_mes`: ano_mes é coluna derivada da
view, e comparar com ela obriga o Postgres a calcular a expressão linha a
linha. Com o intervalo, os índices ix_despesas_data e ix_receitas_data que já
existem podem ser usados.
"""

from datetime import date
from decimal import Decimal

from freedom.db import query_all, query_one
from freedom.util import MESES, formatar_numero

ZERO = Decimal("0.00")

# Travessão: o card existe, o número não. Ano sem lançamento nenhum, receita
# zero na taxa de poupança, ano que ainda não começou.
SEM_VALOR = "—"

# Rótulos do eixo X. Tupla irmã de util.MESES, derivada dela para não haver
# duas listas de meses que possam divergir: "março" -> "Mar".
MESES_CURTOS = tuple(mes[:3].capitalize() for mes in MESES)

# Séries do gráfico de prioridades. O banco garante a faixa 1-4; os rótulos das
# pontas explicam a escala e o meio fica curto, para a legenda não pesar.
PRIORIDADES = (
    (1, "P1 – mais importante"),
    (2, "P2"),
    (3, "P3"),
    (4, "P4 – menos importante"),
)

# Prioridade é regra da aplicação, não do banco: despesa não essencial antiga
# (ou lançada antes da regra) pode ter prioridade NULL. A série só aparece
# quando existe alguma, para não poluir a legenda de quem sempre preenche.
SEM_PRIORIDADE = "Sem prioridade"


# --------------------------------------------------------------------------
# Ano da tela
# --------------------------------------------------------------------------

def anos_com_lancamento(hoje=None):
    """Anos que têm despesa ou receita, do mais recente para o mais antigo.

    O ano corrente entra sempre, mesmo sem lançamento nenhum: ele é o padrão da
    tela, e um select sem a opção do que está sendo exibido faria o navegador
    destacar outro ano. Mesma decisão de `meses_com_lancamento`.

    UNION (e não UNION ALL) já elimina a repetição entre as duas fontes.
    """
    linhas = query_all(
        "SELECT EXTRACT(YEAR FROM data)::int AS ano FROM vw_despesas"
        " UNION"
        " SELECT EXTRACT(YEAR FROM data)::int AS ano FROM vw_receitas"
    )
    anos = {linha["ano"] for linha in linhas}
    anos.add((hoje or date.today()).year)
    return sorted(anos, reverse=True)


def ano_valido(texto, anos, hoje=None):
    """Texto da query string -> ano a exibir. Nada aqui pode gerar 500.

    Ausente, não numérico ou fora da lista cai no ano corrente em silêncio,
    como os filtros da consulta de despesas.
    """
    corrente = (hoje or date.today()).year
    try:
        ano = int(texto)
    except (TypeError, ValueError):
        return corrente
    return ano if ano in anos else corrente


def _intervalo(ano):
    """Ano -> (1º de janeiro, 1º de janeiro do ano seguinte)."""
    return date(ano, 1, 1), date(ano + 1, 1, 1)


def meses_transcorridos(ano, hoje):
    """Divisor dos cards por mês: quantos meses do ano já aconteceram.

    Ano corrente conta janeiro até o mês de hoje, inclusive — dividir por 12 em
    setembro faria a média mensal parecer um terço menor do que é. Ano passado
    é sempre 12. Ano futuro não tem divisor: devolve None, e quem exibe mostra
    travessão.
    """
    if ano == hoje.year:
        return hoje.month
    return 12 if ano < hoje.year else None


# --------------------------------------------------------------------------
# Consultas (no máximo 12 linhas cada)
# --------------------------------------------------------------------------

def despesas_por_mes(ano):
    """Total, essencial e não essencial de cada mês que teve despesa.

    A essencialidade é a efetiva da view (COALESCE já aplicado); `<> 'Essencial'`
    é o outro lado do CHECK, então as duas parcelas sempre fecham no total.
    """
    inicio, fim = _intervalo(ano)
    return query_all(
        "SELECT EXTRACT(MONTH FROM v.data)::int AS mes,"
        "       SUM(v.valor) AS total,"
        "       COALESCE(SUM(v.valor) FILTER"
        "                (WHERE v.essencialidade = 'Essencial'), 0) AS essencial,"
        "       COALESCE(SUM(v.valor) FILTER"
        "                (WHERE v.essencialidade <> 'Essencial'), 0)"
        "           AS nao_essencial"
        "  FROM vw_despesas v"
        " WHERE v.data >= %s AND v.data < %s"
        " GROUP BY 1 ORDER BY 1",
        (inicio, fim),
    )


def receitas_por_mes(ano):
    """Total de cada mês que teve receita."""
    inicio, fim = _intervalo(ano)
    return query_all(
        "SELECT EXTRACT(MONTH FROM v.data)::int AS mes, SUM(v.valor) AS total"
        "  FROM vw_receitas v"
        " WHERE v.data >= %s AND v.data < %s"
        " GROUP BY 1 ORDER BY 1",
        (inicio, fim),
    )


def pico_de_despesa(ano):
    """A maior despesa individual do ano, ou None se não houver nenhuma.

    Empate no valor é desfeito pela mais recente; o id fecha o critério para a
    resposta não depender da ordem física das linhas.
    """
    inicio, fim = _intervalo(ano)
    return query_one(
        "SELECT v.valor, v.descricao, v.data"
        "  FROM vw_despesas v"
        " WHERE v.data >= %s AND v.data < %s"
        " ORDER BY v.valor DESC, v.data DESC, v.id DESC"
        " LIMIT 1",
        (inicio, fim),
    )


def nao_essenciais_por_prioridade(ano):
    """Não essenciais do ano, por mês e prioridade. Só os gráficos usam.

    A essencialidade é a efetiva da view; `<> 'Essencial'` é o outro lado do
    CHECK. Agrupar por prioridade no banco (no máximo cinco linhas por mês)
    evita trazer lançamento a lançamento só para somar aqui.
    """
    inicio, fim = _intervalo(ano)
    return query_all(
        "SELECT EXTRACT(MONTH FROM v.data)::int AS mes,"
        "       v.prioridade,"
        "       SUM(v.valor) AS total"
        "  FROM vw_despesas v"
        " WHERE v.data >= %s AND v.data < %s"
        "   AND v.essencialidade <> 'Essencial'"
        " GROUP BY 1, 2 ORDER BY 1, 2",
        (inicio, fim),
    )


# --------------------------------------------------------------------------
# Leitura do ano: uma só, servindo cards e gráficos
# --------------------------------------------------------------------------

def _leitura_do_ano(ano, hoje):
    """As linhas do ano, lidas uma vez. Cards e gráficos partem daqui."""
    return {
        "ano": ano,
        "despesas": {l["mes"]: l for l in despesas_por_mes(ano)},
        "receitas": {l["mes"]: l["total"] for l in receitas_por_mes(ano)},
        "prioridades": nao_essenciais_por_prioridade(ano),
        "pico": pico_de_despesa(ano),
        "divisor": meses_transcorridos(ano, hoje),
    }


def meses_do_eixo(divisor):
    """Meses que entram no eixo X dos gráficos.

    Janeiro até o mês corrente no ano atual, janeiro a dezembro nos anteriores.
    Ano futuro não tem meses transcorridos, mas um gráfico sem eixo não diz
    nada: nesse caso o eixo mostra o ano inteiro, todo zerado.
    """
    return list(range(1, (divisor or 12) + 1))


# --------------------------------------------------------------------------
# Composição dos cards
# --------------------------------------------------------------------------

def _card(rotulo, valor=None, texto=None, apoio=None, negativo=False):
    """Um card do painel.

    `valor` é dinheiro (Decimal) e o template o passa pela macro `reais`;
    `texto` já vem pronto (percentual, contagem ou travessão). Um dos dois,
    nunca os dois.
    """
    return {"rotulo": rotulo, "valor": valor, "texto": texto,
            "apoio": apoio, "negativo": negativo}


def _percentual(parte, total):
    """Fatia sobre o total, em texto pt-BR. Travessão quando o total é zero."""
    if not total:
        return SEM_VALOR
    return formatar_numero(parte / total * 100, 1) + "%"


def _nome_do_mes(mes):
    """1 -> 'Janeiro'. Rótulo solto de card, por isso com inicial maiúscula."""
    return MESES[mes - 1].capitalize()


def _cards(leitura):
    """Os treze cards do ano, na ordem em que aparecem na tela.

    Ano sem lançamento nenhum não é caso de erro: os cards de dinheiro mostram
    R$ 0,00 e os de mês e pico mostram travessão.
    """
    despesas = leitura["despesas"]
    receitas = leitura["receitas"]
    pico = leitura["pico"]
    divisor = leitura["divisor"]

    despesa_anual = sum((l["total"] for l in despesas.values()), ZERO)
    essencial = sum((l["essencial"] for l in despesas.values()), ZERO)
    nao_essencial = sum((l["nao_essencial"] for l in despesas.values()), ZERO)
    receita_anual = sum(receitas.values(), ZERO)
    saldo = receita_anual - despesa_anual

    def saldo_do_mes(mes):
        despesa = despesas[mes]["total"] if mes in despesas else ZERO
        return receitas.get(mes, ZERO) - despesa

    # Melhor mês e mês de maior gasto olham só para meses que tiveram algum
    # lançamento: um mês vazio tem saldo zero e venceria um ano inteiro de
    # saldos negativos, apontando como "melhor" um mês em que nada aconteceu.
    com_movimento = sorted(set(despesas) | set(receitas))
    melhor = max(com_movimento, key=saldo_do_mes, default=None)
    maior_gasto = max(despesas, key=lambda m: despesas[m]["total"], default=None)

    # No azul: receita maior que despesa, dentro dos meses já transcorridos.
    # Mês sem lançamento tem os dois lados zerados e não conta.
    azuis = [m for m in com_movimento
             if divisor and m <= divisor and saldo_do_mes(m) > 0]

    return [
        _card("Receita Anual", valor=receita_anual),
        _card("Despesa Anual", valor=despesa_anual),
        _card("Saldo Anual", valor=saldo, negativo=saldo < 0),
        # O vermelho acompanha o percentual, nao o saldo: com receita zero o
        # card mostra travessao, e travessao vermelho nao quer dizer nada.
        _card("Taxa de Poupança",
              texto=_percentual(saldo, receita_anual),
              negativo=saldo < 0 and receita_anual > 0),
        _card("Despesas Essenciais", valor=essencial),
        _card("Despesas Não Essenciais", valor=nao_essencial),
        _card("Despesa Média / Mês",
              valor=(despesa_anual / divisor).quantize(ZERO) if divisor else None,
              texto=None if divisor else SEM_VALOR,
              apoio=f"em {divisor} {'mês' if divisor == 1 else 'meses'}"
                    if divisor else None),
        _card("Melhor Mês (Saldo)",
              valor=saldo_do_mes(melhor) if melhor else None,
              texto=None if melhor else SEM_VALOR,
              apoio=_nome_do_mes(melhor) if melhor else None,
              negativo=bool(melhor) and saldo_do_mes(melhor) < 0),
        _card("Mês de Maior Gasto",
              valor=despesas[maior_gasto]["total"] if maior_gasto else None,
              texto=None if maior_gasto else SEM_VALOR,
              apoio=_nome_do_mes(maior_gasto) if maior_gasto else None),
        _card("Pico de Despesa",
              valor=pico["valor"] if pico else None,
              texto=None if pico else SEM_VALOR,
              apoio=f"{pico['descricao']} · {pico['data']:%d/%m/%Y}"
                    if pico else None),
        _card("% Essencial", texto=_percentual(essencial, despesa_anual)),
        _card("% Não Essencial", texto=_percentual(nao_essencial, despesa_anual)),
        _card("Meses no Azul",
              texto=f"{len(azuis)} de {divisor}" if divisor else SEM_VALOR),
    ]
# --------------------------------------------------------------------------
# Composição dos gráficos
#
# Cada gráfico é uma lista de séries {rotulo, valores}, com um valor por mês do
# eixo. Os rótulos das séries vêm daqui, e não do JavaScript: o que a tela
# escreve é conhecimento da aplicação, como o catálogo de configurações.
# --------------------------------------------------------------------------

def _serie(rotulo, valores):
    """Uma série pronta para o JSON.

    Único ponto do painel em que Decimal vira número de JavaScript. Tudo antes
    daqui é Decimal; nada depois daqui volta a ser somado.
    """
    return {"rotulo": rotulo, "valores": [float(v) for v in valores]}


def _graficos(leitura):
    """Os quatro gráficos, montados das mesmas linhas mensais dos cards."""
    despesas = leitura["despesas"]
    receitas = leitura["receitas"]
    meses = meses_do_eixo(leitura["divisor"])

    def do_mes(mes, coluna):
        """Valor do mês numa coluna das despesas. Mês sem lançamento vale 0."""
        linha = despesas.get(mes)
        return linha[coluna] if linha else ZERO

    receita_mensal = [receitas.get(mes, ZERO) for mes in meses]
    despesa_mensal = [do_mes(mes, "total") for mes in meses]

    # Acumulado em Decimal, mês a mês desde janeiro: é a soma que o gráfico 3
    # mostra, e ela não pode ser feita no JavaScript.
    acumulado, corrente = [], ZERO
    for recebido, gasto in zip(receita_mensal, despesa_mensal):
        corrente += recebido - gasto
        acumulado.append(corrente)

    # (mês, prioridade) -> total, para a pilha do gráfico 4.
    por_prioridade = {(l["mes"], l["prioridade"]): l["total"]
                      for l in leitura["prioridades"]}
    series_prioridade = [
        _serie(rotulo, [por_prioridade.get((mes, p), ZERO) for mes in meses])
        for p, rotulo in PRIORIDADES
    ]
    if any(p is None for _, p in por_prioridade):
        series_prioridade.append(
            _serie(SEM_PRIORIDADE,
                   [por_prioridade.get((mes, None), ZERO) for mes in meses]))

    return {
        "meses": [MESES_CURTOS[mes - 1] for mes in meses],
        "receitas_despesas": [
            _serie("Receitas", receita_mensal),
            _serie("Despesas", despesa_mensal),
        ],
        "essencialidade": [
            _serie("Essenciais", [do_mes(mes, "essencial") for mes in meses]),
            _serie("Não Essenciais",
                   [do_mes(mes, "nao_essencial") for mes in meses]),
            _serie("Total", despesa_mensal),
        ],
        "acumulado": [_serie("Saldo acumulado", acumulado)],
        "prioridades": series_prioridade,
    }


# --------------------------------------------------------------------------
# A tela inteira
# --------------------------------------------------------------------------

def painel_do_ano(ano, hoje=None):
    """Cards e gráficos do ano, com uma leitura só do banco."""
    leitura = _leitura_do_ano(ano, hoje or date.today())
    return {"cards": _cards(leitura), "graficos": _graficos(leitura)}
