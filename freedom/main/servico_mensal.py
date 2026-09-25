"""Leituras e composição da Visão Mensal.

A tela é um mês só: seis cards, duas tabelas de participação (por categoria e
por pessoa) e a matriz que cruza as duas. São **três** consultas:

1. despesas do mês — total, essencial e não essencial, para os cards;
2. receitas do mês — total, para os cards;
3. despesas agrupadas por (categoria, pessoa) — de onde saem as três tabelas.

A terceira é uma só de propósito. As três tabelas são cortes do mesmo cubo:
somar por categoria dá a tabela 1, somar por pessoa dá a tabela 2, e a matriz
é o cubo inteiro. Três consultas dariam três totais que precisariam coincidir
por sorte; com uma, coincidem por construção. O conjunto é pequeno e completo
(categorias × pessoas com despesa no mês), a mesma exceção que a Visão Anual
já abre para as doze linhas mensais — e a composição é toda em `Decimal`.

O filtro é sempre por intervalo de `data` (`>= dia 1` e `< dia 1 do mês
seguinte`), nunca por `ano_mes`: a coluna é derivada da view e comparar com
ela obriga o Postgres a calcular a expressão linha a linha. Com o intervalo,
`ix_despesas_data` e `ix_receitas_data` são usados.

`vw_despesas` traz `pessoa_id`, mas não o nome da pessoa (decisão registrada
no documento do banco: FK sem JOIN de nome, que a aplicação faz quando
precisa). Daí o único JOIN desta tela, com `tb_pessoas`. Ele não pode perder
linha nenhuma — a FK é NOT NULL —, e é isso que mantém o total da matriz
idêntico ao card Despesas.
"""

from datetime import date

from freedom.db import query_all, query_one
from freedom.main.servico import VALOR_NEGATIVO, ZERO, card, percentual
from freedom.util import chave_alfabetica, fracao

# Ordem das categorias na tabela 1 e nas linhas da matriz. A tabela por pessoa
# não entra: ela é sempre por total, porque são poucas linhas e a pergunta ali
# é "quem gastou mais", não "onde está a Fulana na lista".
ORDEM_TOTAL = "total"
ORDEM_NOME = "nome"
ORDENS = (ORDEM_TOTAL, ORDEM_NOME)


# --------------------------------------------------------------------------
# Mês da tela
# --------------------------------------------------------------------------

def mes_valido(texto, hoje=None):
    """Texto da query string -> mês a exibir. Nada aqui pode gerar 500.

    Ausente, não numérico ou fora de 1..12 cai no mês corrente em silêncio —
    mesma regra de `servico.ano_valido`, que cuida do ano.
    """
    corrente = (hoje or date.today()).month
    try:
        mes = int(texto)
    except (TypeError, ValueError):
        return corrente
    return mes if 1 <= mes <= 12 else corrente


def ordem_valida(texto):
    """Texto da query string -> ordem das categorias. Inválida cai em `total`.

    O padrão é o maior gasto: quem abre a tela quer ver primeiro para onde o
    dinheiro foi, não a letra A.
    """
    return texto if texto in ORDENS else ORDEM_TOTAL


def intervalo_do_mes(ano, mes):
    """(ano, mês) -> (dia 1 do mês, dia 1 do mês seguinte).

    Dezembro vira 1º de janeiro do ano seguinte; sem esse caso o intervalo de
    dezembro ficaria vazio.
    """
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return inicio, fim


# --------------------------------------------------------------------------
# Consultas
# --------------------------------------------------------------------------

def despesas_do_mes(inicio, fim):
    """Total, essencial e não essencial do mês. Uma linha, sempre.

    Sem GROUP BY o agregado devolve linha mesmo em mês vazio, e o COALESCE
    troca o NULL do SUM por zero: mês sem despesa chega aqui como R$ 0,00, não
    como None. A essencialidade é a efetiva da view, e `<> 'Essencial'` é o
    outro lado do CHECK — as duas parcelas sempre fecham no total.
    """
    return query_one(
        "SELECT COALESCE(SUM(v.valor), 0) AS total,"
        "       COALESCE(SUM(v.valor) FILTER"
        "                (WHERE v.essencialidade = 'Essencial'), 0) AS essencial,"
        "       COALESCE(SUM(v.valor) FILTER"
        "                (WHERE v.essencialidade <> 'Essencial'), 0)"
        "           AS nao_essencial"
        "  FROM vw_despesas v"
        " WHERE v.data >= %s AND v.data < %s",
        (inicio, fim),
    )


def receitas_do_mes(inicio, fim):
    """Total de receitas do mês, zero quando não houve nenhuma."""
    return query_one(
        "SELECT COALESCE(SUM(v.valor), 0) AS total"
        "  FROM vw_receitas v"
        " WHERE v.data >= %s AND v.data < %s",
        (inicio, fim),
    )["total"]


