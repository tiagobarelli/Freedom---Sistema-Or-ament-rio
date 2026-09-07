"""Lançamento de despesas: tela única, edição em página própria e exclusão.

Leitura vem de `vw_despesas` (servico.py); escrita vai em `tb_despesas`.
"""

from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from psycopg import errors

from freedom.db import executar
from freedom.lancamentos import bp
from freedom.lancamentos.consulta import resultados_apos_exclusao
from freedom.lancamentos.forms import DespesaForm
from freedom.lancamentos.servico import (
    NAO_ESSENCIAL,
    agrupar_por_categoria,
    contas_ativas,
    despesa_para_edicao,
    essencialidade_efetiva,
    linha,
    pessoas_ativas,
    recentes,
    subcategoria,
    subcategorias_ativas,
    sugestoes_de_descricao,
    total_do_mes,
    ultimo_lancamento_do_usuario,
)
from freedom.util import destino_interno


def _opcoes():
    """Tudo que os selects precisam, numa só passada."""
    subs = subcategorias_ativas()
    return {
        "subcategorias": subs,
        "grupos": agrupar_por_categoria(subs),
        "contas": contas_ativas(),
        "pessoas": pessoas_ativas(),
    }


def _pendencias(opcoes):
    """O que impede o lançamento. Vazio = pode lançar."""
    faltando = []
    if not opcoes["subcategorias"]:
        faltando.append(
            ("uma subcategoria ativa (de categoria ativa)",
             url_for("cadastros.subcategorias_lista"), "Cadastrar subcategoria")
        )
    if not opcoes["contas"]:
        faltando.append(
            ("uma conta ativa", url_for("cadastros.contas_lista"),
             "Cadastrar conta")
        )
    if not opcoes["pessoas"]:
        faltando.append(
            ("uma pessoa ativa", url_for("cadastros.pessoas_lista"),
             "Cadastrar pessoa")
        )
    return faltando


def _preparar(form, opcoes):
    form.carregar_opcoes(opcoes["grupos"], opcoes["contas"], opcoes["pessoas"])
    return form


def _prioridade_a_gravar(form, sub):
    """Regra da aplicação: prioridade só existe em despesa não essencial.

    O banco só garante a faixa 1..4 (ver o cabeçalho de 01_schema.sql), então
    a limpeza acontece aqui — mesmo que o POST traga prioridade, se a
    essencialidade efetiva for Essencial ela vira NULL.
    """
    efetiva = essencialidade_efetiva(form.essencialidade_ou_none(), sub)
    if efetiva != NAO_ESSENCIAL:
        return None
    return form.prioridade_int()


def _contexto_lista():
    return {"linhas": recentes(), "resumo": total_do_mes(date.today())}


# --------------------------------------------------------------------------
# Tela principal
# --------------------------------------------------------------------------

@bp.route("/despesas")
@login_required
def despesas_tela():
    opcoes = _opcoes()
    pendencias = _pendencias(opcoes)
    if pendencias:
        return render_template(
            "lancamentos/despesas.html",
            pendencias=pendencias, form=None, sub_selecionada=None,
            **_contexto_lista()
        )

    form = _preparar(DespesaForm(), opcoes)

    # Pré-preenchimento: conta e pessoa do último lançamento deste usuário.
    ultimo = ultimo_lancamento_do_usuario(current_user.id)
    if ultimo:
        form.conta_id.data = ultimo["conta_id"]
        form.pessoa_id.data = ultimo["pessoa_id"]
    else:
        # Sem histórico: a pessoa do próprio usuário, conta em branco.
        form.pessoa_id.data = current_user.pessoa_id

    # Nenhuma subcategoria vem escolhida: o select abre em "Escolha a
    # subcategoria" e a classificacao so aparece depois da escolha.
    return render_template(
        "lancamentos/despesas.html",
        form=form, pendencias=[], sub_selecionada=None, **_contexto_lista()
    )


# --------------------------------------------------------------------------
# Classificação reativa (HTMX)
# --------------------------------------------------------------------------

