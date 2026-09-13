"""Blueprint de cadastros: um módulo por entidade de referência."""

from flask import Blueprint

bp = Blueprint("cadastros", __name__, url_prefix="/cadastros")

# Importados pelo efeito colateral de registrar as rotas em `bp`.
from freedom.cadastros import (  # noqa: E402,F401
    categorias,
    contas,
    pessoas,
    ref_receitas,
    resumos_anuais,
    serie_ipca,
    subcategorias,
)

__all__ = ["bp"]
