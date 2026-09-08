"""Tela de configurações: lançar vigência, editar em linha e excluir.

Uma página só, no formato da tela de receitas: formulário no topo, lista
embaixo, HTMX sem recarregar.

Decisão desta rodada: `tb_configuracoes` aceita UPDATE e DELETE físico pela
interface. Uma vigência digitada errada é lixo, não histórico — mesma regra
dos lançamentos — e nada derivado é armazenado, então apagar uma vigência só
muda o que os relatórios calculam dali em diante.
"""

from datetime import date

from flask import abort, render_template, request
from flask_login import login_required
from psycopg import errors

from freedom.configuracoes import bp
from freedom.configuracoes.forms import ConfiguracaoForm, VigenciaForm
from freedom.configuracoes.servico import (
    catalogo,
    formatar,
    formato_da_chave,
    normalizar_chave,
    secoes,
    sugestoes_de_chave,
    texto_para_edicao,
    valor_vigente,
    vigencia,
)
from freedom.db import executar

MENSAGEM_DUPLICADA = "Já existe um valor para esta chave nesta data."


def _preparar(form, chave):
    """Ata o formulário à chave: é ela que decide como o valor é lido."""
    form.formato = formato_da_chave(chave)
    if isinstance(form, ConfiguracaoForm):
        form.sugestoes = sugestoes_de_chave()
    return form


def _contexto():
    return {"secoes": secoes(), "hoje": date.today()}


def _contexto_formato(chave):
    """O que a dica de formato precisa saber sobre a chave em foco.

    Vai junto do formulário em toda renderização (página, sucesso e erro), e
    sozinho na rota que o HTMX chama a cada tecla.
    """
    chave = normalizar_chave(chave)
    return {
        "chave_atual": chave,
        "info": catalogo(chave),
        "formato": formato_da_chave(chave),
    }


# --------------------------------------------------------------------------
# Tela
# --------------------------------------------------------------------------

@bp.route("")
@login_required
def configuracoes_tela():
    return render_template(
        "configuracoes/configuracoes.html",
        form=_preparar(ConfiguracaoForm(), None),
        **_contexto_formato(None), **_contexto()
    )


@bp.route("/formato")
@login_required
def configuracoes_formato():
    """Diz, enquanto a pessoa digita, como o valor daquela chave será lido.

    Sem isto, `4` numa chave do catálogo e `0,04` numa chave livre gravariam a
    mesma coisa sem nada na tela explicando por quê. O catálogo é conhecimento
    do servidor; mandar o fragmento pronto evita uma segunda cópia dele em JS.
    """
    return render_template("configuracoes/_formato.html",
                           **_contexto_formato(request.args.get("chave")))


# --------------------------------------------------------------------------
# Gravação
# --------------------------------------------------------------------------

@bp.route("", methods=["POST"])
@login_required
def configuracoes_gravar():
    chave = normalizar_chave(request.form.get("chave"))
    form = _preparar(ConfiguracaoForm(), chave)

    if form.validate_on_submit():
        try:
            executar(
                """
                INSERT INTO tb_configuracoes
                    (chave, valor, vigente_desde, observacao)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    chave,
                    form.valor_decimal,
                    form.vigente_desde.data,
                    (form.observacao.data or "").strip() or None,
                ),
            )
        except errors.UniqueViolation:
            # uq_configuracoes_chave_vigencia. Vira erro de campo, nunca 500.
            form.vigente_desde.errors = list(form.vigente_desde.errors) + [
                MENSAGEM_DUPLICADA
            ]
        else:
            # Formulário novo mantendo a chave e a data: lançar as vigências
            # de uma mesma chave em sequência é o caso comum desta tela.
            limpo = _preparar(ConfiguracaoForm(formdata=None), chave)
            limpo.chave.data = chave
            limpo.vigente_desde.data = form.vigente_desde.data
            return render_template(
                "configuracoes/_gravada.html", form=limpo,
                **_contexto_formato(chave), **_contexto()
            )

    return render_template("configuracoes/_erro.html", form=form,
                           **_contexto_formato(chave))


# --------------------------------------------------------------------------
# Edição em linha
#
# Em linha, e não em página separada: a vigência tem três campos e só faz
# sentido olhando a série inteira da chave (qual valor vale hoje, qual é
# futuro). Mandar para outra página para trocar um número tiraria justamente
# esse contexto. A linha vira formulário, e o que volta ao salvar é a seção
# recalculada.
# --------------------------------------------------------------------------

@bp.route("/<int:config_id>/editar")
@login_required
def configuracoes_editar_form(config_id):
    """Troca a <tr> do histórico por uma linha de edição."""
    registro = vigencia(config_id)
    if registro is None:
        abort(404)

    formato = formato_da_chave(registro["chave"])
    dados = dict(registro, valor=texto_para_edicao(registro["valor"], formato))
    return render_template(
        "configuracoes/_linha_edicao.html",
        form=_preparar(VigenciaForm(data=dados), registro["chave"]),
        item=registro,
    )


@bp.route("/<int:config_id>/editar", methods=["POST"])
@login_required
def configuracoes_editar(config_id):
    registro = vigencia(config_id)
    if registro is None:
        abort(404)

    form = _preparar(VigenciaForm(), registro["chave"])
    if form.validate_on_submit():
        try:
            executar(
                """
                UPDATE tb_configuracoes
                   SET valor = %s, vigente_desde = %s, observacao = %s
                 WHERE id = %s
                """,
                (
                    form.valor_decimal,
                    form.vigente_desde.data,
                    (form.observacao.data or "").strip() or None,
                    config_id,
                ),
                # A chave fica fora do UPDATE de propósito: trocar a chave é
                # apagar e lançar de novo.
            )
        except errors.UniqueViolation:
            form.vigente_desde.errors = list(form.vigente_desde.errors) + [
                MENSAGEM_DUPLICADA
            ]
        else:
            # Mudar a data reordena a seção e pode trocar o valor vigente
            # hoje, então a resposta é a lista inteira. O alvo declarado no
            # formulário é a própria linha — é o que o erro precisa trocar —
            # e no sucesso o servidor o redireciona com HX-Retarget.
            return render_template("configuracoes/_lista.html", **_contexto()), 200, {
                "HX-Retarget": "#lista-configuracoes",
                "HX-Reswap": "innerHTML",
            }

    return render_template(
        "configuracoes/_linha_edicao.html", form=form, item=registro
    )


@bp.route("/<int:config_id>/linha")
@login_required
def configuracoes_linha(config_id):
    """Cancelar a edição: devolve a linha de leitura como ela estava."""
    registro = vigencia(config_id)
    if registro is None:
        abort(404)

    formato = formato_da_chave(registro["chave"])
    vigente = valor_vigente(registro["chave"])
    item = dict(
        registro,
        texto=formatar(registro["valor"], formato),
        futura=registro["vigente_desde"] > date.today(),
        e_vigente=bool(vigente and vigente["id"] == registro["id"]),
    )
    return render_template("configuracoes/_linha.html", item=item)


# --------------------------------------------------------------------------
# Exclusão física
# --------------------------------------------------------------------------

@bp.route("/<int:config_id>/excluir", methods=["POST"])
@login_required
def configuracoes_excluir(config_id):
    apagada = executar(
        "DELETE FROM tb_configuracoes WHERE id = %s RETURNING id",
        (config_id,),
        retornar=True,
    )
    if apagada is None:
        abort(404)

    # Apagar mexe no vigente hoje e, se era a última vigência da chave, faz a
    # chave sumir da tela: a resposta é a lista inteira.
    return render_template("configuracoes/_lista.html", **_contexto())
