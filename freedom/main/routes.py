"""Rotas principais. A página inicial é a Visão Anual: o painel do ano."""

from flask import (Blueprint, abort, redirect, render_template, request,
                   url_for)
from flask_login import login_required

from freedom.main import servico, servico_mensal
from freedom.util import MESES, so_fragmento

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    """Painel do ano. O ano vem por GET (`/?ano=2026`) e nunca gera erro.

    A rota só orquestra: a lista de anos, a validação do que veio na URL e a
    composição de cards, gráficos e tabelas moram em `servico.py`, que lê o ano
    uma vez só para os três.
    """
    anos = servico.anos_com_lancamento()
    ano = servico.ano_valido(request.args.get("ano"), anos)
    painel = servico.painel_do_ano(ano)
    return render_template(
        "main/index.html",
        ano=ano,
        anos=anos,
        cards=painel["cards"],
        graficos=painel["graficos"],
        tabelas=painel["tabelas"],
    )


@bp.route("/mensal")
@login_required
def mensal():
    """Painel do mês (`/mensal?ano=2026&mes=2&ordem=nome`). Nunca gera erro.

    Os três parâmetros vêm por GET e caem no padrão em silêncio quando não
    servem — mês corrente para ano e mês, maior gasto para a ordem. Como na
    Visão Anual, a rota só orquestra: validação e composição moram no serviço,
    aqui o `servico_mensal.py`. A lista de anos é a mesma da Anual, lida da
    mesma função.
    """
    anos = servico.anos_com_lancamento()
    ano = servico.ano_valido(request.args.get("ano"), anos)
    mes = servico_mensal.mes_valido(request.args.get("mes"))
    ordem = servico_mensal.ordem_valida(request.args.get("ordem"))
    painel = servico_mensal.painel_do_mes(ano, mes, ordem)
    return render_template(
        "main/mensal.html",
        ano=ano,
        anos=anos,
        mes=mes,
        meses=MESES,
        ordem=ordem,
        periodo=servico_mensal.nome_do_periodo(ano, mes),
        cards=painel["cards"],
        tem_despesa=painel["tem_despesa"],
        tabelas=painel["tabelas"],
    )


@bp.route("/mensal/categoria/<int:categoria_id>")
@login_required
def detalhe_categoria(categoria_id):
    """Fragmento com os lançamentos de uma categoria no mês em exibição.

    Só existe como fragmento: quem chegar aqui pela barra de endereço (sem
    HX-Request, ou restaurando o histórico) vai para a Visão Mensal do mesmo
    período, que é a tela de onde a linha expande. Uma versão de página
    inteira seria uma segunda tela para manter, e ninguém a pediu.

    Os três parâmetros seguem a regra da tela e caem no padrão em silêncio; o
    id, não: ele vem de um link que a própria tela montou, e um id que não
    existe é erro de quem chamou, não filtro inválido.
    """
    anos = servico.anos_com_lancamento()
    ano = servico.ano_valido(request.args.get("ano"), anos)
    mes = servico_mensal.mes_valido(request.args.get("mes"))
    ordem = servico_mensal.ordem_valida(request.args.get("ordem"))

    if not so_fragmento():
        return redirect(url_for("main.mensal", ano=ano, mes=mes, ordem=ordem))

    categoria = servico_mensal.categoria(categoria_id)
    if categoria is None:
        abort(404)

    return render_template(
        "main/_detalhe_categoria.html",
        categoria=categoria,
        periodo=servico_mensal.nome_do_periodo(ano, mes),
        detalhe=servico_mensal.detalhe_da_categoria(ano, mes, categoria_id),
        # Caminho de volta da edição: o mesmo mecanismo da consulta de
        # despesas (`?retorno=`, validado por `destino_interno`), com o
        # período e a ordem que estão na tela.
        retorno=url_for("main.mensal", ano=ano, mes=mes, ordem=ordem),
    )
