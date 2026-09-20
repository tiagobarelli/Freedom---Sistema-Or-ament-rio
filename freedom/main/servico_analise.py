"""As duas Análises: a série de um recorte de despesas no tempo.

A pergunta das telas é "este gasto subiu?", e ela só tem resposta honesta com
duas coisas que este módulo faz:

- **correção pelo IPCA**, por lançamento, no mês do lançamento
  (`valor × índice_base ÷ índice_do_mês`), somada depois. A base é o **último
  mês carregado** de `tb_ipca` — daí o "a preços de agosto de 2026". Mês
  posterior à base não tem índice e usa fator 1: corrigir para o futuro seria
  inventar inflação que o IBGE ainda não publicou;
- **agrupamento** escolhido por quem olha. É a resposta às subcategorias que
  não se gasta todo mês, e ela não passa por classificar subcategoria: o IPVA
  mês a mês é onze zeros e um pico, ano a ano é uma série comparável. Nenhuma
  coluna, nenhuma heurística, nenhuma média móvel além da janela pedida.

Mês sem lançamento é **zero**, nunca buraco: a linha caindo a zero é a
informação ("não gastei"), e interpolar mentiria.

**O que muda de uma tela para a outra é o RECORTE, e só ele.** A análise por
subcategoria (rodada 24) olha uma subcategoria e conta todo lançamento dela;
a análise por prioridade (rodada 26) olha uma faixa de essencialidade ou
prioridade e conta só o que integra a série histórica. Período, agrupamento,
buckets, parcial, deflação, composição, rótulo de ponto e o JSON do gráfico
são os mesmos nas duas, e por isso moram aqui uma vez só — `painel()` é o
caminho inteiro, e as duas rotas se distinguem pelo `Recorte` que entregam.

`tb_despesas.integra_ipca` é lida em **um** lugar do sistema: o recorte da
análise por prioridade (`so_integrantes`). A análise por subcategoria
continua sem lê-la, por decisão do dono.
"""

from collections import namedtuple
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean, median

from freedom import ipca
from freedom.db import query_all, query_one
from freedom.main.servico import card
from freedom.util import (MESES_CURTOS, caixa_marcada, chave_alfabetica,
                          formatar_valor, intervalo_de_meses, nome_do_periodo,
                          somar_meses)

CENTAVO = Decimal("0.01")

# Períodos e agrupamentos. Texto fora da lista cai no padrão, sem erro — a
# mesma regra do ano inválido da Visão Anual.
TRES, SEIS, DOZE = "3m", "6m", "12m"
TUDO, PERSONALIZADO = "tudo", "personalizado"
PERIODOS = (TRES, SEIS, DOZE, TUDO, PERSONALIZADO)
JANELAS = {TRES: 3, SEIS: 6, DOZE: 12}

MES, TRIMESTRE, ANO, MOVEL = "mes", "trimestre", "ano", "12m"
AGRUPAMENTOS = (MES, TRIMESTRE, ANO, MOVEL)

MESES_MOVEIS = 12

ROTULO_PERIODO = {
    TRES: "últimos 3 meses",
    SEIS: "últimos 6 meses",
    DOZE: "últimos 12 meses",
    TUDO: "série inteira",
}
ROTULO_AGRUPAMENTO = {
    MES: "mensal",
    TRIMESTRE: "trimestral",
    ANO: "anual",
    MOVEL: "12 meses móveis",
}

# Como o cartão de resumo chama o período de cada agrupamento: o adjetivo que
# fecha "Média..." e a frase da contagem. A frase inteira está aqui, e não
# montada com um plural solto, porque "janelas" é feminino e os outros três
# são masculinos — o acordo de gênero é texto, e texto vem pronto do Python.
RESUMO_UNIDADE = {
    MES:       (" mensal",     "%d meses completos"),
    TRIMESTRE: (" trimestral", "%d trimestres completos"),
    ANO:       (" anual",      "%d anos completos"),
    MOVEL:     ("",            "%d janelas de 12 meses completas"),
}

# Abaixo disto não há o que resumir: a média de um período é o próprio
# período, e a mediana também.
MINIMO_RESUMO = 2


# --------------------------------------------------------------------------
# 1. Parâmetros
# --------------------------------------------------------------------------

