"""Blueprint de configurações: parâmetros do sistema com vigência.

Uma tela só. O que muda de verdade aqui é o tempo: cada valor vale a partir de
uma data, e o passado nunca é reescrito.
"""

from flask import Blueprint

bp = Blueprint("configuracoes", __name__, url_prefix="/configuracoes")

# Importado pelo efeito colateral de registrar as rotas em `bp`.
from freedom.configuracoes import rotas  # noqa: E402,F401

__all__ = ["bp"]
