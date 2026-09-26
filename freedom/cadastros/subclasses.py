"""Cadastro de subclasses de alocação (tb_alocacao_subclasses), da rodada 37.

O segundo nível da alocação: o "balde" dentro de uma classe, que costuma
levar o nome de um ETF (VWRA, B5P211). É a subclasse que a composição de um
ativo cita, e o plano dá a cada uma um alvo sobre a classe dela.

No molde de `subcategorias.py`: a classe se escolhe por `<select>` (cadastro
fechado), a lista filtra por classe, e a unicidade é a mesma —
`(classe_id, nome)`. Sem excluir: composição e plano apontam para ela.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import SubclasseAlocacaoForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    contagem,
    executar,
)
from freedom.db import query_all, query_one

_SELECT_LINHA = """
    SELECT s.id,
           s.nome,
           s.ativo,
           s.classe_id,
           c.nome  AS classe_nome,
           c.ativo AS classe_ativa
      FROM tb_alocacao_subclasses s
      JOIN tb_alocacao_classes    c ON c.id = s.classe_id
"""


def _buscar(subclasse_id):
    return query_one(_SELECT_LINHA + " WHERE s.id = %s", (subclasse_id,))


def _opcoes_classe(classe_atual_id=None):
    """Classes ativas e, na edição, também a já vinculada mesmo se inativa.

    Sem a exceção, renomear uma subclasse cuja classe foi desativada
    obrigaria a trocar a classe dela — a mesma razão de `subcategorias.py`.
    """
    linhas = query_all(
        """
        SELECT id, nome, ativo
          FROM tb_alocacao_classes
         WHERE ativo = TRUE OR id = %s
         ORDER BY nome
        """,
        (classe_atual_id,),
    )
    return [
        (linha["id"], linha["nome"] if linha["ativo"]
         else f"{linha['nome']} (inativa)")
        for linha in linhas
    ]


@bp.route("/subclasses")
@login_required
def subclasses_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    filtro_classe = request.args.get("classe_id", type=int)

    linhas = query_all(
        _SELECT_LINHA
        + """
         WHERE (%s OR s.ativo = TRUE)
           -- O cast ::int e obrigatorio: sem ele o Postgres nao consegue
           -- inferir o tipo do parametro comparado com NULL.
           AND (%s::int IS NULL OR s.classe_id = %s::int)
         ORDER BY c.nome, s.nome
        """,
        (mostrar_inativos, filtro_classe, filtro_classe),
    )
    classes = query_all("SELECT id, nome FROM tb_alocacao_classes ORDER BY nome")
    return render_template(
        "cadastros/subclasses_lista.html",
        linhas=linhas,
        contagem=contagem("subclasses"),
        classes=classes,
        filtro_classe=filtro_classe,
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/subclasses/nova", methods=["GET", "POST"])
@login_required
def subclasses_nova():
    form = SubclasseAlocacaoForm()
    form.classe_id.choices = _opcoes_classe()

    if not form.classe_id.choices:
        flash("Cadastre uma classe antes de criar subclasses.", "aviso")
        return redirect(url_for("cadastros.classes_lista"))

    if form.validate_on_submit():
        try:
            executar(
                "INSERT INTO tb_alocacao_subclasses (classe_id, nome)"
                " VALUES (%s, %s)",
                (form.classe_id.data, form.nome.data),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Subclasse criada.", "sucesso")
            return redirect(url_for("cadastros.subclasses_lista"))

    return render_template("cadastros/subclasses_form.html", form=form,
                           registro=None)


@bp.route("/subclasses/<int:subclasse_id>/editar", methods=["GET", "POST"])
@login_required
def subclasses_editar(subclasse_id):
    registro = _buscar(subclasse_id)
    if registro is None:
        abort(404)

    form = SubclasseAlocacaoForm(data=registro)
    form.classe_id.choices = _opcoes_classe(registro["classe_id"])

    if form.validate_on_submit():
        try:
            executar(
                "UPDATE tb_alocacao_subclasses SET classe_id = %s, nome = %s"
                " WHERE id = %s",
                (form.classe_id.data, form.nome.data, subclasse_id),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Subclasse atualizada.", "sucesso")
            return redirect(url_for("cadastros.subclasses_lista"))

    return render_template("cadastros/subclasses_form.html", form=form,
                           registro=registro)


@bp.route("/subclasses/<int:subclasse_id>/alternar", methods=["POST"])
@login_required
def subclasses_alternar(subclasse_id):
    """Troca ativa/inativa e devolve só o <tr>.

    Como na classe: o plano e as composições que já a citam continuam
    valendo; ela só deixa de ser oferecida para linha nova.
    """
    linha = alternar_ativo("subclasses", subclasse_id)
    if linha is None:
        abort(404)
    return render_template("cadastros/_linha_subclasse.html",
                           item=_buscar(subclasse_id))