def periodo_valido(texto):
    return texto if texto in PERIODOS else DOZE


def agrupamento_valido(texto):
    return texto if texto in AGRUPAMENTOS else MES


def mes_de_texto(texto):
    """'2026-05' -> date(2026, 5, 1); qualquer outra coisa -> None.

    É o formato que o `<input type="month">` manda, e o mesmo que uma pessoa
    digita à mão no campo de reserva.
    """
    if not texto:
        return None
    partes = str(texto).strip().split("-")
    if len(partes) != 2:
        return None
    try:
        return date(int(partes[0]), int(partes[1]), 1)
    except ValueError:
        return None


def texto_do_mes(mes):
    """date -> 'AAAA-MM', a forma que volta para o campo do formulário."""
    return f"{mes.year:04d}-{mes.month:02d}" if mes else ""


def texto_do_campo(digitado, resolvido, periodo):
    """O que volta para o campo de mês do formulário.

    No personalizado vale o que a pessoa escolheu — mas só se for um mês
    legível; fora dele, o período resolvido, para quem trocar para
    "Personalizado" começar de onde estava em vez de um campo em branco.
    """
    if periodo == PERSONALIZADO:
        return texto_do_mes(mes_de_texto(digitado))
    return texto_do_mes(resolvido)


def resolver_periodo(periodo, de, ate, acervo, mes_corrente):
    """Os parâmetros -> (primeiro mês, último mês, erro).

    As janelas de 3, 6 e 12 meses terminam no **mês corrente**, inclusive: é o
    mês em que se está olhando, ainda que incompleto — escondê-lo faria a tela
    parecer desatualizada. "Série inteira" é o acervo todo.

    Só o personalizado produz erro: ali alguém digitou, e mês malformado ou
    invertido merece resposta em vez de um gráfico que não é o pedido.
    """
    if periodo == PERSONALIZADO:
        primeiro, ultimo = mes_de_texto(de), mes_de_texto(ate)
        if primeiro is None or ultimo is None:
            return None, None, "Informe o mês inicial e o final no formato AAAA-MM."
        if primeiro > ultimo:
            return None, None, "O mês inicial não pode ser depois do final."
        return primeiro, ultimo, None

    if periodo == TUDO:
        if acervo is None:
            return None, None, None
        return acervo[0], acervo[1], None

    return somar_meses(mes_corrente, -(JANELAS[periodo] - 1)), mes_corrente, None


# --------------------------------------------------------------------------
# 2. O recorte: a única coisa que separa as duas telas
# --------------------------------------------------------------------------

Recorte = namedtuple("Recorte", "nome condicao params so_integrantes",
                     defaults=(False,))
Recorte.__doc__ = """Que despesas esta tela soma, e com que nome.

- `nome`: o que abre o subtítulo ("Mercado (Alimentação)", "P2");
- `condicao`: o pedaço de SQL que escolhe as linhas, com `%(nome)s`;
- `params`: os parâmetros dessa condição;
- `so_integrantes`: quando True, só entram as despesas marcadas como parte da
  série histórica (`integra_ipca`), e a consulta devolve de quebra quanto
  ficou de fora. É o que a análise por prioridade tem e a por subcategoria
  não."""


# --- o recorte da análise por subcategoria ---

def subcategorias_com_lancamento():
    """As subcategorias que aparecem no acervo, em grupos por categoria.

    Só as que têm lançamento: oferecer uma subcategoria sem nenhum gasto é
    oferecer um gráfico vazio. A ordenação é a pt-BR de `chave_alfabetica`,
    feita em Python — nunca `locale`.
    """
    linhas = query_all(
        "SELECT DISTINCT subcategoria_id AS id, subcategoria, categoria"
        "  FROM vw_despesas"
    )
    linhas.sort(key=lambda l: (chave_alfabetica(l["categoria"]),
                               chave_alfabetica(l["subcategoria"])))

    grupos, atual = [], None
    for linha in linhas:
        if atual is None or atual["categoria"] != linha["categoria"]:
            atual = {"categoria": linha["categoria"], "itens": []}
            grupos.append(atual)
        atual["itens"].append({"id": linha["id"], "nome": linha["subcategoria"]})
    return grupos