@bp.route("/despesas/classificacao")
@login_required
def despesas_classificacao():
    """Resumo da classificação + campo prioridade quando fizer sentido."""
    sub = subcategoria(request.args.get("subcategoria_id", type=int))
    override = request.args.get("essencialidade") or None
    efetiva = essencialidade_efetiva(override, sub)

    prioridade = request.args.get("prioridade") or ""
    # Só faz sentido preservar a prioridade se o campo vai continuar existindo.
    if efetiva != NAO_ESSENCIAL:
        prioridade = ""

    return render_template(
        "lancamentos/_classificacao.html",
        sub=sub, efetiva=efetiva, prioridade=prioridade, override=override,
    )



# --------------------------------------------------------------------------
# Autocomplete de descricao
# --------------------------------------------------------------------------

@bp.route("/despesas/sugestoes")
@login_required
def despesas_sugestoes():
    """Lista de descricoes ja usadas que casam com o trecho digitado.

    Devolve fragmento vazio abaixo de 2 caracteres; o JS trata a lista vazia
    fechando o painel. So na tela de lancamento - editar e corrigir um
    registro especifico, nao repetir um anterior.
    """
    return render_template(
        "lancamentos/_sugestoes.html",
        sugestoes=sugestoes_de_descricao(request.args.get("q")),
    )


# --------------------------------------------------------------------------
# Gravação
# --------------------------------------------------------------------------

