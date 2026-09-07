"""Blueprint de lançamentos (despesas nesta rodada; receitas ficam para outra)."""

from flask import Blueprint

bp = Blueprint("lancamentos", __name__, url_prefix="/lancamentos")

# Importado pelo efeito colateral de registrar as rotas em `bp`.
from freedom.lancamentos import consulta, despesas  # noqa: E402,F401

__all__ = ["bp"]
