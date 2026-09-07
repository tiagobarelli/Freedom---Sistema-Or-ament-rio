"""Rotas de autenticacao: /login e /logout."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from freedom.auth.forms import LoginForm
from freedom.auth.models import User
from freedom.util import destino_interno

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_login(form.login.data)
        # Mensagem unica para login inexistente, inativo ou senha errada: nao
        # entregar a quem tenta adivinhar qual das tres coisas falhou.
        if user is None or not check_password_hash(user.senha_hash, form.senha.data):
            flash("Login ou senha invalidos.", "erro")
        else:
            login_user(user)
            proximo = destino_interno(request.args.get("next"))
            return redirect(proximo or url_for("main.index"))

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("Sessao encerrada.", "info")
    return redirect(url_for("auth.login"))