def despesas_por_categoria_e_pessoa(inicio, fim):
    """Despesas do mês somadas por (categoria, pessoa). Uma linha por par.

    O `categoria_id` vem junto porque a linha da tabela precisa dele para
    montar o link do detalhe; agrupar por ele não muda nada, já que o nome é
    UNIQUE em `tb_categorias`.

    É a consulta que sustenta as três tabelas. O par sem despesa simplesmente
    não vem — é o GROUP BY sobre o intervalo que garante que só apareça
    categoria e pessoa com movimento no mês, sem filtro extra. A ordem daqui
    não é a da tela (quem ordena é a composição, conforme o seletor), mas
    fixá-la deixa o resultado estável entre execuções.
    """
    return query_all(
        "SELECT v.categoria_id, v.categoria, p.nome AS pessoa,"
        "       SUM(v.valor) AS total"
        "  FROM vw_despesas v"
        "  JOIN tb_pessoas  p ON p.id = v.pessoa_id"
        " WHERE v.data >= %s AND v.data < %s"
        " GROUP BY v.categoria_id, v.categoria, p.nome"
        " ORDER BY v.categoria, p.nome",
        (inicio, fim),
    )


# --------------------------------------------------------------------------
# Composição: do cubo (categoria, pessoa) para as três tabelas
# --------------------------------------------------------------------------

def _somar_por(linhas, coluna):
    """{nome: total} somando as linhas do cubo por uma das duas dimensões."""
    totais = {}
    for linha in linhas:
        nome = linha[coluna]
        totais[nome] = totais.get(nome, ZERO) + linha["total"]
    return totais


def _ordenar(totais, ordem):
    """Nomes de `totais` na ordem pedida.

    Em `total`, o maior primeiro, com o nome desempatando: dois totais iguais
    não podem trocar de lugar conforme a ordem física das linhas do banco.
    """
    if ordem == ORDEM_NOME:
        return sorted(totais, key=chave_alfabetica)
    return sorted(totais, key=lambda nome: (-totais[nome], chave_alfabetica(nome)))


def _tabela_participacao(nomes, totais, coluna, total_geral, ids=None):
    """Tabela de duas colunas de número: total e % do total, mais o rodapé.

    `coluna` é o nome da chave da primeira coluna ("categoria" ou "pessoa"),
    porque as duas tabelas são a mesma tabela sobre dimensões diferentes.

    `ids` só chega na de categoria: é o que a linha expansível usa para pedir
    o detalhe. A de pessoa não expande (rodada 13), e sem os ids o template
    não tem como oferecer o que não existe.
    """
    return {
        "linhas": [
            {coluna: nome,
             "id": ids.get(nome) if ids else None,
             "total": totais[nome],
             "pct": fracao(totais[nome], total_geral)}
            for nome in nomes
        ],
        "total": {"total": total_geral,
                  "pct": fracao(total_geral, total_geral)},
    }


def _matriz(categorias, pessoas, linhas, por_categoria, por_pessoa, total_geral):
    """Pessoa × Categoria: as mesmas linhas e colunas das duas tabelas.

    A ordem das categorias e a das pessoas vêm prontas de fora, e são as
    mesmas das tabelas — conferir a matriz contra elas é ler duas listas na
    mesma ordem, não procurar.

    Célula sem despesa vale ZERO, e não None: aqui o zero é informação (essa
    pessoa não gastou nessa categoria neste mês), diferente do travessão da
    Visão Anual, que quer dizer "não há conta a fazer". Quem atenua a cor é o
    template.
    """
    celulas = {(l["categoria"], l["pessoa"]): l["total"] for l in linhas}
    return {
        "pessoas": pessoas,
        "linhas": [
            {"categoria": categoria,
             "celulas": [celulas.get((categoria, pessoa), ZERO)
                         for pessoa in pessoas],
             "total": por_categoria[categoria]}
            for categoria in categorias
        ],
        # O rodapé é a tabela por pessoa deitada, lida do mesmo dicionário: os
        # dois números não têm como divergir.
        "rodape": {"celulas": [por_pessoa[pessoa] for pessoa in pessoas],
                   "total": total_geral},
    }


# --------------------------------------------------------------------------
# Composição dos cards
# --------------------------------------------------------------------------

def _cards(receitas, despesas):
    """Os seis cards do mês, na ordem em que aparecem na tela.

    Mês sem lançamento nenhum não é caso de erro: os quatro cards de dinheiro
    mostram R$ 0,00 e a taxa mostra travessão, porque sem receita não há conta
    a fazer.

    Desde a rodada 27 o que sai daqui é o NOME DA CLASSE do valor, e não o
    booleano `negativo` que o template traduzia: os cards do mês passaram a
    ser os mesmos `kpi` da Visão Anual, e é a Anual que já emitia a classe.
    Um formato só para os dois painéis, e a cor continua decidida em Python.
    O acento do saldo positivo é da Anual e só dela — aqui, positivo é tinta
    normal, como sempre foi nesta tela.
    """
    receita = receitas
    despesa = despesas["total"]
    saldo = receita - despesa
    return [
        card("Receitas", valor=receita),
        card("Despesas", valor=despesa),
        card("Saldo", valor=saldo,
             classe=VALOR_NEGATIVO if saldo < 0 else None),
        # O vermelho acompanha o percentual, não o saldo: com receita zero o
        # card mostra travessão, e travessão vermelho não quer dizer nada.
        card("Taxa de Poupança",
             texto=percentual(saldo, receita),
             classe=VALOR_NEGATIVO if saldo < 0 and receita > 0 else None),
        card("Essenciais", valor=despesas["essencial"]),
        card("Não Essenciais", valor=despesas["nao_essencial"]),
    ]