def recorte_da_subcategoria(sub_id):
    """O recorte de uma subcategoria, ou None quando o id não serve.

    Subcategoria inexistente ou sem lançamento não é erro: é como se não
    tivessem escolhido nenhuma, e a tela volta ao convite.
    """
    if not sub_id:
        return None
    linha = query_one(
        "SELECT subcategoria FROM vw_despesas WHERE subcategoria_id = %s LIMIT 1",
        (sub_id,),
    )
    if linha is None:
        return None
    return Recorte(nome=linha["subcategoria"],
                   condicao="v.subcategoria_id = %(sub)s",
                   params={"sub": sub_id})


# --- o recorte da análise por prioridade (rodada 26) ---

ESSENCIAL = "Essencial"
NAO_ESSENCIAL = "Não Essencial"

# (chave na URL, rótulo do <select>, nome que abre o subtítulo).
#
# Dois nomes porque são dois lugares: no select cabe "P4 — menos importante",
# que é onde a pessoa escolhe e precisa lembrar o que significa; no subtítulo,
# ao lado do período e do agrupamento, o que cabe é "P4".
FAIXAS = (
    ("essencial", "Essencial",             "Essencial"),
    ("p1",        "P1 — mais importante",  "P1"),
    ("p2",        "P2",                    "P2"),
    ("p3",        "P3",                    "P3"),
    ("p4",        "P4 — menos importante", "P4"),
)


def faixa_valida(texto):
    """A chave da faixa, ou None. Faixa desconhecida vira "não escolheu".

    Diferente de período e agrupamento, que caem num padrão: aqui não há
    padrão que se possa escolher pela pessoa — somar "Essencial" porque a URL
    veio torta seria responder outra pergunta.
    """
    return texto if any(texto == chave for chave, _, _ in FAIXAS) else None


def recorte_da_faixa(faixa):
    """O recorte de uma das cinco faixas, ou None quando a faixa não serve.

    A essencialidade é a **efetiva** da view (`COALESCE` da despesa com a da
    subcategoria), e em "Essencial" ela vence sozinha: o banco não impede que
    uma despesa essencial carregue prioridade de um registro antigo, e essa
    prioridade não a move de faixa.

    Despesa não essencial **sem prioridade** não cai em faixa nenhuma, e isso
    não precisa de cláusula: `prioridade = 4` sobre NULL é NULL, que não é
    verdadeiro. Ela é desprezada, por decisão do dono — não há sexta faixa e
    ela não engorda a P4.
    """
    if faixa is None:
        return None

    nome = next(n for chave, _, n in FAIXAS if chave == faixa)
    if faixa == "essencial":
        condicao = "v.essencialidade = %(essencialidade)s"
        params = {"essencialidade": ESSENCIAL}
    else:
        condicao = ("v.essencialidade = %(essencialidade)s"
                    " AND v.prioridade = %(prioridade)s")
        params = {"essencialidade": NAO_ESSENCIAL, "prioridade": int(faixa[1])}

    return Recorte(nome=nome, condicao=condicao, params=params,
                   so_integrantes=True)


# --------------------------------------------------------------------------
# 3. Consultas
# --------------------------------------------------------------------------

def intervalo_do_acervo():
    """(primeiro mês, último mês) com lançamento no acervo inteiro, ou None.

    É do ACERVO, e não do recorte: "série inteira" quer dizer o período que o
    sistema cobre, para duas subcategorias (ou duas faixas) serem comparáveis
    lado a lado.
    """
    linha = query_one("SELECT MIN(data) AS de, MAX(data) AS ate FROM vw_despesas")
    if linha is None or linha["de"] is None:
        return None
    return (date(linha["de"].year, linha["de"].month, 1),
            date(linha["ate"].year, linha["ate"].month, 1))


_MES = "date_trunc('month', v.data)::date"

# A correção é por LANÇAMENTO, no mês do lançamento, e a soma vem depois:
# deflacionar a soma do mês pelo índice do mês dá o mesmo número, mas
# deflacionar a soma do TRIMESTRE por um índice só não daria — e é o
# agrupamento que a tela oferece. Por isso a conta mora no SQL, linha a linha.
#
# COALESCE no denominador: mês posterior à base não tem índice carregado, e o
# fator vira base/base = 1.
_CORRIGIDO = "SUM(v.valor * %(base)s / COALESCE(i.numero_indice, %(base)s))"
# Sem IPCA carregado não há o que corrigir; a coluna existe para a composição
# não ter dois caminhos, e vale o nominal.
_SEM_CORRECAO = "SUM(v.valor)"

