"""Leituras, montagem e regras do orçamento mensal.

O orçamento é por **subcategoria**: orçar categoria pede um número que ninguém
sabe dizer ("quanto vou gastar em Lazer?"), enquanto a linha de subcategoria
tem histórico próprio de onde o número sai. A categoria aparece na tela como
soma das subcategorias dela, e não como registro.

Duas tabelas: `tb_orcamento_meses` guarda o que é do MÊS (receita planejada,
encerramento) e `tb_orcamentos`, uma linha por subcategoria. O mês existe antes
das linhas e sobrevive a elas — mês recém-criado ou esvaziado continua aberto.

**Nada de referência é gravado.** "Média 12m" e "Realizado no mês anterior" são
recalculados de `vw_despesas` a cada exibição: gravá-los criaria um segundo
número sobre os mesmos lançamentos, que envelheceria no instante em que alguém
editasse uma despesa do período.

O filtro é sempre por intervalo de `data`, nunca por `ano_mes` da view — a
coluna é derivada e comparar com ela custa um Seq Scan.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from freedom.db import executar, get_connection, query_all, query_one
from freedom.util import MESES, chave_alfabetica

ZERO = Decimal("0.00")
CENTAVO = Decimal("0.01")
MESES_DA_MEDIA = 12

# Quantos meses à frente a tela oferece para criar. Um ano cobre o
# planejamento de quem fecha o mês em dia e o de quem monta o ano inteiro de
# uma vez; mais que isso seria um select de rolar sem ninguém usar.
HORIZONTE = 12


class RegraDoOrcamento(Exception):
    """Operação recusada por regra de negócio, com mensagem pronta para a tela.

    Existe para a rota não precisar decidir o texto: quem conhece a regra é
    quem a aplica. Nunca vira 500 — a rota devolve 409 com a mensagem.
    """


# --------------------------------------------------------------------------
# Mês como data
# --------------------------------------------------------------------------

def primeiro_dia(ano, mes):
    return date(ano, mes, 1)


def somar_meses(ano_mes, passos):
    """Desloca um dia-1 em N meses, para frente ou para trás."""
    total = ano_mes.year * 12 + (ano_mes.month - 1) + passos
    return date(total // 12, total % 12 + 1, 1)


def mes_seguinte(ano_mes):
    return somar_meses(ano_mes, 1)


def mes_anterior(ano_mes):
    return somar_meses(ano_mes, -1)


def mes_corrente(hoje=None):
    """O dia 1 do mês de hoje. É o padrão da tela e o piso do que se cria."""
    hoje = hoje or date.today()
    return date(hoje.year, hoje.month, 1)


def nome_do_periodo(ano_mes):
    """date(2026, 9, 1) -> 'setembro de 2026'. Minúscula: vive em frase."""
    return f"{MESES[ano_mes.month - 1]} de {ano_mes.year}"


def texto_do_mes(ano_mes):
    """date -> 'AAAA-MM', a forma que viaja na URL das rotas de fragmento."""
    return f"{ano_mes.year:04d}-{ano_mes.month:02d}"


def mes_da_url(texto):
    """'2026-09' -> date(2026, 9, 1), ou None se não for um mês de calendário.

    Nada aqui pode gerar 500: quem chama trata o None como 404.
    """
    try:
        ano, mes = texto.split("-")
        return date(int(ano), int(mes), 1)
    except (AttributeError, ValueError):
        return None


def _intervalo(ano_mes):
    """Mês -> (dia 1, dia 1 do mês seguinte), para o filtro por `data`."""
    return ano_mes, mes_seguinte(ano_mes)


def _intervalo_da_media(ano_mes):
    """Os 12 meses fechados anteriores ao mês.

    Para setembro de 2026: de 1º de setembro de 2025 a 1º de setembro de 2026
    (exclusivo), ou seja, set/2025 a ago/2026. O próprio mês fica de fora — ele
    é o que se está planejando, e ainda não aconteceu.
    """
    return somar_meses(ano_mes, -MESES_DA_MEDIA), ano_mes


def _media(total):
    """Soma dos 12 meses -> provisão mensal, duas casas, ROUND_HALF_UP.

    Divide por 12 sempre, mesmo que a subcategoria tenha gasto em um mês só:
    o orçamento é provisão para o mês típico, não média dos meses em que houve
    gasto. IPVA uma vez por ano vira um doze avos por mês, que é exatamente o
    que se quer guardar.
    """
    return (Decimal(total) / MESES_DA_MEDIA).quantize(CENTAVO, ROUND_HALF_UP)


# --------------------------------------------------------------------------
# Leituras do orçamento
# --------------------------------------------------------------------------

def meses_com_orcamento():
    """Meses orçados, do mais recente para o mais antigo."""
    return [l["ano_mes"] for l in query_all(
        "SELECT ano_mes FROM tb_orcamento_meses ORDER BY ano_mes DESC")]


def mes_escolhido(ano, mes_texto, orcados, hoje=None):
    """Qual mês a tela abre, a partir do que veio na URL. Nunca gera erro.

    Ano ou mês ausente, inválido ou sem orçamento cai na escolha automática:
    o mês corrente se ele estiver orçado, senão o orçamento mais recente — que
    é onde o trabalho parou —, senão None, e a tela mostra o convite para
    criar o primeiro.
    """
    try:
        pedido = date(int(ano), int(mes_texto), 1)
    except (TypeError, ValueError):
        pedido = None
    if pedido in orcados:
        return pedido
    corrente = mes_corrente(hoje)
    if corrente in orcados:
        return corrente
    return orcados[0] if orcados else None


def mes(ano_mes):
    """O cabeçalho do mês, ou None se não houver orçamento nele."""
    return query_one(
        "SELECT ano_mes, receita_planejada, criado_em, encerrado_em, observacoes"
        "  FROM tb_orcamento_meses WHERE ano_mes = %s", (ano_mes,))


def existe_mes_posterior(ano_mes):
    return bool(query_one(
        "SELECT 1 AS ha FROM tb_orcamento_meses WHERE ano_mes > %s LIMIT 1",
        (ano_mes,)))


def linhas_do_mes(ano_mes):
    """As linhas orçadas, com categoria e subcategoria já resolvidas."""
    return query_all(
        "SELECT o.id, o.subcategoria_id, o.valor_planejado,"
        "       s.nome AS subcategoria, c.nome AS categoria"
        "  FROM tb_orcamentos    o"
        "  JOIN tb_subcategorias s ON s.id = o.subcategoria_id"
        "  JOIN tb_categorias    c ON c.id = s.categoria_id"
        " WHERE o.ano_mes = %s",
        (ano_mes,))


def linha(linha_id):
    """Uma linha com o mês a que pertence — é ele que diz se pode mudar."""
    return query_one(
        "SELECT o.id, o.ano_mes, o.subcategoria_id, o.valor_planejado,"
        "       s.nome AS subcategoria, c.nome AS categoria,"
        "       m.encerrado_em"
        "  FROM tb_orcamentos       o"
        "  JOIN tb_subcategorias    s ON s.id = o.subcategoria_id"
        "  JOIN tb_categorias       c ON c.id = s.categoria_id"
        "  JOIN tb_orcamento_meses  m ON m.ano_mes = o.ano_mes"
        " WHERE o.id = %s",
        (linha_id,))


def subcategorias_disponiveis(ano_mes):
    """Subcategorias ativas que ainda não têm linha no mês.

    Categoria inativa não entra: a subcategoria dela não aparece em formulário
    nenhum, e orçar o que não se pode lançar não faria sentido.
    """
    return query_all(
        "SELECT s.id, s.nome, c.nome AS categoria"
        "  FROM tb_subcategorias s"
        "  JOIN tb_categorias    c ON c.id = s.categoria_id"
        " WHERE s.ativo = TRUE AND c.ativo = TRUE"
        "   AND NOT EXISTS (SELECT 1 FROM tb_orcamentos o"
        "                    WHERE o.subcategoria_id = s.id AND o.ano_mes = %s)"
        " ORDER BY c.nome, s.nome",
        (ano_mes,))


# --------------------------------------------------------------------------
# Referências calculadas de vw_despesas / vw_receitas
# --------------------------------------------------------------------------

def despesa_por_subcategoria(inicio, fim):
    """{subcategoria_id: total} no intervalo. Base da média e do realizado."""
    return {l["subcategoria_id"]: l["total"] for l in query_all(
        "SELECT v.subcategoria_id, SUM(v.valor) AS total"
        "  FROM vw_despesas v"
        " WHERE v.data >= %s AND v.data < %s"
        " GROUP BY v.subcategoria_id",
        (inicio, fim))}


def receita_do_intervalo(inicio, fim):
    return query_one(
        "SELECT COALESCE(SUM(v.valor), 0) AS total"
        "  FROM vw_receitas v"
        " WHERE v.data >= %s AND v.data < %s",
        (inicio, fim))["total"]


def medias_de_12_meses(ano_mes):
    """{subcategoria_id: provisão mensal} dos 12 meses fechados anteriores."""
    inicio, fim = _intervalo_da_media(ano_mes)
    return {sub: _media(total)
            for sub, total in despesa_por_subcategoria(inicio, fim).items()}


def realizado_do_mes_anterior(ano_mes):
    """{subcategoria_id: total} gasto no mês imediatamente anterior."""
    return despesa_por_subcategoria(*_intervalo(mes_anterior(ano_mes)))


def receita_media_de_12_meses(ano_mes):
    return _media(receita_do_intervalo(*_intervalo_da_media(ano_mes)))


# --------------------------------------------------------------------------
# Criação do mês
# --------------------------------------------------------------------------

def _sugestao_pelo_historico(ano_mes):
    """(linhas, receita) a partir dos 12 meses fechados anteriores.

    Só subcategoria ATIVA e com despesa no período entra: sugerir zero para as
    outras encheria a tela de linhas que a pessoa teria de apagar uma a uma.
    """
    medias = medias_de_12_meses(ano_mes)
    ativas = query_all(
        "SELECT s.id FROM tb_subcategorias s"
        "  JOIN tb_categorias c ON c.id = s.categoria_id"
        " WHERE s.ativo = TRUE AND c.ativo = TRUE")
    linhas = [(s["id"], medias[s["id"]]) for s in ativas
              if medias.get(s["id"], ZERO) > 0]
    return linhas, receita_media_de_12_meses(ano_mes)


def _copia_do_mes_anterior(ano_mes):
    """(linhas, receita) copiadas do mês imediatamente anterior, ou None.

    Copiar é o caminho normal de quem já orça: o mês que vem parece com o
    passado, e o que mudou a pessoa ajusta na tela. Só o mês IMEDIATAMENTE
    anterior serve — pular meses traria um plano de antes de tudo que
    aconteceu no meio.
    """
    anterior = mes_anterior(ano_mes)
    cabecalho = mes(anterior)
    if cabecalho is None:
        return None
    linhas = [(l["subcategoria_id"], l["valor_planejado"])
              for l in linhas_do_mes(anterior)]
    return linhas, cabecalho["receita_planejada"]


def pode_criar(ano_mes, hoje=None):
    """Um mês é criável se ainda não tem orçamento e não ficou para trás.

    "Não ficou para trás" tem duas saídas: ou é o mês corrente (ou futuro), ou
    é o mês seguinte a um que já tem orçamento — que é o passo natural depois
    de encerrar. Sem a segunda, encerrar um mês passado deixaria a sequência
    sem como continuar.
    """
    if mes(ano_mes) is not None:
        return False
    return (ano_mes >= mes_corrente(hoje)
            or mes(mes_anterior(ano_mes)) is not None)


def meses_criaveis(hoje=None):
    """O mês corrente e os doze seguintes que ainda não têm orçamento."""
    corrente = mes_corrente(hoje)
    candidatos = [somar_meses(corrente, n) for n in range(HORIZONTE + 1)]
    orcados = set(meses_com_orcamento())
    return [m for m in candidatos if m not in orcados]


def criar(ano_mes, hoje=None):
    """Abre o mês e grava as linhas sugeridas, tudo numa transação.

    Ou nasce o mês inteiro, com as linhas, ou não nasce nada: um cabeçalho sem
    linhas por falha no meio seria um orçamento vazio que ninguém pediu.
    """
    if mes(ano_mes) is not None:
        raise RegraDoOrcamento(
            f"{nome_do_periodo(ano_mes).capitalize()} já tem orçamento.")
    if not pode_criar(ano_mes, hoje):
        raise RegraDoOrcamento(
            "Só dá para criar o orçamento do mês corrente, de um mês futuro ou "
            "do mês seguinte a um que já esteja orçado.")

    copiado = _copia_do_mes_anterior(ano_mes)
    linhas, receita = copiado if copiado else _sugestao_pelo_historico(ano_mes)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tb_orcamento_meses (ano_mes, receita_planejada)"
            " VALUES (%s, %s)", (ano_mes, receita))
        for subcategoria_id, valor in linhas:
            cur.execute(
                "INSERT INTO tb_orcamentos (subcategoria_id, ano_mes, valor_planejado)"
                " VALUES (%s, %s, %s)", (subcategoria_id, ano_mes, valor))
    return {"origem": "cópia" if copiado else "histórico", "linhas": len(linhas)}


# --------------------------------------------------------------------------
# Escritas do mês aberto
#
# Toda escrita passa por `_exigir_aberto`: é a regra que o banco não impõe.
# --------------------------------------------------------------------------

def _exigir_aberto(cabecalho):
    if cabecalho is None:
        raise RegraDoOrcamento("Este mês não tem orçamento.")
    if cabecalho["encerrado_em"] is not None:
        raise RegraDoOrcamento(
            "Mês encerrado não aceita alteração. Reabra antes de editar.")


def gravar_valor(linha_id, valor):
    registro = linha(linha_id)
    _exigir_aberto(registro)
    executar("UPDATE tb_orcamentos SET valor_planejado = %s WHERE id = %s",
             (valor, linha_id))
    return registro["ano_mes"]


def excluir_linha(linha_id):
    registro = linha(linha_id)
    _exigir_aberto(registro)
    executar("DELETE FROM tb_orcamentos WHERE id = %s", (linha_id,))
    return registro["ano_mes"]


def acrescentar_linha(ano_mes, subcategoria_id, valor):
    _exigir_aberto(mes(ano_mes))
    executar(
        "INSERT INTO tb_orcamentos (subcategoria_id, ano_mes, valor_planejado)"
        " VALUES (%s, %s, %s)", (subcategoria_id, ano_mes, valor))


def gravar_receita(ano_mes, valor):
    _exigir_aberto(mes(ano_mes))
    executar("UPDATE tb_orcamento_meses SET receita_planejada = %s"
             " WHERE ano_mes = %s", (valor, ano_mes))


def encerrar(ano_mes):
    cabecalho = mes(ano_mes)
    _exigir_aberto(cabecalho)
    executar("UPDATE tb_orcamento_meses SET encerrado_em = now()"
             " WHERE ano_mes = %s", (ano_mes,))


def reabrir(ano_mes):
    cabecalho = mes(ano_mes)
    if cabecalho is None:
        raise RegraDoOrcamento("Este mês não tem orçamento.")
    if cabecalho["encerrado_em"] is None:
        raise RegraDoOrcamento("Este mês já está aberto.")
    if existe_mes_posterior(ano_mes):
        raise RegraDoOrcamento(
            "Só o último mês orçado pode ser reaberto: os meses seguintes "
            "foram copiados deste e passariam a descender de números que "
            "mudaram depois.")
    executar("UPDATE tb_orcamento_meses SET encerrado_em = NULL"
             " WHERE ano_mes = %s", (ano_mes,))


def excluir_mes(ano_mes):
    """Apaga as linhas e o mês, nessa ordem, numa transação.

    A FK é ON DELETE RESTRICT de propósito: apagar o mês com linhas dentro tem
    de ser um ato deliberado de quem escreveu isto, não um efeito colateral em
    cascata de um clique.
    """
    _exigir_aberto(mes(ano_mes))
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tb_orcamentos WHERE ano_mes = %s", (ano_mes,))
        cur.execute("DELETE FROM tb_orcamento_meses WHERE ano_mes = %s", (ano_mes,))


# --------------------------------------------------------------------------
# Composição da tela
# --------------------------------------------------------------------------

def _fracao(parte, total):
    """Percentual, ou None quando não há denominador (a tela mostra '—')."""
    return parte / total * 100 if total else None


def painel_do_mes(ano_mes):
    """Tudo que a tela do mês precisa, em quatro consultas.

    As somas são feitas aqui sobre um conjunto pequeno e completo — as linhas
    do mês, que o SQL já trouxe inteiras — e em `Decimal`. Total da categoria e
    rodapé leem da MESMA lista, então "a soma dos subtotais dá o total" é
    estrutural, não coincidência.
    """
    cabecalho = mes(ano_mes)
    if cabecalho is None:
        return None

    medias = medias_de_12_meses(ano_mes)
    anterior = realizado_do_mes_anterior(ano_mes)

    por_categoria = {}
    for l in linhas_do_mes(ano_mes):
        item = dict(
            l,
            media=medias.get(l["subcategoria_id"], ZERO),
            realizado=anterior.get(l["subcategoria_id"], ZERO),
        )
        por_categoria.setdefault(l["categoria"], []).append(item)

    grupos = []
    for categoria in sorted(por_categoria, key=chave_alfabetica):
        itens = sorted(por_categoria[categoria],
                       key=lambda i: chave_alfabetica(i["subcategoria"]))
        grupos.append({
            "categoria": categoria,
            "linhas": itens,
            "planejado": sum((i["valor_planejado"] for i in itens), ZERO),
            "media": sum((i["media"] for i in itens), ZERO),
            "realizado": sum((i["realizado"] for i in itens), ZERO),
        })

    planejado = sum((g["planejado"] for g in grupos), ZERO)
    receita = cabecalho["receita_planejada"]
    poupanca = receita - planejado

    return {
        "ano_mes": ano_mes,
        "periodo": nome_do_periodo(ano_mes),
        "aberto": cabecalho["encerrado_em"] is None,
        "encerrado_em": cabecalho["encerrado_em"],
        "receita": receita,
        "grupos": grupos,
        "quantidade": sum(len(g["linhas"]) for g in grupos),
        "total": {
            "planejado": planejado,
            "media": sum((g["media"] for g in grupos), ZERO),
            "realizado": sum((g["realizado"] for g in grupos), ZERO),
            "poupanca": poupanca,
            "taxa": _fracao(poupanca, receita),
        },
        "disponiveis": subcategorias_disponiveis(ano_mes),
        "pode_reabrir": not existe_mes_posterior(ano_mes),
        # Textos prontos para o template: quem sabe escrever "2026-09" na URL e
        # "outubro de 2026" na frase é o servidor, como em toda tela daqui.
        "mes_url": texto_do_mes(ano_mes),
        "seguinte_url": texto_do_mes(mes_seguinte(ano_mes)),
        "seguinte_periodo": nome_do_periodo(mes_seguinte(ano_mes)),
        "seguinte_criavel": pode_criar(mes_seguinte(ano_mes)),
    }
