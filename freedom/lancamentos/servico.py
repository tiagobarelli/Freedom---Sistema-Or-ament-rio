"""Consultas e helpers da área de lançamentos.

Leitura sai sempre de `vw_despesas` (que já traz categoria e essencialidade
efetiva); INSERT, UPDATE e DELETE vão em `tb_despesas`.
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from freedom.db import query_all, query_one

ESSENCIAL = "Essencial"
NAO_ESSENCIAL = "Não Essencial"

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


# --------------------------------------------------------------------------
# Valor monetário
# --------------------------------------------------------------------------

class ValorInvalido(Exception):
    """Texto digitado que não vira um valor monetário aceitável."""


# Agrupamento de milhar bem formado: 1-3 dígitos e depois grupos de 3.
# Compilado por separador; nada de .format() aqui, que colidiria com as
# chaves de quantificador do próprio regex.
_AGRUPAMENTO = {
    ",": re.compile(r"\d{1,3}(,\d{3})+"),
    ".": re.compile(r"\d{1,3}(\.\d{3})+"),
}


def _partir(bruto):
    """Decide o que em `bruto` é milhar e o que é decimal.

    Devolve (parte_inteira, casas_decimais) já sem separadores. A regra:

      - `,` e `.` juntos: o separador mais à direita é o decimal, o outro é
        milhar (1.234,56 e 1,234.56 dão os dois 1234,56);
      - um separador só, uma vez só: 3 dígitos depois dele = milhar
        (1.234 e 1,234 = 1234,00); 1 ou 2 dígitos = decimal (1.5 = 1,50);
        nenhum dígito = separador solto no fim, aceito (10. = 10,00);
        mais de 3 dígitos = erro;
      - o mesmo separador repetido: todos são milhar (1.234.567).

    O caso de 1 ou 2 dígitos é o que importa no celular, onde o teclado
    numérico costuma oferecer só o ponto: 1.5 tem que virar 1,50, não 15,00.
    """
    tem_virgula, tem_ponto = "," in bruto, "." in bruto

    if tem_virgula and tem_ponto:
        decimal_sep = "," if bruto.rfind(",") > bruto.rfind(".") else "."
        milhar_sep = "." if decimal_sep == "," else ","
        if bruto.count(decimal_sep) > 1:
            raise ValorInvalido(
                "Valor inválido: há mais de um separador decimal."
            )
        inteiro, _, decimais = bruto.rpartition(decimal_sep)
        return inteiro.replace(milhar_sep, ""), decimais

    if not tem_virgula and not tem_ponto:
        return bruto, ""

    sep = "," if tem_virgula else "."

    if bruto.count(sep) > 1:
        # Repetido: só pode ser milhar, e o agrupamento tem que fechar.
        if not _AGRUPAMENTO[sep].fullmatch(bruto):
            raise ValorInvalido(
                "Valor inválido. Escreva como 1.234.567,89."
            )
        return bruto.replace(sep, ""), ""

    inteiro, _, depois = bruto.partition(sep)
    if len(depois) == 3:
        return inteiro + depois, ""      # 1.234 / 1,234 -> milhar
    if len(depois) <= 2:
        return inteiro, depois           # 1.5 / 10,99 / 10. -> decimal
    raise ValorInvalido("Use no máximo 2 casas decimais.")


def converter_valor(texto):
    """Converte o texto digitado em Decimal com 2 casas.

    Única função de conversão do sistema: lançamento e edição passam por aqui.
    Levanta ValorInvalido com mensagem pronta para virar erro de campo — nunca
    deixa estourar o CHECK (valor > 0) do banco.
    """
    if texto is None:
        raise ValorInvalido("Informe o valor.")

    bruto = str(texto).strip()
    for lixo in ("R$", " ", "\xa0", " "):  # inclui espaços finos de colagem
        bruto = bruto.replace(lixo, "")
    if not bruto:
        raise ValorInvalido("Informe o valor.")

    if not re.fullmatch(r"-?[\d.,]+", bruto):
        raise ValorInvalido("Valor inválido. Use apenas números, como 1234,56.")

    negativo = bruto.startswith("-")
    bruto = bruto.lstrip("-")
    if not bruto:
        raise ValorInvalido("Informe o valor.")

    inteiro, decimais = _partir(bruto)

    inteiro = inteiro or "0"
    if not inteiro.isdigit() or (decimais and not decimais.isdigit()):
        raise ValorInvalido("Valor inválido. Use apenas números, como 1234,56.")
    # Vale para todos os ramos de _partir: dinheiro não é arredondado em
    # silêncio, quem digitou 3 casas vê o erro.
    if len(decimais) > 2:
        raise ValorInvalido("Use no máximo 2 casas decimais.")

    try:
        valor = Decimal(f"{inteiro}.{decimais or '0'}")
    except InvalidOperation:
        raise ValorInvalido("Valor inválido.") from None

    if negativo:
        valor = -valor
    if valor <= 0:
        raise ValorInvalido("O valor deve ser maior que zero.")
    if valor >= Decimal("10000000000"):
        raise ValorInvalido("Valor alto demais.")

    return valor.quantize(Decimal("0.01"))


def formatar_valor(valor):
    """Decimal -> '1.234,56' (sem o prefixo R$, que fica no template)."""
    if valor is None:
        return ""
    return f"{Decimal(valor):,.2f}".replace(",", "\x00").replace(".", ",") \
                                   .replace("\x00", ".")


# --------------------------------------------------------------------------
# Opções dos selects
# --------------------------------------------------------------------------

def subcategorias_ativas():
    """Só subcategorias ativas de categorias ativas, ordenadas para o optgroup."""
    return query_all(
        """
        SELECT s.id, s.nome, s.essencialidade,
               c.id AS categoria_id, c.nome AS categoria_nome
          FROM tb_subcategorias s
          JOIN tb_categorias    c ON c.id = s.categoria_id
         WHERE s.ativo = TRUE AND c.ativo = TRUE
         ORDER BY c.nome, s.nome
        """
    )


def agrupar_por_categoria(linhas):
    """[(nome_categoria, [(id, nome), ...]), ...] preservando a ordem do SELECT."""
    grupos, atual, nome_atual = [], None, None
    for linha in linhas:
        if linha["categoria_nome"] != nome_atual:
            nome_atual = linha["categoria_nome"]
            atual = []
            grupos.append((nome_atual, atual))
        atual.append((linha["id"], linha["nome"]))
    return grupos


def contas_ativas():
    return query_all(
        "SELECT id, nome FROM tb_contas WHERE ativa = TRUE ORDER BY nome"
    )


def pessoas_ativas():
    return query_all(
        "SELECT id, nome FROM tb_pessoas WHERE ativo = TRUE ORDER BY nome"
    )


def subcategoria(subcategoria_id):
    """Subcategoria com a categoria, sem exigir que estejam ativas.

    Usada na edição e na rota de classificação: uma despesa antiga pode
    apontar para subcategoria que foi desativada depois.
    """
    if not subcategoria_id:
        return None
    return query_one(
        """
        SELECT s.id, s.nome, s.essencialidade, s.ativo,
               c.nome AS categoria_nome
          FROM tb_subcategorias s
          JOIN tb_categorias    c ON c.id = s.categoria_id
         WHERE s.id = %s
        """,
        (subcategoria_id,),
    )


# --------------------------------------------------------------------------
# Essencialidade efetiva
# --------------------------------------------------------------------------

def essencialidade_efetiva(override, sub):
    """COALESCE(despesa.essencialidade, subcategoria.essencialidade).

    Mesma regra da vw_despesas, repetida aqui porque o formulário precisa
    dela antes de existir linha no banco.
    """
    if override:
        return override
    if sub:
        return sub["essencialidade"]
    return None


# --------------------------------------------------------------------------
# Lista e totais
# --------------------------------------------------------------------------

# vw_despesas não traz nome de conta nem de pessoa (decisão registrada no
# schema); o JOIN é feito aqui.
_SELECT_LISTA = """
    SELECT v.id, v.data, v.ano_mes, v.descricao, v.valor,
           v.subcategoria, v.categoria, v.essencialidade, v.prioridade,
           v.integra_ipca, v.observacoes, v.criado_em, v.atualizado_em,
           v.conta_id, v.pessoa_id, v.usuario_id,
           ct.nome AS conta_nome,
           p.nome  AS pessoa_nome
      FROM vw_despesas v
      JOIN tb_contas  ct ON ct.id = v.conta_id
      JOIN tb_pessoas p  ON p.id  = v.pessoa_id
