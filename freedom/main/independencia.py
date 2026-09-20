"""A rota da página de Independência financeira.

Só orquestra, como as das duas Análises: lê a query string, entrega a data e
deixa o resto com `servico_independencia.painel()`. Nenhuma conta e nenhum
texto moram aqui.

**A URL é o estado.** Um GET, recarga da página inteira, sem HTMX: a tela é
reproduzível por link, e os três campos de premissa são a própria query string
— `?r=4&tsr=4&s=50` é uma simulação que se manda por mensagem. Parâmetro
ausente, ilegível ou fora da faixa cai no valor vigente, em silêncio, como o
ano da Visão Anual.

**Nada é gravado.** A simulação vive na URL e morre com ela: `tb_configuracoes`
é lida e nunca escrita, aqui e no serviço. Quem grava premissa é a tela de
Parâmetros, para onde a nota do topo aponta.

Sem olho: só a Visão Anual tem.
"""

from datetime import date

from flask import render_template, request
from flask_login import login_required

from freedom.main import servico_independencia as servico
from freedom.main.routes import bp


@bp.route("/independencia")
@login_required
def independencia():
    return render_template("main/independencia.html",
                           **servico.painel(request.args, date.today()))
