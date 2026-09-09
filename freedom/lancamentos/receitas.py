"""Receitas: lançamento em série, consulta filtrada, edição e exclusão.

Uma página só (`/lancamentos/receitas`) com formulário em cima e o bloco de
resultados embaixo. A mesma rota devolve a página inteira ou só o bloco,
conforme o pedido venha do HTMX — igual à consulta de despesas.

Leitura vem de `vw_receitas` (servico_receitas.py); escrita vai em
`tb_receitas`.
"""

import math

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from psycopg import errors

from freedom.db import executar
from freedom.lancamentos import bp

from freedom.lancamentos.forms import ReceitaForm
# id_valido e pagina_pedida são a regra comum das duas telas de lista (id de
# filtro inexistente cai no padrão, página mínima 1); moram em servico.py para
# não haver duas cópias. `so_fragmento` subiu para util.py na rodada 13, quando
# a Visão Mensal virou a terceira tela a precisar dele.
from freedom.lancamentos.servico import (
    deslocar_mes,
    id_valido,
    mes_corrente,
    mes_valido,
    pagina_pedida,
    pessoas_ativas,
    rotulo_mes,
)
from freedom.lancamentos.servico_receitas import (
    POR_PAGINA,
    fonte,
    fontes_ativas,
    meses_com_lancamento,
    opcoes_de_filtro,
    pagina_de_receitas,
    pessoa,
    receita_para_edicao,
    resumo_por_categoria,
    totais_do_filtro,
)
from freedom.util import destino_interno, so_fragmento

# Parâmetros que compõem o estado da tela e viajam na URL. São deliberadamente
# diferentes dos nomes dos campos do formulário de lançamento (pessoa_id,
# ref_receita_id): o POST manda os dois conjuntos juntos, via hx-include, e
# nomes iguais se atropelariam.
PARAMETROS = ("mes", "pessoa", "fonte", "q", "pagina")


# --------------------------------------------------------------------------
# Filtros
# --------------------------------------------------------------------------

def ler_filtros(args, opcoes):
    """Lê e valida a query string (ou o corpo do POST). Nada aqui gera 500.

    Qualquer parâmetro sem sentido (mes=abc, pessoa=99999) volta para o padrão
    em silêncio.
    """
    mes = args.get("mes")
    return {
        "mes": int(mes) if mes_valido(mes) else mes_corrente(),
        "pessoa": id_valido(args, "pessoa", opcoes["pessoas"]),
        "fonte": id_valido(args, "fonte", opcoes["fontes"]),
        "q": (args.get("q") or "").strip()[:100] or None,
    }


def query_string(filtros, pagina=None, **troca):
    """Monta a query string desta tela, para links e para o parâmetro retorno."""
    dados = dict(filtros)
    dados["pagina"] = pagina or 1
    dados.update(troca)
    # O mês viaja sempre (a tela é sempre de um mês) e a página 1, por ser o
    # padrão, fica fora. O `== 1` é testado só na página: id de pessoa ou de
    # fonte pode ser 1 e não pode sumir da URL.
    return {
        k: v for k, v in dados.items()
        if k == "mes" or (v not in (None, "")
                          and not (k == "pagina" and v == 1))
    }


def _contexto(args):
    """Tudo que o bloco de resultados precisa, já filtrado e paginado."""
    opcoes = opcoes_de_filtro()
    filtros = ler_filtros(args, opcoes)

    totais = totais_do_filtro(filtros)
    quantidade = totais["quantidade"]
    paginas = max(1, math.ceil(quantidade / POR_PAGINA))

    # Página além do fim volta para a última: pagina=9999 não pode dar erro
    # nem tela em branco.
    pagina = min(pagina_pedida(args), paginas)

    linhas = pagina_de_receitas(filtros, pagina) if quantidade else []
    primeiro = (pagina - 1) * POR_PAGINA + 1 if quantidade else 0
    ultimo = primeiro + len(linhas) - 1 if quantidade else 0

    return {
        "filtros": filtros,
        "opcoes": opcoes,
        "totais": totais,
        "resumo": resumo_por_categoria(filtros),
        "linhas": linhas,
        "pagina": pagina,
        "paginas": paginas,
        "primeiro": primeiro,
        "ultimo": ultimo,
        "quantidade": quantidade,
        "rotulo_mes": rotulo_mes(filtros["mes"]),
        "mes_anterior": deslocar_mes(filtros["mes"], -1),
        "mes_seguinte": deslocar_mes(filtros["mes"], 1),
        "meses": meses_com_lancamento(filtros["mes"]),
        "query_string": query_string,
        # Caminho de volta para a edição preservar filtros e página.
        "retorno": url_for("lancamentos.receitas_tela",
                           **query_string(filtros, pagina)),
    }