# --------------------------------------------------------------------------
# A tela inteira
# --------------------------------------------------------------------------

def painel_do_mes(ano, mes, ordem):
    """Cards e as três tabelas do mês, com três consultas ao banco."""
    inicio, fim = intervalo_do_mes(ano, mes)
    despesas = despesas_do_mes(inicio, fim)
    receitas = receitas_do_mes(inicio, fim)
    linhas = despesas_por_categoria_e_pessoa(inicio, fim)

    por_categoria = _somar_por(linhas, "categoria")
    por_pessoa = _somar_por(linhas, "pessoa")
    # O denominador das barras é o total do próprio cubo, e não o card: assim
    # o rodapé das duas tabelas fecha em 100,0% por construção, e a conferência
    # contra o card Despesas continua sendo uma conferência de verdade.
    total = sum(por_categoria.values(), ZERO)

    categorias = _ordenar(por_categoria, ordem)
    pessoas = _ordenar(por_pessoa, ORDEM_TOTAL)
    ids = {l["categoria"]: l["categoria_id"] for l in linhas}

    return {
        "cards": _cards(receitas, despesas),
        # Mês sem despesa: as três tabelas saem da tela e dão lugar a uma linha
        # só. Quem decide isso é o template, olhando esta bandeira.
        "tem_despesa": bool(linhas),
        "tabelas": {
            "categorias": _tabela_participacao(
                categorias, por_categoria, "categoria", total, ids),
            "pessoas": _tabela_participacao(
                pessoas, por_pessoa, "pessoa", total),
            "matriz": _matriz(categorias, pessoas, linhas,
                              por_categoria, por_pessoa, total),
        },
    }


# --------------------------------------------------------------------------
# Detalhe de uma categoria (fragmento da linha expansível)
#
# Uma consulta, e a mesma regra de intervalo do resto da tela. O agrupamento
# por subcategoria é feito aqui, e não com um segundo GROUP BY: as linhas já
# vêm todas, ordenadas, e passar duas vezes no banco para somar o que já está
# na mão só teria como resultado dois números que precisariam coincidir.
# --------------------------------------------------------------------------

def categoria(categoria_id):
    """A categoria, ou None. Id inexistente vira 404 na rota, nunca 500."""
    return query_one(
        "SELECT id, nome FROM tb_categorias WHERE id = %s", (categoria_id,))


def lancamentos_da_categoria(inicio, fim, categoria_id):
    """Lançamentos de uma categoria no mês, com o nome de quem gastou.

    A observação vem junto desde a rodada 36, para o "i" da linha, como nas
    listas de lançamento.

    `vw_despesas` traz `pessoa_id`, não o nome — mesmo JOIN do cubo. A ordem
    do SQL agrupa por subcategoria e, dentro dela, põe o mais antigo primeiro;
    o `id` fecha o critério para dois lançamentos do mesmo dia não trocarem de
    lugar entre uma leitura e outra.
    """
    return query_all(
        "SELECT v.id, v.data, v.descricao, v.valor, v.subcategoria,"
        "       v.observacoes, p.nome AS pessoa"
        "  FROM vw_despesas v"
        "  JOIN tb_pessoas  p ON p.id = v.pessoa_id"
        " WHERE v.data >= %s AND v.data < %s AND v.categoria_id = %s"
        " ORDER BY v.subcategoria, v.data, v.id",
        (inicio, fim, categoria_id),
    )


def detalhe_da_categoria(ano, mes, categoria_id):
    """Grupos por subcategoria, com subtotal, e o total da categoria.

    O total daqui tem que ser idêntico ao "Total no mês" da linha expandida:
    são as mesmas despesas, o mesmo intervalo e o mesmo filtro de categoria,
    somadas em `Decimal` nos dois lugares.

    A ordem dos grupos é a chave alfabética pt-BR, e não a do `ORDER BY`: o
    SQL já entrega assim com a collation atual do banco, mas ordenar aqui
    deixa a tela igual em qualquer collation, do mesmo jeito que na tabela por
    categoria.
    """
    inicio, fim = intervalo_do_mes(ano, mes)
    linhas = lancamentos_da_categoria(inicio, fim, categoria_id)

    por_subcategoria = {}
    for linha in linhas:
        por_subcategoria.setdefault(linha["subcategoria"], []).append(linha)

    return {
        "grupos": [
            {"subcategoria": nome,
             "quantidade": len(itens),
             "total": sum((i["valor"] for i in itens), ZERO),
             "lancamentos": itens}
            for nome, itens in sorted(por_subcategoria.items(),
                                      key=lambda par: chave_alfabetica(par[0]))
        ],
        "total": sum((l["valor"] for l in linhas), ZERO),
        "quantidade": len(linhas),
    }
