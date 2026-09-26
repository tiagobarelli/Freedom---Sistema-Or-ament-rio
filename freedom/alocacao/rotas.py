"""Rotas da Alocação. Só orquestram: regra, conta e texto moram nos serviços.

**A URL é o estado**, como no Orçamento: `?modo=plano|balanceamento`, a
vigência aberta no modo Plano (`?plano=AAAA-MM-DD`) e, no Balanceamento, o
aporte e o caixa de cada classe. Valor fora da lista cai no padrão em
silêncio. O padrão do modo é o Balanceamento — é a leitura, e é o que se abre
mais vezes; sem plano, ele mesmo convida a ir montar um.

Quatro rotas: a tela (GET), criar plano (POST comum, recarga inteira — cria
um plano e troca a vigência aberta, é uma navegação), gravar a grade (POST
por HTMX, que devolve a grade) e excluir plano (POST por HTMX com
confirmação, que manda o navegador de volta à tela).
"""

from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.alocacao import balanceamento, bp, plano
from freedom.util import data_de_texto, data_por_extenso, so_fragmento

PLANO = "plano"
BALANCEAMENTO = "balanceamento"
MODOS = (BALANCEAMENTO, PLANO)


def _modo(texto):
    return texto if texto in MODOS else BALANCEAMENTO


def _tela_do_plano(data=None):
    return url_for("alocacao.alocacao_tela", modo=PLANO,
                   plano=data.isoformat() if data else None)


@bp.route("")
@login_required
def alocacao_tela():
    modo = _modo(request.args.get("modo"))
    hoje = date.today()
    servico = plano if modo == PLANO else balanceamento
    return render_template("alocacao/alocacao.html", modo=modo,
                           **servico.painel(request.args, hoje))


@bp.route("/plano", methods=["POST"])
@login_required
def alocacao_criar():
    """Abre um plano na data digitada, copiando o que vale nela.

    POST comum, sem HTMX: criar troca a vigência aberta, o seletor e a grade
    — é uma navegação. O campo de data vem com `novalidate` no formulário, e
    por isso a data ilegível chega aqui e volta com texto, em vez de travar o
    botão (a armadilha do `<input type="date">`).
    """
    data = data_de_texto(request.form.get("vigente_desde"))
    if data is None:
        flash("Informe a data em que o plano passa a valer.", "erro")
        return redirect(_tela_do_plano())
    try:
        origem = plano.criar(data)
    except errors.UniqueViolation:
        # A PK de tb_alocacao_planos: já há plano nessa data. Abre-se ele.
        flash(f"Já existe um plano vigente desde {data_por_extenso(data)}.",
              "erro")
        return redirect(_tela_do_plano(data))
    flash(plano.texto_da_criacao(data, origem), "sucesso")
    return redirect(_tela_do_plano(data))


@bp.route("/plano/<data_plano>", methods=["POST"])
@login_required
def alocacao_gravar(data_plano):
    """Acerta a grade do plano. Nada é gravado se algum bloco não fecha.

    Sempre 200 com a grade: com o aviso do que mudou, ou com as recusas no
    bloco que falhou. Sem HTMX não há onde encaixar o fragmento, e a pessoa
    volta para a tela — a regra da foto de patrimônio.
    """
    data = data_de_texto(data_plano)
    if data is None:
        abort(404)
    if not so_fragmento():
        return redirect(_tela_do_plano(data))
    try:
        contexto = plano.gravar_da_tela(data, request.form, date.today())
    except plano.PlanoInexistente:
        abort(404)
    return render_template("alocacao/_plano_grade.html", **contexto)


@bp.route("/plano/<data_plano>/excluir", methods=["POST"])
@login_required
def alocacao_excluir(data_plano):
    """Apaga o plano inteiro e manda o navegador de volta à tela.

    A confirmação é o `hx-confirm` do botão. A resposta é 204 com
    `HX-Redirect`: excluir troca o seletor e a grade de uma vez, e recarregar
    a página é mais honesto do que remendar os dois pedaços. O flash vai na
    sessão e aparece na tela seguinte.
    """
    data = data_de_texto(data_plano)
    if data is None or not plano.excluir(data):
        abort(404)
    flash(f"Plano de {data_por_extenso(data)} excluído.", "sucesso")
    return "", 204, {"HX-Redirect": _tela_do_plano()}
