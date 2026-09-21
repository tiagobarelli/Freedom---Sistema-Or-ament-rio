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

    # Nome proprio para o cookie de sessao, e nao o `session` que o Flask usa
    # por padrao. O servidor de producao hospeda OUTROS sistemas web na mesma
    # maquina, em portas diferentes -- e cookie de navegador ignora porta: o
    # host e o mesmo, o jar e o mesmo. Outro app Flask de la grava `session`,
    # e os dois se sobrescreviam: o Freedom deslogava sozinho poucos segundos
    # depois do login (302 para /login sem nenhum /logout no meio), e o outro
    # sistema deslogava quando o Freedom abria. Com nome proprio cada um tem o
    # seu, e os dois convivem no mesmo navegador.
    SESSION_COOKIE_NAME = "freedom_session"

    # Cookie de sessao: sem HTTPS no acesso local/Tailscale, entao Secure fica
    # desligado. HttpOnly e SameSite continuam valendo.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
