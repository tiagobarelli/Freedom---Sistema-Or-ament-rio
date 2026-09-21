# Freedom — Deploy no servidor

Roteiro para pôr o Freedom em produção num servidor Ubuntu, do zero, e para
mantê-lo depois. Os comandos são para copiar e colar, na ordem em que estão.
Cada seção termina dizendo **o que se espera ver**; se o que apareceu foi
outra coisa, pare ali.

Em produção o sistema inteiro roda em `docker compose`: três serviços —
`postgres` (o banco), `app` (o Flask servido por gunicorn) e `pgadmin`. O
código chega por `git clone` / `git pull`, e o banco nasce da restauração de
um dump gerado pela página de Backup do ambiente de desenvolvimento.

**Fora do escopo deste roteiro**, e de propósito: agendamento de qualquer
espécie (o IPCA se atualiza pelo botão da tela, e por mais nada), segundo
usuário do sistema e a instalação do Tailscale — a rede já funciona, e é por
ela que se chega ao servidor.

---

## 1. Pré-requisitos no servidor

Ubuntu com Docker Engine, o plugin `compose` e o `git`. Conferir:

```bash
docker --version
docker compose version
git --version
```

Se faltar o Docker, a instalação é a oficial do Docker Engine para Ubuntu
(pacote `docker-ce` mais `docker-compose-plugin`), e depois:

```bash
sudo usermod -aG docker "$USER"
```

Sair e entrar de novo na sessão para o grupo valer.

**Esperado**: as três versões impressas, e `docker compose ps` rodando sem
`sudo` e sem erro de permissão.

---

## 2. Clonar o repositório

```bash
cd ~
git clone <url-do-repositorio> freedom
cd freedom
ls
```

**Esperado**: a raiz do projeto, com `docker-compose.yml`, `Dockerfile`,
`CHANGELOG.md`, `freedom/`, `templates/`, `static/` e `db/`. Não há `.env` —
ele é o próximo passo.

---

## 3. Criar o `.env` no servidor

O `.env` **não está no git**, e **não se copia o do Windows**: além de ser
outro banco e outra senha, o arquivo de lá tem fim de linha CRLF, e o `\r` que
sobra entra no valor da variável — uma senha com `\r` no fim falha de um jeito
que não parece senha errada.

Escolha as portas conferindo o que já está escutando no servidor:

```bash
ss -tlnp
```

Crie o arquivo:

```bash
nano .env
```

Com este conteúdo, trocando o que está entre `<>`:

```ini
# Banco (lidos pelo docker-compose.yml e pelo servico app)
POSTGRES_DB=<nome_do_banco>
POSTGRES_USER=<usuario_do_banco>
POSTGRES_PASSWORD=<senha_do_banco>
POSTGRES_PORT=<porta_livre_para_o_postgres>

# pgAdmin
PGADMIN_EMAIL=<email_de_login_do_pgadmin>
PGADMIN_PASSWORD=<senha_do_pgadmin>
PGADMIN_PORT=<porta_livre_para_o_pgadmin>

# Aplicacao
APP_PORT=<porta_livre_para_o_app>
SECRET_KEY=<gerada_no_passo_abaixo>
```

O que cada chave faz:

| Chave | Função |
|---|---|
| `POSTGRES_DB` | Nome do banco que o Postgres cria na primeira subida. |
| `POSTGRES_USER` | Dono do banco. É com ele que o app se conecta. |
| `POSTGRES_PASSWORD` | Senha desse usuário. |
| `POSTGRES_PORT` | Porta do **host** que publica o Postgres do container. Dentro do compose o app não passa por ela — fala com `postgres:5432` pela rede interna. Serve ao pgAdmin e ao `psql` do servidor. |
| `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` | Login do pgAdmin. |
| `PGADMIN_PORT` | Porta do host para o pgAdmin. |
| `APP_PORT` | Porta do host para o Freedom. É a que se digita no navegador, pelo endereço do servidor na rede. |
| `SECRET_KEY` | Assina o cookie de sessão e os tokens CSRF. Trocá-la derruba as sessões abertas. |

Duas chaves do desenvolvimento **não existem aqui**: `DATABASE_URL`, que o
compose monta sozinho para o serviço `app` (com host `postgres` e porta interna
`5432`), e `PG_DUMP`, que só existe porque o Windows não tem o cliente do
Postgres no PATH — a imagem do app tem. `DB_POOL_MIN` e `DB_POOL_MAX` também
podem ficar de fora: sem elas valem 1 e 5.

