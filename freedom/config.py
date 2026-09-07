"""Configuracao do app, lida do .env na raiz do projeto."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Raiz do projeto: pasta que contem o pacote freedom/, templates/ e static/.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ["SECRET_KEY"]
    DATABASE_URL = os.environ["DATABASE_URL"]

    # Tamanho do pool. O sistema e de uso domestico; poucas conexoes bastam.
    DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", 1))
    DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", 5))

    # Cookie de sessao: sem HTTPS no acesso local/Tailscale, entao Secure fica
    # desligado. HttpOnly e SameSite continuam valendo.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
