"""Cadastro de contas (tb_contas).

Serve só para classificar de onde o dinheiro saiu; não há saldo. Atenção: esta
é a única tabela de referência cuja coluna de situação chama `ativa`.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import ContaForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    executar,
)
from freedom.db import query_all, query_one

# `ativa` vira `ativo` no resultado para as macros de tabela funcionarem igual
# às das outras entidades.
_SELECT_LINHA = """
    SELECT id, nome, tipo, observacao, ativa AS ativo
      FROM tb_contas
"""


def _buscar(conta_id):
    return query_one(_SELECT_LINHA + " WHERE id = %s", (conta_id,))


@bp.route("/contas")
@login_required
def contas_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    linhas = query_all(
        _SELECT_LINHA + " WHERE (%s OR ativa = TRUE) ORDER BY nome",
        (mostrar_inativos,),
    )
    return render_template(
        "cadastros/contas_lista.html",
        linhas=linhas,
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/contas/nova", methods=["GET", "POST"])
@login_required
def contas_nova():
    form = ContaForm()
    if form.validate_on_submit():
        try:
            executar(
                """
                INSERT INTO tb_contas (nome, tipo, observacao)
                VALUES (%s, %s, %s)
                """,
                (
                    form.nome.data.strip(),
                    form.tipo.data,
                    (form.observacao.data or "").strip() or None,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Conta criada.", "sucesso")
            return redirect(url_for("cadastros.contas_lista"))

    return render_template("cadastros/contas_form.html", form=form, registro=None)


@bp.route("/contas/<int:conta_id>/editar", methods=["GET", "POST"])
@login_required
def contas_editar(conta_id):
    registro = _buscar(conta_id)
    if registro is None:
        abort(404)

    form = ContaForm(data=registro)
    if form.validate_on_submit():
        try:
            executar(
                """
                UPDATE tb_contas
                   SET nome = %s, tipo = %s, observacao = %s
                 WHERE id = %s
                """,
                (
                    form.nome.data.strip(),
                    form.tipo.data,
                    (form.observacao.data or "").strip() or None,
                    conta_id,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Conta atualizada.", "sucesso")
            return redirect(url_for("cadastros.contas_lista"))

    return render_template(
        "cadastros/contas_form.html", form=form, registro=registro
    )


@bp.route("/contas/<int:conta_id>/alternar", methods=["POST"])
@login_required
def contas_alternar(conta_id):
    linha = alternar_ativo("contas", conta_id)
    if linha is None:
        abort(404)
    return render_template("cadastros/_linha_conta.html", item=_buscar(conta_id))