> **As senhas do servidor são novas, e não as de casa.** O `.env` de
> desenvolvimento nasceu com valores fáceis, de máquina que ninguém alcança; o
> servidor está numa rede que outras pessoas usam. `POSTGRES_PASSWORD` e
> `PGADMIN_PASSWORD` devem ser **longas, aleatórias e diferentes entre si** —
> e diferentes do nome do usuário e do banco. O mesmo gerador da `SECRET_KEY`
> serve: `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`.

Gere a `SECRET_KEY` **no servidor**, e cole o resultado no arquivo:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Proteja o arquivo:

```bash
chmod 600 .env
```

**Esperado**: `cat .env` mostra as nove chaves preenchidas, sem aspas em volta
dos valores e sem linha em branco no meio de um valor.

> As seções seguintes usam `$POSTGRES_USER` e `$POSTGRES_DB` nos comandos. Para
> que existam na sessão do shell (o `set -a` põe no ambiente tudo o que o
> arquivo define):
>
> ```bash
> set -a; . ./.env; set +a
> ```

---

## 4. Subir só o banco

A primeira subida do Postgres é a única em que o `db/init/01_schema.sql` roda
sozinho — é assim que a imagem oficial trata a pasta
`docker-entrypoint-initdb.d`.

```bash
docker compose up -d postgres
docker compose ps
```

Espere o `postgres` aparecer como `healthy` (o healthcheck roda a cada 10 s).
Confira que o schema entrou:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"
```

**Esperado**: `docker compose ps` com `postgres` em `Up (healthy)`, e a lista
com as 15 tabelas `tb_*`, todas vazias.

---

## 5. Levar o dump para o servidor

O dump sai da página **Configurações › Backup** do Freedom que roda no
Windows: "Executar backup" → "Confirmar e baixar". O arquivo se chama
`freedom_AAAAMMDD-HHMM.sql`.

Do Windows, com PowerShell, na pasta onde o arquivo caiu:

```powershell
scp .\freedom_AAAAMMDD-HHMM.sql <usuario>@<servidor>:~/freedom/
```

No servidor:

```bash
cd ~/freedom
ls -lh freedom_*.sql
head -5 freedom_*.sql
```

**Esperado**: o arquivo com o mesmo tamanho que tinha no Windows, e as
primeiras linhas começando com `--`.

> O dump tem o `senha_hash` de todo mundo e tudo o que a casa gasta e recebe.
> Depois de restaurar, apague-o do servidor ou guarde-o com o mesmo cuidado
> que o `.env`.

---

## 6. Restaurar

O banco criado no passo 4 já tem o schema **vazio**, e o dump traz o schema
**inteiro** de novo. Restaurar por cima daria erro em cada `CREATE TABLE`. Por
isso o schema é esvaziado antes — é o que os dois comandos abaixo fazem, nesta
ordem.

Esvaziar:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

Restaurar, mandando o arquivo pela entrada padrão:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 -f - < freedom_AAAAMMDD-HHMM.sql
echo "codigo de saida: $?"
```

O `-T` é obrigatório: sem ele o `docker compose exec` pede um terminal e o
arquivo não chega pela entrada padrão. O `-v ON_ERROR_STOP=1` é o que faz o
`psql` **parar no primeiro erro** em vez de seguir até o fim e terminar com
código 0 sobre um banco pela metade.

Conferir o que entrou:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT 'despesas' AS tabela, count(*) FROM tb_despesas
   UNION ALL SELECT 'receitas', count(*) FROM tb_receitas
   UNION ALL SELECT 'ipca', count(*) FROM tb_ipca
   UNION ALL SELECT 'patrimonio', count(*) FROM tb_patrimonio_snapshots
   UNION ALL SELECT 'usuarios', count(*) FROM tb_usuarios;"
