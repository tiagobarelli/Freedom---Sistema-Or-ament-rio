from freedom.main.routes import bp

# Importados pelo efeito colateral de registrar as rotas em `bp`.
from freedom.main import analise  # noqa: E402,F401
from freedom.main import independencia  # noqa: E402,F401

__all__ = ["bp"]