@bp.route("/despesas", methods=["POST"])
@login_required
def despesas_gravar():
    opcoes = _opcoes()
    if _pendencias(opcoes):
        abort(409)

    form = _preparar(DespesaForm(), opcoes)

    if form.validate_on_submit():
        sub = subcategoria(form.subcategoria_id.data)
        try:
            nova = executar(
                """
                INSERT INTO tb_despesas
                    (data, descricao, valor, subcategoria_id, conta_id,
                     pessoa_id, usuario_id, essencialidade, prioridade,
                     integra_ipca, observacoes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    form.data.data,
                    form.descricao.data.strip(),
                    form.valor_decimal,
                    form.subcategoria_id.data,
                    form.conta_id.data,
                    form.pessoa_id.data,
                    # Autoria vem sempre da sessão, nunca do formulário.
                    current_user.id,
                    form.essencialidade_ou_none(),
                    _prioridade_a_gravar(form, sub),
                    form.integra_ipca.data,
                    (form.observacoes.data or "").strip() or None,
                ),
                retornar=True,
            )
        except errors.CheckViolation:
            form.valor.errors = list(form.valor.errors) + [
                "O banco recusou este valor. Confira o que foi digitado."
            ]
        except errors.ForeignKeyViolation:
            form.subcategoria_id.errors = list(form.subcategoria_id.errors) + [
                "Uma das opções escolhidas não existe mais. Recarregue a página."
            ]
        else:
            # Formulário novo, preservando o que se repete entre lançamentos.
            limpo = _preparar(DespesaForm(formdata=None), opcoes)
            limpo.data.data = form.data.data
            limpo.conta_id.data = form.conta_id.data
            limpo.pessoa_id.data = form.pessoa_id.data
            limpo.essencialidade.data = form.essencialidade.data
            limpo.integra_ipca.data = form.integra_ipca.data
            limpo.mais_opcoes.data = form.mais_opcoes.data

            return render_template(
                "lancamentos/_gravado.html",
                item=linha(nova["id"]),
                form=limpo,
                resumo=total_do_mes(date.today()),
                sub_selecionada=None,
            )

    # Erro de validação: devolve o formulário com os erros, lista intacta.
    # Sempre 200 para o HTMX processar o fragmento.
    return render_template(
        "lancamentos/_formulario_oob.html",
        form=form,
        sub_selecionada=subcategoria(
            request.form.get("subcategoria_id", type=int)
        ),
    )


# --------------------------------------------------------------------------
# Edição
# --------------------------------------------------------------------------

@bp.route("/despesas/<int:despesa_id>/editar", methods=["GET", "POST"])
@login_required
def despesas_editar(despesa_id):
    registro = despesa_para_edicao(despesa_id)
    if registro is None:
        abort(404)

    retorno = destino_interno(request.args.get("retorno"))
    opcoes = _opcoes()
    # A subcategoria original entra nas opções mesmo se tiver sido desativada,
    # senão a edição perderia a classificação da despesa.
    if not any(s["id"] == registro["subcategoria_id"]
               for s in opcoes["subcategorias"]):
        original = subcategoria(registro["subcategoria_id"])
        if original:
            opcoes["grupos"] = list(opcoes["grupos"]) + [
                (f"{original['categoria_nome']} (inativa)",
                 [(original["id"], original["nome"])])
            ]

    if request.method == "POST":
        form = _preparar(DespesaForm(), opcoes)
    else:
        dados = dict(registro)
        dados["valor"] = f"{registro['valor']:.2f}".replace(".", ",")
        dados["essencialidade"] = registro["essencialidade"] or ""
        dados["prioridade"] = (
            str(registro["prioridade"]) if registro["prioridade"] else ""
        )
        form = _preparar(DespesaForm(data=dados), opcoes)

    if form.validate_on_submit():
        sub = subcategoria(form.subcategoria_id.data)
        try:
            executar(
                """
                UPDATE tb_despesas
                   SET data = %s, descricao = %s, valor = %s,
                       subcategoria_id = %s, conta_id = %s, pessoa_id = %s,
                       essencialidade = %s, prioridade = %s,
                       integra_ipca = %s, observacoes = %s
                 WHERE id = %s
                """,
                (
                    form.data.data,
                    form.descricao.data.strip(),
                    form.valor_decimal,
                    form.subcategoria_id.data,
                    form.conta_id.data,
                    form.pessoa_id.data,
                    form.essencialidade_ou_none(),
                    _prioridade_a_gravar(form, sub),
                    form.integra_ipca.data,
                    (form.observacoes.data or "").strip() or None,
                    despesa_id,
                ),
            )
            # usuario_id fica de fora do UPDATE de proposito: a autoria do
            # lancamento original e preservada.
        except errors.CheckViolation:
            form.valor.errors = list(form.valor.errors) + [
                "O banco recusou este valor. Confira o que foi digitado."
            ]
        else:
            flash("Despesa atualizada.", "sucesso")
            # Volta para a consulta com os mesmos filtros e pagina, quando foi
            # de la que se chegou aqui. So caminho interno e aceito.
            return redirect(retorno or url_for("lancamentos.despesas_tela"))

    return render_template(
        "lancamentos/despesa_editar.html",
        form=form,
        retorno=retorno,
        despesa=registro,
        sub_selecionada=subcategoria(form.subcategoria_id.data)
        if form.subcategoria_id.data else None,
    )


# --------------------------------------------------------------------------
# Exclusão física
# --------------------------------------------------------------------------

@bp.route("/despesas/<int:despesa_id>/excluir", methods=["POST"])
@login_required
def despesas_excluir(despesa_id):
    """Movimento se exclui; referência se desativa.

    tb_despesas não tem coluna de situação e um lançamento digitado errado é
    lixo, não histórico. DELETE físico, só nesta tabela.
    """
    apagada = executar(
        "DELETE FROM tb_despesas WHERE id = %s RETURNING id",
        (despesa_id,),
        retornar=True,
    )
    if apagada is None:
        abort(404)

    if request.args.get("origem") == "consulta":
        # Totais, resumo e paginacao mudam juntos: devolve o bloco inteiro.
        return resultados_apos_exclusao(request.args)

    # Tela de lancamento: a <tr> some pelo hx-swap do proprio botao e aqui vai
    # so o total do mes. Comportamento da rodada 4, inalterado.
    return render_template(
        "lancamentos/_total_oob.html", resumo=total_do_mes(date.today())
    )
