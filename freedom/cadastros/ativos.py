"""Cadastro de ativos de patrimônio (tb_ativos).

Um **ativo** é onde o patrimônio está aplicado: um título, um fundo, um
imóvel, a reserva na conta. Não é conta de lançamento nem categoria — nada
aqui cruza com despesa ou receita. A tabela existe no schema desde a rodada 1
e nunca tinha recebido uma linha nem uma tela; esta é a tela.

Padrão de cadastro sem desvio: lista com badge e interruptor de inativos,
criar e editar em página própria, ativar/desativar por HTMX trocando só a
`<tr>`, **sem excluir** — referência se desativa, e um ativo apagado levaria
junto as fotos que o citam (a FK é `ON DELETE RESTRICT`, e é ela que o
impediria de qualquer jeito).

Duas coisas são próprias daqui:

- **`classe` é texto livre**, não select: `tb_ativos.classe` não tem CHECK, de
  propósito (decisão registrada no `.md` do banco). A taxonomia de onde o
  dinheiro está é do dono e muda com o tempo. A `combobox` oferece o que já
  existe, sem impedir o que ainda não;
- **inativo quer dizer "posição encerrada"**, e não "cadastro errado". O ativo
  encerrado some da grade da foto de patrimônio e não recebe linha nova, mas
  as fotos antigas dele continuam lá e continuam contando no total — quem
  avisa que isso está acontecendo é a nota do card daquela tela.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.cadastros import bp
from freedom.cadastros.forms import AtivoForm
from freedom.cadastros.servico import (
    alternar_ativo,
    aplicar_erro_duplicado,
    contagem,
    executar,
)
from freedom.db import query_all, query_one
from freedom.util import chave_alfabetica

_SELECT_LINHA = """
    SELECT id, nome, classe, observacao, ativo
      FROM tb_ativos
"""


def _buscar(ativo_id):
    return query_one(_SELECT_LINHA + " WHERE id = %s", (ativo_id,))


def classes_existentes():
    """As classes já usadas, em ordem alfabética pt-BR, para a `combobox`.

    A ordenação é a de `chave_alfabetica` (NFD, em Python), e não a do banco:
    a lista é de dezenas de itens e sai de um DISTINCT sem ORDER BY — quem a
    põe em ordem é a aplicação, como em toda lista que a tela monta.

    Inclui as classes de ativos encerrados: quem reabre uma posição quer
    encontrar o nome que já usava.
    """
    linhas = query_all("SELECT DISTINCT classe FROM tb_ativos")
    return sorted((l["classe"] for l in linhas), key=chave_alfabetica)


@bp.route("/ativos")
@login_required
def ativos_lista():
    mostrar_inativos = request.args.get("inativos") == "1"
    linhas = query_all(
        _SELECT_LINHA + " WHERE (%s OR ativo = TRUE) ORDER BY classe, nome",
        (mostrar_inativos,),
    )
    return render_template(
        "cadastros/ativos_lista.html",
        linhas=linhas,
        contagem=contagem("ativos"),
        mostrar_inativos=mostrar_inativos,
    )


@bp.route("/ativos/novo", methods=["GET", "POST"])
@login_required
def ativos_novo():
    form = AtivoForm()
    if form.validate_on_submit():
        try:
            executar(
                "INSERT INTO tb_ativos (nome, classe, observacao)"
                " VALUES (%s, %s, %s)",
                (
                    form.nome.data,
                    form.classe.data,
                    (form.observacao.data or "").strip() or None,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Ativo criado.", "sucesso")
            return redirect(url_for("cadastros.ativos_lista"))

    return render_template("cadastros/ativos_form.html", form=form,
                           registro=None, classes=classes_existentes())


@bp.route("/ativos/<int:ativo_id>/editar", methods=["GET", "POST"])
@login_required
def ativos_editar(ativo_id):
    registro = _buscar(ativo_id)
    if registro is None:
        abort(404)

    form = AtivoForm(data=registro)
    if form.validate_on_submit():
        try:
            executar(
                "UPDATE tb_ativos SET nome = %s, classe = %s, observacao = %s"
                " WHERE id = %s",
                (
                    form.nome.data,
                    form.classe.data,
                    (form.observacao.data or "").strip() or None,
                    ativo_id,
                ),
            )
        except errors.UniqueViolation as exc:
            aplicar_erro_duplicado(form, exc)
        else:
            flash("Ativo atualizado.", "sucesso")
            return redirect(url_for("cadastros.ativos_lista"))

    return render_template("cadastros/ativos_form.html", form=form,
                           registro=registro, classes=classes_existentes())


@bp.route("/ativos/<int:ativo_id>/alternar", methods=["POST"])
@login_required
def ativos_alternar(ativo_id):
    """Encerrar ou reabrir a posição. Só a `<tr>` volta.

    As fotos do ativo não são tocadas: encerrar uma posição é dizer que ela
    não recebe valor novo, não apagar o que ela já valeu.
    """
    linha = alternar_ativo("ativos", ativo_id)
    if linha is None:
        abort(404)
    return render_template("cadastros/_linha_ativo.html", item=_buscar(ativo_id))
