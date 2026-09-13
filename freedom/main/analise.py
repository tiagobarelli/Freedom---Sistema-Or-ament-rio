"""Rota da Análise por subcategoria (`/analise/subcategoria`).

Só orquestra: lê os quatro parâmetros da URL, pede a série ao serviço e
escolhe o template. Toda conta e todo texto moram em `servico_analise.py`.

**A URL é o estado.** Tudo por GET, recarga da página inteira, sem HTMX: a
tela é reproduzível por link, o botão voltar desfaz o último filtro e abrir a
mesma URL em outra aba dá a mesma tela. Parâmetro inválido cai no padrão em
silêncio, como o ano da Visão Anual — menos o período personalizado, onde um
mês malformado ou invertido é erro de formulário, porque ali o usuário digitou
algo e merece saber o que houve.
"""

from datetime import date

from flask import render_template, request
from flask_login import login_required

from freedom import ipca
from freedom.main import servico_analise as servico
from freedom.main.routes import bp
from freedom.util import somar_meses


@bp.route("/analise/subcategoria")
@login_required
def analise_subcategoria():
    hoje = date.today()
    mes_corrente = date(hoje.year, hoje.month, 1)

    base = ipca.base_de_correcao()
    acervo = servico.intervalo_do_acervo()
    primeiro_acervo = acervo[0] if acervo else None

    sub_id = request.args.get("sub", type=int)
    # Subcategoria inexistente ou sem lançamento não é erro: é como se não
    # tivessem escolhido nenhuma, e a tela volta ao convite.
    nome_sub = servico.nome_da_subcategoria(sub_id) if sub_id else None

    periodo = servico.periodo_valido(request.args.get("periodo"))
    agrupar = servico.agrupamento_valido(request.args.get("agrupar"))
    de, ate = request.args.get("de", ""), request.args.get("ate", "")
    # A correção só é oferecida com IPCA carregado; sem base não há a que
    # corrigir, e a caixa vem desabilitada no formulário.
    corrigir = servico.correcao_pedida(request.args.get("ipca")) and base is not None

    primeiro, ultimo, erro = servico.resolver_periodo(
        periodo, de, ate, acervo, mes_corrente)

    resultado, sem_lancamento = None, False
    if nome_sub and primeiro and not erro:
        # A janela de 12 meses móveis olha 11 meses para trás do período
        # exibido; os demais agrupamentos leem só o que mostram.
        recuo = servico.MESES_MOVEIS - 1 if agrupar == servico.MOVEL else 0
        linhas = servico.linhas_por_mes(
            sub_id,
            somar_meses(primeiro, -recuo),
            somar_meses(ultimo, 1),
            base["numero_indice"] if base else None,
        )
        if linhas:
            resultado = servico.montar(
                linhas, primeiro, ultimo, agrupar, periodo, nome_sub,
                mes_corrente, primeiro_acervo,
                base_mes=base["mes"] if corrigir else None)
        else:
            sem_lancamento = True

    return render_template(
        "main/analise.html",
        grupos=servico.subcategorias_com_lancamento(),
        sub=sub_id if nome_sub else None,
        periodo=periodo,
        agrupar=agrupar,
        corrigir=corrigir,
        # O campo volta com o que o usuário escolheu, mas só se for um mês de
        # verdade: `<input type="month">` recusa texto fora do formato, mostra
        # o campo vazio e ainda avisa no console. Quem explica o que houve é a
        # mensagem de erro, não um valor que o navegador não sabe exibir.
        de=servico.texto_do_campo(de, primeiro, periodo),
        ate=servico.texto_do_campo(ate, ultimo, periodo),
        tem_ipca=base is not None,
        erro=erro,
        sem_lancamento=sem_lancamento,
        r=resultado,
        grafico=servico.para_grafico(resultado, corrigir) if resultado else None,
    )
