"""As rotas da tela de Patrimônio: a foto mensal dos ativos.

Tela única, no molde de Receitas: a grade de uma data é o próprio editor, e
embaixo dela ficam os dois cards, a alocação por classe e o histórico de
fotos. Três rotas: a página (GET), a gravação (POST) e a exclusão de uma foto
inteira (POST).

Só orquestra. Conta, texto, travessão e SQL moram em `servico_patrimonio.py`.

**A data é o estado, e viaja na URL** (`?data=AAAA-MM-DD`). Trocar a data é um
GET com recarga da página inteira — a mesma exceção dos seletores de painel —,
e `?data=` ilegível ou futura cai no padrão em silêncio. No POST a regra é
outra, de propósito: ali alguém digitou uma data e mandou gravar, e uma foto
que fosse parar noutra data sem avisar seria pior que um erro de campo.

A gravação e a exclusão devolvem a grade no alvo principal e, **fora de
banda**, o bloco de cards + alocação + histórico: as duas ações mexem nas duas
regiões de uma vez, e devolver só uma deixaria um total velho na tela.
"""

from datetime import date

from flask import abort, redirect, render_template, request, url_for
from flask_login import login_required

from freedom import ipca
from freedom.lancamentos import bp
from freedom.lancamentos import servico_patrimonio as servico
from freedom.util import caixa_marcada, so_fragmento


def _corrigir(campos):
    """A caixa "Corrigir pelo IPCA" marcada E haver IPCA carregado.

    A segunda metade é da rota, e não do template: sem série carregada não há
    a que corrigir, e deixar a decisão para o Jinja seria decidir estado lá.
    """
    return caixa_marcada(campos.get("ipca")) and ipca.base_de_correcao() is not None


@bp.route("/patrimonio")
@login_required
def patrimonio_tela():
    hoje = date.today()
    data_foto = servico.data_valida(request.args.get("data"), hoje)
    return render_template(
        "lancamentos/patrimonio.html",
        **servico.painel(data_foto, hoje,
                         corrigir=_corrigir(request.args)))


@bp.route("/patrimonio", methods=["POST"])
@login_required
def patrimonio_gravar():
    """Acerta a foto da data. Nada é gravado se alguma linha não serve.

    A data vem do mesmo campo da barra de filtros (por `hx-include`), e não de
    um campo escondido: é o que permite recusá-la com erro no campo quando ela
    é futura. Data recusada usa a data VÁLIDA para remontar a grade — a tela
    tem de voltar mostrando alguma coisa, e o erro diz o que houve.
    """
    hoje = date.today()
    bruto = request.form.get("data")
    data_foto = servico.data_valida(bruto, hoje)
    corrigir = _corrigir(request.form)

    # Sem HTMX não há onde encaixar o fragmento, então a gravação nem começa e
    # a pessoa volta para a tela — a mesma regra do botão do IPCA (rodada 23).
    # O caminho existe porque o formulário leva o token CSRF num campo oculto:
    # sem ele, um POST sem JavaScript morreria em 400, que não é uma resposta.
    if not so_fragmento():
        return redirect(url_for("lancamentos.patrimonio_tela",
                                data=data_foto.isoformat(),
                                ipca="1" if corrigir else None))

    erro_data = servico.erro_da_data(bruto, hoje)

    # Só os ativos EM CARTEIRA são lidos, e são eles que delimitam o que a
    # gravação pode tocar: linha de posição encerrada não entra no upsert nem
    # no DELETE, nem que o corpo do POST traga o campo dela.
    ativos = servico.grade_da_data(data_foto)
    valores, erros, digitado = servico.ler_valores(request.form, ativos)

    if erro_data or erros:
        # Uma linha errada derruba a gravação inteira: meia foto no banco é um
        # total errado que ninguém vê. Sempre 200, para o HTMX trocar o
        # fragmento; a recusa aparece no campo.
        return render_template(
            "lancamentos/_patrimonio_resposta.html",
            **servico.painel(data_foto, hoje, corrigir=corrigir,
                             digitado=digitado, erros=erros,
                             erro_data=erro_data))

    vazios = [a["id"] for a in ativos if a["id"] not in valores]
    contagens = servico.gravar_foto(data_foto, valores, vazios)

    return render_template(
        "lancamentos/_patrimonio_resposta.html",
        **servico.painel(data_foto, hoje, corrigir=corrigir,
                         aviso=servico.texto_do_aviso(data_foto, contagens)))


@bp.route("/patrimonio/<data_foto>/excluir", methods=["POST"])
@login_required
def patrimonio_excluir(data_foto):
    """Apaga a foto inteira de uma data, com confirmação em dois passos.

    A data da GRADE viaja em `?data=`, e não é a mesma coisa que a data
    apagada: a resposta remonta a grade que está na tela. Quando as duas
    coincidem, os campos voltam a mostrar as sugestões do último valor
    conhecido — que é o que a grade de uma data sem foto mostra.
    """
    alvo = servico.data_de_texto(data_foto)
    if alvo is None:
        abort(404)
    quantas = servico.excluir_foto(alvo)
    if not quantas:
        abort(404)

    hoje = date.today()
    grade = servico.data_valida(request.args.get("data"), hoje)
    return render_template(
        "lancamentos/_patrimonio_resposta.html",
        **servico.painel(grade, hoje, corrigir=_corrigir(request.args),
                         aviso=servico.texto_da_exclusao(alvo, quantas)))