# Recorte com `so_integrantes`: as três somas de cima passam a contar só as
# despesas marcadas como parte da série histórica. O FILTER vai nas SOMAS, e
# não no WHERE, justamente para as desprezadas continuarem alcançáveis na
# mesma varredura — é delas que sai o "ficou de fora" abaixo.
_SO_INTEGRANTES = "FILTER (WHERE v.integra_ipca)"

# ... e é este o "ficou de fora": total e quantidade das desprezadas, no
# PERÍODO EXIBIDO. O limite inferior é próprio porque a janela de 12 meses
# móveis consulta mais meses do que a tela mostra, e a nota fala do que está
# na tela. Um número do período inteiro, e não por ponto: a pergunta é "o que
# esta tela não está mostrando?".
_FORA = """,
           COALESCE(SUM(v.valor) FILTER (WHERE NOT v.integra_ipca
                                           AND v.data >= %(exibido)s), 0)
                                             AS fora_valor,
           COUNT(*) FILTER (WHERE NOT v.integra_ipca
                              AND v.data >= %(exibido)s)
                                             AS fora_quantidade"""

_SQL_SERIE = """
    SELECT {mes}                              AS mes,
           COALESCE(SUM(v.valor) {dentro}, 0) AS nominal,
           COALESCE({corrigido} {dentro}, 0)  AS corrigido,
           COUNT(*) {dentro}                  AS quantidade{fora}
      FROM vw_despesas v
      LEFT JOIN tb_ipca i ON i.mes = {mes}
     WHERE {recorte}
       AND v.data >= %(inicio)s
       AND v.data <  %(fim)s
     GROUP BY {grupos}
     ORDER BY 1
"""


def consultar(recorte, inicio, exibido, fim, base):
    """Uma consulta: por mês, soma nominal, soma corrigida e quantidade.

    `inicio` e `fim` são o primeiro dia do primeiro mês e o primeiro dia do mês
    SEGUINTE ao último — o filtro é `data >= ... AND data < ...`, que é o que
    faz o índice `ix_despesas_data` ser usado. `ano_mes` da view serve para
    exibir e agrupar, nunca para filtrar. `exibido` é o primeiro mês que a
    tela mostra, que só difere de `inicio` na janela de 12 meses móveis.

    Devolve (linhas por mês, total do recorte). O total vem por
    `GROUPING SETS ((mês), ())` — a mesma varredura, uma linha a mais, com
    `mes` nulo — e só existe quando o recorte despreza alguma coisa; é dele
    que sai o "ficou de fora". Recorte que não despreza nada não paga por
    uma pergunta que não faz.

    Meses sem lançamento simplesmente não voltam; quem os transforma em zero é
    a composição.
    """
    sql = _SQL_SERIE.format(
        mes=_MES,
        corrigido=_CORRIGIDO if base is not None else _SEM_CORRECAO,
        dentro=_SO_INTEGRANTES if recorte.so_integrantes else "",
        fora=_FORA if recorte.so_integrantes else "",
        recorte=recorte.condicao,
        grupos=f"GROUPING SETS (({_MES}), ())" if recorte.so_integrantes
               else _MES,
    )
    linhas = query_all(sql, {**recorte.params, "inicio": inicio, "fim": fim,
                             "exibido": exibido, "base": base})
    return ([l for l in linhas if l["mes"] is not None],
            next((l for l in linhas if l["mes"] is None), None))


# --------------------------------------------------------------------------
# 4. Composição (pura)
# --------------------------------------------------------------------------

def _centavos(valor):
    """Arredonda só no ponto, e só aqui: as somas em SQL ficam com a precisão
    do NUMERIC, e o corte a centavos é a última coisa que acontece."""
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _grade(primeiro, ultimo):
    """Todos os meses de `primeiro` a `ultimo`, inclusive."""
    meses, atual = [], primeiro
    while atual <= ultimo:
        meses.append(atual)
        atual = somar_meses(atual, 1)
    return meses


