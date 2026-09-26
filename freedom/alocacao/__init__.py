"""Blueprint da alocação da carteira: o plano e o balanceamento.

Uma tela, dois modos. No **Plano** se escrevem os alvos — de cada classe
sobre o total e de cada subclasse sobre a classe —, com vigência. No
**Balanceamento** se lê a última foto de patrimônio contra o plano vigente, e
se pede a conta de como repartir um aporte.

É o começo do módulo de investimentos (rodada 37). A foto de patrimônio não
muda de contrato: o valor de cada balde sai dela vezes a composição do ativo.
"""

from flask import Blueprint

bp = Blueprint("alocacao", __name__, url_prefix="/alocacao")

# Importado pelo efeito colateral de registrar as rotas em `bp`.
from freedom.alocacao import rotas  # noqa: E402,F401

__all__ = ["bp"]
