"""Rotas principais. A página inicial é a Visão Anual: o painel do ano."""

from flask import Blueprint, render_template, request
from flask_login import login_required

from freedom.main import servico

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
