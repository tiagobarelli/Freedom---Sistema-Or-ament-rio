"""Independência financeira: quanto falta, no modelo do Mr. Money Mustache.

A tela responde uma pergunta só, e ela não é sobre o mês: **em quantos anos a
casa deixa de depender do salário?** O modelo é o do texto "The Shockingly
Simple Math Behind Early Retirement" — com a renda líquida normalizada em 1,
taxa de poupança `s`, retorno real anual `r` e taxa segura de retirada `TSR`,
partindo de patrimônio zero:

    n = ln(1 + r·(1 − s) / (s·TSR)) / ln(1 + r)

e o patrimônio necessário é o gasto anual × (1/TSR). O que o modelo pede não é
quanto se ganha: é que **fração** da renda sobra. Duas casas com rendas muito
diferentes e a mesma taxa de poupança levam o mesmo tempo — é isso que a curva
desenha, e é por isso que a tabela ano a ano compara taxas, e não reais.

**As premissas são as vigentes HOJE, em todas as linhas.** `R`, `TSR` e `S`
saem de `tb_configuracoes` numa consulta só, e a mesma tripla vale para a
tabela inteira, para os cards e para a curva. O histórico de vigências existe e
NÃO é lido por linha, por decisão do dono: a tabela só compara anos se todos
estiverem sob a mesma premissa — senão a coluna "Anos até a IF" misturaria
modelos, e comparar 2023 com 2026 deixaria de significar alguma coisa.

Esta é a **primeira leitura** das três chaves: elas existem desde a rodada 8 e
nada as lia. Nada é gravado aqui, em lugar nenhum — a simulação dos três campos
vive na URL e morre com ela.

Três consultas, e são estas: os vigentes (o `DISTINCT ON` de Parâmetros), as
receitas e despesas somadas por ano (uma varredura, com o acumulado saindo da
mesma passagem por `GROUPING SETS ((ano), ())`) e as despesas dos últimos 12
meses fechados, por intervalo de `data`. O primeiro mês do acervo de despesas
sai da segunda, por um `MIN(data) FILTER`: é a mesma varredura, e uma consulta
só para descobrir onde o acervo começa seria uma ida ao banco de graça.

O que é conta mora em função pura, com a data entrando por parâmetro — `hoje`
nunca é lido do relógio aqui dentro.
"""

from collections import namedtuple
from datetime import date
from decimal import (ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal,
                     InvalidOperation)

from freedom.configuracoes.servico import (PERCENTUAL, formatar,
                                           valores_vigentes)
from freedom.db import query_all, query_one
from freedom.main.servico import SEM_VALOR, card
from freedom.util import (MESES, ValorInvalido, com_sinal, converter_numero,
                          data_por_extenso, formatar_numero, formatar_valor,
                          fracao, intervalo_de_meses, nome_do_periodo,
                          somar_meses)

ZERO = Decimal("0.00")
CENTAVO = Decimal("0.01")
DECIMO = Decimal("0.1")
CEM = Decimal(100)

# A janela da curva. Abaixo de 5 % o prazo explode (a 1 % passa de 300 anos) e
# o gráfico viraria uma parede; acima de 95 % o modelo já respondeu.
TAXA_MINIMA = Decimal(5)
TAXA_MAXIMA = Decimal(95)
PASSO_CURVA = Decimal(1)
PASSO_REFERENCIA = Decimal(5)

MESES_FECHADOS = 12

# Os três parâmetros: (nome na URL, chave em tb_configuracoes, rótulo do campo,
# símbolo). O rótulo aparece no formulário e na nota do que falta; o símbolo, na
# nota da simulação e no apoio dos cards. Os quatro nomes de cada parâmetro
# ficam escritos uma vez só, aqui.
PARAMETROS = (
    ("r",   "R",   "Retorno real (r)",              "r"),
    ("tsr", "TSR", "Taxa segura de retirada (TSR)", "TSR"),
    ("s",   "S",   "Meta de poupança (s)",          "s"),
)


# --------------------------------------------------------------------------
# 1. A conta (pura)
# --------------------------------------------------------------------------

def anos_ate_if(s, r, tsr):
    """Anos de trabalho até a independência, partindo de patrimônio zero.

    Os três entram como fração (`0.035` é 3,5 %) e qualquer um pode ser `None`
    — é o que acontece num banco em que a chave nunca foi cadastrada. Devolve
    `Decimal` sem arredondar: quem corta a casa decimal é a exibição, porque a
    mesma conta alimenta a curva, os cards e a tabela, e arredondar aqui faria
    os três divergirem no último dígito.

    Os casos de borda, todos com resposta e nenhum com exceção:

    - parâmetro ausente -> `None`. Não há prazo a dizer, e zero seria mentira;
    - `s <= 0` -> `None`. Quem não poupa não chega — e ano em que se gastou
      mais do que se ganhou tem taxa negativa, que é caso real do acervo e não
      erro de entrada;
    - `tsr <= 0` -> `None`: patrimônio nenhum sustenta um gasto se não se pode
      retirar nada dele;
    - `s >= 1` -> `0`. Poupar tudo é já estar lá;
    - `r == 0` -> o LIMITE da fórmula quando `r` tende a zero,
      `(1 − s)/(s·TSR)`: sem juro nenhum, basta acumular o patrimônio
      necessário guardando a sobra. A fórmula cheia daria 0/0 aqui, e `r = 0`
      é premissa que alguém pode querer simular — é o cenário pessimista.
    """
    if s is None or r is None or tsr is None:
        return None
    if r < 0 or tsr <= 0 or s <= 0:
        return None
    if s >= 1:
        return Decimal(0)
    if r == 0:
        return (1 - s) / (s * tsr)
    # Com r > 0, s em (0, 1) e tsr > 0 o argumento do ln é sempre maior que 1:
    # o logaritmo não tem como receber zero nem negativo por este caminho.
    return (1 + r * (1 - s) / (s * tsr)).ln() / (1 + r).ln()


