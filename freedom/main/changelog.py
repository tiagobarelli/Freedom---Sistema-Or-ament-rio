"""A rota da página de Histórico de versões.

Só orquestra, como a da Independência: o texto do changelog já foi lido e
renderizado uma vez, na subida do app (`freedom/versao.py`), e aqui só se
escolhe o template. Nenhuma leitura de disco por request.

O HTML entregue ao template **já vem marcado como seguro**, e quem o marcou
foi o servidor, com o motivo escrito lá: o markdown é um arquivo do
REPOSITÓRIO, versionado junto com o código, e não entrada de usuário. Nenhuma
tela do sistema escreve no `CHANGELOG.md`.

O número da versão do subtítulo NÃO é passado daqui: ele chega pelo mesmo
context processor que abastece o rodapé da sidebar, e é essa a prova de que
os dois lugares dizem a mesma coisa.
"""

from flask import current_app, render_template
from flask_login import login_required

from freedom.main.routes import bp


@bp.route("/changelog")
@login_required
def changelog():
    return render_template(
        "main/changelog.html", changelog_html=current_app.config["CHANGELOG_HTML"]
    )
