"""Blueprint do orçamento: planejar o mês antes de ele acontecer.

Uma tela por mês. O mês nasce sugerido — copiado do anterior, ou tirado da
média dos doze meses fechados —, fica aberto para ajuste e depois se encerra.
Encerrado, vira registro histórico e só volta a mudar se for reaberto.
"""

from flask import Blueprint

bp = Blueprint("orcamento", __name__, url_prefix="/orcamento")

# Importado pelo efeito colateral de registrar as rotas em `bp`.
from freedom.orcamento import rotas  # noqa: E402,F401

__all__ = ["bp"]
