"""Leituras e composição da Visão Anual.

A tela é um painel de treze cards (quatro KPIs grandes e nove indicadores
secundários), quatro gráficos e duas tabelas sobre um ano
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
from freedom.util import (MESES_CURTOS, formatar_numero, formatar_valor,
                          fracao, nome_do_mes)

ZERO = Decimal("0.00")

# Travessão: o card existe, o número não. Ano sem lançamento nenhum, receita
# zero na taxa de poupança, ano que ainda não começou.
SEM_VALOR = "—"

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

# Classes de CSS que os cards carregam. Ficam aqui, e não no Jinja, pela mesma
# razão do travessão e do vermelho: quem decide o que a tela mostra é a
# aplicação. O template só emite o nome que recebeu.
VALOR_ACENTO = "kpi__valor--acento"        # saldo positivo, no teal do tema
VALOR_NEGATIVO = "kpi__valor--negativo"    # saldo ou taxa negativos
NOTA_BLOCO = "indicador__nota--bloco"      # nota do pico, em linha própria
BARRA_RECEITA = "kpi__preenchimento--receita"
BARRA_DESPESA = "kpi__preenchimento--despesa"

# Linha da tabela mensal sem lançamento nenhum: nem despesa, nem receita. Não é
# zero de verdade, é ausência, e por isso o mês inteiro fica esmaecido.
LINHA_VAZIA = "linha--vazia"


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


def resumo_do_ano(ano):
    """O resumo escrito para um ano, ou None. Consulta por chave primária.

    Mora aqui, ao lado de `anos_com_lancamento`, e não no módulo de cadastro:
    esta é a leitura, e quem lê é a Visão Anual. O cadastro (que escreve,
    lista e apaga) importa esta função em vez de repetir o SELECT — um resumo,
    uma origem, como todo número que aparece em dois lugares.

    `None` significa "este ano não tem resumo", e a tela não mostra card
    nenhum: nem aviso, nem convite para escrever um.
    """
    return query_one(
        "SELECT ano, texto, criado_em, atualizado_em"
        "  FROM tb_resumos_anuais WHERE ano = %s",
        (ano,),
    )


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

def card(rotulo, valor=None, texto=None, apoio=None, negativo=False,
         classe=None, barra=None, apoio_rotulo=None, apoio_classe=None,
         nota=None):
    """Um card do painel.

    `valor` é dinheiro (Decimal) e o template o passa pela macro `reais`;
    `texto` já vem pronto (percentual, contagem ou travessão). Um dos dois,
    nunca os dois. `apoio` é a nota complementar — o mês, o divisor da média,
    a descrição e a data do pico.

    `classe` e `barra` entraram na rodada 17, com o desenho novo:

    - `classe` é o nome da classe CSS que o template emite (valor do KPI em
      acento ou em vermelho, nota do pico numa linha própria). A regra que
      escolhe cada uma é da aplicação, e por isso mora aqui: em Jinja não se
      decide cor nem forma, do mesmo jeito que não se decide travessão.
    - `barra` é o trilho de proporção dos dois primeiros KPIs, no formato
      {"classe": ..., "pct": Decimal}. `None` quando não há barra a desenhar
      (sem receita não existe a fração despesa ÷ receita).

    Os três últimos entraram na rodada 28, quando o acompanhamento do
    orçamento passou a montar os cards dele por aqui em vez de ter um
    `_card` próprio. Existem porque o card dele diz DUAS coisas sobre o
    mesmo número:

    - `apoio_rotulo` é a palavra antes do valor de apoio ("planejado"). Fica
      separada porque a cor não pode alcançá-la: quem fica vermelho é o
      número, não o rótulo dele. Sem `apoio_rotulo` o `apoio` é a frase
      inteira, como sempre foi na Anual e nas análises.
    - `apoio_classe` é a classe do valor de apoio (a poupança PLANEJADA
      também pode ser negativa, num mês que planeja gastar mais do que
      recebe).
    - `nota` é a terceira linha do card, no formato {"texto", "classe"} — o
      "X% consumido" do card de Despesas, na cor que a faixa mandou.

    Sem underscore porque a Visão Mensal e o orçamento montam os cards deles
    com esta mesma função: o formato que o template lê é um só, e não três
    parecidos. Cada tela lê do dicionário o que usa e ignora o resto.
    """
    return {"rotulo": rotulo, "valor": valor, "texto": texto,
            "apoio": apoio, "negativo": negativo,
            "classe": classe, "barra": barra,
            "apoio_rotulo": apoio_rotulo, "apoio_classe": apoio_classe,
            "nota": nota}


def percentual(parte, total):
    """`fracao` já em texto pt-BR, para os cards. Travessão quando não há.

    Compartilhada com a Visão Mensal: a taxa de poupança do mês é a mesma
    conta da do ano, e o travessão de receita zero também.
    """
    parcela = fracao(parte, total)
    return SEM_VALOR if parcela is None else formatar_numero(parcela, 1) + "%"


def _plural_meses(quantidade):
    """1 -> 'mês', qualquer outro -> 'meses'. Sai das notas dos cards."""
    return "mês" if quantidade == 1 else "meses"


def _cards(leitura, totais):
    """Os treze cards do ano, separados nos dois blocos em que a tela os mostra.

    Devolve {"kpis": [4], "indicadores": [9]} — os mesmos treze números de
    sempre, agora em duas listas, porque o desenho da rodada 17 os separa: os
    quatro grandes em cartões próprios e os nove restantes em linhas de um
    cartão só, na ordem do handoff. Continua sendo UMA composição: quem lê o
    ano lê uma vez, e os dois blocos saem dos mesmos totais.

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

    # Uma conta, dois lugares: a nota da taxa de poupança ("Média mensal R$ X")
    # e o indicador "Despesa média / mês" mostram este mesmo número.
    media = (despesa_anual / divisor).quantize(ZERO) if divisor else None

    # Fração do trilho vermelho do KPI de despesa. `fracao` já devolve None sem
    # receita — é o caso em que o cartão troca a barra pelo travessão. Acima de
    # 100% (gastou mais do que entrou) o trilho enche e para: barra é
    # proporção, e proporção não passa do trilho. O número exato continua no
    # card e na taxa de poupança.
    consumo = fracao(despesa_anual, receita_anual)
    cheia = Decimal(100)

    kpis = [
        card("Receita anual", valor=receita_anual,
             barra={"classe": BARRA_RECEITA, "pct": cheia}),
        card("Despesa anual", valor=despesa_anual,
             barra=None if consumo is None
                   else {"classe": BARRA_DESPESA, "pct": min(consumo, cheia)},
             apoio=SEM_VALOR if consumo is None else None),
        # Saldo é o número da tela: acento quando sobra, vermelho quando falta.
        card("Saldo anual", valor=saldo, negativo=saldo < 0,
             classe=VALOR_NEGATIVO if saldo < 0 else VALOR_ACENTO,
             apoio=(f"{len(azuis)} de {divisor} {_plural_meses(divisor)} no azul"
                    if divisor else None)),
        # O vermelho acompanha o percentual, nao o saldo: com receita zero o
        # card mostra travessao, e travessao vermelho nao quer dizer nada.
        card("Taxa de poupança",
             texto=percentual(saldo, receita_anual),
             negativo=saldo < 0 and receita_anual > 0,
             classe=VALOR_NEGATIVO if saldo < 0 and receita_anual > 0 else None,
             apoio=(f"Média mensal R$ {formatar_valor(media)}"
                    if media is not None else None)),
    ]

    indicadores = [
        card("Despesas essenciais", valor=essencial),
        card("Despesas não essenciais", valor=nao_essencial),
        # A única nota que não cabe ao lado do valor: descrição digitada pela
        # pessoa mais a data. Vai numa linha própria, e é `classe` que diz isso.
        card("Pico de despesa",
             valor=pico["valor"] if pico else None,
             texto=None if pico else SEM_VALOR,
             apoio=f"{pico['descricao']} · {pico['data']:%d/%m/%Y}"
                    if pico else None,
             classe=NOTA_BLOCO),
        card("% essencial", texto=percentual(essencial, despesa_anual)),
        card("% não essencial", texto=percentual(nao_essencial, despesa_anual)),
        card("Despesa média / mês",
             valor=media,
             texto=None if divisor else SEM_VALOR,
             apoio=(f"{divisor} {_plural_meses(divisor)}" if divisor else None)),
        card("Melhor mês (saldo)",
             valor=saldo_do_mes(melhor) if melhor else None,
             texto=None if melhor else SEM_VALOR,
             apoio=nome_do_mes(melhor) if melhor else None,
             negativo=bool(melhor) and saldo_do_mes(melhor) < 0),
        card("Mês de maior gasto",
             valor=despesas[maior_gasto]["total"] if maior_gasto else None,
             texto=None if maior_gasto else SEM_VALOR,
             apoio=nome_do_mes(maior_gasto) if maior_gasto else None),
        card("Meses no azul",
             texto=f"{len(azuis)} de {divisor}" if divisor else SEM_VALOR),
    ]

    return {"kpis": kpis, "indicadores": indicadores}
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

        # Mês sem despesa E sem receita: os zeros da linha não são resultado,
        # são ausência de lançamento. A linha inteira sai esmaecida — quem
        # decide isso é aqui, não o Jinja, como o travessão e o vermelho.
        linhas.append({
            "mes": nome_do_mes(mes),
            "mes_curto": MESES_CURTOS[mes - 1],
            "classe": None if despesa_do_mes or mes in receitas else LINHA_VAZIA,
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
            "classe": None,
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
        # Contador do cabeçalho do cartão. Vem pronto, com o plural resolvido:
        # contar linhas e escolher entre "categoria" e "categorias" seriam duas
        # decisões em Jinja, e a tela não decide nada.
        "contador": f"{len(linhas)} {'categoria' if len(linhas) == 1 else 'categorias'}",
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