```

**Esperado**: a restauração termina **sem nenhuma linha de `ERROR`** e com
código de saída `0`, e as contagens batem com as do banco de desenvolvimento.

### 6.1 Prova de que o `01_schema.sql` já basta

O script de schema é idempotente: reaplicá-lo sobre o banco restaurado não muda
nada. Vale conferir uma vez, porque é essa propriedade que dispensa ferramenta
de migração.

O `--restrict-key=comparacao` está aí por um motivo bobo e real: sem ele o
`pg_dump` põe no arquivo uma chave **aleatória a cada execução**
(`\restrict <chave>`), e aí dois dumps do mesmo banco já diferem em duas
linhas. Fixando a chave, `diff` idêntico quer dizer schema idêntico.

```bash
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --schema-only --no-owner --no-privileges --restrict-key=comparacao \
  > /tmp/schema_antes.sql

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/01_schema.sql

docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --schema-only --no-owner --no-privileges --restrict-key=comparacao \
  > /tmp/schema_depois.sql

diff /tmp/schema_antes.sql /tmp/schema_depois.sql && echo "schema identico"
```

**Esperado**: o `psql` do meio imprime uma enxurrada de
`NOTICE: ... already exists, skipping` — é o script dizendo que não precisou
fazer nada — e **nenhum `ERROR`**.

Quanto ao `diff`, há um caso previsto em que ele não sai vazio da primeira vez,
e é só esse:

> As cinco linhas do corpo da função `fn_set_atualizado_em` aparecem dos dois
> lados, **iguais a olho nu**. Não é diferença de conteúdo: é fim de linha. O
> banco de desenvolvimento guarda esse corpo com CRLF, herdado de quando o
> `01_schema.sql` foi aplicado pela primeira vez, e a reaplicação grava LF. O
> `diff` enxerga, o Postgres não.

Se for isso, **repita os três comandos**. Da segunda vez o `diff` tem de sair
vazio, imprimindo `schema identico` — e é essa segunda passada que prova a
idempotência. Qualquer outra diferença (tabela, coluna, índice, restrição) não
é normalização e merece parar para olhar.

Conferido nesta rodada, sobre o acervo real: fora os `\r`, os dois dumps são
idênticos linha a linha (1.624 linhas), e a segunda aplicação devolveu o mesmo
SHA-256 da primeira.

---

## 7. Subir o sistema inteiro

```bash
docker compose up -d --build
docker compose ps
```

O `--build` constrói a imagem do `app` a partir do `Dockerfile`. Da primeira
vez leva alguns minutos (baixa a base do Python e instala as dependências);
depois, com o cache, é rápido.

**Esperado**: `docker compose ps` com os três serviços em `Up`, e o `postgres`
em `Up (healthy)`.

---

## 8. Conferências

**8.1 — O app responde.** No navegador, pela rede:
`http://<endereco-do-servidor>:<APP_PORT>`.

**Esperado**: a tela de login.

**8.2 — Versão.** Entre com o seu login. No rodapé do menu, o número da
versão. Clique nele.

**Esperado**: rodapé mostrando `1.0`, e a página de histórico abrindo com a
entrada `## 1.0` no topo.

**8.3 — Os dados chegaram.** Abra a Visão Anual e a Visão Mensal.

**Esperado**: os mesmos números do sistema de desenvolvimento — cards, tabelas
e gráficos.

**8.4 — Backup de dentro do servidor.** Configurações › Backup › "Executar
backup" › "Confirmar e baixar". Pelo navegador, o arquivo cai na máquina de
onde se está acessando.

**Esperado**: o arquivo baixa. Conferindo o `COPY` das despesas, o número de
linhas é o mesmo do `count(*)` do passo 6.

**8.5 — O IPCA.** Cadastros › IPCA › "Atualizar do IBGE".

**Esperado**: a faixa responde — "Nenhum mês novo" se a série já está em dia,
ou o mês carregado. Se responder erro de rede, é o container sem saída para a
internet; o resto do sistema não depende disso.

**8.6 — A dica de mês.** Na mesma tela, a frase "O IBGE já deve ter publicado
&lt;mês&gt;".

**Esperado**: o mês coerente com a data de hoje — do dia 12 em diante, o mês
anterior; antes disso, o retrasado. Se vier errado, o fuso do container está em
UTC: confira o `TZ: America/Sao_Paulo` do serviço `app` no
`docker-compose.yml`.

**8.7 — Console limpo.** Com o DevTools aberto (F12), navegue pelas telas.

**Esperado**: nenhum erro no console e, na aba **Rede**, nenhuma requisição a
domínio de fora — só `/static/...` e as rotas do próprio sistema.

---

