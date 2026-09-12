"""Resumos anuais (tb_resumos_anuais).

Um texto por ano que explica os números daquele ano. Fica no grupo Cadastros
porque é o que é: entrada do dono, escrita fora do fluxo de lançamento, sem
relação com nenhuma outra linha do banco.

Três diferenças em relação aos cinco cadastros vizinhos, todas consequência de
o resumo não ser tabela de referência:

- a chave é o **ano**, e não um id — há no máximo um resumo por ano;
- não há `ativo`: resumo se **exclui** (regra da rodada 20, ao lado da
  configuração e da linha de orçamento), então a segunda ação da linha é
  Excluir, e não Desativar;
- não há contagem nem interruptor de inativos, porque não há inativo.

Duas funções vêm de `freedom/main/servico.py` em vez de serem repetidas aqui,
e a dependência aponta só nesse sentido (cadastro -> painel), nunca de volta:

- `anos_com_lancamento`, onde sempre morou. Os anos que este cadastro oferece
  são, por definição, "os anos que a Visão Anual mostra" — se um dia
  divergirem serão duas perguntas diferentes, e hoje são a mesma;
- `resumo_do_ano`, a leitura por chave. Quem lê o resumo para exibir é a Visão
  Anual; aqui ela serve para carregar o texto na edição. Um resumo, uma
  origem — a mesma regra dos números que aparecem em duas telas.

Este módulo é o dono da escrita: INSERT, UPDATE, DELETE e a lista.
"""

from flask import (abort, flash, redirect, render_template, request, url_for)
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import ResumoAnualForm
from freedom.db import executar, query_all
from freedom.main.servico import anos_com_lancamento, resumo_do_ano
from freedom.util import destino_interno

# Trecho de uma linha na lista. 120 cabe na coluna a 1440px sem estourar e
# ainda diz do que o resumo trata.
LARGURA_TRECHO = 120


def _trecho(texto):
    """Texto de vários parágrafos -> uma linha curta para a lista.

    Quebra de linha vira espaço e os brancos se juntam: na célula da tabela o
    resumo tem de caber numa linha só. O corte é decidido aqui, e não no
    template, como todo o resto do que a tela mostra.
    """
    uma_linha = " ".join(texto.split())
    if len(uma_linha) <= LARGURA_TRECHO:
        return uma_linha
    return uma_linha[:LARGURA_TRECHO].rstrip() + "…"


def _listar():
    """Do ano mais recente para o mais antigo, pronto para a tela."""
    linhas = query_all(
        "SELECT ano, texto, criado_em, atualizado_em"
        "  FROM tb_resumos_anuais ORDER BY ano DESC"
    )
    return [
        {
            "ano": l["ano"],
            "trecho": _trecho(l["texto"]),
            # Qual dos dois carimbos a tela mostra é decisão da aplicação:
            # `atualizado_em` fica NULL até o primeiro UPDATE (ver o DDL).
            "alterado_em": l["atualizado_em"] or l["criado_em"],
            "editado": l["atualizado_em"] is not None,
        }
        for l in linhas
    ]


def anos_disponiveis():
    """Anos que a Visão Anual mostra e que ainda não têm resumo.

    Do mais recente para o mais antigo, como o seletor de ano da Anual.
    """
    ocupados = {l["ano"] for l in query_all("SELECT ano FROM tb_resumos_anuais")}
    return [a for a in anos_com_lancamento() if a not in ocupados]


def _contexto_lista():
    return {"linhas": _listar(), "anos": anos_disponiveis()}


@bp.route("/resumos-anuais")
@login_required
def resumos_lista():
    return render_template("cadastros/resumos_lista.html", **_contexto_lista())


@bp.route("/resumos-anuais/novo", methods=["GET", "POST"])
@login_required
def resumos_novo():
    """Escrever o resumo de um ano que ainda não tem.

    A lista de anos é carregada de novo no POST: entre abrir o formulário e
    gravar, o ano pode ter ganhado resumo em outra aba. Se ganhou, quem barra é
    `validate_ano`; se as duas abas gravarem no mesmo instante, quem barra é a
    chave primária, e a `UniqueViolation` vira erro do campo ano.
    """
    anos = anos_disponiveis()
    form = ResumoAnualForm()
    form.carregar_anos(anos)

    if form.validate_on_submit():
        try:
            executar(
                "INSERT INTO tb_resumos_anuais (ano, texto) VALUES (%s, %s)",
                (form.ano.data, form.texto.data),
            )
        except errors.UniqueViolation:
            form.ano.errors = list(form.ano.errors) + [
                "Este ano acabou de ganhar um resumo. Recarregue a página."
            ]
        else:
            flash(f"Resumo de {form.ano.data} criado.", "sucesso")
            return redirect(url_for("cadastros.resumos_lista"))

    return render_template(
        "cadastros/resumos_form.html", form=form, registro=None, anos=anos,
        retorno=None,
    )


@bp.route("/resumos-anuais/<int:ano>/editar", methods=["GET", "POST"])
@login_required
def resumos_editar(ano):
    """Só o texto se edita: o ano é a chave, e trocar de ano é outro resumo."""
    registro = resumo_do_ano(ano)
    if registro is None:
        abort(404)

    # A Visão Anual manda `?retorno=` apontando para ela mesma no ano exibido.
    retorno = destino_interno(request.args.get("retorno"))

    form = ResumoAnualForm(data=registro)
    # O ano não é editável, mas o campo existe no formulário: carregá-lo com o
    # ano do registro é o que faz `validate_ano` aceitar o POST.
    form.carregar_anos([ano])

    if form.validate_on_submit():
        executar(
            "UPDATE tb_resumos_anuais SET texto = %s WHERE ano = %s",
            (form.texto.data, ano),
        )
        flash(f"Resumo de {ano} atualizado.", "sucesso")
        return redirect(retorno or url_for("cadastros.resumos_lista"))

    return render_template(
        "cadastros/resumos_form.html", form=form, registro=registro,
        anos=[ano], retorno=retorno,
    )


@bp.route("/resumos-anuais/<int:ano>/excluir", methods=["POST"])
@login_required
def resumos_excluir(ano):
    """DELETE físico, como configuração e linha de orçamento.

    Apagar devolve o ano à lista de disponíveis e pode esvaziar a página, então
    a resposta é a lista inteira mais o botão "Novo resumo" da barra superior,
    trocado fora de banda — os dois dependem do mesmo fato.
    """
    apagado = executar(
        "DELETE FROM tb_resumos_anuais WHERE ano = %s RETURNING ano",
        (ano,),
        retornar=True,
    )
    if apagado is None:
        abort(404)

    return render_template("cadastros/_lista_resumos.html",
                           oob=True, **_contexto_lista())
