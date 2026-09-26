"""O que o plano, o balanceamento, a composição do ativo e a tela de
Patrimônio dividem.

A alocação da carteira tem dois níveis: a **classe** (Inflação, Ações Brasil,
Internacional), com alvo sobre o total, e a **subclasse** dentro dela, com
alvo sobre a classe. A subclasse é um "balde" que costuma levar o nome de um
ETF, e é ela que a composição de um ativo cita: um ativo simples é 100 % de
uma subclasse; a previdência se reparte entre subclasses de classes
diferentes.

Três coisas moram aqui, e não em nenhum dos três módulos que as usam:

- a **leitura de percentual** dos campos (a grade do plano e a da composição
  leem o mesmo texto do mesmo jeito);
- as **referências** (classes e subclasses com a situação de cada uma), que
  as duas grades e o balanceamento desenham;
- os **valores da última foto** por classe e subclasse — a foto de
  patrimônio vezes a composição. É a origem única do número que a tela de
  Patrimônio mostra no card de alocação e do "Atual" do balanceamento: dois
  lugares que mostram o mesmo número leem da mesma origem.

Percentual é sempre FRAÇÃO por dentro (0.37 é 37 %), como em
`tb_configuracoes`, e só vira texto no ponto exibido.
"""

from decimal import ROUND_HALF_UP, Decimal

from freedom.db import query_all
from freedom.util import (ValorInvalido, chave_alfabetica, converter_numero,
                          formatar_numero)

UM = Decimal(1)
CEM = Decimal(100)

# Prefixo de campo que as duas grades de percentual usam para a subclasse. A
# grade do plano tem também o da classe e o da caixa "Recebe aporte". Ficam
# aqui porque são contrato entre o serviço que lê e o template que escreve.
PREFIXO_CLASSE = "classe_"
PREFIXO_SUBCLASSE = "subclasse_"
PREFIXO_APORTE = "aporte_"
PREFIXO_COMPOSICAO = "comp_"


# --------------------------------------------------------------------------
# 1. Percentual (puras)
# --------------------------------------------------------------------------

def ler_percentual(texto):
    """Texto de um campo de percentual -> fração, ou None quando vazio. Pura.

    Vazio quer dizer "fora" (da composição, do plano) e nunca zero — a mesma
    distinção da foto de patrimônio. O resto é `converter_numero` com
    `percentual=True`, o de Parâmetros: `37`, `37%` e `37,0` são 0.37, e até
    quatro casas no percentual cabem nas seis da fração.

    Levanta `ValorInvalido` com texto pronto para o campo. Acima de 100 % é
    recusado aqui, antes do CHECK do banco: nenhum alvo nem parte de ativo
    passa do todo.
    """
    bruto = (texto or "").strip()
    if not bruto:
        return None
    valor = converter_numero(bruto, percentual=True)
    if valor > UM:
        raise ValorInvalido("Não pode passar de 100%.")
    return valor


def arredondar(valor, casas):
    """ROUND_HALF_UP em `casas` decimais. O corte do ponto exibido, e só dele.

    `formatar_numero` formataria um `Decimal` com o arredondamento do
    contexto, que é o do banqueiro (0,125 viraria 0,12). O projeto arredonda
    meio para cima, e por isso quem vai virar texto passa por aqui antes.
    """
    return Decimal(valor).quantize(Decimal(1).scaleb(-casas),
                                   rounding=ROUND_HALF_UP)


def centavos(valor):
    """Dinheiro no ponto exibido: duas casas, ROUND_HALF_UP."""
    return arredondar(valor, 2)


def texto_percentual(fracao, casas=2):
    """0.335 -> '33,50%'. Pura. `None` volta como None (quem chama põe o
    travessão, que é texto de tela e não desta função)."""
    if fracao is None:
        return None
    return formatar_numero(arredondar(fracao * CEM, casas), casas) + "%"


def soma_de_cem(valores):
    """True quando as frações somam exatamente 100 %. Pura.

    Exatamente: é `Decimal`, e as frações têm no máximo seis casas, então
    33,3333 + 33,3333 + 33,3334 fecham em 1 sem tolerância nenhuma — e
    99,5 % não fecha, que é o erro que a regra existe para pegar.
    """
    return sum(valores, Decimal(0)) == UM


# --------------------------------------------------------------------------
# 2. Referências
# --------------------------------------------------------------------------

_SQL_REFERENCIAS = """
    SELECT c.id    AS classe_id,
           c.nome  AS classe,
           c.ativo AS classe_ativa,
           s.id    AS subclasse_id,
           s.nome  AS subclasse,
           s.ativo AS subclasse_ativa
      FROM tb_alocacao_classes c
      LEFT JOIN tb_alocacao_subclasses s ON s.classe_id = c.id
"""


def referencias():
    """Todas as classes, cada uma com as suas subclasses, em ordem pt-BR.

    Uma consulta, e a árvore montada aqui: é só o formato, e não uma conta.
    Inativas vêm junto, marcadas — quem decide se elas aparecem é cada tela,
    pela regra do sistema (aparece se já está no plano ou na composição,
    nunca entra em linha nova).
    """
    classes = {}
    for l in query_all(_SQL_REFERENCIAS):
        classe = classes.setdefault(l["classe_id"], {
            "id": l["classe_id"], "nome": l["classe"],
            "ativo": l["classe_ativa"], "subclasses": [],
        })
        if l["subclasse_id"] is not None:
            classe["subclasses"].append({
                "id": l["subclasse_id"], "nome": l["subclasse"],
                "ativo": l["subclasse_ativa"], "classe_id": l["classe_id"],
            })
    arvore = sorted(classes.values(), key=lambda c: chave_alfabetica(c["nome"]))
    for classe in arvore:
        classe["subclasses"].sort(key=lambda s: chave_alfabetica(s["nome"]))
    return arvore


