"""Rotas principais. A página inicial é a Visão Anual: o painel do ano."""

from flask import Blueprint, render_template, request
from flask_login import login_required

from freedom.main import servico, servico_mensal
from freedom.util import MESES

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