# --------------------------------------------------------------------------
# Formulário
# --------------------------------------------------------------------------

def _opcoes():
    """O que os selects de lançamento oferecem: só o que está ativo.

    O `ativo=True` é acrescentado à mão porque `pessoas_ativas()` não traz a
    coluna — ela só devolve ativas. A macro do formulário usa esse campo para
    marcar "(inativa)", o que na prática só acontece na edição, quando a
    pessoa original desativada é reanexada às opções.
    """
    return {
        "fontes": fontes_ativas(),
        "pessoas": [dict(p, ativo=True) for p in pessoas_ativas()],
    }


def _pendencias(opcoes):
    """O que impede o lançamento. Vazio = pode lançar."""
    faltando = []
    if not opcoes["fontes"]:
        faltando.append(
            ("uma fonte de receita ativa",
             url_for("cadastros.ref_receitas_lista"), "Cadastrar fonte")
        )
    if not opcoes["pessoas"]:
        faltando.append(
            ("uma pessoa ativa", url_for("cadastros.pessoas_lista"),
             "Cadastrar pessoa")
        )
    return faltando


def _preparar(form, opcoes):
    form.carregar_opcoes(opcoes["fontes"], opcoes["pessoas"])
    return form


# --------------------------------------------------------------------------
# Tela principal
# --------------------------------------------------------------------------

@bp.route("/receitas")
@login_required
def receitas_tela():
    contexto = _contexto(request.args)

    # Pedido de fragmento não remonta o formulário: ele fica fora de
    # #resultados-receitas e não é trocado quando um filtro muda.
    if so_fragmento():
        return render_template("lancamentos/_receitas_resultados.html", **contexto)

    opcoes = _opcoes()
    pendencias = _pendencias(opcoes)
    form = None
    if not pendencias:
        form = _preparar(ReceitaForm(), opcoes)
        # Nenhuma fonte vem escolhida: o select abre em "Escolha a fonte".
        # A pessoa começa em quem está logado, que é quem mais lança para si.
        form.pessoa_id.data = current_user.pessoa_id

    return render_template(
        "lancamentos/receitas.html",
        form=form, pendencias=pendencias, **contexto
    )


# --------------------------------------------------------------------------
# Gravação (lançamento em série)
# --------------------------------------------------------------------------

