"""Análise por subcategoria: a série de uma subcategoria no tempo.

A pergunta da tela é "este gasto subiu?", e ela só tem resposta honesta com
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

`tb_despesas.integra_ipca` **não é lida aqui** — é de uma tela futura, por
decisão do dono.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from freedom.db import query_all, query_one
from freedom.util import (MESES_CURTOS, chave_alfabetica, intervalo_de_meses,
                          nome_do_periodo, somar_meses)

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")

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


# --------------------------------------------------------------------------
# 1. Parâmetros
# --------------------------------------------------------------------------

def periodo_valido(texto):
    return texto if texto in PERIODOS else DOZE


def agrupamento_valido(texto):
    return texto if texto in AGRUPAMENTOS else MES


def correcao_pedida(texto):
    """A caixa marcada. Só `1` liga; qualquer outra coisa é não."""
    return texto == "1"


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
# 2. Consultas
# --------------------------------------------------------------------------

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


def nome_da_subcategoria(sub_id):
    """'Combustível', ou None quando o id não existe ou não tem lançamento."""
    linha = query_one(
        "SELECT subcategoria FROM vw_despesas WHERE subcategoria_id = %s LIMIT 1",
        (sub_id,),
    )
    return linha["subcategoria"] if linha else None


def intervalo_do_acervo():
    """(primeiro mês, último mês) com lançamento no acervo inteiro, ou None.

    É do ACERVO, e não da subcategoria: "série inteira" quer dizer o período
    que o sistema cobre, para duas subcategorias serem comparáveis lado a lado.
    """
    linha = query_one("SELECT MIN(data) AS de, MAX(data) AS ate FROM vw_despesas")
    if linha is None or linha["de"] is None:
        return None
    return (date(linha["de"].year, linha["de"].month, 1),
            date(linha["ate"].year, linha["ate"].month, 1))


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

_SQL_SERIE = """
    SELECT date_trunc('month', v.data)::date AS mes,
           SUM(v.valor)                      AS nominal,
           {corrigido}                       AS corrigido,
           COUNT(*)                          AS quantidade
      FROM vw_despesas v
      LEFT JOIN tb_ipca i ON i.mes = date_trunc('month', v.data)::date
     WHERE v.subcategoria_id = %(sub)s
       AND v.data >= %(inicio)s
       AND v.data <  %(fim)s
     GROUP BY 1
     ORDER BY 1
"""


def linhas_por_mes(sub_id, inicio, fim, base):
    """Uma consulta: por mês, soma nominal, soma corrigida e quantidade.

    `inicio` e `fim` são o primeiro dia do primeiro mês e o primeiro dia do mês
    SEGUINTE ao último — o filtro é `data >= ... AND data < ...`, que é o que
    faz o índice `ix_despesas_data` ser usado. `ano_mes` da view serve para
    exibir e agrupar, nunca para filtrar.

    Meses sem lançamento simplesmente não voltam; quem os transforma em zero é
    a composição.
    """
    sql = _SQL_SERIE.format(
        corrigido=_CORRIGIDO if base is not None else _SEM_CORRECAO)
    return query_all(sql, {"sub": sub_id, "inicio": inicio, "fim": fim,
                           "base": base})


# --------------------------------------------------------------------------
# 3. Composição (pura)
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


def montar(linhas, primeiro, ultimo, agrupar, periodo, nome_sub, mes_corrente,
           primeiro_acervo, base_mes=None):
    """Tudo o que a tela mostra, com o texto já escrito.

    `base_mes` só vem preenchido quando a correção está ligada: é ele que
    escreve o "a preços de agosto de 2026" do subtítulo.
    """
    pontos = montar_pontos(linhas, primeiro, ultimo, agrupar, mes_corrente,
                           primeiro_acervo)

    if periodo == PERSONALIZADO:
        rotulo_periodo = intervalo_de_meses(primeiro, ultimo)
    else:
        rotulo_periodo = ROTULO_PERIODO[periodo]

    partes = [nome_sub, rotulo_periodo, ROTULO_AGRUPAMENTO[agrupar]]
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
        "subtitulo": " · ".join(partes),
        "rotulo_corrigido": rotulo_corrigido,
        "nota": nota,
    }


# --------------------------------------------------------------------------
# 4. O que vai para o gráfico
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
