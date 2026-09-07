Contexto: projeto "Freedom", sistema web pessoal de controle financeiro.
O banco PostgreSQL 16 já está rodando via `docker-compose.yml` e o schema
já foi aplicado por `db/init/01_schema.sql`. A especificação do banco é
`docs/Freedom - Estrutura do Banco de Dados.md` — leia os dois antes de
começar; são a fonte da verdade e você não deve alterar o schema.
Credenciais e `DATABASE_URL` estão no `.env`. Ambiente: Windows, PowerShell,
venv já criado em `.venv` (use `.venv\Scripts\python` e
`.venv\Scripts\pip`; nunca instale nada fora dele).

Stack (já decidida, não proponha alternativas):
- Flask 3 com Blueprints, Jinja2, HTMX (arquivo local em static/)
- psycopg 3 + psycopg_pool para acesso ao banco, SQL direto,
  `row_factory=dict_row`. Sem ORM.
- Flask-Login para sessão; hash de senha com `werkzeug.security`
  (`generate_password_hash` / `check_password_hash`, método padrão scrypt)
- Flask-WTF para formulários e CSRF
- python-dotenv para carregar o `.env`

Entrega desta rodada — SOMENTE isto:
1. Esqueleto do projeto com application factory (`create_app`), config
   lida do `.env`, um blueprint `auth` e um blueprint `main` com uma rota
   `/` protegida por login que renderiza uma página vazia com o texto
   "Freedom" e o nome do usuário logado. Nenhuma outra tela.
2. Módulo `freedom/db.py` que cria um `ConnectionPool` na inicialização
   do app, fecha no teardown, e expõe um helper para obter conexão
   (context manager). Todas as queries parametrizadas.
3. Login (`/login`, `/logout`) consultando `tb_usuarios` com
   `ativo = TRUE`, join em `tb_pessoas` para trazer o nome. O objeto
   `current_user` deve expor id, login, nome da pessoa e pessoa_id.
4. Comando CLI `flask create-user --login X --pessoa "Nome"` que pede a
   senha de forma interativa (sem eco), cria a pessoa em `tb_pessoas` se
   não existir e o usuário em `tb_usuarios` com o hash, tudo em uma
   transação. Deve falhar com mensagem clara se o login já existir.
5. `requirements.txt` com versões fixadas, `.gitignore` (venv, .env,
   __pycache__, instance/), e `README.md` curto com os comandos para
   subir o banco, ativar o venv, instalar, criar o usuário e rodar.
6. `templates/base.html` mínimo com bloco de conteúdo e HTMX carregado.
   Sem CSS ainda além de um `static/css/app.css` vazio com um comentário
   — o estilo entra na próxima rodada.

Estrutura esperada:
  freedom/            (pacote: __init__.py com create_app, db.py,
                       auth/, main/, cli.py)
  templates/
  static/
  db/init/01_schema.sql   (já existe, não tocar)
  docs/                   (já existe, não tocar)
  run.py ou uso de FLASK_APP

Regras:
- Não crie tabelas, colunas, views ou triggers. Não use ORM nem
  migrações. Não invente funcionalidades além das listadas.
- Não gere SQL de seed; o usuário master será criado com o comando.
- Se algo na especificação estiver ambíguo, pergunte antes de decidir.
- Ao terminar, valide de fato: rode `flask create-user`, suba o app,
  faça login com esses dados e confirme que `/` mostra o nome da pessoa
  e que `/logout` encerra a sessão. Mostre o resultado e liste qualquer
  ponto em que precisou interpretar as instruções.