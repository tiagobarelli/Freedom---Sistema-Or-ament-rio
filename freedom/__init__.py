"""Freedom - sistema pessoal de controle financeiro.

Application factory. Rode com:
    set FLASK_APP=freedom
    flask run
ou pelo run.py na raiz.
"""

from flask import Flask, flash, make_response, redirect, request
from flask_login import LoginManager, login_url
from flask_wtf.csrf import CSRFProtect

from freedom import db, versao
from freedom.config import BASE_DIR, Config
from freedom.util import caminho_interno

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    # templates/ e static/ ficam na raiz do projeto, fora do pacote.
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config.from_object(config_class)

    csrf.init_app(app)
    db.init_app(app)

    # A versão do sistema e o histórico de versões saem do CHANGELOG.md da
    # raiz, lido UMA VEZ, aqui. Não há constante de versão em Python: fonte
    # única. Changelog ausente ou sem título derruba a subida, de propósito —
    # um sistema que não sabe que versão é não deve atender.
    app.config["VERSAO"], app.config["CHANGELOG_HTML"] = versao.carregar(
        BASE_DIR / "CHANGELOG.md"
    )

    # O rodapé da sidebar mostra o número em toda tela autenticada, e a página
    # de histórico o repete no subtítulo. Um valor, um lugar.
    @app.context_processor
    def versao_do_sistema():
        return {"versao": app.config["VERSAO"]}

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."
    login_manager.login_message_category = "info"

    @login_manager.unauthorized_handler
    def sem_sessao():
        """Quem chegou sem sessão. Dois caminhos, porque são duas perguntas.

        Fica colado no `login_view` e no `login_message` acima de propósito:
        os três dizem a mesma coisa — para onde vai quem não entrou, e com que
        aviso — e separá-los seria deixar dois lugares para discordar.

        **Requisição do HTMX** (cabeçalho `HX-Request`): o navegador tem de
        SAIR da página, não receber pedaço nenhum. Sem isso o XHR segue o 302
        até `/login`, volta com a página de login inteira e o HTMX a encaixa
        no alvo do disparador — o cartão "Faça login para continuar." aparecia
        dentro do formulário de despesa, no lugar das sugestões da descrição.
        A resposta é 204 sem corpo, e quem manda o navegador embora é o
        cabeçalho `HX-Redirect`, que o HTMX trata ANTES de qualquer troca.

        A tela em que a pessoa estava vem do `HX-Current-URL` (o disparador
        não sabe dela, e `request.url` aqui é a rota do fragmento, que não é
        lugar de voltar). `caminho_interno` reduz a URL ao caminho e recusa o
        que não for daqui; sem cabeçalho ou com cabeçalho torto, vai-se para o
        login sem `next`, que é melhor que um `next` inventado.

        **Requisição comum**: exatamente o que o Flask-Login já fazia, e pelo
        mesmo `login_url` que ele usa por dentro — mesmo flash, mesma
        categoria, mesmo `?next=` reduzido a caminho e query. Esta rodada não
        mexeu nesse caminho, e o relatório dela prova a URL idêntica.
        """
        flash(login_manager.login_message, login_manager.login_message_category)

        if "HX-Request" not in request.headers:
            return redirect(
                login_url(login_manager.login_view, next_url=request.url)
            )

        resposta = make_response("", 204)
        resposta.headers["HX-Redirect"] = login_url(
            login_manager.login_view,
            next_url=caminho_interno(request.headers.get("HX-Current-URL")),
        )
        return resposta

    from freedom.auth.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(user_id)

    from freedom.auth import bp as auth_bp
    from freedom.cadastros import bp as cadastros_bp
    from freedom.configuracoes import bp as configuracoes_bp
    from freedom.lancamentos import bp as lancamentos_bp
    from freedom.main import bp as main_bp
    from freedom.orcamento import bp as orcamento_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(cadastros_bp)
    app.register_blueprint(lancamentos_bp)
    app.register_blueprint(configuracoes_bp)
    app.register_blueprint(orcamento_bp)

    from freedom.util import formatar_numero, formatar_valor

    # Usado pela macro `reais`: 1234.56 -> '1.234,56'.
    app.add_template_filter(formatar_valor, "moeda")
    # Numero pt-BR com casas a escolher: 13.58 -> '13,6' com `| numero(1)`.
    # Existe para percentual em tela nao sair com ponto decimal.
    app.add_template_filter(formatar_numero, "numero")

    from freedom.cli import register_cli

    register_cli(app)

    return app
