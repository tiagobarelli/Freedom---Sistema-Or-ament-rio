"""Cadastro de ativos de patrimônio (tb_ativos).

Um **ativo** é onde o patrimônio está aplicado: um título, um fundo, um
imóvel, a reserva na conta. Não é conta de lançamento nem categoria — nada
aqui cruza com despesa ou receita. A tabela existe no schema desde a rodada 1
e ganhou esta tela na 30.

Padrão de cadastro sem desvio: lista com badge e interruptor de inativos,
criar e editar em página própria, ativar/desativar por HTMX trocando só a
`<tr>`, **sem excluir** — referência se desativa, e um ativo apagado levaria
junto as fotos que o citam (a FK é `ON DELETE RESTRICT`, e é ela que o
impediria de qualquer jeito).

Duas coisas são próprias daqui:

- **a composição** (rodada 37): de que subclasses de alocação o ativo é
  feito, numa grade de percentuais dentro do mesmo formulário, gravada junto
  com o ativo numa transação. Tomou o lugar do antigo campo `classe`, texto
  livre: a previdência se reparte entre classes diferentes, e um texto só não
  dizia isso. Quem lê, valida e grava a grade é `alocacao/composicao.py`;
- **inativo quer dizer "posição encerrada"**, e não "cadastro errado". O ativo
  encerrado some da grade da foto de patrimônio e não recebe linha nova, mas
  as fotos antigas dele continuam lá e continuam contando no total — quem
  avisa que isso está acontecendo é a nota do card daquela tela.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.alocacao import composicao
from freedom.alocacao.servico import referencias
from freedom.cadastros import bp
from freedom.cadastros.forms import AtivoForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    contagem,
)
from freedom.db import query_all, query_one

# A linha da lista com a composição resumida. Os dois arrays saem na mesma
# ordem (do maior pedaço para o menor), e quem os junta em texto é
# `composicao.resumo`. O FILTER tira o NULL que o LEFT JOIN põe no ativo sem
# composição: sem ele, o array seria `{NULL}`, e não vazio.
_SELECT_LINHA = """
    SELECT a.id, a.nome, a.observacao, a.ativo,
           array_agg(sc.nome ORDER BY comp.percentual DESC, sc.nome)
               FILTER (WHERE comp.id IS NOT NULL) AS partes,
           array_agg(comp.percentual ORDER BY comp.percentual DESC, sc.nome)
               FILTER (WHERE comp.id IS NOT NULL) AS percentuais
      FROM tb_ativos a
      LEFT JOIN tb_alocacao_composicao comp ON comp.ativo_id = a.id
      LEFT JOIN tb_alocacao_subclasses sc   ON sc.id = comp.subclasse_id
"""


def _com_resumo(linha):
    return dict(linha, composicao=composicao.resumo(linha["partes"],
                                                     linha["percentuais"]))


def _buscar(ativo_id):
    linha = query_one(_SELECT_LINHA + " WHERE a.id = %s GROUP BY a.id",
                      (ativo_id,))
    return _com_resumo(linha) if linha else None


@bp.route("/ativos")
@login_required
def ativos_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    linhas = query_all(
        _SELECT_LINHA + " WHERE (%s OR a.ativo = TRUE)"
                        " GROUP BY a.id ORDER BY a.nome",
        (mostrar_inativos,),
    )
    return render_template(
        "cadastros/ativos_lista.html",
        linhas=[_com_resumo(l) for l in linhas],
        contagem=contagem("ativos"),
        mostrar_inativos=mostrar_inativos,
    )


def _formulario(registro):
    """Criar e editar são o mesmo formulário, e o mesmo caminho.

    A grade da composição é lida à mão (`composicao.ler`) ao lado do
    WTForms, e as três recusas — campo do ativo, campo da grade e soma —
    somam-se: quem errou o nome E a soma vê os dois de uma vez. Nada é
    gravado enquanto houver uma.
    """
    ativo_id = registro["id"] if registro else None
    form = AtivoForm(data=registro)
    atual = composicao.do_ativo(ativo_id)
    grupos = composicao.grupos_da_grade(referencias(), atual)
    digitado, erros, erro_soma = None, None, None

    if request.method == "POST":
        valores, erros, digitado = composicao.ler(request.form, grupos)
        erro_soma = None if erros else composicao.validar(valores)
        if form.validate_on_submit() and not erros and not erro_soma:
            try:
                composicao.gravar(ativo_id, form.nome.data,
                                  (form.observacao.data or "").strip() or None,
                                  valores)
            except errors.UniqueViolation as exc:
                aplicar_erro_duplicado(form, exc)
            else:
                flash("Ativo atualizado." if registro else "Ativo criado.",
                      "sucesso")
                return redirect(url_for("cadastros.ativos_lista"))

    return render_template(
        "cadastros/ativos_form.html", form=form, registro=registro,
        grade=composicao.montar(grupos, atual, digitado, erros),
        erro_composicao=erro_soma,
        prefixo_campo=composicao.PREFIXO_COMPOSICAO)


@bp.route("/ativos/novo", methods=["GET", "POST"])
@login_required
def ativos_novo():
    return _formulario(None)


@bp.route("/ativos/<int:ativo_id>/editar", methods=["GET", "POST"])
@login_required
def ativos_editar(ativo_id):
    registro = _buscar(ativo_id)
    if registro is None:
        abort(404)
    return _formulario(registro)


@bp.route("/ativos/<int:ativo_id>/alternar", methods=["POST"])
@login_required
def ativos_alternar(ativo_id):
    """Encerrar ou reabrir a posição. Só a `<tr>` volta.

    As fotos do ativo não são tocadas, nem a composição dele: encerrar uma
    posição é dizer que ela não recebe valor novo, não apagar o que ela já
    valeu nem do que ela era feita.
    """
    linha = alternar_ativo("ativos", ativo_id)
    if linha is None:
        abort(404)
    return render_template("cadastros/_linha_ativo.html", item=_buscar(ativo_id))
