"""Blueprint de lançamentos: despesas, receitas e a foto de patrimônio."""

from flask import Blueprint

bp = Blueprint("lancamentos", __name__, url_prefix="/lancamentos")

# Importados pelo efeito colateral de registrar as rotas em `bp`.
from freedom.lancamentos import (  # noqa: E402,F401
    consulta,
    despesas,
    patrimonio,
    receitas,
)

__all__ = ["bp"]
