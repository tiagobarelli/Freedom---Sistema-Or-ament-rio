# Freedom

Sistema web pessoal de controle financeiro. Roda localmente; acesso dos demais
membros da casa via Tailscale. PostgreSQL 16 em Docker, aplicação em Flask.

## Pré-requisitos

- Docker Desktop
- Python 3.14 (o venv em `venv/` já está criado)

## 1. Subir o banco

```powershell
docker compose up -d
```

Sobe o PostgreSQL na porta 5432 e o pgAdmin em <http://localhost:5050>
(login `admin@freedom.com` / `admin`; o servidor "Freedom" já vem registrado,
a senha do banco é `freedom`).

O schema em `db/init/01_schema.sql` roda sozinho na primeira criação do volume.
Para reaplicar num banco já existente (é idempotente):

```powershell
docker compose exec -T postgres psql -U freedom -d freedom -f /docker-entrypoint-initdb.d/01_schema.sql
```

## 2. Ativar o venv e instalar

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Se a política de execução do PowerShell bloquear o `Activate.ps1`, dá para
pular a ativação e chamar os executáveis direto: `.\venv\Scripts\python.exe`
e `.\venv\Scripts\pip.exe`.

## 3. Criar o usuário master

Não existe seed de usuário em SQL — a senha precisa passar pelo hash da
aplicação. O comando cria a pessoa em `tb_pessoas` se ela ainda não existir e
o usuário em `tb_usuarios`, tudo numa transação. A senha é pedida na hora,
sem eco, e não fica no histórico do shell.

```powershell
$env:FLASK_APP = "freedom"
flask create-user --login tiago --pessoa "Tiago"
```

Para trocar a senha depois (mesma regra: pedida na hora, sem eco):

```powershell
flask set-password --login tiago
```

## 4. Rodar

```powershell
python run.py
```

Ou, equivalente:

```powershell
$env:FLASK_APP = "freedom"
flask run
```

A aplicação sobe em <http://127.0.0.1:5000>. `/` exige login e redireciona
para `/login`; `/logout` encerra a sessão.

## Estrutura

```
freedom/            pacote da aplicação
  __init__.py       application factory (create_app)
  config.py         configuração lida do .env
  db.py             pool de conexões psycopg 3
  auth/             login, logout, modelo de usuário
  main/             página inicial
  cadastros/        telas de referência, um módulo por entidade
    servico.py      ativar/desativar e tradução de UNIQUE, compartilhados
    forms.py        formulários das cinco entidades
  cli.py            comandos create-user e set-password
templates/          Jinja2
  base.html         shell (usado pelo login)
  layout_app.html   shell + sidebar (telas autenticadas)
  _macros.html      macros de campo, tabela, badge e ações
  cadastros/        listas, formulários e parciais de linha (HTMX)
static/             css e htmx
db/init/            DDL do banco
docs/               especificação do banco (fonte da verdade)
```

## Cadastros

As telas em `/cadastros` cobrem categorias, subcategorias, contas, pessoas e
fontes de receita. Não existe excluir: o schema usa `ativo`/`ativa` e as FKs
são `ON DELETE RESTRICT`, então desativar é o que tira o registro dos
formulários sem quebrar o histórico. A lista esconde os inativos por padrão;
o filtro "Mostrar inativos" os traz de volta.

## Configuração

Fica toda no `.env`, que **não** vai para o git. Chaves usadas pela aplicação:

| Chave | Função |
|---|---|
| `DATABASE_URL` | String de conexão do psycopg. |
| `SECRET_KEY` | Assina o cookie de sessão e os tokens CSRF. |
| `DB_POOL_MIN` / `DB_POOL_MAX` | Tamanho do pool (padrão 1 e 5). |

Num clone novo, o `.env` precisa ser recriado — inclusive com uma `SECRET_KEY`
nova:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
