"""Rotas de autenticacao: /login, /logout e a troca de senha."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from freedom.auth.forms import LoginForm, TrocaSenhaForm
from freedom.auth.models import User
from freedom.auth.servico import trocar_senha
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


def _recusar(campo, mensagem):
    """Pendura a recusa no campo, como fazem os cadastros: a tela volta com o
    texto embaixo do campo que errou, e não num aviso solto no topo."""
    campo.errors = list(campo.errors) + [mensagem]


@bp.route("/conta/senha", methods=["GET", "POST"])
@login_required
def alterar_senha():
    """Troca da própria senha, pela interface.

    POST comum com redirect para si mesma (PRG), e não HTMX: o sucesso é uma
    faixa de flash mais uma tela limpa, e recarregar a página depois disso não
    pode reenviar o formulário.

    Duas recusas moram aqui, cada uma com o texto no campo que errou (senha
    atual que não confere, nova igual à atual); as outras duas — tamanho
    mínimo e confirmação diferente — são validadores do formulário. Recusa
    NÃO grava nada, e a tela volta com os três campos de senha vazios: o
    `PasswordField` do WTForms nunca devolve o valor ao navegador.

    **A sessão atual continua valendo**, e as outras sessões do mesmo usuário
    também: trocar a senha não derruba ninguém. É decisão, e não esquecimento
    — o sistema é doméstico, não está na internet e tem dois usuários; quem
    troca a senha aqui troca por gosto, e não porque alguém entrou. Invalidar
    as outras sessões pediria versão de sessão no banco, e isso é mecanismo
    demais para o que há a proteger.

    Quem grava é `servico.trocar_senha`, a mesma função do
    `flask set-password`. Conferir a senha atual é trabalho DESTA rota: o
    comando é o caminho de quem não a tem.
    """
    form = TrocaSenhaForm()
    if form.validate_on_submit():
        if not check_password_hash(current_user.senha_hash, form.senha_atual.data):
            _recusar(form.senha_atual, "A senha atual não confere.")
        elif check_password_hash(current_user.senha_hash, form.senha_nova.data):
            # Comparada com o HASH, e não com o texto do primeiro campo: o que
            # a regra recusa é gravar de novo a senha que já está lá.
            _recusar(form.senha_nova, "A nova senha é igual à atual.")
        else:
            trocar_senha(current_user.login, form.senha_nova.data)
            flash("Senha alterada.", "sucesso")
            return redirect(url_for("auth.alterar_senha"))

    return render_template("auth/senha.html", form=form)
