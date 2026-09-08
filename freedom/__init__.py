"""Freedom - sistema pessoal de controle financeiro.

Application factory. Rode com:
    set FLASK_APP=freedom
    flask run
ou pelo run.py na raiz.
"""

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from freedom import db
from freedom.config import BASE_DIR, Config

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

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faca login para continuar."
    login_manager.login_message_category = "info"

    from freedom.auth.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(user_id)

    from freedom.auth import bp as auth_bp
    from freedom.cadastros import bp as cadastros_bp
    from freedom.configuracoes import bp as configuracoes_bp
    from freedom.lancamentos import bp as lancamentos_bp
    from freedom.main import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(cadastros_bp)
    app.register_blueprint(lancamentos_bp)
    app.register_blueprint(configuracoes_bp)

    from freedom.util import formatar_valor

    # Usado pela macro `reais`: 1234.56 -> '1.234,56'.
    app.add_template_filter(formatar_valor, "moeda")

    from freedom.cli import register_cli

    register_cli(app)

    return app
