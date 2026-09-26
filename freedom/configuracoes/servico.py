"""Catálogo de chaves, leitura e formatação dos parâmetros de configuração.

O banco guarda sempre o número final em `tb_configuracoes.valor`
(`NUMERIC(12,6)`): 4% é gravado como `0.040000`. O que aquele número
significa — percentual ou número puro — é conhecimento da aplicação e mora no
CATALOGO abaixo, não em coluna nova.

Regra de vigência, repetida em todas as consultas daqui: o valor de uma chave
numa data é o registro com o maior `vigente_desde` menor ou igual à data.
Vigência futura existe, aparece na tela e simplesmente ainda não vale.
"""

import re
from datetime import date
from itertools import groupby
from operator import itemgetter

from freedom.db import query_all, query_one
from freedom.util import converter_numero, formatar_numero

PERCENTUAL = "percentual"
NUMERO = "numero"

# Chaves conhecidas. Acrescentar uma aqui só muda rótulo, texto de ajuda e
# como o número é lido e exibido — nunca o schema.
# `recusa_zero` é a mensagem de erro de campo quando a chave não admite zero.
# A regra mora AQUI, e não num `if` do formulário, pelo mesmo motivo do
# formato: o que cada chave significa é conhecimento do catálogo, e o
# formulário só aplica o que ele diz. Chave sem a entrada aceita zero — é o
# caso de `R` (carteira sem juro real é cenário legítimo) e de toda chave
# livre, que nem passa pelo catálogo.
CATALOGO = {
    "TSR": {
        "rotulo": "Taxa segura de retirada (anual)",
        "descricao": "Quanto dá para retirar do patrimônio por ano sem consumi-lo.",
        "formato": PERCENTUAL,
        "recusa_zero": "A taxa segura de retirada não pode ser zero: o "
                       "patrimônio necessário seria infinito.",
    },
    "R": {
        "rotulo": "Retorno real anual esperado da carteira",
        "descricao": "Retorno anual já descontada a inflação.",
        "formato": PERCENTUAL,
    },
    "S": {
        "rotulo": "Meta de taxa de poupança",
        "descricao": "Quanto da receita se pretende poupar por mês.",
        "formato": PERCENTUAL,
        "recusa_zero": "A meta de poupança não pode ser zero: quem não poupa "
                       "não chega à independência.",
    },
    # Rodada 37. Desvio RELATIVO ao próprio alvo, e não em pontos
    # percentuais: 20 % num alvo de 5 % aceita de 4 % a 6 %, e num alvo de
    # 40 %, de 32 % a 48 %. Quem a lê é o balanceamento da Alocação, e sem
    # vigência a coluna de situação some — nunca um padrão inventado.
    "TOL": {
        "rotulo": "Tolerância da alocação",
        "descricao": "Quanto uma linha da alocação pode se afastar do próprio "
                     "alvo, em proporção dele, antes de ficar fora: 20% num "
                     "alvo de 5% aceita de 4% a 6%.",
        "formato": PERCENTUAL,
        "recusa_zero": "A tolerância não pode ser zero: qualquer centavo de "
                       "diferença deixaria a linha fora do alvo.",
    },
}


# --------------------------------------------------------------------------
# Chaves
# --------------------------------------------------------------------------

def normalizar_chave(texto):
    """Maiúsculas e sem espaços nas pontas. `tsr ` e `TSR` são a mesma chave."""
    return (texto or "").strip().upper()


def catalogo(chave):
    """A entrada do catálogo, ou None se a chave for livre."""
    return CATALOGO.get(normalizar_chave(chave))


def mensagem_de_zero(chave):
    """A mensagem de recusa do zero desta chave, ou None se ela o aceita.

    Quem decide é o CATALOGO; o formulário só pergunta. Chave livre não tem
    entrada e aceita zero, como sempre aceitou.
    """
    info = catalogo(chave)
    return info.get("recusa_zero") if info else None


def formato_da_chave(chave):
    """Percentual só para chave conhecida; chave livre é número puro.

    É o que evita a ambiguidade do `0,04`: numa chave do catálogo ele seria
    0,04% (quase zero) e quase certamente não é o que a pessoa quis dizer.
    """
    info = catalogo(chave)
    return info["formato"] if info else NUMERO


def chaves_existentes():
    """Chaves já usadas no banco, para o combobox sugerir."""
    return [l["chave"] for l in query_all(
        "SELECT DISTINCT chave FROM tb_configuracoes ORDER BY chave")]


def sugestoes_de_chave():
    """Catálogo + o que já existe no banco, sem repetir, em ordem."""
    return sorted(set(CATALOGO) | set(chaves_existentes()))


