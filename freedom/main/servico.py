"""Leituras e composição da Visão Anual.

A tela é um painel de treze cards, quatro gráficos e duas tabelas sobre um ano
inteiro, e são cinco consultas: despesas agregadas por mês, receitas agregadas
por mês, o maior lançamento individual do ano, as não essenciais agrupadas por
mês e prioridade (gráfico 4) e as despesas agrupadas por categoria (tabela 2).
Nenhuma delas devolve mais que doze linhas por mês.

Cards, gráficos e a tabela mensal saem das MESMAS linhas mensais:
`painel_do_ano` lê uma vez e compõe os três. É a única soma que a aplicação faz fora do banco, e existe
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


def despesas_por_categoria(ano):
    """Total de cada categoria que teve despesa no ano, da maior para a menor.

    Só a tabela por categoria usa. Categoria sem despesa no ano não aparece —
    é o GROUP BY sobre o intervalo que garante isso, sem filtro extra. O nome
    desempata os totais iguais, para a ordem não depender do banco.
    """
    inicio, fim = _intervalo(ano)
    return query_all(
        "SELECT v.categoria, SUM(v.valor) AS total"
        "  FROM vw_despesas v"
        " WHERE v.data >= %s AND v.data < %s"
        " GROUP BY v.categoria"
        " ORDER BY SUM(v.valor) DESC, v.categoria",
        (inicio, fim),
    )


# --------------------------------------------------------------------------
# Leitura do ano: uma só, servindo cards, gráficos e tabelas
# --------------------------------------------------------------------------

def _leitura_do_ano(ano, hoje):
    """As linhas do ano, lidas uma vez. Tudo na tela parte daqui."""
    return {
        "ano": ano,
        "despesas": {l["mes"]: l for l in despesas_por_mes(ano)},
        "receitas": {l["mes"]: l["total"] for l in receitas_por_mes(ano)},
        "prioridades": nao_essenciais_por_prioridade(ano),
        "categorias": despesas_por_categoria(ano),
        "pico": pico_de_despesa(ano),
        "divisor": meses_transcorridos(ano, hoje),
    }


def _totais_do_ano(leitura):
    """Os cinco totais do ano, somados uma vez só.

    Cards e linha de totais da tabela mensal leem daqui, e não cada um da sua
    conta: é o que garante que "Saldo Anual" no card e no rodapé da tabela
    sejam o mesmo número, e não dois números que por acaso coincidem.
    """
    despesas = leitura["despesas"].values()
    receita = sum(leitura["receitas"].values(), ZERO)
    despesa = sum((l["total"] for l in despesas), ZERO)
    return {
        "receita": receita,
        "despesa": despesa,
        "essencial": sum((l["essencial"] for l in despesas), ZERO),
        "nao_essencial": sum((l["nao_essencial"] for l in despesas), ZERO),
        "saldo": receita - despesa,
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

def card(rotulo, valor=None, texto=None, apoio=None, negativo=False):
    """Um card do painel.

    `valor` é dinheiro (Decimal) e o template o passa pela macro `reais`;
    `texto` já vem pronto (percentual, contagem ou travessão). Um dos dois,
    nunca os dois.

    Sem underscore porque a Visão Mensal monta os cards dela com esta mesma
    função: o formato que o template lê é um só, e não dois parecidos.
    """
    return {"rotulo": rotulo, "valor": valor, "texto": texto,
            "apoio": apoio, "negativo": negativo}


def fracao(parte, total):
    """Fatia sobre o total, em pontos percentuais (Decimal), ou None.

    None quando não há denominador: percentual sem base não é zero por cento,
    é uma conta que não existe. Quem exibe troca por travessão.

    Compartilhada com a Visão Mensal (barras das tabelas por categoria e por
    pessoa), por isso sem underscore.
    """
    return parte / total * 100 if total else None


def percentual(parte, total):
    """`fracao` já em texto pt-BR, para os cards. Travessão quando não há.

    Compartilhada com a Visão Mensal: a taxa de poupança do mês é a mesma
    conta da do ano, e o travessão de receita zero também.
    """
    parcela = fracao(parte, total)
    return SEM_VALOR if parcela is None else formatar_numero(parcela, 1) + "%"


def _nome_do_mes(mes):
    """1 -> 'Janeiro'. Rótulo solto de card, por isso com inicial maiúscula."""
    return MESES[mes - 1].capitalize()


def _cards(leitura, totais):
    """Os treze cards do ano, na ordem em que aparecem na tela.

    Ano sem lançamento nenhum não é caso de erro: os cards de dinheiro mostram
    R$ 0,00 e os de mês e pico mostram travessão.
    """
    despesas = leitura["despesas"]
    receitas = leitura["receitas"]
    pico = leitura["pico"]
    divisor = leitura["divisor"]

    despesa_anual = totais["despesa"]
    essencial = totais["essencial"]
    nao_essencial = totais["nao_essencial"]
    receita_anual = totais["receita"]
    saldo = totais["saldo"]

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
        card("Receita Anual", valor=receita_anual),
        card("Despesa Anual", valor=despesa_anual),
        card("Saldo Anual", valor=saldo, negativo=saldo < 0),
        # O vermelho acompanha o percentual, nao o saldo: com receita zero o
        # card mostra travessao, e travessao vermelho nao quer dizer nada.
        card("Taxa de Poupança",
             texto=percentual(saldo, receita_anual),
             negativo=saldo < 0 and receita_anual > 0),
        card("Despesas Essenciais", valor=essencial),
        card("Despesas Não Essenciais", valor=nao_essencial),
        card("Despesa Média / Mês",
             valor=(despesa_anual / divisor).quantize(ZERO) if divisor else None,
             texto=None if divisor else SEM_VALOR,
             apoio=f"em {divisor} {'mês' if divisor == 1 else 'meses'}"
                    if divisor else None),
        card("Melhor Mês (Saldo)",
             valor=saldo_do_mes(melhor) if melhor else None,
             texto=None if melhor else SEM_VALOR,
             apoio=_nome_do_mes(melhor) if melhor else None,
             negativo=bool(melhor) and saldo_do_mes(melhor) < 0),
        card("Mês de Maior Gasto",
             valor=despesas[maior_gasto]["total"] if maior_gasto else None,
             texto=None if maior_gasto else SEM_VALOR,
             apoio=_nome_do_mes(maior_gasto) if maior_gasto else None),
        card("Pico de Despesa",
             valor=pico["valor"] if pico else None,
             texto=None if pico else SEM_VALOR,
             apoio=f"{pico['descricao']} · {pico['data']:%d/%m/%Y}"
                    if pico else None),
        card("% Essencial", texto=percentual(essencial, despesa_anual)),
        card("% Não Essencial", texto=percentual(nao_essencial, despesa_anual)),
        card("Meses no Azul",
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
# Composição das tabelas
#
# Célula que pode não existir vem como None, e não como zero nem como texto:
# quem decide que "sem valor" se desenha como travessão é o template, do mesmo
# jeito que é ele quem põe o "R$" na frente do dinheiro.
# --------------------------------------------------------------------------

def _tabela_mensal(leitura, totais):
    """Doze linhas (janeiro a dezembro) e a linha de totais.

    Nenhuma consulta a mais: sai das mesmas linhas mensais dos cards. Mês sem
    lançamento vale zero — a tabela é do ano inteiro, não só do que aconteceu.
    """
    despesas = leitura["despesas"]
    receitas = leitura["receitas"]
    divisor = leitura["divisor"]

    linhas, acumulado = [], ZERO
    for mes in range(1, 13):
        despesa_do_mes = despesas.get(mes)
        receita = receitas.get(mes, ZERO)
        despesa = despesa_do_mes["total"] if despesa_do_mes else ZERO
        saldo = receita - despesa
        acumulado += saldo

        # Mês que ainda não chegou não tem acumulado nem taxa: o número
        # existiria (zero), mas descreveria um mês que não começou. As colunas
        # de valor continuam mostrando o que houver — lançamento com data
        # futura é raro, mas escondê-lo seria pior que exibi-lo.
        ainda_nao_chegou = divisor is not None and mes > divisor

        linhas.append({
            "mes": MESES[mes - 1].capitalize(),
            "mes_curto": MESES_CURTOS[mes - 1],
            "receitas": receita,
            "despesas": despesa,
            "essenciais": despesa_do_mes["essencial"] if despesa_do_mes else ZERO,
            "nao_essenciais": (despesa_do_mes["nao_essencial"]
                               if despesa_do_mes else ZERO),
            "saldo": saldo,
            "acumulado": None if ainda_nao_chegou else acumulado,
            "taxa": None if ainda_nao_chegou else fracao(saldo, receita),
        })

    return {
        "linhas": linhas,
        # O acumulado do ano é o saldo do ano, e vem do mesmo lugar do card.
        "total": {
            "mes": "Total",
            "mes_curto": "Total",
            "receitas": totais["receita"],
            "despesas": totais["despesa"],
            "essenciais": totais["essencial"],
            "nao_essenciais": totais["nao_essencial"],
            "saldo": totais["saldo"],
            "acumulado": totais["saldo"],
            "taxa": fracao(totais["saldo"], totais["receita"]),
        },
    }


def _tabela_categorias(leitura, totais):
    """Categorias com despesa no ano, da maior para a menor, com o percentual.

    Ano sem despesa devolve lista vazia e total None: a tela troca a tabela por
    uma linha só dizendo que não houve despesa, em vez de mostrar 0,0% em toda
    parte.
    """
    despesa_anual = totais["despesa"]
    linhas = [
        {"categoria": l["categoria"],
         "total": l["total"],
         "pct": fracao(l["total"], despesa_anual)}
        for l in leitura["categorias"]
    ]
    return {
        "linhas": linhas,
        "total": {"total": despesa_anual,
                  "pct": fracao(despesa_anual, despesa_anual)},
    }


# --------------------------------------------------------------------------
# A tela inteira
# --------------------------------------------------------------------------

def painel_do_ano(ano, hoje=None):
    """Cards, gráficos e tabelas do ano, com uma leitura só do banco."""
    leitura = _leitura_do_ano(ano, hoje or date.today())
    totais = _totais_do_ano(leitura)
    return {
        "cards": _cards(leitura, totais),
        "graficos": _graficos(leitura),
        "tabelas": {
            "mensal": _tabela_mensal(leitura, totais),
            "categorias": _tabela_categorias(leitura, totais),
        },
    }
