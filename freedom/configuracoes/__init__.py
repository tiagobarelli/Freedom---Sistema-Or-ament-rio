"""Blueprint de configurações: o que é do sistema, e não do dinheiro.

Duas telas, um módulo cada:

- `rotas` — os **parâmetros com vigência** (`/configuracoes`), onde o que muda
  de verdade é o tempo: cada valor vale a partir de uma data, e o passado
  nunca é reescrito. O endpoint continua `configuracoes_tela` e a URL continua
  `/configuracoes`; só o nome visível virou "Parâmetros" na rodada 25;
- `backup` — a exportação do banco (`/configuracoes/backup`), rodada 25.

Até a 24 o grupo era um item só e vivia no fim de Cadastros. Com a segunda
tela virou grupo próprio na sidebar.
"""

from flask import Blueprint

bp = Blueprint("configuracoes", __name__, url_prefix="/configuracoes")

# Importados pelo efeito colateral de registrar as rotas em `bp`.
from freedom.configuracoes import backup, rotas  # noqa: E402,F401

__all__ = ["bp"]