def slug(chave):
    """Chave -> pedaço de id de HTML (a chave é texto livre)."""
    return re.sub(r"[^A-Za-z0-9]+", "-", chave).strip("-").lower() or "chave"


# --------------------------------------------------------------------------
# Entrada e exibição do valor
# --------------------------------------------------------------------------

def converter_valor_da_chave(texto, chave):
    """Texto digitado -> Decimal a gravar, conforme o formato da chave.

    Levanta ValorInvalido (de util.py) com mensagem pronta para virar erro de
    campo.
    """
    return converter_numero(texto,
                            percentual=formato_da_chave(chave) == PERCENTUAL)


def _texto(valor, casas_max, casas_min):
    """Número pt-BR sem zeros à toa: 0.030000 vira '0,03', 4.5 vira '4,50'."""
    inteiro, _, decimais = formatar_numero(valor, casas_max).partition(",")
    decimais = decimais.rstrip("0").ljust(casas_min, "0")
    return f"{inteiro},{decimais}" if decimais else inteiro


def formatar(valor, formato):
    """Como o valor aparece na tela: '4,00%' ou '0,04'."""
    if valor is None:
        return ""
    if formato == PERCENTUAL:
        return _texto(valor * 100, 4, 2) + "%"
    return _texto(valor, 6, 2)


def texto_para_edicao(valor, formato):
    """Como o valor volta para o campo: na mesma unidade em que se digita.

    Percentual guardado como 0.045 volta como `4,5`, e não como `0,045`, senão
    salvar sem mexer no campo dividiria o valor por 100 outra vez.
    """
    if valor is None:
        return ""
    if formato == PERCENTUAL:
        return _texto(valor * 100, 4, 0)
    return _texto(valor, 6, 0)


# --------------------------------------------------------------------------
# Leitura
# --------------------------------------------------------------------------

_SELECT = """
    SELECT id, chave, valor, vigente_desde, observacao
      FROM tb_configuracoes
"""


def valor_vigente(chave, quando=None):
    """O valor de uma chave vigente numa data (o dashboard vai usar isto).

    Devolve a linha inteira, e não só o número, porque quem exibe costuma
    querer também desde quando aquele valor vale.
    """
    return query_one(
        _SELECT + " WHERE chave = %s AND vigente_desde <= %s"
                  " ORDER BY vigente_desde DESC LIMIT 1",
        (normalizar_chave(chave), quando or date.today()),
    )


def valores_vigentes(quando=None):
    """Todas as chaves vigentes numa data, numa consulta só.

    DISTINCT ON (chave) com ORDER BY chave, vigente_desde DESC devolve, para
    cada chave, a linha de maior vigente_desde dentro do filtro — que é
    exatamente a definição de valor vigente. Uma consulta por chave seria uma
    ida ao banco por parâmetro do dashboard.
    """
    return query_all(
        "SELECT DISTINCT ON (chave) id, chave, valor, vigente_desde, observacao"
        "  FROM tb_configuracoes"
        " WHERE vigente_desde <= %s"
        " ORDER BY chave, vigente_desde DESC",
        (quando or date.today(),),
    )


def vigencia(config_id):
    return query_one(_SELECT + " WHERE id = %s", (config_id,))


def secoes(quando=None):
    """A tela inteira: uma seção por chave, com o vigente e o histórico.

    Duas consultas, e não uma por chave: o histórico completo (a tabela é de
    dezenas de linhas, não de milhares) e os vigentes pelo DISTINCT ON.
    """
    hoje = quando or date.today()
    vigentes = {l["chave"]: l for l in valores_vigentes(hoje)}
    linhas = query_all(_SELECT + " ORDER BY chave, vigente_desde DESC, id DESC")

    montadas = []
    for chave, grupo in groupby(linhas, key=itemgetter("chave")):
        info = catalogo(chave)
        formato = formato_da_chave(chave)
        vigente = vigentes.get(chave)
        historico = []
        for linha in grupo:
            linha["texto"] = formatar(linha["valor"], formato)
            linha["futura"] = linha["vigente_desde"] > hoje
            linha["e_vigente"] = bool(vigente and linha["id"] == vigente["id"])
            historico.append(linha)
        montadas.append({
            "chave": chave,
            "slug": slug(chave),
            "rotulo": info["rotulo"] if info else None,
            "descricao": info["descricao"] if info else None,
            "formato": formato,
            "do_catalogo": info is not None,
            "vigente": vigente,
            "texto_vigente": formatar(vigente["valor"], formato) if vigente else None,
            "historico": historico,
        })
    return montadas
