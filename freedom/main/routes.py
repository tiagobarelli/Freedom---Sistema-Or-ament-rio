"""Rotas principais. Nesta rodada, so a pagina inicial protegida."""

from flask import Blueprint, render_template
from flask_login import current_user, login_required

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def index():
    return render_template("main/index.html", usuario=current_user)