def anos_restantes(p0, g, a, r, tsr):
    """Anos que faltam a partir de um patrimônio que já existe. Pura.

        n = ln( (G/TSR + A/r) / (P0 + A/r) ) / ln(1 + r)

    É a mesma matemática de `anos_ate_if`, com duas diferenças: o ponto de
    partida não é zero (`P0`) e o aporte (`A`) e o gasto (`G`) entram em reais
    em vez de fração da renda — aqui já se sabe quanto a casa ganha e gasta,
    então não há por que normalizar.

    **As duas são a mesma fórmula**, e isso é verificável: com `P0 = 0`,
    `G = (1 − s)·R` e `A = s·R`, o `R` se cancela e sobra
    `ln(1 + r(1−s)/(s·TSR)) / ln(1+r)` — exatamente `anos_ate_if(s, r, TSR)`,
    para qualquer `R`. É o invariante que a validação desta rodada roda de
    5 % a 95 %.

    As bordas, todas com resposta e nenhuma com exceção:

    - qualquer entrada ausente -> `None`;
    - `A <= 0` -> `None`. Quem não guarda nada não chega, e o logaritmo de um
      quociente maior que 1 dividido por zero não é um prazo;
    - `TSR <= 0` -> `None`, como em `anos_ate_if`: sem retirada não há alvo;
    - `P0 >= G/TSR` -> `0`. O alvo já foi alcançado, e um número negativo de
      anos diria "você se aposentou há três anos", que não é a pergunta;
    - `r == 0` -> o limite `(G/TSR − P0) / A`: sem juro real, o que falta se
      junta guardando a sobra.
    """
    if p0 is None or g is None or a is None or r is None or tsr is None:
        return None
    if r < 0 or tsr <= 0 or a <= 0:
        return None

    alvo = g / tsr
    if p0 >= alvo:
        return Decimal(0)
    if r == 0:
        return (alvo - p0) / a

    # `A/r` é o valor presente do fluxo de aportes perpétuo; somá-lo dos dois
    # lados é o que transforma a progressão em razão pura, e é de onde sai o
    # logaritmo. Com A > 0 e r > 0 o denominador é sempre positivo, e o
    # quociente é maior que 1 porque p0 < alvo — o `ln` não recebe zero nem
    # negativo por este caminho.
    aporte_capitalizado = a / r
    return (((alvo + aporte_capitalizado) / (p0 + aporte_capitalizado)).ln()
            / (1 + r).ln())


def curva(r, tsr, passo=PASSO_CURVA):
    """Os pontos de `n(s)` de 5 % a 95 %, de `passo` em `passo`. Pura.

    Serve a dois lugares, com o mesmo código e os mesmos números: a linha do
    gráfico (passo de 1 p.p.) e a tabela de referência do `<details>` (de 5 em
    5). Duas listas montadas separadamente poderiam discordar justamente nos
    pontos em que se cruzam, que é onde alguém confere.

    Lista vazia quando falta `r` ou `TSR`: sem os dois não há curva, e quem
    desenha não precisa saber por quê.
    """
    pontos, taxa = [], TAXA_MINIMA
    while taxa <= TAXA_MAXIMA:
        anos = anos_ate_if(taxa / CEM, r, tsr)
        if anos is not None:
            pontos.append({"taxa": taxa, "anos": anos})
        taxa += passo
    return pontos


# --------------------------------------------------------------------------
# 2. As premissas: vigentes ou simuladas (leitura da URL, pura)
# --------------------------------------------------------------------------

Premissas = namedtuple(
    "Premissas", "r tsr s campos vigentes simulando faltando fora_da_faixa")
Premissas.__doc__ = """Os três números que a tela inteira usa, e como chegaram.

- `r`, `tsr`, `s`: fração ou `None` (chave sem vigência e sem valor na URL);
- `campos`: o que volta para cada campo do formulário, já formatado;
- `vigentes`: o texto de cada vigente, para a nota da simulação;
- `simulando`: ao menos um dos usados difere do vigente;
- `faltando`: os rótulos dos parâmetros que não têm valor NENHUM;
- `fora_da_faixa`: (símbolo, texto) dos que TÊM vigência, mas com um número
  que a página não pode usar. São coisas diferentes e por isso são duas
  listas: "nunca foi cadastrado" e "está cadastrado como zero" pedem ações
  diferentes de quem lê."""


def _aceitavel(nome, valor):
    """A faixa de cada parâmetro. Fora dela o valor não serve e é ignorado.

    `r` aceita zero (o cenário sem juro real é simulação legítima); `TSR` não,
    porque 1/TSR seria divisão por zero; `s` fica no aberto (0, 1), que é onde
    a fórmula tem sentido — poupar 0 % nunca chega e poupar 100 % já chegou, e
    nenhum dos dois é uma META que alguém digite.
    """
    if nome == "r":
        return valor >= 0
    if nome == "tsr":
        return valor > 0
    return 0 < valor < 1