"""


def recentes(limite=15):
    """As mais recentes por criado_em. Sistema doméstico: mostra de todos."""
    return query_all(
        _SELECT_LISTA + " ORDER BY v.criado_em DESC, v.id DESC LIMIT %s",
        (limite,),
    )


def linha(despesa_id):
    return query_one(_SELECT_LISTA + " WHERE v.id = %s", (despesa_id,))


def despesa_para_edicao(despesa_id):
    """Lê de tb_despesas: a edição precisa do override cru, não do efetivo."""
    return query_one(
        """
        SELECT id, data, descricao, valor, subcategoria_id, conta_id,
               pessoa_id, usuario_id, essencialidade, prioridade,
               integra_ipca, observacoes
          FROM tb_despesas
         WHERE id = %s
        """,
        (despesa_id,),
    )


def total_do_mes(referencia):
    """Soma das despesas do mês da data informada, com o nome do mês."""
    ano_mes = referencia.year * 100 + referencia.month
    linha_total = query_one(
        "SELECT COALESCE(SUM(valor), 0) AS total, count(*) AS quantidade "
        "FROM vw_despesas WHERE ano_mes = %s",
        (ano_mes,),
    )
    return {
        "total": linha_total["total"],
        "quantidade": linha_total["quantidade"],
        "rotulo": f"{MESES[referencia.month - 1]} de {referencia.year}",
    }


def ultimo_lancamento_do_usuario(usuario_id):
    """Conta e pessoa do último lançamento do usuário, para pré-preencher."""
    return query_one(
        "SELECT conta_id, pessoa_id FROM tb_despesas "
        "WHERE usuario_id = %s ORDER BY criado_em DESC, id DESC LIMIT 1",
        (usuario_id,),
    )


# --------------------------------------------------------------------------
# Consulta com filtros
#
# O WHERE e montado como lista de condicoes + lista de parametros. Nenhum
# valor vindo do request entra em f-string de SQL: o unico trecho de SQL
# escolhido dinamicamente e a ordenacao, e vem de um dicionario fechado.
# --------------------------------------------------------------------------

POR_PAGINA = 50

# Whitelist de ordenacao. A chave vem do request; o valor, nunca.
ORDENS = {
    "data": "v.data DESC, v.id DESC",
    "valor": "v.valor DESC, v.id DESC",
}


def mes_valido(ano_mes):
    """AAAAMM -> (ano, mes) se fizer sentido como mes de calendario."""
    try:
        n = int(ano_mes)
    except (TypeError, ValueError):
        return None
    ano, mes = divmod(n, 100)
    if 1900 <= ano <= 2999 and 1 <= mes <= 12:
        return ano, mes
    return None


def mes_corrente():
    hoje = date.today()
    return hoje.year * 100 + hoje.month


def deslocar_mes(ano_mes, passos):
    """Mes anterior/seguinte em AAAAMM, sem depender de biblioteca de datas."""
    ano, mes = divmod(int(ano_mes), 100)
    total = (ano * 12 + (mes - 1)) + passos
    return (total // 12) * 100 + (total % 12) + 1


def rotulo_mes(ano_mes):
    ano, mes = divmod(int(ano_mes), 100)
    return f"{MESES[mes - 1]} de {ano}"


def _where(filtros):
    """Devolve (trecho_where, params) a partir dos filtros ja validados."""
    condicoes = ["v.ano_mes = %s"]
    params = [filtros["mes"]]

    if filtros["pessoa_id"]:
        condicoes.append("v.pessoa_id = %s")
        params.append(filtros["pessoa_id"])
    if filtros["categoria_id"]:
        condicoes.append("v.categoria_id = %s")
        params.append(filtros["categoria_id"])
    if filtros["conta_id"]:
        condicoes.append("v.conta_id = %s")
        params.append(filtros["conta_id"])
    if filtros["essencialidade"]:
        # Coluna efetiva da view (COALESCE ja aplicado), nunca a crua.
        condicoes.append("v.essencialidade = %s")
        params.append(filtros["essencialidade"])
    if filtros["q"]:
        # ILIKE sem unaccent: 'cafe' nao acha 'café'. Instalar a extensao
        # esta fora do escopo desta rodada.
        condicoes.append("v.descricao ILIKE '%%' || %s || '%%'")
        params.append(filtros["q"])

    return " WHERE " + " AND ".join(condicoes), params


def totais_do_filtro(filtros):
    """Uma linha com total, contagem e a divisao essencial x nao essencial.

    Agregacao no banco sobre o filtro inteiro: nunca somando as linhas da
    pagina em Python, que dariam so o total da pagina visivel.
    """
    where, params = _where(filtros)
    linha = query_one(
        "SELECT count(*) AS quantidade, "
        "       COALESCE(SUM(v.valor), 0) AS total, "
        "       COALESCE(SUM(v.valor) FILTER "
        "                (WHERE v.essencialidade = 'Essencial'), 0) AS essencial, "
        "       COALESCE(SUM(v.valor) FILTER "
        "                (WHERE v.essencialidade <> 'Essencial'), 0) "
        "           AS nao_essencial, "
        "       count(*) FILTER (WHERE v.essencialidade = 'Essencial') "
        "           AS qtd_essencial "
        "  FROM vw_despesas v" + where,
        params,
    )
    total = linha["total"] or 0
    linha["pct_essencial"] = (
        float(linha["essencial"]) * 100 / float(total) if total else 0.0
    )
    linha["pct_nao_essencial"] = (
        float(linha["nao_essencial"]) * 100 / float(total) if total else 0.0
    )
    return linha


def resumo_por_categoria(filtros):
    """Valor e percentual por categoria, do maior para o menor."""
    where, params = _where(filtros)
    linhas = query_all(
        "SELECT v.categoria, count(*) AS quantidade, SUM(v.valor) AS total "
        "  FROM vw_despesas v" + where +
        " GROUP BY v.categoria ORDER BY SUM(v.valor) DESC, v.categoria",
        params,
    )
    total_geral = sum(l["total"] for l in linhas) or 0
    for l in linhas:
        l["pct"] = float(l["total"]) * 100 / float(total_geral) if total_geral else 0.0
    return linhas


def pagina_de_despesas(filtros, pagina):
    """Uma pagina de resultados, ja com nome de conta e de pessoa."""
    where, params = _where(filtros)
    ordem = ORDENS[filtros["ordem"]]      # chave validada; valor da whitelist
    return query_all(
        _SELECT_LISTA + where + f" ORDER BY {ordem} LIMIT %s OFFSET %s",
        params + [POR_PAGINA, (pagina - 1) * POR_PAGINA],
    )


def meses_com_lancamento(incluir=None):
    """Meses que tem despesa, do mais recente para o mais antigo.

    `incluir` garante que o mes selecionado apareca no seletor mesmo sem
    lancamento nenhum (a navegacao por setas pode chegar num mes vazio).
    """
    meses = [l["ano_mes"] for l in query_all(
        "SELECT DISTINCT ano_mes FROM vw_despesas ORDER BY ano_mes DESC"
    )]
    for extra in filter(None, (incluir, mes_corrente())):
        if extra not in meses:
            meses.append(extra)
    return sorted(set(meses), reverse=True)


def opcoes_de_filtro():
    """Pessoas, categorias e contas: TODAS, inclusive inativas.

    O historico precisa continuar consultavel depois que algo e desativado.
    """
    return {
        "pessoas": query_all(
            "SELECT id, nome, ativo FROM tb_pessoas ORDER BY nome"),
        "categorias": query_all(
            "SELECT id, nome, ativo FROM tb_categorias ORDER BY nome"),
        "contas": query_all(
            "SELECT id, nome, ativa AS ativo FROM tb_contas ORDER BY nome"),
    }
