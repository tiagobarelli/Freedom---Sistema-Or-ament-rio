"""Rotas do orçamento. Só orquestram: regra e leitura moram em `servico.py`.

Duas famílias de URL:

- as do MÊS carregam o período no caminho (`/orcamento/2026-09/receita`),
  porque a receita, o encerramento e o acréscimo de linha são atos sobre o mês;
- as da LINHA carregam só o id (`/orcamento/linha/42`), porque a linha já sabe
  de que mês é — e é o mês dela que diz se ela pode mudar.

Toda escrita bem-sucedida devolve o **corpo inteiro** do mês. É deliberado:
editar uma linha muda o subtotal da categoria dela, o total planejado, a
poupança e a taxa; excluir muda também o combobox de subcategorias
disponíveis. Devolver só a `<tr>` deixaria quatro números velhos na tela. O
alvo declarado no HTML é a própria linha (que é o que a resposta de ERRO
precisa trocar) e, no sucesso, o servidor redireciona o swap com `HX-Retarget`
— mesmo padrão da tela de configurações.
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import login_required
from psycopg import errors

from freedom.orcamento import bp, servico
from freedom.orcamento.forms import LinhaForm, NovaLinhaForm, ReceitaForm
from freedom.orcamento.servico import RegraDoOrcamento
from freedom.util import MESES

# Resposta de uma regra recusada: 409 (conflito com o estado do recurso), não
# 400 nem 500. O corpo é a faixa de aviso que o HTMX encaixa no topo da tela.
CONFLITO = 409


def _corpo(ano_mes, **extra):
    """O bloco inteiro do mês, que é a resposta de toda escrita bem-sucedida."""
    painel = servico.painel_do_mes(ano_mes)
    if painel is None:
        abort(404)
    return render_template("orcamento/_corpo.html", p=painel, **extra)


def _recolocar(ano_mes, **extra):
    """`_corpo` com as instruções para o HTMX trocar o bloco, e não a linha."""
    return _corpo(ano_mes, **extra), 200, {
        "HX-Retarget": "#orcamento-corpo",
        "HX-Reswap": "innerHTML",
    }


def _aviso(mensagem):
    """Regra recusada vira faixa legível, sempre no mesmo lugar da tela."""
    return render_template("orcamento/_aviso.html", mensagem=mensagem), CONFLITO, {
        "HX-Retarget": "#orcamento-aviso",
        "HX-Reswap": "innerHTML",
    }


def _mes_da_url(texto):
    ano_mes = servico.mes_da_url(texto)
    if ano_mes is None:
        abort(404)
    return ano_mes


def _linha(linha_id):
    registro = servico.linha(linha_id)
    if registro is None:
        abort(404)
    return registro


# --------------------------------------------------------------------------
# A tela
# --------------------------------------------------------------------------

@bp.route("")
@login_required
def orcamento_tela():
    """`/orcamento?ano=2026&mes=9`. Sem parâmetro válido, escolhe sozinha.

    A ordem de preferência é a que a pessoa espera ao abrir a tela: o mês
    corrente, se ele estiver orçado; senão o orçamento mais recente, que é
    onde o trabalho parou; senão a tela vazia com o convite para criar.
    """
    orcados = servico.meses_com_orcamento()
    ano_mes = servico.mes_escolhido(request.args.get("ano"),
                                    request.args.get("mes"), orcados)
    return render_template(
        "orcamento/orcamento.html",
        p=servico.painel_do_mes(ano_mes) if ano_mes else None,
        ano_mes=ano_mes,
        # Rótulos prontos: quem sabe escrever "setembro de 2026" é o servidor,
        # como em toda outra tela deste projeto.
        anos=sorted({o.year for o in orcados}, reverse=True),
        meses=[{"numero": o.month, "rotulo": MESES[o.month - 1].capitalize()}
               for o in sorted(orcados)
               if ano_mes and o.year == ano_mes.year],
        criaveis=[{"valor": servico.texto_do_mes(c),
                   "rotulo": servico.nome_do_periodo(c).capitalize()}
                  for c in servico.meses_criaveis()],
    )


# --------------------------------------------------------------------------
# Ciclo de vida do mês
# --------------------------------------------------------------------------

@bp.route("/criar", methods=["POST"])
@login_required
def orcamento_criar():
    """Abre o mês com as linhas sugeridas. Recarrega a tela inteira.

    Sem HTMX de propósito: criar troca o mês exibido, o seletor, o combobox e
    tudo o mais — é uma navegação, não um pedaço de tela.
    """
    ano_mes = _mes_da_url(request.form.get("ano_mes"))
    try:
        servico.criar(ano_mes)
    except errors.UniqueViolation:
        # A PK de tb_orcamento_meses. Dois cliques no mesmo botão chegam aqui.
        return _erro_de_tela(
            f"{servico.nome_do_periodo(ano_mes).capitalize()} já tem orçamento.")
    except RegraDoOrcamento as regra:
        return _erro_de_tela(str(regra))
    return _redirecionar(ano_mes)


@bp.route("/<mes>/encerrar", methods=["POST"])
@login_required
def orcamento_encerrar(mes):
    ano_mes = _mes_da_url(mes)
    try:
        servico.encerrar(ano_mes)
    except RegraDoOrcamento as regra:
        return _aviso(str(regra))
    return _recolocar(ano_mes)


@bp.route("/<mes>/reabrir", methods=["POST"])
@login_required
def orcamento_reabrir(mes):
    ano_mes = _mes_da_url(mes)
    try:
        servico.reabrir(ano_mes)
    except RegraDoOrcamento as regra:
        return _aviso(str(regra))
    return _recolocar(ano_mes)


@bp.route("/<mes>/excluir", methods=["POST"])
@login_required
def orcamento_excluir(mes):
    """Apaga o mês aberto e volta para a tela, que escolhe outro sozinha."""
    ano_mes = _mes_da_url(mes)
    try:
        servico.excluir_mes(ano_mes)
    except RegraDoOrcamento as regra:
        return _aviso(str(regra))
    return _redirecionar(None)


# --------------------------------------------------------------------------
# Receita planejada do mês
# --------------------------------------------------------------------------

@bp.route("/<mes>/receita/editar")
@login_required
def orcamento_receita_form(mes):
    ano_mes = _mes_da_url(mes)
    cabecalho = servico.mes(ano_mes)
    if cabecalho is None:
        abort(404)
    form = ReceitaForm(data={"valor": _texto(cabecalho["receita_planejada"])})
    return render_template("orcamento/_receita_edicao.html",
                           form=form, mes_url=mes)


@bp.route("/<mes>/receita")
@login_required
def orcamento_receita_cancelar(mes):
    """Cancelar a edição da receita: o bloco de leitura de volta."""
    ano_mes = _mes_da_url(mes)
    painel = servico.painel_do_mes(ano_mes)
    if painel is None:
        abort(404)
    return render_template("orcamento/_receita.html", p=painel)


@bp.route("/<mes>/receita", methods=["POST"])
@login_required
def orcamento_receita(mes):
    ano_mes = _mes_da_url(mes)
    form = ReceitaForm()
    if form.validate_on_submit():
        try:
            servico.gravar_receita(ano_mes, form.valor_decimal)
        except RegraDoOrcamento as regra:
            return _aviso(str(regra))
        return _recolocar(ano_mes)
    return render_template("orcamento/_receita_edicao.html",
                           form=form, mes_url=mes)


# --------------------------------------------------------------------------
# Linhas
# --------------------------------------------------------------------------

@bp.route("/linha/<int:linha_id>/editar")
@login_required
def orcamento_linha_form(linha_id):
    registro = _linha(linha_id)
    form = LinhaForm(data={"valor": _texto(registro["valor_planejado"])})
    return render_template("orcamento/_linha_edicao.html",
                           form=form, l=registro)


@bp.route("/linha/<int:linha_id>")
@login_required
def orcamento_linha(linha_id):
    """Cancelar a edição: a linha de leitura de volta, como estava.

    As duas referências são recalculadas aqui também — a linha sozinha não
    pode voltar com números diferentes dos que o resto da tabela mostra.
    """
    registro = _linha(linha_id)
    ano_mes = registro["ano_mes"]
    return render_template("orcamento/_linha.html", l=dict(
        registro,
        media=servico.medias_de_12_meses(ano_mes).get(
            registro["subcategoria_id"], servico.ZERO),
        realizado=servico.realizado_do_mes_anterior(ano_mes).get(
            registro["subcategoria_id"], servico.ZERO),
    ), aberto=registro["encerrado_em"] is None)


@bp.route("/linha/<int:linha_id>", methods=["POST"])
@login_required
def orcamento_linha_gravar(linha_id):
    registro = _linha(linha_id)
    form = LinhaForm()
    if form.validate_on_submit():
        try:
            servico.gravar_valor(linha_id, form.valor_decimal)
        except RegraDoOrcamento as regra:
            return _aviso(str(regra))
        return _recolocar(registro["ano_mes"])
    return render_template("orcamento/_linha_edicao.html",
                           form=form, l=registro)


@bp.route("/linha/<int:linha_id>/excluir", methods=["POST"])
@login_required
def orcamento_linha_excluir(linha_id):
    registro = _linha(linha_id)
    try:
        servico.excluir_linha(linha_id)
    except RegraDoOrcamento as regra:
        return _aviso(str(regra))
    return _corpo(registro["ano_mes"])


@bp.route("/<mes>/linhas", methods=["POST"])
@login_required
def orcamento_linha_nova(mes):
    ano_mes = _mes_da_url(mes)
    form = NovaLinhaForm()
    form.disponiveis = servico.subcategorias_disponiveis(ano_mes)
    if form.validate_on_submit():
        try:
            servico.acrescentar_linha(
                ano_mes, form.subcategoria_id.data, form.valor_decimal)
        except RegraDoOrcamento as regra:
            return _aviso(str(regra))
        except errors.UniqueViolation:
            # uq_orcamentos_subcategoria_ano_mes: dois envios do mesmo form.
            form.subcategoria_id.errors = list(form.subcategoria_id.errors) + [
                "Esta subcategoria já está no mês."]
        else:
            # O alvo declarado no formulário é o próprio formulário (é o que o
            # erro precisa trocar); no sucesso o corpo inteiro toma o lugar
            # dele, e sem o HX-Retarget a tabela nova entraria DENTRO do
            # formulário de acrescentar.
            return _recolocar(ano_mes)
    return render_template("orcamento/_nova_linha.html",
                           form=form, p=servico.painel_do_mes(ano_mes))


# --------------------------------------------------------------------------
# Auxiliares de resposta
# --------------------------------------------------------------------------

def _texto(valor):
    """Decimal -> o texto que a pessoa vê no input, com vírgula."""
    return f"{valor:.2f}".replace(".", ",")


def _redirecionar(ano_mes):
    """Volta para a tela do mês (ou para a escolha automática)."""
    if ano_mes is None:
        return redirect(url_for("orcamento.orcamento_tela"))
    return redirect(url_for("orcamento.orcamento_tela",
                            ano=ano_mes.year, mes=ano_mes.month))


def _erro_de_tela(mensagem):
    """Erro de uma ação de página inteira: volta para a tela com a faixa."""
    flash(mensagem, "erro")
    return redirect(url_for("orcamento.orcamento_tela"))