def _digitado(args, nome):
    """O valor que veio na URL, ou None. Nunca levanta.

    Ausente, ilegível e fora da faixa dão todos a mesma coisa — `None` —, e
    quem chamou cai no vigente. É a regra do ano inválido da Visão Anual: um
    parâmetro torto na barra de endereço não vira tela de erro. Aqui nem o
    equivalente do período personalizado das Análises produz mensagem: não há
    campo obrigatório, e o campo volta preenchido com o que foi de fato usado,
    que é a resposta mais direta a "o que você fez com o que eu digitei?".
    """
    try:
        valor = converter_numero(args.get(nome), percentual=True)
    except (ValorInvalido, InvalidOperation):
        return None
    return valor if _aceitavel(nome, valor) else None


def resolver_premissas(args, vigentes):
    """(query string, vigentes do banco) -> `Premissas`. Pura.

    `vigentes` é {chave: Decimal}, como `valores_vigentes` devolve depois de
    reduzido ao número. Chave sem vigência entra como ausente, e a tela
    continua de pé com travessão no que dependia dela.
    """
    usados, campos, textos, faltando, fora, simulando = {}, {}, {}, [], [], False

    for nome, chave, rotulo, simbolo in PARAMETROS:
        vigente = vigentes.get(chave)
        # Vigente fora da faixa (uma TSR gravada como zero, por exemplo) não é
        # premissa: `tb_configuracoes` não tem CHECK de sinal, e quem sabe o
        # que cada chave significa é a aplicação. Desde a rodada 31 Parâmetros
        # recusa o zero em TSR e S, mas uma linha antiga pode tê-lo — e o
        # histórico de vigências não se reescreve.
        descartado = vigente is not None and not _aceitavel(nome, vigente)
        if descartado:
            fora.append((simbolo, formatar(vigente, PERCENTUAL)))
            vigente = None

        valor = _digitado(args, nome)
        if valor is None:
            valor = vigente
        elif valor != vigente:
            simulando = True

        # "Descartei o que estava lá" e "não havia nada" são avisos
        # diferentes, e o parâmetro entra em uma lista só.
        if valor is None and not descartado:
            faltando.append(rotulo)

        usados[nome] = valor
        # O campo volta com o valor EFETIVAMENTE usado, no formato em que
        # Parâmetros exibe ("3,50%"). O sinal junto é de propósito: o rótulo do
        # campo não diz a unidade, e `converter_numero` lê "3,5" e "3,5%" do
        # mesmo jeito — o que volta ao servidor é o mesmo número, sem perder
        # casa nenhuma das quatro que se pode digitar.
        campos[nome] = formatar(valor, PERCENTUAL)
        textos[simbolo] = formatar(vigente, PERCENTUAL) if vigente is not None \
            else SEM_VALOR

    return Premissas(r=usados["r"], tsr=usados["tsr"], s=usados["s"],
                     campos=campos, vigentes=textos, simulando=simulando,
                     faltando=tuple(faltando), fora_da_faixa=tuple(fora))


def _texto_do_parametro(premissas, nome):
    """O parâmetro como a tela o escreve, ou travessão quando não há."""
    return premissas.campos[nome] or SEM_VALOR


# --------------------------------------------------------------------------
# 3. Consultas
# --------------------------------------------------------------------------

Leitura = namedtuple("Leitura", "por_ano total doze foto")
Leitura.__doc__ = """O que o banco trouxe.

- `por_ano` e `total`: as linhas da tabela e o acumulado, da MESMA consulta —
  é dele que saem o rodapé e o card da taxa acumulada, que por isso mostram o
  mesmo número por construção;
- `doze`: despesas E receitas dos 12 meses fechados, também na mesma
  varredura. A despesa é a base do número de independência (rodada 29); as
  duas juntas são o gasto e o aporte dos "Anos restantes" (rodada 31);
- `foto`: a última foto de patrimônio, ou `None`. Vem de `ultima_foto()`, de
  `lancamentos/servico_patrimonio.py` — quem é dono do conceito de foto é
  aquela tela, e esta o importa."""

# Uma varredura das duas views: uma linha por ano, mais a do acumulado.
#
# O UNION ALL com uma coluna de tipo é o que permite somar receita e despesa
# lado a lado sem dois agregados correndo em paralelo e sem FULL JOIN: um ano
# que só tem receita (ou só despesa) continua aparecendo, com zero do outro
# lado — e é esse o critério da tabela, qualquer ano com receita OU despesa.
# `anos_com_lancamento` de `main/servico.py` não serve aqui: ela olha as duas
# views, mas ACRESCENTA o ano corrente mesmo sem lançamento nenhum, porque é o
# padrão do seletor daquela tela.
#
# `GROUPING SETS ((ano), ())` responde as duas perguntas na mesma passagem: as
# linhas por ano e a de total, com `ano` nulo. Atenção: o conjunto `()` devolve
# linha MESMO sem nenhuma linha de entrada, então acervo vazio não se testa
# pelo resultado estar vazio — testa-se pelas linhas por ano.
#
# Os dois agregados de data vêm de carona porque a varredura já é esta:
# `MAX(data)` por ano escreve o "parcial · até setembro" do ano corrente, e
# `MIN(data) FILTER (WHERE tipo = 'd')` na linha do total diz onde o acervo de
# DESPESAS começa, que é o que decide se os 12 meses fechados cabem nele.
_SQL_ANOS = """
    SELECT EXTRACT(YEAR FROM t.data)::int                        AS ano,
           COALESCE(SUM(t.valor) FILTER (WHERE t.tipo = 'r'), 0) AS receitas,
           COALESCE(SUM(t.valor) FILTER (WHERE t.tipo = 'd'), 0) AS despesas,
           MAX(t.data)                                           AS ultima,
           MIN(t.data) FILTER (WHERE t.tipo = 'd')               AS primeira_despesa
      FROM (SELECT data, valor, 'r' AS tipo FROM vw_receitas
            UNION ALL
            SELECT data, valor, 'd' AS tipo FROM vw_despesas) t
     GROUP BY GROUPING SETS ((EXTRACT(YEAR FROM t.data)::int), ())
     ORDER BY 1 NULLS LAST
"""