@bp.route("/receitas", methods=["POST"])
@login_required
def receitas_gravar():
    opcoes = _opcoes()
    if _pendencias(opcoes):
        abort(409)

    form = _preparar(ReceitaForm(), opcoes)

    if form.validate_on_submit():
        try:
            executar(
                """
                INSERT INTO tb_receitas
                    (data, descricao, valor, ref_receita_id, pessoa_id,
                     usuario_id, anotacoes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    form.data.data,
                    form.descricao.data.strip(),
                    form.valor_decimal,
                    form.ref_receita_id.data,
                    form.pessoa_id.data,
                    # Autoria vem sempre da sessão, nunca do formulário.
                    current_user.id,
                    (form.anotacoes.data or "").strip() or None,
                ),
            )
        except errors.CheckViolation:
            form.valor.errors = list(form.valor.errors) + [
                "O banco recusou este valor. Confira o que foi digitado."
            ]
        except errors.ForeignKeyViolation:
            form.ref_receita_id.errors = list(form.ref_receita_id.errors) + [
                "Uma das opções escolhidas não existe mais. Recarregue a página."
            ]
        else:
            # Formulário novo, preservando o que se repete entre lançamentos.
            limpo = _preparar(ReceitaForm(formdata=None), opcoes)
            limpo.data.data = form.data.data
            limpo.ref_receita_id.data = form.ref_receita_id.data
            limpo.pessoa_id.data = form.pessoa_id.data

            # O bloco de resultados é recalculado com os filtros vigentes, que
            # o hx-include mandou junto no POST: receita de outro mês não pode
            # aparecer na lista, e o total tem que continuar batendo.
            return render_template(
                "lancamentos/_receita_gravada.html",
                form=limpo, **_contexto(request.form)
            )

    # Erro de validação: devolve o formulário com os erros e a lista intacta.
    # Sempre 200 para o HTMX processar o fragmento.
    return render_template("lancamentos/_receita_erro.html", form=form)


# --------------------------------------------------------------------------
# Edição
# --------------------------------------------------------------------------

@bp.route("/receitas/<int:receita_id>/editar", methods=["GET", "POST"])
@login_required
def receitas_editar(receita_id):
    registro = receita_para_edicao(receita_id)
    if registro is None:
        abort(404)

    retorno = destino_interno(request.args.get("retorno"))
    opcoes = _opcoes()
    # A fonte original entra nas opções mesmo desativada, senão a edição
    # perderia a classificação que a receita já tinha.
    if not any(f["id"] == registro["ref_receita_id"] for f in opcoes["fontes"]):
        original = fonte(registro["ref_receita_id"])
        if original:
            opcoes["fontes"] = list(opcoes["fontes"]) + [original]
    # Mesma ideia para a pessoa: quem recebeu não some da edição por ter sido
    # desativada depois.
    if not any(p["id"] == registro["pessoa_id"] for p in opcoes["pessoas"]):
        original = pessoa(registro["pessoa_id"])
        if original:
            opcoes["pessoas"] = list(opcoes["pessoas"]) + [original]

    if request.method == "POST":
        form = _preparar(ReceitaForm(), opcoes)
    else:
        dados = dict(registro)
        dados["valor"] = f"{registro['valor']:.2f}".replace(".", ",")
        form = _preparar(ReceitaForm(data=dados), opcoes)

    if form.validate_on_submit():
        try:
            executar(
                """
                UPDATE tb_receitas
                   SET data = %s, descricao = %s, valor = %s,
                       ref_receita_id = %s, pessoa_id = %s, anotacoes = %s
                 WHERE id = %s
                """,
                (
                    form.data.data,
                    form.descricao.data.strip(),
                    form.valor_decimal,
                    form.ref_receita_id.data,
                    form.pessoa_id.data,
                    (form.anotacoes.data or "").strip() or None,
                    receita_id,
                ),
            )
            # usuario_id fica de fora do UPDATE de propósito: a autoria do
            # lançamento original é preservada.
        except errors.CheckViolation:
            form.valor.errors = list(form.valor.errors) + [
                "O banco recusou este valor. Confira o que foi digitado."
            ]
        else:
            flash("Receita atualizada.", "sucesso")
            # Volta para a lista com os mesmos filtros e página, quando foi de
            # lá que se chegou aqui. Só caminho interno é aceito.
            return redirect(retorno or url_for("lancamentos.receitas_tela"))

    return render_template(
        "lancamentos/receita_editar.html",
        form=form, retorno=retorno, receita=registro
    )


# --------------------------------------------------------------------------
# Exclusão física
# --------------------------------------------------------------------------

@bp.route("/receitas/<int:receita_id>/excluir", methods=["POST"])
@login_required
def receitas_excluir(receita_id):
    """Movimento se exclui; referência se desativa.

    tb_receitas não tem coluna de situação e um lançamento digitado errado é
    lixo, não histórico. DELETE físico, só nesta tabela.
    """
    apagada = executar(
        "DELETE FROM tb_receitas WHERE id = %s RETURNING id",
        (receita_id,),
        retornar=True,
    )
    if apagada is None:
        abort(404)

    # Apagar uma linha mexe em lista, total, resumo e paginação de uma vez:
    # devolve o bloco inteiro, já recalculado com os filtros vigentes.
    return render_template(
        "lancamentos/_receitas_resultados.html", **_contexto(request.args)
    )
