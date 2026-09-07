"""Cadastro de fontes de receita (tb_ref_receitas).

Categoria e subcategoria vivem na mesma tabela porque o volume é pequeno; a
chave natural é o par (categoria, subcategoria).
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import RefReceitaForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    executar,
)
from freedom.db import query_all, query_one

_SELECT_LINHA = """
    SELECT id, categoria, subcategoria, observacao, ativo
      FROM tb_ref_receitas
"""


def _buscar(ref_id):
    return query_one(_SELECT_LINHA + " WHERE id = %s", (ref_id,))


@bp.route("/fontes-receita")
@login_required
def ref_receitas_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    linhas = query_all(
        _SELECT_LINHA
        + " WHERE (%s OR ativo = TRUE) ORDER BY categoria, subcategoria",
        (mostrar_inativos,),
    )
    return render_template(
        "cadastros/ref_receitas_lista.html",
        linhas=linhas,
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/fontes-receita/nova", methods=["GET", "POST"])
@login_required
def ref_receitas_nova():
    form = RefReceitaForm()
    if form.validate_on_submit():
        try:
            executar(
                """
                INSERT INTO tb_ref_receitas (categoria, subcategoria, observacao)
                VALUES (%s, %s, %s)
                """,
                (
                    form.categoria.data.strip(),
                    form.subcategoria.data.strip(),
                    (form.observacao.data or "").strip() or None,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Fonte de receita criada.", "sucesso")
            return redirect(url_for("cadastros.ref_receitas_lista"))

    return render_template(
        "cadastros/ref_receitas_form.html", form=form, registro=None
    )


@bp.route("/fontes-receita/<int:ref_id>/editar", methods=["GET", "POST"])
@login_required
def ref_receitas_editar(ref_id):
    registro = _buscar(ref_id)
    if registro is None:
        abort(404)

    form = RefReceitaForm(data=registro)
    if form.validate_on_submit():
        try:
            executar(
                """
                UPDATE tb_ref_receitas
                   SET categoria = %s, subcategoria = %s, observacao = %s
                 WHERE id = %s
                """,
                (
                    form.categoria.data.strip(),
                    form.subcategoria.data.strip(),
                    (form.observacao.data or "").strip() or None,
                    ref_id,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Fonte de receita atualizada.", "sucesso")
            return redirect(url_for("cadastros.ref_receitas_lista"))

    return render_template(
        "cadastros/ref_receitas_form.html", form=form, registro=registro
    )


@bp.route("/fontes-receita/<int:ref_id>/alternar", methods=["POST"])
@login_required
def ref_receitas_alternar(ref_id):
    linha = alternar_ativo("ref_receitas", ref_id)
    if linha is None:
        abort(404)
    return render_template(
        "cadastros/_linha_ref_receita.html", item=_buscar(ref_id)
    )
