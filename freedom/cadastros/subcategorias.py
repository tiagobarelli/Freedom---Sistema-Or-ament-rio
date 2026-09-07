"""Cadastro de subcategorias de despesa (tb_subcategorias).

A subcategoria é a única coisa escolhida ao lançar uma despesa: categoria e
essencialidade padrão vêm daqui via JOIN.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import SubcategoriaForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    executar,
)
from freedom.db import query_all, query_one

_SELECT_LINHA = """
    SELECT s.id,
           s.nome,
           s.essencialidade,
           s.ativo,
           s.categoria_id,
           c.nome  AS categoria_nome,
           c.ativo AS categoria_ativa
      FROM tb_subcategorias s
      JOIN tb_categorias    c ON c.id = s.categoria_id
"""


def _buscar(subcategoria_id):
    return query_one(_SELECT_LINHA + " WHERE s.id = %s", (subcategoria_id,))


def _opcoes_categoria(categoria_atual_id=None):
    """Categorias ativas e, na edição, também a já vinculada mesmo se inativa.

    Sem a exceção, editar a essencialidade de uma subcategoria cuja categoria
    foi desativada obrigaria a trocar a categoria dela.
    """
    linhas = query_all(
        """
        SELECT id, nome, ativo
          FROM tb_categorias
         WHERE ativo = TRUE OR id = %s
         ORDER BY nome
        """,
        (categoria_atual_id,),
    )
    return [
        (linha["id"], linha["nome"] if linha["ativo"]
         else f"{linha['nome']} (inativa)")
        for linha in linhas
    ]


@bp.route("/subcategorias")
@login_required
def subcategorias_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    filtro_categoria = request.args.get("categoria_id", type=int)

    linhas = query_all(
        _SELECT_LINHA
        + """
         WHERE (%s OR s.ativo = TRUE)
           -- O cast ::int e obrigatorio: sem ele o Postgres nao consegue
           -- inferir o tipo do parametro comparado com NULL e recusa a query.
           AND (%s::int IS NULL OR s.categoria_id = %s::int)
         ORDER BY c.nome, s.nome
        """,
        (mostrar_inativos, filtro_categoria, filtro_categoria),
    )
    categorias = query_all(
        "SELECT id, nome FROM tb_categorias ORDER BY nome"
    )
    return render_template(
        "cadastros/subcategorias_lista.html",
        linhas=linhas,
        categorias=categorias,
        filtro_categoria=filtro_categoria,
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/subcategorias/nova", methods=["GET", "POST"])
@login_required
def subcategorias_nova():
    form = SubcategoriaForm()
    form.categoria_id.choices = _opcoes_categoria()

    if not form.categoria_id.choices:
        flash("Cadastre uma categoria antes de criar subcategorias.", "aviso")
        return redirect(url_for("cadastros.categorias_lista"))

    if form.validate_on_submit():
        try:
            executar(
                """
                INSERT INTO tb_subcategorias (categoria_id, nome, essencialidade)
                VALUES (%s, %s, %s)
                """,
                (
                    form.categoria_id.data,
                    form.nome.data.strip(),
                    form.essencialidade.data,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Subcategoria criada.", "sucesso")
            return redirect(url_for("cadastros.subcategorias_lista"))

    return render_template(
        "cadastros/subcategorias_form.html", form=form, registro=None
    )


@bp.route("/subcategorias/<int:subcategoria_id>/editar", methods=["GET", "POST"])
@login_required
def subcategorias_editar(subcategoria_id):
    registro = _buscar(subcategoria_id)
    if registro is None:
        abort(404)

    form = SubcategoriaForm(data=registro)
    form.categoria_id.choices = _opcoes_categoria(registro["categoria_id"])

    if form.validate_on_submit():
        try:
            executar(
                """
                UPDATE tb_subcategorias
                   SET categoria_id = %s, nome = %s, essencialidade = %s
                 WHERE id = %s
                """,
                (
                    form.categoria_id.data,
                    form.nome.data.strip(),
                    form.essencialidade.data,
                    subcategoria_id,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Subcategoria atualizada.", "sucesso")
            return redirect(url_for("cadastros.subcategorias_lista"))

    return render_template(
        "cadastros/subcategorias_form.html", form=form, registro=registro
    )


@bp.route("/subcategorias/<int:subcategoria_id>/alternar", methods=["POST"])
@login_required
def subcategorias_alternar(subcategoria_id):
    linha = alternar_ativo("subcategorias", subcategoria_id)
    if linha is None:
        abort(404)
    return render_template(
        "cadastros/_linha_subcategoria.html", item=_buscar(subcategoria_id)
    )
