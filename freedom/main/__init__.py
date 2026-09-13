from freedom.main.routes import bp

# Importado pelo efeito colateral de registrar a rota em `bp`.
from freedom.main import analise  # noqa: E402,F401

__all__ = ["bp"]
