"""A composição de um ativo: de que subclasses ele é feito.

Um ativo simples é 100 % de uma subclasse. A previdência se reparte: 40 %
VWRA (na classe Internacional) e 60 % B5P211 (na Inflação). É a composição
que liga a foto de patrimônio — que tem um valor por ATIVO — à alocação, que
fala de classes e subclasses.

**Sem vigência, por decisão do dono**: a composição descreve o produto, e
mudá-la muda a leitura de fotos antigas. **Ativo sem composição é
permitido**: é o caso do ativo agregado que carrega a série de fotos desde
2013, e ele aparece como "Não classificado" onde a alocação é lida.

A grade mora no formulário do ativo e grava junto com ele, numa transação.
Aceita exatamente duas formas: soma 100 %, ou tudo vazio. Qualquer outra soma
é recusada com texto e nada é gravado — nem o nome do ativo.
"""

from decimal import Decimal

from freedom.alocacao.servico import (PREFIXO_COMPOSICAO, ler_percentual,
                                      rotulo_de_referencia, soma_de_cem,
                                      texto_percentual)
from freedom.configuracoes.servico import PERCENTUAL, texto_para_edicao
from freedom.db import get_connection, query_all
from freedom.util import ValorInvalido

SEM_COMPOSICAO = "Sem composição"


def do_ativo(ativo_id):
    """{subclasse_id: fração} de um ativo. Vazio para ativo novo."""
    if ativo_id is None:
        return {}
    return {l["subclasse_id"]: l["percentual"] for l in query_all(
        "SELECT subclasse_id, percentual FROM tb_alocacao_composicao"
        " WHERE ativo_id = %s", (ativo_id,))}


def grupos_da_grade(arvore, atual):
    """Que subclasses a grade desenha, agrupadas por classe. Pura.

    Todas as ativas (de classe ativa) e, pela regra da referência inativa, as
    inativas que já estão na composição — marcadas, editáveis, e nunca
    oferecidas a quem ainda não as tem. Classe sem subclasse a mostrar não
    aparece.
    """
    grupos = []
    for classe in arvore:
        subs = [s for s in classe["subclasses"]
                if s["id"] in atual or (s["ativo"] and classe["ativo"])]
        if subs:
            grupos.append({"classe": classe, "subclasses": subs})
    return grupos


def ler(campos, grupos):
    """O corpo do POST -> (valores, erros, digitado). Pura.

    Só lê as subclasses que a grade desenhou: campo de subclasse inativa
    forjado não tem onde encaixar. Zero é recusado com texto, e não tratado
    como vazio em silêncio — na composição quem não participa não tem linha
    (o banco exige > 0), e a mensagem diz o que fazer.
    """
    valores, erros, digitado = {}, {}, {}
    for grupo in grupos:
        for sub in grupo["subclasses"]:
            texto = (campos.get(f"{PREFIXO_COMPOSICAO}{sub['id']}") or "").strip()
            digitado[sub["id"]] = texto
            try:
                valor = ler_percentual(texto)
            except ValorInvalido as exc:
                erros[sub["id"]] = str(exc)
                continue
            if valor is None:
                continue
            if valor == 0:
                erros[sub["id"]] = "Zero não participa: deixe o campo vazio."
            else:
                valores[sub["id"]] = valor
    return valores, erros, digitado


def validar(valores):
    """A recusa da soma, ou None. Pura. Tudo vazio passa; 100 % passa."""
    if not valores or soma_de_cem(valores.values()):
        return None
    soma = texto_percentual(sum(valores.values(), Decimal(0)))
    return (f"A composição soma {soma}; precisa somar 100% ou ficar "
            "toda vazia.")


def montar(grupos, atual, digitado=None, erros=None):
    """As linhas da grade, com o texto de cada campo pronto. Pura.

    Num GET o campo mostra a fração gravada na unidade em que se digita
    (`40`, e não `0,4`); depois de uma recusa, o que foi digitado.
    """
    erros = erros or {}
    montados = []
    for grupo in grupos:
        classe = grupo["classe"]
        montados.append({
            "rotulo": rotulo_de_referencia(classe["nome"], classe["ativo"]),
            "subclasses": [{
                "id": s["id"],
                "rotulo": rotulo_de_referencia(s["nome"], s["ativo"]),
                "campo": (digitado.get(s["id"], "") if digitado is not None
                          else (texto_para_edicao(atual[s["id"]], PERCENTUAL)
                                if s["id"] in atual else "")),
                "erro": erros.get(s["id"]),
            } for s in grupo["subclasses"]],
        })
    return montados


def gravar(ativo_id, nome, observacao, valores):
    """Grava o ativo e a composição dele numa transação. Devolve o id.

    `ativo_id` None cria; senão atualiza. A composição é refeita inteira —
    apaga as linhas do ativo e insere as da grade —, porque nada aponta para
    `tb_alocacao_composicao` e o resultado é, por definição, o que a grade
    diz. Um nome repetido estoura o UNIQUE de `tb_ativos` antes de a
    composição ser tocada, e a transação inteira volta: quem traduz o erro é
    a rota.
    """
    with get_connection() as conn, conn.cursor() as cur:
        if ativo_id is None:
            cur.execute("INSERT INTO tb_ativos (nome, observacao)"
                        " VALUES (%s, %s) RETURNING id", (nome, observacao))
            ativo_id = cur.fetchone()["id"]
        else:
            cur.execute("UPDATE tb_ativos SET nome = %s, observacao = %s"
                        " WHERE id = %s", (nome, observacao, ativo_id))
        cur.execute("DELETE FROM tb_alocacao_composicao WHERE ativo_id = %s",
                    (ativo_id,))
        if valores:
            cur.execute(
                "INSERT INTO tb_alocacao_composicao"
                "       (ativo_id, subclasse_id, percentual)"
                " SELECT %s, subclasse_id, percentual"
                "   FROM unnest(%s::int[], %s::numeric[])"
                "     AS t(subclasse_id, percentual)",
                (ativo_id, list(valores), list(valores.values())))
    return ativo_id


def resumo(nomes, percentuais):
    """'VWRA' / 'VWRA 40% · B5P211 60%' / 'Sem composição'. Pura.

    O que a lista de ativos mostra no lugar da antiga coluna de classe. Um
    ativo inteiro numa subclasse dispensa o "100%"; repartido, cada pedaço
    diz quanto é. Os pedaços chegam na ordem da consulta (do maior para o
    menor).
    """
    if not nomes:
        return SEM_COMPOSICAO
    if len(nomes) == 1:
        return nomes[0]
    return " · ".join(
        f"{nome} {_percentual_curto(pct)}" for nome, pct in zip(nomes, percentuais))


def _percentual_curto(fracao):
    """0.4 -> '40%', 0.335 -> '33,5%': sem zeros à toa, como se digitou."""
    return texto_para_edicao(fracao, PERCENTUAL) + "%"