## 9. Rodar comandos `flask` em produção

Os comandos do sistema rodam dentro do container do app, que já tem o ambiente
e a conexão com o banco:

```bash
docker compose exec app flask --app freedom carregar-ipca
docker compose exec app flask --app freedom create-user --login <login> --pessoa "<Nome>"
docker compose exec app flask --app freedom set-password --login <login>
```

O `set-password` **pergunta a senha no terminal** e não a mostra enquanto se
digita. Por isso ele roda sem `-T`: precisa do terminal interativo. A senha não
fica no histórico do shell, e não deve ser passada por argumento em nenhuma
circunstância.

**Esperado**: `carregar-ipca` relata os meses carregados ou diz que não há mês
novo; `create-user` e `set-password` confirmam em uma linha.

---

## 10. Atualizar o sistema

Quando houver versão nova no repositório:

```bash
cd ~/freedom
git pull
docker compose up -d --build app
docker compose ps
```

Só o `app` precisa ser reconstruído: banco e pgAdmin são imagens de terceiros e
não mudam. O banco não é tocado — o volume continua onde está.

Se a atualização mexeu no schema, o `01_schema.sql` **não roda sozinho** (isso
só acontece na primeira criação do volume). Aplique-o à mão, que é idempotente:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/01_schema.sql
```

**Esperado**: `docker compose ps` com os três serviços em `Up` de novo, e o
rodapé do menu mostrando o número da versão nova.

---

## 11. Logs

```bash
docker compose logs -f app          # o que o gunicorn esta servindo, ao vivo
docker compose logs --tail=100 app  # as ultimas 100 linhas
docker compose logs postgres
```

O gunicorn escreve o log de acesso no stdout (`--access-logfile -`), que é de
onde o `docker compose logs` o lê. Não há arquivo de log em disco.

**Esperado**: uma linha por requisição, com método, caminho e status.

---

## 12. pgAdmin

`http://<endereco-do-servidor>:<PGADMIN_PORT>`, com o `PGADMIN_EMAIL` e a
`PGADMIN_PASSWORD` do `.env`.

O servidor já vem registrado pelo `db/pgadmin/servers.json`. Se for preciso
registrá-lo à mão, o host é **`postgres`** — o nome do serviço — e a porta é
**5432**, a interna. O `POSTGRES_PORT` do `.env` é a porta do host, e de dentro
da rede do compose ela não é o caminho.

**Esperado**: a árvore do banco abrindo com as 15 tabelas e as duas views.

---

## 13. Parar e voltar

```bash
docker compose stop     # para os tres, sem apagar nada
docker compose start    # volta
docker compose restart  # para e volta
```

Os três serviços estão com `restart: unless-stopped`: depois de um reinício do
servidor, eles voltam sozinhos.

Duas coisas garantem isso, e é bom saber qual faz o quê:

- **No `docker compose up`**, o `app` espera o `postgres` ficar `healthy` antes
  de subir (`depends_on` com `condition: service_healthy`). Dá para ver no
  próprio comando: ele imprime `postgres Waiting`, depois `postgres Healthy`,
  e só então `app Starting`.
- **No `restart` e depois de um reinício da máquina**, essa espera **não
  vale** — o `depends_on` é do `up`, e o `restart` reinicia os dois ao mesmo
  tempo. Quem cobre esse caso é outra coisa: se o banco ainda não atende, o
  `create_app` falha, o gunicorn diz `Worker failed to boot` e encerra, e o
  `restart: unless-stopped` sobe o container de novo — e de novo, até o banco
  responder. Medido: com o `postgres` parado de propósito, o `app` ficou nesse
  laço; assim que o banco voltou, o sistema respondeu em 3 segundos, sem
  nenhum comando.

Ou seja: não há passo manual depois de um reinício, nem no caso feliz nem no
caso em que o banco demora. Se quiser a subida ordenada mesmo assim, use
`docker compose up -d` em vez de `restart`.

**Nunca** use `docker compose down -v` neste projeto: o `-v` apaga os volumes,
e com eles o banco inteiro. `down` sozinho derruba os containers e preserva os
dados; mesmo assim, prefira `stop`.

**Esperado**: depois de `docker compose restart`, `docker compose ps` com os
três em `Up` e `postgres` em `Up (healthy)`, e o sistema respondendo no
navegador sem mais nenhum comando.