def rotulo_de_referencia(nome, ativo):
    """'VWRA' ou 'VWRA (inativa)'. Classe e subclasse são femininas as duas."""
    return nome if ativo else f"{nome} (inativa)"


# --------------------------------------------------------------------------
# 3. A última foto em classes e subclasses
# --------------------------------------------------------------------------

# A foto de patrimônio vezes a composição, numa varredura só.
#
# `partes` tem uma linha por PEDAÇO de ativo: o ativo com composição entra uma
# vez por subclasse, já multiplicado pela fração dela; o ativo sem composição
# entra inteiro, marcado como não classificado. As duas metades são
# disjuntas (`NOT EXISTS`), então nada conta duas vezes.
#
# `GROUPING SETS` responde as três perguntas na mesma passagem:
#
# - (classificado, classe, subclasse, ativo): o valor de cada subclasse e, do
#   lado não classificado, o de cada ativo sem composição;
# - (classificado, classe): o valor de cada classe — que é, por construção,
#   a soma das subclasses dela, como a regra da alocação define;
# - (classificado): o total investido (classificado) e o total do que ficou
#   de fora.
#
# `GROUPING(classe_id, subclasse_id, ativo_id)` diz o nível da linha: 0 no
# detalhe, 3 na classe, 7 no total.
#
# Todas as linhas da última foto entram, de ativo em carteira ou encerrado: é
# a mesma definição de patrimônio da tela de Patrimônio, onde a posição
# encerrada com valor lançado continua no total. A composição aplicada é a
# ATUAL — ela não tem vigência, por decisão do dono.
#
# O produto `valor × percentual` fica com oito casas e a soma não arredonda:
# o corte a centavos é do ponto exibido.
_SQL_VALORES = """
    WITH ultima AS (
        SELECT max(data) AS data FROM tb_patrimonio_snapshots
    ),
    partes AS (
        SELECT TRUE             AS classificado,
               c.id             AS classe_id,
               c.nome           AS classe,
               comp.subclasse_id,
               NULL::int        AS ativo_id,
               NULL::text       AS ativo,
               s.valor * comp.percentual AS valor
          FROM tb_patrimonio_snapshots s
          JOIN tb_alocacao_composicao comp ON comp.ativo_id = s.ativo_id
          JOIN tb_alocacao_subclasses sc   ON sc.id = comp.subclasse_id
          JOIN tb_alocacao_classes    c    ON c.id = sc.classe_id
         WHERE s.data = (SELECT data FROM ultima)
        UNION ALL
        SELECT FALSE, NULL, NULL, NULL, a.id, a.nome, s.valor
          FROM tb_patrimonio_snapshots s
          JOIN tb_ativos a ON a.id = s.ativo_id
         WHERE s.data = (SELECT data FROM ultima)
           AND NOT EXISTS (SELECT 1
                             FROM tb_alocacao_composicao comp
                            WHERE comp.ativo_id = s.ativo_id)
    )
    SELECT (SELECT data FROM ultima) AS data,
           classificado, classe_id, classe, subclasse_id, ativo_id, ativo,
           SUM(valor) AS valor,
           GROUPING(classe_id, subclasse_id, ativo_id) AS nivel
      FROM partes
     GROUP BY GROUPING SETS (
           (classificado, classe_id, classe, subclasse_id, ativo_id, ativo),
           (classificado, classe_id, classe),
           (classificado))
"""

_DETALHE, _CLASSE, _TOTAL = 0, 3, 7


def valores_da_foto():
    """A última foto em classes, subclasses e o que não se classifica.

    Devolve um dicionário, ou None quando não há foto nenhuma:

    - `data`: a data da última foto;
    - `subclasses` e `classes`: {id: valor}, sem arredondar;
    - `nomes_classes`: {id: nome}, para quem não carrega as referências (a
      tela de Patrimônio);
    - `total`: o total investido — só o classificado, que é o denominador de
      todo percentual do balanceamento;
    - `nao_classificados`: [{"nome", "valor"}], em ordem pt-BR, e
      `total_nao_classificado`.
    """
    linhas = query_all(_SQL_VALORES)
    if not linhas:
        return None

    foto = {"data": linhas[0]["data"], "subclasses": {}, "classes": {},
            "nomes_classes": {}, "total": Decimal(0),
            "nao_classificados": [], "total_nao_classificado": Decimal(0)}
    for l in linhas:
        if l["classificado"]:
            if l["nivel"] == _DETALHE:
                foto["subclasses"][l["subclasse_id"]] = l["valor"]
            elif l["nivel"] == _CLASSE:
                foto["classes"][l["classe_id"]] = l["valor"]
                foto["nomes_classes"][l["classe_id"]] = l["classe"]
            else:
                foto["total"] = l["valor"]
        elif l["nivel"] == _DETALHE:
            foto["nao_classificados"].append(
                {"nome": l["ativo"], "valor": l["valor"]})
        elif l["nivel"] == _TOTAL:
            foto["total_nao_classificado"] = l["valor"]
    foto["nao_classificados"].sort(key=lambda a: chave_alfabetica(a["nome"]))
    return foto
