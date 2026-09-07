"""Cadastro de categorias de despesa (tb_categorias)."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import CategoriaForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    executar,
)
from freedom.db import query_all, query_one


def _buscar(categoria_id):
    return query_one(
        "SELECT id, nome, ativo FROM tb_categorias WHERE id = %s",
        (categoria_id,),
    )


@bp.route("/categorias")
@login_required
def categorias_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    linhas = query_all(
        """
        SELECT id, nome, ativo
          FROM tb_categorias
         WHERE (%s OR ativo = TRUE)
         ORDER BY nome
        """,
        (mostrar_inativos,),
    )
    return render_template(
        "cadastros/categorias_lista.html",
        linhas=linhas,
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/categorias/nova", methods=["GET", "POST"])
@login_required
def categorias_nova():
    form = CategoriaForm()
    if form.validate_on_submit():
        try:
            executar(
                "INSERT INTO tb_categorias (nome) VALUES (%s)",
                (form.nome.data.strip(),),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Categoria criada.", "sucesso")
            return redirect(url_for("cadastros.categorias_lista"))

    return render_template(
        "cadastros/categorias_form.html", form=form, registro=None
    )


@bp.route("/categorias/<int:categoria_id>/editar", methods=["GET", "POST"])
@login_required
def categorias_editar(categoria_id):
    registro = _buscar(categoria_id)
    if registro is None:
        abort(404)

    form = CategoriaForm(data=registro)
    if form.validate_on_submit():
        try:
            executar(
                "UPDATE tb_categorias SET nome = %s WHERE id = %s",
                (form.nome.data.strip(), categoria_id),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Categoria atualizada.", "sucesso")
            return redirect(url_for("cadastros.categorias_lista"))

    return render_template(
        "cadastros/categorias_form.html", form=form, registro=registro
    )


@bp.route("/categorias/<int:categoria_id>/alternar", methods=["POST"])
@login_required
def categorias_alternar(categoria_id):
    """Troca ativo/inativo e devolve só o <tr>, para o HTMX substituir a linha."""
    linha = alternar_ativo("categorias", categoria_id)
    if linha is None:
        abort(404)
    registro = _buscar(categoria_id)
    return render_template("cadastros/_linha_categoria.html", item=registro)