# Os 12 meses fechados, agora com os DOIS lados. Filtro por INTERVALO de
# `data`, nunca por `ano_mes`: é o que faz `ix_despesas_data` e
# `ix_receitas_data` serem usados — e por isso o intervalo vai dentro de cada
# ramo do UNION, e não por fora, onde o planejador teria de empurrá-lo.
#
# Até a rodada 30 esta consulta só somava despesa, porque só o número de
# independência dependia dela. O aporte dos "Anos restantes" é
# `receitas − despesas` do MESMO período, e pedi-lo numa segunda consulta
# seria varrer duas vezes a mesma janela.
_SQL_DOZE_MESES = """
    SELECT COALESCE(SUM(valor) FILTER (WHERE tipo = 'd'), 0) AS despesas,
           COALESCE(SUM(valor) FILTER (WHERE tipo = 'r'), 0) AS receitas
      FROM (SELECT valor, 'd' AS tipo FROM vw_despesas
             WHERE data >= %(inicio)s AND data < %(fim)s
            UNION ALL
            SELECT valor, 'r' AS tipo FROM vw_receitas
             WHERE data >= %(inicio)s AND data < %(fim)s) t
"""


def janela_fechada(hoje):
    """Os 12 meses que terminam no mês ANTERIOR ao corrente. Pura.

    "Fechado" é mês que já acabou: em 20/09/2026 a janela é setembro/2025 a
    agosto/2026. Incluir o mês em curso faria o número de independência
    despencar todo dia 1º e subir ao longo do mês, sem que nada tivesse
    mudado na vida da casa.

    Devolve (primeiro mês, primeiro dia do mês seguinte ao último), que é o
    par que o filtro `data >= ... AND data < ...` quer.
    """
    fim = date(hoje.year, hoje.month, 1)       # o mês em curso fica de fora
    return somar_meses(fim, -MESES_FECHADOS), fim


ZERO_DOZE = {"despesas": Decimal(0), "receitas": Decimal(0)}


def consultar(hoje):
    """As três consultas de dado. A das configurações é `vigentes`."""
    # Importado AQUI, e não no topo: `servico_patrimonio` importa o helper
    # `card` de `main/servico.py`, e carregar `freedom.main` executa o
    # `__init__` do blueprint, que importa esta rota de volta. O ciclo só
    # aparece quando alguém importa o serviço de patrimônio PRIMEIRO — o que
    # a validação faz, e o servidor não fazia. Adiar o import até a chamada
    # desfaz o nó sem mover ninguém de lugar.
    from freedom.lancamentos.servico_patrimonio import ultima_foto

    linhas = query_all(_SQL_ANOS)
    inicio, fim = janela_fechada(hoje)
    doze = query_one(_SQL_DOZE_MESES, {"inicio": inicio, "fim": fim})
    return Leitura(
        por_ano=[l for l in linhas if l["ano"] is not None],
        total=next((l for l in linhas if l["ano"] is None), None),
        doze=doze or dict(ZERO_DOZE),
        foto=ultima_foto(),
    )


def vigentes(hoje):
    """As três chaves vigentes hoje, pelo `DISTINCT ON` de Parâmetros.

    Uma consulta para as três, e não uma por chave. Chaves fora do catálogo
    que existam no banco vêm juntas e são ignoradas: quem escolhe as três é
    `PARAMETROS`.
    """
    return {l["chave"]: l["valor"] for l in valores_vigentes(hoje)}


# --------------------------------------------------------------------------
# 4. Composição (pura)
# --------------------------------------------------------------------------

