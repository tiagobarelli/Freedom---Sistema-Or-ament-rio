"""Cadastro de pessoas (tb_pessoas).

Pessoa não é usuário: toda pessoa pode receber despesas, mas só entra no
sistema quem tiver registro em tb_usuarios (criado pela CLI).
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import PessoaForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    executar,
)
from freedom.db import query_all, query_one


def _buscar(pessoa_id):
    return query_one(
        "SELECT id, nome, ativo FROM tb_pessoas WHERE id = %s", (pessoa_id,)
    )


@bp.route("/pessoas")
@login_required
def pessoas_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    linhas = query_all(
        """
        SELECT p.id,
               p.nome,
               p.ativo,
               EXISTS (SELECT 1 FROM tb_usuarios u WHERE u.pessoa_id = p.id)
                   AS tem_usuario
          FROM tb_pessoas p
         WHERE (%s OR p.ativo = TRUE)
         ORDER BY p.nome
        """,
        (mostrar_inativos,),
    )
    return render_template(
        "cadastros/pessoas_lista.html",
        linhas=linhas,
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/pessoas/nova", methods=["GET", "POST"])
@login_required
def pessoas_nova():
    form = PessoaForm()
    if form.validate_on_submit():
        try:
            executar(
                "INSERT INTO tb_pessoas (nome) VALUES (%s)",
                (form.nome.data.strip(),),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Pessoa criada.", "sucesso")
            return redirect(url_for("cadastros.pessoas_lista"))

    return render_template("cadastros/pessoas_form.html", form=form, registro=None)


@bp.route("/pessoas/<int:pessoa_id>/editar", methods=["GET", "POST"])
@login_required
def pessoas_editar(pessoa_id):
    registro = _buscar(pessoa_id)
    if registro is None:
        abort(404)

    form = PessoaForm(data=registro)
    if form.validate_on_submit():
        try:
            executar(
                "UPDATE tb_pessoas SET nome = %s WHERE id = %s",
                (form.nome.data.strip(), pessoa_id),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Pessoa atualizada.", "sucesso")
            return redirect(url_for("cadastros.pessoas_lista"))

    return render_template(
        "cadastros/pessoas_form.html", form=form, registro=registro
    )


@bp.route("/pessoas/<int:pessoa_id>/alternar", methods=["POST"])
@login_required
def pessoas_alternar(pessoa_id):
    linha = alternar_ativo("pessoas", pessoa_id)
    if linha is None:
        abort(404)
    registro = query_one(
        """
        SELECT p.id, p.nome, p.ativo,
               EXISTS (SELECT 1 FROM tb_usuarios u WHERE u.pessoa_id = p.id)
                   AS tem_usuario
          FROM tb_pessoas p
         WHERE p.id = %s
        """,
        (pessoa_id,),
    )
    return render_template("cadastros/_linha_pessoa.html", item=registro)