def _somar(por_mes, meses):
    """(nominal, corrigido, quantidade) do conjunto de meses, sem arredondar."""
    nominal = corrigido = Decimal(0)
    quantidade = 0
    for mes in meses:
        linha = por_mes.get(mes)
        if linha is None:
            continue
        nominal += linha["nominal"]
        corrigido += linha["corrigido"]
        quantidade += linha["quantidade"]
    return nominal, corrigido, quantidade


def _ponto(rotulo, por_mes, meses, parcial):
    nominal, corrigido, quantidade = _somar(por_mes, meses)
    return {
        "rotulo": rotulo,
        "nominal": _centavos(nominal),
        "corrigido": _centavos(corrigido),
        "quantidade": quantidade,
        "parcial": parcial,
    }


def _rotulo_mes(mes):
    """date -> 'jan/2026'."""
    return f"{MESES_CURTOS[mes.month - 1].lower()}/{mes.year}"


def montar_pontos(linhas, primeiro, ultimo, agrupar, mes_corrente,
                  primeiro_acervo):
    """Linhas por mês -> os pontos do gráfico e da tabela. Pura.

    Nem banco nem relógio: o mês corrente entra por parâmetro, como a data que
    a tela do IPCA passa para `mes_esperado`. É o que permite exercitar cada
    agrupamento com uma série sintética de três meses.

    "Parcial" é o bucket que não cabe inteiro no período (as pontas de um
    trimestre ou de um ano recortados) ou que contém o mês em curso — quem
    olha precisa saber que aquele ponto ainda vai crescer.
    """
    por_mes = {l["mes"]: l for l in linhas}
    meses = _grade(primeiro, ultimo)

    if agrupar == MES:
        return [_ponto(_rotulo_mes(mes), por_mes, [mes], mes == mes_corrente)
                for mes in meses]

    if agrupar == MOVEL:
        # Cada ponto é a soma dos 12 meses terminados nele, e a janela olha
        # para trás mesmo fora do período exibido. Só janelas COMPLETAS: uma
        # janela que começasse antes do acervo somaria zeros que não são
        # "não gastei", são "não existe registro".
        pontos = []
        for mes in meses:
            inicio = somar_meses(mes, -(MESES_MOVEIS - 1))
            if primeiro_acervo is None or inicio < primeiro_acervo:
                continue
            janela = _grade(inicio, mes)
            pontos.append(_ponto(f"12 m até {_rotulo_mes(mes)}", por_mes,
                                 janela, mes_corrente in janela))
        return pontos

    # Trimestre e ano: buckets de calendário. O bucket é marcado parcial
    # quando o período recorta algum mês dele — o primeiro e o último de uma
    # janela móvel quase sempre são.
    tamanho = 3 if agrupar == TRIMESTRE else 12
    pontos, vistos = [], set()
    for mes in meses:
        inicio_bucket = date(mes.year, ((mes.month - 1) // tamanho) * tamanho + 1, 1)
        if inicio_bucket in vistos:
            continue
        vistos.add(inicio_bucket)

        completo = _grade(inicio_bucket, somar_meses(inicio_bucket, tamanho - 1))
        dentro = [m for m in completo if primeiro <= m <= ultimo]
        rotulo = (str(inicio_bucket.year) if agrupar == ANO
                  else f"{(inicio_bucket.month - 1) // 3 + 1}T {inicio_bucket.year}")
        pontos.append(_ponto(rotulo, por_mes, dentro,
                             len(dentro) < tamanho or mes_corrente in dentro))
    return pontos


def _nota_fora(total):
    """A nota do que o recorte desprezou no período, ou None. Pura.

    Só chega aqui com conteúdo o recorte que despreza alguma coisa (hoje, o da
    análise por prioridade). O plural é decidido aqui, como todo texto: o
    template não sabe contar.
    """
    if total is None or not total["fora_quantidade"]:
        return None
    n = total["fora_quantidade"]
    quantos = "1 lançamento" if n == 1 else f"{n} lançamentos"
    ficaram = "ficou" if n == 1 else "ficaram"
    return (f"{quantos} desta faixa, somando R$ "
            f"{formatar_valor(total['fora_valor'])}, {ficaram} de fora no "
            "período exibido: são gastos pontuais, desmarcados no lançamento "
            "para não distorcer a série histórica.")


def _resumo(pontos, agrupar, corrigido):
    """Média, mediana e total dos períodos COMPLETOS, ou None. Pura.

    Sai dos pontos que a tabela imprime, e não de uma consulta nova: são o
    conjunto pequeno e completo cuja definição É "estas linhas" — a exceção
    que a regra dos agregados prevê. E sai dos MESMOS números da tabela, já
    arredondados a centavos, que é o que faz somar a coluna à mão dar o total
    do cartão.

    **Parcial fica de fora**, por decisão do dono. O mês em curso e as pontas
    recortadas de um trimestre arrastam a média para baixo sem que nada na
    tela explique por quê: nos doze meses de "Essencial", setembro pela
    metade tirava R$ 300 da média. O preço é que às vezes não sobra nada para
    resumir — agrupamento anual numa janela de doze meses tem os dois anos
    recortados —, e aí o cartão simplesmente não aparece, que é mais honesto
    do que a média de dois meios-anos.

    Com a correção ligada o resumo é dos valores reais; sem ela, dos
    nominais. Nunca dos dois: o cartão acompanha a coluna em destaque, e o
    subtítulo da página já diz a que preços ela está.
    """
    chave = "corrigido" if corrigido else "nominal"
    valores = [p[chave] for p in pontos if not p["parcial"]]
    if len(valores) < MINIMO_RESUMO:
        return None

    adjetivo, contagem = RESUMO_UNIDADE[agrupar]
    quantos = contagem % len(valores)
    # `mean` e `median` do stdlib preservam Decimal (conferido): não há float
    # no caminho, e o corte a centavos continua acontecendo só no fim.
    return [
        card(f"Média{adjetivo}", valor=_centavos(mean(valores)),
             apoio=f"em {quantos}"),
        # Os dois apoios abaixo não repetem o substantivo de propósito:
        # "janelas" é feminino e os outros três masculinos, e "os mesmos
        # janelas" é o tipo de concordância que só aparece na tela.
        card(f"Mediana{adjetivo}", valor=_centavos(median(valores)),
             apoio="metade ficou abaixo disso"),
        card("Total", valor=_centavos(sum(valores)),
             apoio="a soma dos mesmos períodos"),
    ]


def montar(linhas, primeiro, ultimo, agrupar, periodo, nome, mes_corrente,
           primeiro_acervo, base_mes=None, total=None):
    """Tudo o que a tela mostra, com o texto já escrito.

    `nome` é o que abre o subtítulo, e é a única coisa que a composição sabe
    sobre qual das duas telas a chamou: "Mercado (Alimentação)" numa,
    "P2" na outra.

    `base_mes` só vem preenchido quando a correção está ligada: é ele que
    escreve o "a preços de agosto de 2026" do subtítulo. `total` é a linha de
    total da consulta, de onde sai o "ficou de fora".
    """
    pontos = montar_pontos(linhas, primeiro, ultimo, agrupar, mes_corrente,
                           primeiro_acervo)

    if periodo == PERSONALIZADO:
        rotulo_periodo = intervalo_de_meses(primeiro, ultimo)
    else:
        rotulo_periodo = ROTULO_PERIODO[periodo]

    partes = [nome, rotulo_periodo, ROTULO_AGRUPAMENTO[agrupar]]
    rotulo_corrigido = None
    if base_mes is not None:
        rotulo_corrigido = f"A preços de {nome_do_periodo(base_mes)}"
        partes.append(f"a preços de {nome_do_periodo(base_mes)}")

    # A nota fala só do mês em curso: um bucket parcial das pontas já se
    # explica pelo rótulo do período, mas "o mês ainda não acabou" não.
    nota = None
    if pontos and pontos[-1]["parcial"] and mes_corrente <= ultimo:
        nota = (f"O último ponto inclui {nome_do_periodo(mes_corrente)}, "
                "que ainda está em curso.")

    return {
        "pontos": pontos,
        "resumo": _resumo(pontos, agrupar, base_mes is not None),
        "subtitulo": " · ".join(partes),
        "rotulo_corrigido": rotulo_corrigido,
        "nota": nota,
        "nota_fora": _nota_fora(total),
    }


# --------------------------------------------------------------------------
# 5. O que vai para o gráfico
# --------------------------------------------------------------------------

def para_grafico(resultado, corrigir):
    """Os mesmos pontos da tabela, no formato que o `analise.js` desenha.

    É o **único** lugar onde `Decimal` vira `float`, e só depois de o valor já
    estar arredondado a centavos: o JavaScript recebe número pronto e não faz
    conta nenhuma. Os rótulos vêm daqui prontos, inclusive o da série
    corrigida — o JS não escreve texto.

    Zero é zero: a lista traz `0.0`, nunca `null`. Buraco viraria linha
    interpolada, e "não gastei" não é "não sei".
    """
    pontos = resultado["pontos"]
    series = [{"rotulo": "Nominal",
               "valores": [float(p["nominal"]) for p in pontos]}]
    if corrigir:
        series.append({"rotulo": resultado["rotulo_corrigido"],
                       "valores": [float(p["corrigido"]) for p in pontos]})
    return {
        "rotulos": [p["rotulo"] for p in pontos],
        "series": series,
        "quantidades": [p["quantidade"] for p in pontos],
        "parciais": [p["parcial"] for p in pontos],
    }


# --------------------------------------------------------------------------
# 6. A tela inteira
# --------------------------------------------------------------------------

def painel(args, recorte, hoje):
    """Da URL ao que o template mostra. O caminho é um só para as duas telas.

    A rota lê o que é dela — a subcategoria ou a faixa — e entrega o recorte
    já montado; daqui para a frente não há diferença entre as duas análises.
    `recorte` nulo é "ainda não escolheram": nada é consultado e a tela fica
    no convite.

    `hoje` entra por parâmetro, como em toda função deste módulo que precisa
    saber a data.
    """
    mes_corrente = date(hoje.year, hoje.month, 1)

    base = ipca.base_de_correcao()
    acervo = intervalo_do_acervo()
    primeiro_acervo = acervo[0] if acervo else None

    periodo = periodo_valido(args.get("periodo"))
    agrupar = agrupamento_valido(args.get("agrupar"))
    de, ate = args.get("de", ""), args.get("ate", "")
    # A correção só é oferecida com IPCA carregado; sem base não há a que
    # corrigir, e a caixa vem desabilitada no formulário.
    corrigir = caixa_marcada(args.get("ipca")) and base is not None

    primeiro, ultimo, erro = resolver_periodo(periodo, de, ate, acervo,
                                              mes_corrente)

    resultado, sem_lancamento = None, False
    if recorte and primeiro and not erro:
        # A janela de 12 meses móveis olha 11 meses para trás do período
        # exibido; os demais agrupamentos leem só o que mostram.
        recuo = MESES_MOVEIS - 1 if agrupar == MOVEL else 0
        linhas, total = consultar(
            recorte,
            somar_meses(primeiro, -recuo),
            primeiro,
            somar_meses(ultimo, 1),
            base["numero_indice"] if base else None,
        )
        if linhas:
            resultado = montar(
                linhas, primeiro, ultimo, agrupar, periodo, recorte.nome,
                mes_corrente, primeiro_acervo,
                base_mes=base["mes"] if corrigir else None, total=total)
        else:
            # Nenhuma linha por mês: nem desprezada havia. Um recorte cujas
            # despesas foram TODAS desprezadas não cai aqui — ele desenha a
            # série em zero e explica o porquê na nota, que é mais honesto do
            # que dizer "nenhum lançamento" sobre um mês em que se gastou.
            sem_lancamento = True

    return {
        "escolhido": recorte is not None,
        "periodo": periodo,
        "agrupar": agrupar,
        "corrigir": corrigir,
        # O campo volta com o que o usuário escolheu, mas só se for um mês de
        # verdade: `<input type="month">` recusa texto fora do formato, mostra
        # o campo vazio e ainda avisa no console. Quem explica o que houve é a
        # mensagem de erro, não um valor que o navegador não sabe exibir.
        "de": texto_do_campo(de, primeiro, periodo),
        "ate": texto_do_campo(ate, ultimo, periodo),
        "tem_ipca": base is not None,
        "erro": erro,
        "sem_lancamento": sem_lancamento,
        "r": resultado,
        "grafico": para_grafico(resultado, corrigir) if resultado else None,
    }
