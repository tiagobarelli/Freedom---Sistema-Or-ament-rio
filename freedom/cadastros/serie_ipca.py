"""Tela da série do IPCA (`/cadastros/ipca`): leitura e o botão que a atualiza.

Fica no grupo Cadastros pelo mesmo motivo dos resumos anuais: é referência que
o sistema consulta, não movimento. A diferença é que aqui o dono não digita
nada — quem enche `tb_ipca` é o IBGE, por dois caminhos que são a **mesma
função** (`ipca.carregar`): o comando `flask carregar-ipca` e o botão
"Atualizar do IBGE" desta tela.

O nome do módulo é `serie_ipca` e não `ipca` para não colidir com
`freedom/ipca.py`, que é o dono da carga, da consulta e de todo texto que a
tela mostra. Aqui só sobra o que é de rota: ler o modo, escolher o template e
traduzir a falha em status HTTP.

Sem formulário do WTForms: o POST não tem campo para validar — é um gatilho.
O CSRF vem do `hx-headers` do `<body>` e também de um campo escondido, que é o
que faz o POST sem JavaScript chegar à rota (e ser redirecionado) em vez de
morrer em 400.
"""

from datetime import date

import psycopg
from flask import redirect, render_template, request, url_for
from flask_login import login_required

from freedom import ipca
from freedom.cadastros import bp
from freedom.util import MESES_CURTOS, so_fragmento

# As duas falhas que a tela sabe mostrar, e os dois únicos status de erro que
# o `htmx-config` do base.html manda trocar nesta tela: 502 quando o IBGE não
# respondeu ou respondeu torto, 503 quando o banco recusou. 500 fica de fora
# de propósito — um 500 não tratado traz a página de erro do Flask, e ela não
# pode cair dentro do cartão.
FALHA_IBGE = 502
FALHA_BANCO = 503


def _contexto(modo, faixa=None):
    """Tudo o que a tela mostra, do mesmo jeito no GET e na resposta do botão.

    A dica de mês provável nasce aqui porque é a única coisa da tela que
    depende do relógio; `ipca.texto_da_dica` recebe a data e não a lê.
    """
    matriz = ipca.matriz(ipca.serie(), modo)
    return {
        "ipca": matriz,
        "meses": MESES_CURTOS,
        "faixa": faixa,
        "dica": ipca.texto_da_dica(date.today(), matriz["ultimo"]),
    }


@bp.route("/ipca")
@login_required
def serie_ipca():
    """`/cadastros/ipca?modo=variacao|indice`. Modo inválido não gera erro."""
    modo = ipca.modo_valido(request.args.get("modo"))
    return render_template("cadastros/serie_ipca.html", **_contexto(modo))


@bp.route("/ipca/atualizar", methods=["POST"])
@login_required
def serie_ipca_atualizar():
    """Busca no IBGE e devolve o cartão inteiro, mais o subtítulo fora de banda.

    O cartão inteiro, e não só a linha nova: um mês a mais muda a célula do
    mês, o "No ano" daquele ano, a nota do ano incompleto e a dica — devolver
    só a célula deixaria três números velhos na tela.
    """
    modo = ipca.modo_valido(request.form.get("modo"))

    # Rota só de fragmento: sem HTMX não há onde encaixar a resposta, então a
    # carga nem começa e a pessoa volta para a tela.
    if not so_fragmento():
        return redirect(url_for("cadastros.serie_ipca", modo=modo))

    try:
        resultado = ipca.carregar(ipca.TEMPO_LIMITE_WEB)
    except ipca.ErroIpca as erro:
        faixa = {"texto": ipca.texto_do_erro(erro), "erro": True}
        status = FALHA_BANCO if erro.etapa == ipca.ETAPA_BANCO else FALHA_IBGE
    except psycopg.Error as erro:
        # Cinto além do suspensório: `gravar` já traduz o erro do banco em
        # ErroIpca, mas um psycopg que escape por outro caminho não pode virar
        # traceback na cara de quem clicou.
        faixa = {"texto": f"Falha ao gravar: {str(erro).strip()}", "erro": True}
        status = FALHA_BANCO
    else:
        faixa = {"texto": ipca.texto_da_faixa(resultado), "erro": False}
        status = 200

    return render_template("cadastros/_resposta_ipca.html",
                           **_contexto(modo, faixa)), status
