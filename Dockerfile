# Imagem de produção do Freedom (rodada 33).
#
# Roda no servidor Ubuntu como terceiro serviço do docker compose, ao lado de
# postgres e pgadmin. O desenvolvimento continua como sempre: venv no host e
# `flask --debug run`. Esta imagem não existe para o Windows do dono — ela é
# construída lá, pelo `docker compose up -d --build`.
#
# O roteiro do servidor está em docs/Freedom - Deploy.md.

FROM python:3.14-slim

# tzdata: o TZ do compose (America/Sao_Paulo) só tem efeito se o sistema tiver
#   a base de fusos. Sem ela o container fica em UTC e a "dica de mês provável"
#   do IPCA, que vira o dia 12, viraria três horas mais tarde do que deve.
#   O pacote `tzdata` do requirements.txt serve ao zoneinfo do Python; este
#   serve ao resto do sistema (o `date`, o log do gunicorn).
# postgresql-client: traz o `pg_dump` que a página de Backup executa. Desde
#   esta rodada ele roda na própria máquina e fala com o banco por TCP, então
#   precisa estar aqui dentro. O Debian desta imagem traz um pg_dump mais novo
#   que o servidor Postgres 16 do compose — essa direção é a suportada
#   (cliente novo, servidor antigo); a inversa é que não é.
RUN apt-get update \
    && apt-get install --no-install-recommends -y tzdata postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# As dependências antes do código: mudar um template não refaz o pip install.
COPY requirements.txt requirements-prod.txt ./
RUN pip install -r requirements-prod.txt

# Só o que `create_app` precisa. BASE_DIR é o pai do pacote freedom/, ou seja
# /app: é de lá que saem templates/, static/ e o CHANGELOG.md de onde o número
# da versão é lido na subida.
#
# O que NÃO entra, e por quê: `.env` (o ambiente vem do compose, e a chave do
# dono não tem por que viajar dentro de uma imagem), `venv/` e `.git/` (peso
# sem uso), `docs/` e os dois handoffs de design (documentação, não execução),
# `requirements-dev.txt` e o Playwright (validação roda no Windows), `db/`
# (o initdb é montado pelo compose a partir do repositório clonado) e as
# capturas. O .dockerignore repete a lista, para o contexto do build também
# não carregá-los até o daemon.
COPY freedom/ ./freedom/
COPY templates/ ./templates/
COPY static/ ./static/
COPY CHANGELOG.md ./

EXPOSE 8000

# `--timeout 150` é o número que amarra esta linha ao backup: o
# `TEMPO_LIMITE` de freedom/configuracoes/backup.py é 120 s, e é quanto o
# worker pode ficar parado esperando o pg_dump terminar. Um `--timeout` menor
# que isso faria o gunicorn matar o worker no meio de um dump que ainda ia dar
# certo, e a tela mostraria queda de conexão em vez de backup. A regra é
# `--timeout` > `TEMPO_LIMITE`, e os 30 s de folga cobrem o tempo de montar a
# resposta com os bytes na memória. Mudou um, mude o outro.
# O botão "Atualizar do IBGE" cabe folgado: o `TEMPO_LIMITE_WEB` do
# freedom/ipca.py é 20 s.
#
# Dois workers: a casa tem duas pessoas. Log de acesso no stdout, que é onde o
# `docker compose logs` vai buscá-lo.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "150", \
     "--access-logfile", "-", \
     "freedom:create_app()"]