def _centavos(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _decimo(valor):
    """Arredonda para uma casa com ROUND_HALF_UP: o número COMO A TELA O MOSTRA.

    `anos_ate_if` e `fracao` não arredondam, de propósito — o corte acontece
    aqui, num lugar só. Quem vai virar texto passa por esta função, e as duas
    colunas de diferença passam por ela ANTES de subtrair (ver `_linha`).
    """
    return None if valor is None else valor.quantize(DECIMO,
                                                     rounding=ROUND_HALF_UP)


def _uma_casa(valor):
    """Número com uma casa, ou travessão. É o formato de toda taxa da tela."""
    return SEM_VALOR if valor is None else formatar_numero(_decimo(valor), 1)


def _uma_casa_com_sinal(valor):
    """'+17,7', '-23,0' — ou travessão. Uma casa, sinal sempre explícito.

    Uma coluna de desvio sem o "+" obriga quem lê a lembrar de que lado está o
    zero. Quem põe o sinal é `com_sinal` de `util.py`, a mesma que a variação
    do patrimônio usa; aqui fica só o formato desta tela — uma casa decimal e
    o travessão de "não há número".
    """
    if valor is None:
        return SEM_VALOR
    return com_sinal(formatar_numero(valor, 1), valor)


def _linha(receitas, despesas, premissas, anos_meta, rotulo, marca=None):
    """Uma linha da tabela — um ano ou o acumulado. Pura.

    O acumulado passa por aqui com as MESMAS regras das linhas de ano: a taxa
    do rodapé é `Σ poupado ÷ Σ receitas`, e não a média das taxas anuais, que
    seria outra conta (a média simples trataria um ano magro como um gordo).

    As cores:

    - poupado, taxa e desvio ficam vermelhos quando são NEGATIVOS, que é a
      regra de formatação do projeto;
    - **Δ anos fica vermelho quando é POSITIVO**, e essa é a única inversão da
      tela. Mais anos que a meta é o resultado ruim; menos anos é o bom. Aqui
      a cor segue o SIGNIFICADO, e não o sinal — e por isso está escrito.

    Travessão nunca é vermelho: a classe só entra quando existe número.

    **As duas colunas de diferença são calculadas sobre os valores JÁ
    ARREDONDADOS**, e não sobre os exatos. É o que faz subtrair as duas
    colunas impressas dar o número impresso na terceira: com os exatos, a
    linha de 2025 imprimia 18,3 anos contra uma meta de 23,5 e um Δ de −5,1,
    e quem conferisse a subtração acharia um defeito que não existe. É a mesma
    escolha do resumo das Análises, que soma os pontos já cortados a centavos
    para somar a coluna à mão dar o total do cartão.

    O que NÃO se arredonda antes é a entrada do modelo: `anos_ate_if` recebe a
    taxa exata do ano, e não a de uma casa que a célula mostra — arredondar o
    que entra numa fórmula é mexer na resposta, e não na exibição dela.

    Os valores de taxa e anos saem junto dos textos, já arredondados, porque é
    deles que o gráfico desenha: o ponto do ano é o mesmo `Decimal` que a
    célula imprimiu.
    """
    poupado = receitas - despesas
    exata = fracao(poupado, receitas)         # em pontos percentuais, ou None
    taxa = _decimo(exata)

    desvio = None
    if taxa is not None and premissas.s is not None:
        desvio = taxa - premissas.s * CEM

    anos = _decimo(anos_ate_if(exata / CEM, premissas.r, premissas.tsr)
                   if exata is not None else None)

    delta = (anos - anos_meta
             if anos is not None and anos_meta is not None else None)

    return {
        "rotulo": rotulo,
        "marca": marca,
        "receitas": receitas,
        "despesas": despesas,
        "poupado": poupado,
        "poupado_negativo": poupado < 0,
        "taxa": _uma_casa(taxa) + ("%" if taxa is not None else ""),
        "taxa_negativa": taxa is not None and taxa < 0,
        "desvio": _uma_casa_com_sinal(desvio),
        "desvio_negativo": desvio is not None and desvio < 0,
        "anos": _uma_casa(anos),
        "delta": _uma_casa_com_sinal(delta),
        "delta_negativo": delta is not None and delta > 0,
        "taxa_valor": taxa,
        "anos_valor": anos,
    }


def _marca_parcial(linha, hoje):
    """'parcial · até setembro' no ano corrente, ou None. Pura.

    O mês é o do ÚLTIMO lançamento do ano (despesa ou receita, o que for mais
    recente), e não o mês de hoje: um ano corrente cujo último lançamento é de
    julho está fechado até julho, e dizer "até setembro" prometeria dois meses
    de dado que não existem.

    O ano parcial ENTRA no acumulado, e isso é decisão do dono: numerador e
    denominador cobrem o mesmo período, então a taxa dele é legítima — ao
    contrário do resumo das Análises, onde o período parcial fica de fora
    porque lá o que se compara é o tamanho de um período com o de outro. Nada
    nesta tela é anualizado.
    """
    if linha["ano"] != hoje.year or linha["ultima"] is None:
        return None
    return f"parcial · até {MESES[linha['ultima'].month - 1]}"


def base_dos_doze(leitura, hoje):
    """(cobre, despesas, receitas) dos 12 meses fechados. Pura.

    `cobre` é False quando o acervo de despesas começa DEPOIS do início da
    janela: a soma existe, mas não é de doze meses, e um número de
    independência calculado sobre oito meses de gasto seria um terço menor do
    que a verdade sem nada na tela dizendo isso. Os dois cards que dependem
    dessa base — "Número de independência" e "Anos restantes" — mostram
    travessão juntos, porque é a MESMA base.
    """
    inicio, _fim = janela_fechada(hoje)
    primeira = leitura.total["primeira_despesa"] if leitura.total else None
    cobre = (primeira is not None
             and date(primeira.year, primeira.month, 1) <= inicio)
    return cobre, leitura.doze["despesas"], leitura.doze["receitas"]


def _card_numero(leitura, premissas, hoje):
    """O número de independência: o gasto de 12 meses fechados × (1/TSR).

    Se o acervo de despesas começa DEPOIS do início da janela, a soma existe
    mas não é de doze meses — e um número de independência calculado sobre
    oito meses de gasto seria um terço menor do que a verdade, sem nada na
    tela dizendo isso. Nesse caso o card mostra travessão e a nota diz onde o
    acervo começa.
    """
    inicio, fim = janela_fechada(hoje)
    primeira = leitura.total["primeira_despesa"] if leitura.total else None
    cobre, despesas, _receitas = base_dos_doze(leitura, hoje)

    if cobre:
        nota = (f"despesas de {intervalo_de_meses(inicio, somar_meses(fim, -1))}"
                f": R$ {formatar_valor(_centavos(despesas))}")
    elif primeira is not None:
        nota = f"acervo começa em {nome_do_periodo(primeira)}"
    else:
        nota = "nenhuma despesa lançada"

    valor = (_centavos(despesas / premissas.tsr)
             if cobre and premissas.tsr is not None else None)

    return card("Número de independência", valor=valor,
                texto=SEM_VALOR if valor is None else None,
                nota={"texto": nota, "classe": None})


def _card_acumulada(leitura, rodape, hoje):
    """A taxa de poupança de todo o acervo.

    Lê a MESMA linha de que o rodapé da tabela sai — o conjunto `()` da
    consulta agrupada —, e por isso os dois números não podem divergir: é o
    mesmo `Decimal` formatado duas vezes.
    """
    anos = [l["ano"] for l in leitura.por_ano]
    nota = None
    if anos:
        periodo = (f"{anos[0]}–{anos[-1]}" if anos[0] != anos[-1]
                   else str(anos[0]))
        if hoje.year in anos:
            periodo += f" · {hoje.year} parcial"
        nota = {"texto": periodo, "classe": None}

    # O apoio inteiro leva a cor, e não só o número: "-3,0 p.p. vs meta" é uma
    # frase só, e deixar o "vs meta" em cinza ao lado sugeriria que a
    # comparação é outro assunto.
    apoio = apoio_classe = None
    if rodape["desvio"] != SEM_VALOR:
        apoio = f"{rodape['desvio']} p.p. vs meta"
        apoio_classe = "negativo" if rodape["desvio_negativo"] else None

    return card("Taxa de poupança acumulada", texto=rodape["taxa"],
                classe=("kpi__valor--negativo" if rodape["taxa_negativa"]
                        else None),
                apoio=apoio, apoio_classe=apoio_classe, nota=nota)


def _cards_partida(leitura, premissas, hoje, alvo):
    """A segunda fileira: de onde a casa parte, e quanto falta. Pura.

    `alvo` é o MESMO `Decimal` que o card "Número de independência" imprime —
    não é recalculado aqui. É o que faz "Alcançado" e "Falta" fecharem quando
    alguém os confere contra o card de cima com uma calculadora.

    Sem foto de patrimônio os quatro mostram travessão, e quem explica é a
    nota do topo: quatro cartões de "—" sem motivo seriam um defeito à vista.
    """
    foto = leitura.foto
    p0 = foto["total"] if foto else None
    cobre, despesas, receitas = base_dos_doze(leitura, hoje)

    # --- 1. o patrimônio ---
    nota_foto = None
    if foto and foto["faltando"]:
        # A foto pode estar incompleta, e o total só conta o que foi lançado
        # (decisão da rodada 30): o card avisa em vez de somar o último valor
        # conhecido de quem ficou de fora.
        quantos = foto["faltando"]
        nota_foto = {"texto": "foto incompleta: "
                              + ("falta 1 ativo" if quantos == 1
                                 else f"faltam {quantos} ativos"),
                     "classe": None}
    patrimonio = card("Patrimônio na última foto", valor=p0,
                      texto=SEM_VALOR if p0 is None else None,
                      apoio=data_por_extenso(foto["data"]) if foto else None,
                      nota=nota_foto)

    # --- 2. alcançado ---
    parcela = fracao(p0, alvo) if p0 is not None and alvo is not None else None
    alcancado = card(
        "Alcançado",
        texto=(_uma_casa(parcela) + "%") if parcela is not None else SEM_VALOR,
        apoio=(f"do alvo de R$ {formatar_valor(alvo)}"
               if alvo is not None else None))

    # --- 3. falta ---
    if p0 is None or alvo is None:
        falta = card("Falta", texto=SEM_VALOR)
    elif p0 >= alvo:
        # Zero, e não um número negativo: "falta -R$ 200.000" não é uma falta.
        falta = card("Falta", valor=ZERO, apoio="alvo alcançado")
    else:
        falta = card("Falta", valor=_centavos(alvo - p0))

    return [patrimonio, alcancado, falta,
            _card_restantes(premissas, p0, cobre, despesas, receitas)]


def _card_restantes(premissas, p0, cobre, despesas, receitas):
    """Quantos anos faltam com o aporte dos 12 meses fechados. Puro.

    O gasto é o MESMO dos 12 meses fechados que alimenta o número de
    independência, e o aporte é `receitas − despesas` do mesmo período: os
    dois saem da mesma janela, senão o prazo compararia um ano com outro.

    A variante "na meta" do apoio troca as duas pontas pela meta de poupança
    (`A = s·R₁₂`, `G = (1 − s)·R₁₂`) e muda o alvo junto — é outro cenário, e
    por isso é apoio e não o número do card.
    """
    aporte = receitas - despesas
    valido = cobre and receitas > 0

    anos = (anos_restantes(p0, despesas, aporte, premissas.r, premissas.tsr)
            if valido and p0 is not None else None)

    apoio = None
    if valido and p0 is not None and premissas.s is not None:
        na_meta = anos_restantes(p0, (1 - premissas.s) * receitas,
                                 premissas.s * receitas,
                                 premissas.r, premissas.tsr)
        if na_meta is not None:
            apoio = (f"na meta ({_texto_do_parametro(premissas, 's')}): "
                     f"{_uma_casa(na_meta)} anos")

    if not valido:
        nota = "sem receita nos 12 meses fechados" if cobre else None
    elif aporte <= 0:
        nota = "sem aporte nos 12 meses"
    else:
        nota = ("12 meses fechados: poupança de "
                f"{_uma_casa(fracao(aporte, receitas))}%")

    return card("Anos restantes", texto=_uma_casa(anos), apoio=apoio,
                nota={"texto": nota, "classe": None} if nota else None)


def _cards(leitura, rodape, premissas, anos_meta, hoje):
    """Os quatro cards, pelo helper `card` da Visão Anual. Puro.

    Os dois do meio não dependem de dado nenhum — são leitura direta das
    premissas —, e por isso continuam respondendo num banco recém-criado, sem
    lançamento algum: "o gasto anual vale 28,6 vezes" é verdade sobre a TSR,
    não sobre o acervo. Os outros dois mostram travessão quando falta a
    premissa de que dependem ou quando o acervo não alcança.
    """
    multiplo = (_uma_casa(1 / premissas.tsr) + "×"
                if premissas.tsr is not None else SEM_VALOR)

    return [
        _card_numero(leitura, premissas, hoje),
        card("Múltiplo do gasto anual", texto=multiplo,
             apoio=f"TSR {_texto_do_parametro(premissas, 'tsr')}"),
        card("Anos até a IF na meta", texto=_uma_casa(anos_meta),
             apoio=f"poupando {_texto_do_parametro(premissas, 's')}"),
        _card_acumulada(leitura, rodape, hoje),
    ]


def _notas(premissas, foto):
    """As notas do topo. Puras.

    Podem aparecer juntas — simular um valor, não ter vigência de outro, ter
    um terceiro gravado fora da faixa e ainda não haver foto de patrimônio são
    quatro fatos independentes —, e por isso são quatro textos, e não um com
    quatro caras.
    """
    simulacao = None
    if premissas.simulando:
        lista = ", ".join(f"{simbolo} {premissas.vigentes[simbolo]}"
                          for _, _, _, simbolo in PARAMETROS)
        simulacao = ("Simulação com os valores digitados. "
                     f"Vigentes: {lista}.")

    faltando = None
    if premissas.faltando:
        # Plural decidido aqui, como todo texto: o template não sabe contar, e
        # "1 parâmetros" é o tipo de coisa que só aparece num banco novo — ou
        # seja, na primeira vez que alguém abre a tela.
        um = len(premissas.faltando) == 1
        quais = ", ".join(premissas.faltando)
        faltando = (f"{quais} {'não tem' if um else 'não têm'} valor vigente. "
                    f"O que depende {'desse parâmetro' if um else 'desses parâmetros'}"
                    " aparece com travessão até ser cadastrado.")

    # Cadastrado, porém inutilizável: dizer "não tem valor vigente" mandaria
    # cadastrar o que já está lá. O texto nomeia o número que foi ignorado,
    # que é o que se vai procurar em Parâmetros.
    fora = None
    if premissas.fora_da_faixa:
        um = len(premissas.fora_da_faixa) == 1
        quais = ", ".join(f"{simbolo} vigente é {texto}"
                          for simbolo, texto in premissas.fora_da_faixa)
        fora = (f"{quais}, fora da faixa; a página ignorou "
                f"{'o valor' if um else 'os valores'}.")

    sem_foto = None
    if foto is None:
        sem_foto = ("Sem foto de patrimônio. O ponto de partida aparece "
                    "assim que a primeira foto for lançada.")

    return simulacao, faltando, fora, sem_foto


def _subtitulo(premissas, hoje):
    """"Simulação — nada é gravado", ou a data das premissas por extenso."""
    if premissas.simulando:
        return "Simulação — nada é gravado"
    return f"Premissas vigentes em {data_por_extenso(hoje)}"


def montar(leitura, premissas, hoje):
    """Tudo o que a tela mostra, com texto, classe e travessão já decididos.

    Pura: recebe o que o banco trouxe, as premissas e a data. Nem relógio nem
    consulta daqui para baixo.
    """
    # Arredondado aqui, uma vez: é o número que o card "Anos até a IF na meta"
    # imprime, e é dele que a coluna Δ subtrai — ver `_linha`.
    anos_meta = _decimo(anos_ate_if(premissas.s, premissas.r, premissas.tsr))

    linhas = [
        _linha(l["receitas"], l["despesas"], premissas, anos_meta,
               str(l["ano"]), _marca_parcial(l, hoje))
        for l in leitura.por_ano
    ]

    total = leitura.total
    rodape = _linha(total["receitas"] if total else Decimal(0),
                    total["despesas"] if total else Decimal(0),
                    premissas, anos_meta, "Acumulado")

    simulacao, faltando, fora, sem_foto = _notas(premissas, leitura.foto)

    # Os quatro de cima primeiro: o alvo sai do primeiro deles, e é ele que a
    # segunda fileira divide e subtrai. Uma origem, dois usos.
    cards = _cards(leitura, rodape, premissas, anos_meta, hoje)

    return {
        "premissas": premissas,
        # O formulário desenha um campo por parâmetro a partir daqui: nome,
        # rótulo e ordem saem do mesmo lugar de que sai a leitura da URL.
        "parametros": PARAMETROS,
        "subtitulo": _subtitulo(premissas, hoje),
        "nota_simulacao": simulacao,
        "nota_faltando": faltando,
        "nota_fora": fora,
        "nota_sem_foto": sem_foto,
        "cards": cards,
        "cards_partida": _cards_partida(leitura, premissas, hoje,
                                        cards[0]["valor"]),
        "linhas": linhas,
        "rodape": rodape,
        "vazio": not linhas,
        "referencia": [{"taxa": _uma_casa(p["taxa"]) + "%",
                        "anos": _uma_casa(p["anos"])}
                       for p in curva(premissas.r, premissas.tsr,
                                      PASSO_REFERENCIA)],
        "grafico": para_grafico(curva(premissas.r, premissas.tsr), linhas,
                                premissas, anos_meta),
    }


# --------------------------------------------------------------------------
# 5. O que vai para o gráfico
# --------------------------------------------------------------------------

def _rotulo_ponto(quem, taxa, anos):
    """'2024: 57,7% → 14,7 anos'. O tooltip inteiro vem daqui, pronto."""
    return f"{quem}: {_uma_casa(taxa)}% → {_uma_casa(anos)} anos"


def _ponto(taxa, anos, rotulo):
    """O ÚNICO lugar em que `Decimal` vira `float` nesta tela — e só depois do
    arredondamento de exibição, para o que o gráfico desenha ser exatamente o
    que a tabela imprime."""
    return {"x": float(taxa.quantize(DECIMO, rounding=ROUND_HALF_UP)),
            "y": float(anos.quantize(DECIMO, rounding=ROUND_HALF_UP)),
            "rotulo": rotulo}


def _eixo(pontos, meta):
    """Os limites do eixo x: 5 a 95, abertos o quanto for preciso. Pura.

    A curva vive entre 5 % e 95 %, e é essa a janela do desenho. Mas um ano do
    acervo (ou uma meta simulada) pode cair fora dela, e ponto que existe e
    não é desenhado seria a tela escondendo um dado que a tabela mostra — por
    isso o eixo se abre até caber, em vez de recortar. Com o acervo de hoje
    (taxas de 17 % a 58 %) os limites são exatamente 5 e 95.
    """
    minimo, maximo = TAXA_MINIMA, TAXA_MAXIMA
    for taxa in [p["taxa"] for p in pontos] + ([meta["taxa"]] if meta else []):
        minimo = min(minimo, taxa.to_integral_value(rounding=ROUND_FLOOR))
        maximo = max(maximo, taxa.to_integral_value(rounding=ROUND_CEILING))
    return {"min": float(minimo), "max": float(maximo)}


def para_grafico(pontos_curva, linhas, premissas, anos_meta):
    """Os três conjuntos que o `independencia.js` desenha, ou None. Pura.

    O JavaScript não faz conta nem escreve texto: cada ponto chega com o
    rótulo do tooltip pronto, e os nomes das séries e os títulos dos eixos vêm
    junto. Sem `r` ou sem `TSR` não há curva, e aí não há gráfico — quem
    explica o que falta é a nota do topo.

    Os pontos dos anos saem das linhas JÁ COMPOSTAS, e não de um recálculo:
    conferir o gráfico contra a tabela é conferir o mesmo `Decimal`.
    """
    if not pontos_curva:
        return None

    dos_anos = [p for p in linhas
                if p["taxa_valor"] is not None and p["anos_valor"] is not None]

    meta = None
    if premissas.s is not None and anos_meta is not None:
        meta = {"taxa": premissas.s * CEM, "anos": anos_meta}

    return {
        "curva": {
            "nome": "Curva do modelo",
            "pontos": [_ponto(p["taxa"], p["anos"],
                              _rotulo_ponto("Poupando", p["taxa"], p["anos"]))
                       for p in pontos_curva],
        },
        "anos": {
            "nome": "Anos do acervo",
            "pontos": [_ponto(p["taxa_valor"], p["anos_valor"],
                              _rotulo_ponto(p["rotulo"], p["taxa_valor"],
                                            p["anos_valor"]))
                       for p in dos_anos],
        },
        "meta": ({"nome": "Meta",
                  "pontos": [_ponto(meta["taxa"], meta["anos"],
                                    _rotulo_ponto("Meta", meta["taxa"],
                                                  meta["anos"]))]}
                 if meta else None),
        "eixo": _eixo([{"taxa": p["taxa_valor"]} for p in dos_anos], meta),
        "titulo_x": "Taxa de poupança (%)",
        "titulo_y": "Anos até a IF",
    }


# --------------------------------------------------------------------------
# 6. A tela inteira
# --------------------------------------------------------------------------

def painel(args, hoje):
    """Da URL ao que o template mostra. Três consultas, nenhuma a mais."""
    premissas = resolver_premissas(args, vigentes(hoje))
    return montar(consultar(hoje), premissas, hoje)
