"""Cadastro de classes de alocação (tb_alocacao_classes), da rodada 37.

O primeiro nível da alocação da carteira: Inflação, Ações Brasil,
Internacional. O plano dá a cada classe um alvo sobre o total, e o
balanceamento compara com o que a foto de patrimônio diz.

Padrão de cadastro sem desvio, no molde de `categorias.py`: lista com badge e
interruptor de inativos, criar e editar em página própria, ativar/desativar
por HTMX trocando só a `<tr>`, **sem excluir** — é referência, e o plano e as
subclasses apontam para ela com FK `ON DELETE RESTRICT`.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import ClasseAlocacaoForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    contagem,
    executar,
)
from freedom.db import query_all, query_one

# A contagem de subclasses ativas vai junto: é o que diz, na lista, se a
# classe já pode entrar num plano (classe sem subclasse não fecha 100 %).
_SELECT_LINHA = """
    SELECT c.id, c.nome, c.ativo,
           count(s.id) FILTER (WHERE s.ativo) AS subclasses
      FROM tb_alocacao_classes c
      LEFT JOIN tb_alocacao_subclasses s ON s.classe_id = c.id
"""


def _com_contagem(linha):
    n = linha["subclasses"]
    texto = ("nenhuma subclasse ativa" if n == 0
             else f"{n} subclasse{'s' if n != 1 else ''} ativa{'s' if n != 1 else ''}")
    return dict(linha, texto_subclasses=texto)


def _buscar(classe_id):
    linha = query_one(_SELECT_LINHA + " WHERE c.id = %s GROUP BY c.id",
                      (classe_id,))
    return _com_contagem(linha) if linha else None


@bp.route("/classes")
@login_required
def classes_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    linhas = query_all(
        _SELECT_LINHA + " WHERE (%s OR c.ativo = TRUE)"
                        " GROUP BY c.id ORDER BY c.nome",
        (mostrar_inativos,),
    )
    return render_template(
        "cadastros/classes_lista.html",
        linhas=[_com_contagem(l) for l in linhas],
        contagem=contagem("classes"),
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/classes/nova", methods=["GET", "POST"])
@login_required
def classes_nova():
    form = ClasseAlocacaoForm()
    if form.validate_on_submit():
        try:
            executar("INSERT INTO tb_alocacao_classes (nome) VALUES (%s)",
                     (form.nome.data,))
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Classe criada.", "sucesso")
            return redirect(url_for("cadastros.classes_lista"))

    return render_template("cadastros/classes_form.html", form=form,
                           registro=None)


@bp.route("/classes/<int:classe_id>/editar", methods=["GET", "POST"])
@login_required
def classes_editar(classe_id):
    registro = _buscar(classe_id)
    if registro is None:
        abort(404)

    form = ClasseAlocacaoForm(data=registro)
    if form.validate_on_submit():
        try:
            executar("UPDATE tb_alocacao_classes SET nome = %s WHERE id = %s",
                     (form.nome.data, classe_id))
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Classe atualizada.", "sucesso")
            return redirect(url_for("cadastros.classes_lista"))

    return render_template("cadastros/classes_form.html", form=form,
                           registro=registro)


@bp.route("/classes/<int:classe_id>/alternar", methods=["POST"])
@login_required
def classes_alternar(classe_id):
    """Troca ativa/inativa e devolve só o <tr>, para o HTMX substituir a linha.

    Desativar não tira a classe de plano nenhum nem de composição nenhuma: o
    que já a cita continua valendo, e ela só deixa de ser oferecida para
    linha nova.
    """
    linha = alternar_ativo("classes", classe_id)
    if linha is None:
        abort(404)
    return render_template("cadastros/_linha_classe.html",
                           item=_buscar(classe_id))
