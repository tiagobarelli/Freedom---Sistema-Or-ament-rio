# CLAUDE.md

Orientações para o Claude Code (e qualquer agente) trabalhando neste repositório.

> **Idioma**: tudo em português do Brasil — interface, nomes de função, variáveis,
> comentários, mensagens de commit. Não traduza identificadores existentes nem
> introduza nomes em inglês. Comentários explicam **por que**, não o que.

---

## 1. O que é o Freedom

Sistema web pessoal de controle financeiro de uma família. Roda localmente em
Windows (Postgres em Docker, Flask no host); no futuro os demais membros da casa
acessam pela rede Tailscale. **Nada é exposto na internet.**

Registra despesas e receitas, classifica por categoria/subcategoria/pessoa/conta,
e mostra painéis anual e mensal, além de um orçamento por subcategoria. O objetivo
de longo prazo inclui deflação por IPCA, patrimônio e metas de independência
financeira. A série do IPCA está no banco desde a rodada 21, tem tela própria
desde a 22 e **já corrige valor** na Análise por subcategoria (rodada 24).
Patrimônio e metas **existem desde as rodadas 29 e 30**: `/independencia`
calcula quanto falta para a independência financeira a partir de TSR, S e R, e
`/lancamentos/patrimonio` guarda uma foto mensal dos ativos, com evolução,
tendência e projeção de cinco anos. A refatoração visual está **concluída**
(rodadas 17, 18, 27 e 28): não existe tema antigo no repositório.

**Há dado real em produção** (mais de 3.500 despesas e quase 400 receitas, de
2023 a 2026, e **161 fotos de patrimônio, de abril de 2013 a agosto de 2026**).
O acervo cresce para trás: 2023 e 2024 entraram por carga a partir de CSV
exportado do Moneystats, a série de patrimônio inteira veio de outro CSV do
dono, e ele pretende chegar a 2012. Ver a seção 8 antes de escrever qualquer
coisa no banco.

## 2. Rodar

Pré-requisitos: Docker Desktop e o `venv/`, que já vem criado na máquina do dono
com **Python 3.14** — é o que roda hoje, e nada do `requirements.txt` faltou
wheel. (O aviso antigo de "use 3.12" ficou de quando havia dependência sem wheel
para a 3.14; não vale mais. Num clone novo, conferir antes de trocar de versão.)

```powershell
docker compose up -d postgres pgadmin    # em dev sobe-se só o banco e o pgAdmin
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m flask --app freedom --debug run --port 5000
```

O `docker-compose.yml` tem **três** serviços desde a rodada 33 — `postgres`,
`app` e `pgadmin`. Em desenvolvimento o `app` não sobe: quem serve é o
`flask run` do host, com recarga. `docker compose up -d` sem nomear serviço
subiria os três e poria um segundo Freedom na `APP_PORT`, o que não é erro mas
não é o que se quer aqui. Quem sobe os três é o servidor — ver
`docs/Freedom - Deploy.md`.

**Nenhum serviço tem `container_name`.** Quem precisa falar com o banco usa o
nome do SERVIÇO (`postgres`), que é o que a rede do compose resolve, e todo
comando é `docker compose exec <servico>`, nunca `docker exec <nome>`. Nome
fixo impedia subir um segundo projeto compose ao lado do de desenvolvimento.

**Sempre com `--debug`.** Sem ele o Jinja não recarrega template e o Python não
recarrega módulo — duas rodadas do projeto perderam a validação inteira por causa
disso, porque a captura "depois" comparava HTML velho com CSS novo. **Reinicie o
servidor depois de mexer em código, antes de validar.**

O schema em `db/init/01_schema.sql` roda sozinho na primeira criação do volume. É
idempotente; para reaplicar num banco com dados:

```powershell
docker compose exec -T postgres psql -U <usuario> -d <banco> -f /docker-entrypoint-initdb.d/01_schema.sql
```

Não existe seed de usuário em SQL (a senha precisa passar pelo hash da aplicação):

```powershell
flask create-user --login <login> --pessoa "<Nome>"
flask set-password --login <login>
```

A série do IPCA entra pelo comando abaixo ou pelo botão "Atualizar do IBGE" da
tela do IPCA (`/cadastros/ipca`, rodada 23) — os dois passam pela mesma função:

```powershell
flask carregar-ipca
```

Roda depois do dia 10 de cada mês, quando o IBGE publica o índice do mês
anterior. Rodar de novo é inofensivo (upsert que nunca apaga linha).

### `.env` (não versionado)

O `.env` fica na raiz e **nunca** vai para o git. Chaves usadas:

| Chave | Função |
|---|---|
| `DATABASE_URL` | String de conexão do psycopg. É a do **host** (`localhost` e `POSTGRES_PORT`), do `flask run`. O serviço `app` não a lê do `.env`: o compose monta a dele, com host `postgres` e a porta interna 5432. |
| `SECRET_KEY` | Assina o cookie de sessão e os tokens CSRF. |
| `DB_POOL_MIN` / `DB_POOL_MAX` | Tamanho do pool (padrão 1 e 5). |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_PORT` | Lidos pelo `docker-compose.yml`. |
| `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` / `PGADMIN_PORT` | idem. |
| `APP_PORT` | Porta do host que publica o serviço `app`. Só o compose a lê, e ela tem padrão (8000) — em dev pode faltar. |
| `PG_DUMP` | Caminho do `pg_dump.exe` para a página de Backup. Existe porque o Windows não tem o cliente do Postgres no PATH; a imagem de produção tem, e lá a chave não existe. Ausente, vale `pg_dump`. **Barra normal, não contrabarra**: o `python-dotenv` interpreta escapes em valor sem aspas, e `in` vira dois caracteres de controle. |
| `senha_teste` | Senha do usuário de teste, usada só pela validação em navegador. |

Num clone novo o `.env` precisa ser recriado. Gere a `SECRET_KEY` com
`python -c "import secrets; print(secrets.token_hex(32))"`.

**Nunca escreva o valor de nenhuma dessas chaves em código, prompt, commit,
relatório ou documento.** Referencie sempre pelo nome da variável.

## 3. Stack (fechada — não proponha alternativas)

| Camada | Escolha |
|---|---|
| Web | Flask 3, application factory (`create_app` em `freedom/__init__.py`), Blueprints |
| Banco | psycopg 3 + `psycopg_pool`, SQL direto parametrizado, `row_factory=dict_row`. **Sem ORM, sem migrações** |
| Auth | Flask-Login; hash com `werkzeug.security` (scrypt) |
| Formulários | Flask-WTF (CSRF em todo POST) |
| Interatividade | HTMX 2.0.4 (arquivo local) + JS vanilla pontual |
| Gráficos | Chart.js 4.5.1, UMD **local**, nas cinco telas que desenham: Visão Anual, as duas Análises, Independência e Patrimônio — esta com **dois** canvas (evolução e tendência) e por isso a única que precisa destruir instância antes de redesenhar. Núcleo, sem plugins. O comum a todas mora em `static/js/graficos.js`; `analise.js` serve às duas Análises sem ramificar por página |
| CSS | Um arquivo escrito à mão (`static/css/app.css`), tokens em `:root`, uma camada só. **Sem Tailwind, sem React, sem biblioteca de ícones** |
| Ícones | Lucide (ISC), **SVG inline** pela macro `icone` em `templates/_macros.html`. O da **aba** é `static/favicon.svg`. O do **app instalado** é outra coisa e mora em `static/icones/` — PNG, porque o iOS não aceita SVG ali (rodada 34) |
| Markdown | Python-Markdown (`markdown`), núcleo sem extensões, **no servidor**, e num lugar só: o `CHANGELOG.md` da raiz virando HTML na subida do app (rodada 32). Nada de markdown no cliente, e nada de markdown em texto de usuário — o resumo anual continua sendo texto puro |
| Dinheiro | `Decimal` em todo cálculo; `float` só na serialização final para JSON de gráfico |
| Testes/validação | Playwright (`requirements-dev.txt`), navegador real |
| Imagens | Pillow, **só em `requirements-dev.txt`** e só para derivar os PNGs de `static/icones/` uma vez (rodada 34). A aplicação não o importa, e ele não entra em `requirements.txt` nem na imagem |
| Produção | gunicorn (`requirements-prod.txt`, que é `-r requirements.txt` mais ele), dentro da imagem do `Dockerfile` da raiz — `python:3.14-slim` com `tzdata` e `postgresql-client` do Debian. `.dockerignore` diz o que nem chega ao daemon. **Só na imagem**: em desenvolvimento quem serve é o `flask --debug run`, e o gunicorn nem é instalado |

**Nenhuma requisição a domínio externo, em nenhuma tela.** Sem CDN, sem unpkg, sem
fonte web. A única chamada externa do sistema inteiro é a da API do SIDRA
(`urllib.request` da stdlib), e ela sai por **dois gatilhos, os dois manuais**:
`flask carregar-ipca` (rodada 21) e o botão "Atualizar do IBGE" da tela do IPCA
(rodada 23), que passam pela mesma função. **Nunca por agendamento** — não há
cron, thread nem tarefa do Windows dentro do app. Nenhuma tela pede nada a
domínio externo: quem fala com o IBGE é o servidor, quando alguém manda. A tipografia é a fonte do sistema. Isso é verificável e é verificado: a
validação de cada rodada confere que a aba Rede só tem `/static/...`.

O sistema sai do próprio processo em **mais um** ponto, e ele não é rede
externa: o `pg_dump` que a página de Backup executa (`subprocess.run` com lista
de argumentos, `shell=False`, rodada 25). Desde a rodada 33 ele é o `pg_dump`
da própria máquina que serve o app e fala com o banco **por TCP**, com host,
porta, usuário, banco e senha saindo do `DATABASE_URL` — a senha em
`PGPASSWORD` no `env=` do subprocesso, nunca em argumento. Em produção o
executável vem do `postgresql-client` da imagem; no Windows, da variável
`PG_DUMP`. Não há mais `docker exec` em código nenhum, e o app não precisa de
daemon do Docker ao alcance. Vale a mesma regra do SIDRA — **só por clique**,
nunca por agendamento.

**Um número amarra dois arquivos**: o `--timeout` do gunicorn (Dockerfile, 150 s)
tem de ser MAIOR que o `TEMPO_LIMITE` do backup (`freedom/configuracoes/backup.py`,
120 s), senão o worker morre no meio de um dump que ia dar certo e a tela
mostra queda de conexão em vez de arquivo. O `TEMPO_LIMITE_WEB` do IPCA (20 s)
cabe folgado. Mudou um, mude o outro.

O roteiro de produção está em **`docs/Freedom - Deploy.md`**: pré-requisitos,
`.env` do servidor, restauração do dump, subida, conferências, comandos
`flask` dentro do container e atualização.

**`depends_on: service_healthy` vale no `up`, e só nele.** Medido na rodada
33: `docker compose restart` sobe `app` e `postgres` ao mesmo tempo (236 ms de
diferença, com o banco ainda em `starting`), e depois de um reinício da
máquina quem manda é a política de restart do daemon, não o compose. O que
cobre esse caso é o `restart: unless-stopped`: sem banco, o `create_app`
falha, o gunicorn encerra com "Worker failed to boot" e o container volta a
tentar — até o banco atender (medido: 3 s depois de o banco voltar, sem
nenhum comando). Não escreva que o `depends_on` garante a ordem no reinício;
ele garante no `up`.

## 4. Mapa do código

```
freedom/
  __init__.py      create_app: CSRF, pool, Flask-Login, blueprints, CLI,
                   filtros Jinja `moeda` e `numero`
  config.py        lê o .env; template_folder/static_folder apontam para a raiz
  db.py            ConnectionPool, dict_row, get_connection(), query_one(),
                   query_all(), executar()
  util.py          destino_interno(); ValorInvalido, converter_valor,
                   converter_numero(percentual=), formatar_valor,
                   formatar_numero, escapar_like; MESES e MESES_CURTOS;
                   nome_do_periodo(ano, mês) ou (date) -> "agosto de 2026";
                   data_por_extenso(date) -> "31 de agosto de 2026";
                   com_sinal(texto, valor) põe o "+" do positivo no texto já
                   formatado (desvio da Independência e variação do
                   Patrimônio); caixa_marcada(texto) lê a caixa de um filtro
                   GET; parece_zero(texto) para o zero que é entrada legítima
                   (orçamento e foto de patrimônio);
                   nome_do_mes(mês) -> "Janeiro";
                   intervalo_de_meses(a, b); somar_meses(mês, passos);
                   so_fragmento; dobrar (NFD — nunca `locale`),
                   chave_alfabetica; fracao
  cli.py           flask create-user, flask set-password, flask carregar-ipca
                   — a gravação da senha é de auth/servico.py, e a saída do
                   comando não mudou com isso (rodada 32)
  versao.py        a versão do sistema e o histórico, do CHANGELOG.md da raiz:
                   versao_atual(texto) é pura (o primeiro token depois de
                   `## `) e carregar(caminho) lê, renderiza o markdown e marca
                   o HTML como seguro. ErroVersao derruba a subida — não há
                   versão "—". Chamada UMA vez, no create_app, que guarda
                   VERSAO e CHANGELOG_HTML no config e publica `versao` a todo
                   template por context processor
  ipca.py          IPCA de ponta a ponta. Carga: buscar (rede), interpretar
                   (pura), gravar (banco, uma transação só) — tb_ipca só se
                   alimenta daqui; carregar() encadeia as três e é o caminho
                   do comando E do botão. Leitura: serie() e matriz() (pura).
                   Texto pronto: texto_da_faixa, texto_do_erro, texto_das_nulas,
                   texto_da_dica; datas: mes_esperado e pendente (puras, a data
                   entra por parâmetro)
  auth/            /login, /logout (POST com CSRF) e /conta/senha, a troca da
                   própria senha (GET/POST, rodada 32): POST comum com
                   redirect para si mesma, quatro recusas com texto no campo.
                   servico.py tem trocar_senha(login, senha_nova) — o ÚNICO
                   lugar que gera hash de senha, e o caminho tanto da tela
                   quanto do `flask set-password`. Conferir a senha atual é da
                   rota, nunca da função
  main/            "/" Visão Anual, "/mensal" Visão Mensal,
                   "/mensal/categoria/<id>" fragmento
                   servico.py        Anual: painel_do_ano, _totais_do_ano
                                     (origem única dos totais), _tabela_mensal,
                                     _tabela_categorias, _graficos;
                                     helpers card e percentual — `card` serve
                                     também à Mensal, ao resumo das análises e ao
                                     acompanhamento do Orçamento (apoio_rotulo,
                                     apoio_classe e nota desde a 28);
                                     anos_com_lancamento e resumo_do_ano, que o
                                     cadastro de resumos importa daqui
                   servico_mensal.py Mensal: painel_do_mes e as três tabelas
                   analise.py        as DUAS análises, só as rotas:
                                     "/analise/subcategoria" (rodada 24) e
                                     "/analise/prioridade" (rodada 26). Cada
                                     uma lê da URL o que é dela, monta o
                                     Recorte e entrega o resto a painel()
                   servico_analise.py o serviço das duas. `Recorte` (nome,
                                     condição SQL, params, so_integrantes) é a
                                     única coisa que as separa; painel() é o
                                     caminho da URL à tela; consultar() é a
                                     consulta única; montar_pontos, montar,
                                     _resumo e para_grafico são puras
                   independencia.py  a rota GET "/independencia" (rodada 29),
                                     só ela: lê a query string e chama o
                                     serviço
                   changelog.py      a rota GET "/changelog" (rodada 32), só
                                     ela: o HTML já veio pronto do create_app,
                                     aqui se escolhe o template. O número da
                                     versão do subtítulo NÃO é passado daqui —
                                     vem do context processor, o mesmo do
                                     rodapé
                   servico_independencia.py o modelo do Mr. Money Mustache.
                                     anos_ate_if (de patrimônio zero),
                                     anos_restantes (da última foto, rodada
                                     31 — as duas são a MESMA fórmula, e o
                                     invariante prova), curva,
                                     resolver_premissas, janela_fechada,
                                     base_dos_doze, montar, _eixo e
                                     para_grafico são puras; consultar() faz
                                     as duas consultas de dinheiro mais a
                                     `ultima_foto()` que importa de
                                     `lancamentos/servico_patrimonio.py`, e
                                     vigentes(), a das configurações — é a
                                     PRIMEIRA leitura de TSR, R e S. Quatro
                                     consultas
  cadastros/       /cadastros — um módulo por entidade + servico.py
                   (alternar_ativo, traduzir_unique, contagem).
                   ativos.py é o cadastro dos ativos de patrimônio (rodada
                   30): padrão dos outros, com `classe` em texto livre pela
                   macro `combobox` — inativo aqui lê-se "posição encerrada".
                   resumos_anuais.py é o de fora da série: chave é o ano, não
                   há `ativo`, e a segunda ação é Excluir.
                   serie_ipca.py tem a tela do IPCA: GET /cadastros/ipca e
                   POST /cadastros/ipca/atualizar (o botão). O nome evita
                   colisão com freedom/ipca.py, que é quem tem a consulta, a
                   matriz e todo o texto. Templates: serie_ipca.html mais os
                   parciais _cartao_ipca, _subtitulo_ipca (OOB) e _resposta_ipca
  lancamentos/     /lancamentos — despesas.py, consulta.py, receitas.py,
                   servico.py, servico_receitas.py, forms.py
                   patrimonio.py       a foto mensal dos ativos (rodada 30):
                                       GET da tela, POST que grava a foto e
                                       POST que exclui a foto de uma data
                   servico_patrimonio.py o serviço dela. Puras: fim_do_mes,
                                       data_padrao, salto_de_mes (as duas
                                       setas de mês da barra),
                                       ajuste_exponencial e montar_tendencia
                                       (a curva de tendência e os cinco anos
                                       de projeção), data_valida,
                                       erro_da_data, ler_valores,
                                       montar_grade, montar_cards,
                                       montar_alocacao, montar_historico,
                                       para_grafico e os textos. gravar_foto
                                       acerta a data numa transação só (upsert
                                       com `RETURNING (xmax = 0)` mais o
                                       DELETE dos vazios); `ultima_foto()` é a
                                       leitura que a Independência importa
                                       (rodada 31), e o histórico traz o total
                                       corrigido pelo IPCA na mesma varredura
                                       do `LAG`; quatro consultas por
                                       carregamento
  configuracoes/   /configuracoes — um módulo por assunto:
                   rotas.py  parâmetros com vigência (CATALOGO em Python:
                             formato e, desde a rodada 31, se a chave recusa
                             zero — TSR e S recusam, R aceita).
                             Chama-se "Parâmetros" na tela desde a rodada 25;
                             o endpoint e a URL não mudaram
                   backup.py a página de backup (rodada 25): gerar_dump() roda
                             o pg_dump da própria máquina por TCP (rodada 33),
                             bufferiza e devolve os bytes mais o nome do
                             arquivo. `_identificacao` tira host, porta,
                             usuário, banco e senha do DATABASE_URL;
                             `_executavel` lê a variável PG_DUMP; `_ambiente`
                             põe a senha em PGPASSWORD
  orcamento/       /orcamento — servico.py (montagem; criar() escolhe a origem:
                   copia o mês anterior se houver, senão média de 12 meses) e
                   acompanhamento.py (leitura; _card traduz para main.servico.card)
templates/         base.html (o `htmx-config` que libera 409/502/503; e o
                   `<head>` de TODA tela, login incluído: favicon SVG da aba
                   mais as seis tags do app instalado — manifesto,
                   apple-touch-icon e os quatro `meta` de nome, modo autônomo
                   e barra de status, rodada 34),
                   layout_app.html (sidebar: temAtivo() abre o grupo do item
                   ativo antes de pintar, sem gravar), auth/login.html (fora do
                   layout, cartão de 380px), _macros.html + uma pasta por
                   blueprint. orcamento/ tem dez arquivos; configuracoes/ tem
                   configuracoes.html, _lista.html, _formulario.html e
                   _linha_edicao.html.
                   lancamentos/ tem os cinco da foto de patrimônio
                   (patrimonio.html mais _patrimonio_barra, _grade, _resumo e
                   _resposta).
                   auth/senha.html é a troca de senha (card + macros
                   `campo` e `acoes_formulario`, nenhum CSS próprio) e
                   main/changelog.html é o histórico de versões (um `.card
                   prosa` com o HTML do markdown).
                   main/_analise.html é o corpo que as duas Análises estendem;
                   analise.html e analise_prioridade.html só preenchem título,
                   primeiro campo do filtro, convite e (só a segunda) o aviso
                   fixo. main/independencia.html tem corpo próprio e NÃO
                   estende _analise.html
static/css/app.css seções numeradas 1–8 (ver seção 7 deste arquivo)
CHANGELOG.md       a fonte ÚNICA do número de versão (raiz, versionado — ao
                   contrário do README). Entrada nova no topo, `## <versão> —
                   DD/MM/AAAA`; o rodapé da sidebar e o subtítulo do histórico
                   saem daí
static/icones/     o ícone do APP INSTALADO (rodada 34): apple-touch-icon.png
                   (180), icone-192.png e icone-512.png, e mais nada. Os três
                   são o MIOLO do original — 80 px recortados de cada lado,
                   para não sobrar canto arredondado nem a franja clara da
                   borda, que viraria filete branco sob a máscara do celular.
                   O original de 1024 NÃO mora aqui: é `docs/icones/`, porque
                   nenhuma tela o serve. Derivados uma vez com Pillow; o
                   comando está logo abaixo desta árvore
static/manifest.webmanifest  nome, `start_url`, `display: standalone`, as cores
                   de abertura (`--bg`, e não o roxo do ícone) e os PNGs de 192
                   e 512 com `purpose: any`. O Flask já o serve como
                   `application/manifest+json` (o `mimetypes` do Python conhece
                   a extensão, no Windows e na imagem) — não há
                   `mimetypes.add_type` no `create_app`
static/js/         htmx.min.js, chart.umd.js; graficos.js (o que as telas
                   com gráfico fazem igual: cor por variável CSS, moeda,
                   eixo, base de opções, linha) + visao_anual.js, analise.js,
                   independencia.js e patrimonio.js — este último redesenha
                   depois do swap do HTMX (`htmx:afterSettle` filtrado pelo id
                   do cartão), destruindo a instância anterior
db/init/01_schema.sql
Dockerfile         a imagem de produção (rodada 33): python:3.14-slim, tzdata e
                   postgresql-client do Debian, requirements-prod.txt e o
                   comando do gunicorn. O `--timeout` dele está amarrado ao
                   TEMPO_LIMITE do backup — ver §3
.dockerignore      o que nem chega ao daemon no build (.env, venv/, .git/,
                   docs/, handoffs, requirements-dev.txt, db/, capturas).
                   **Duas classes de padrão, e a diferença importa**: os de
                   lixo do Python levam `**/` (`**/__pycache__`), senão só
                   pegam a raiz e o bytecode do Windows entra na imagem
                   (rodada 33); os de captura e dump NÃO levam (`*.png`,
                   `*.sql`), senão alcançam `static/icones/` e a imagem sobe
                   com os ícones fora — o manifesto apontando para 404
                   (rodada 34). Nada debaixo de `static/` se filtra por
                   extensão: aquilo é a aplicação
requirements-prod.txt  `-r requirements.txt` mais o gunicorn. Só a imagem usa
docs/              Freedom - Estrutura do Banco de Dados.md   (fonte da verdade)
                   Freedom - Histórico e Estado do Projeto.md (decisões e lições)
                   Freedom - Deploy.md                        (o roteiro do servidor)
                   icones/elo-1024.png                        (o original do dono)
```

### Como os ícones de app foram derivados

O original é `docs/icones/elo-1024.png`, e está em `docs/` de propósito: é
matéria-prima, não arquivo servido — a imagem de produção não o carrega, já
que o `.dockerignore` deixa `docs/` de fora. Os três PNGs de `static/icones/`
saem dele por este comando, que **roda uma vez** e não é script do projeto
(salve num arquivo temporário FORA do repositório e rode da raiz):

```python
from PIL import Image

RECORTE = 80                       # px de cada lado; ver o porquê abaixo
original = Image.open("docs/icones/elo-1024.png").convert("RGBA")
L = original.size[0]
miolo = original.crop((RECORTE, RECORTE, L - RECORTE, L - RECORTE))

# Depois do recorte não sobra um pixel translúcido; RGB tira o canal alfa,
# que o iOS não quer no apple-touch-icon.
assert miolo.getchannel("A").getextrema() == (255, 255)
miolo = miolo.convert("RGB")

for nome, lado in [("apple-touch-icon.png", 180),
                   ("icone-192.png", 192),
                   ("icone-512.png", 512)]:
    saida = miolo.resize((lado, lado), Image.Resampling.LANCZOS)
    saida.save(f"static/icones/{nome}", format="PNG", optimize=True)
```

**O 80 não é chute**, e é o número que não se deve mexer sem refazer a conta:
o canto arredondado do original tem raio 228 px; a borda do quadrado só fica
inteiramente opaca a partir de **68 px**; e até **72 px** ainda entra a franja
CLARA da borda do desenho (canto `(179,151,245)` contra `(150,112,238)` do
degradê 40 px adentro), que é justamente o filete branco que a máscara do
celular revelaria. 80 px deixa 8 px de folga além disso e ainda é o **maior**
recorte que sobrevive inteiro à máscara REDONDA do Android — o ponto mais
externo do desenho fica a 0,982 do raio, e em 90 px já corta. Daí também o
`purpose: any` do manifesto: `maskable` exigiria caber em 0,8.

**Camadas**: a rota só orquestra (valida entrada, escolhe o template). Toda
consulta e toda composição de tela moram em `servico.py`. O template só formata.

## 5. Banco

Fonte da verdade: `docs/Freedom - Estrutura do Banco de Dados.md` e
`db/init/01_schema.sql`. **Se um muda, o outro muda.**

15 tabelas (`tb_categorias`, `tb_subcategorias`, `tb_ref_receitas`, `tb_pessoas`,
`tb_usuarios`, `tb_contas`, `tb_ipca`, `tb_configuracoes`, `tb_despesas`,
`tb_receitas`, `tb_orcamento_meses`, `tb_orcamentos`, `tb_resumos_anuais`,
`tb_ativos`, `tb_patrimonio_snapshots`) e duas views (`vw_despesas`,
`vw_receitas`).

Regras que se aplicam a todo código novo:

- **Leitura sempre pelas views; escrita nas tabelas base.** `vw_despesas` já
  resolve a essencialidade efetiva (`COALESCE(despesa, subcategoria)`).
- **`ano_mes` serve para exibir e agrupar, nunca para filtrar.** Todo filtro de
  período usa `data >= início AND data < início do período seguinte` — é o que
  faz os índices `ix_despesas_data` / `ix_receitas_data` serem usados. Filtrar por
  coluna derivada de view mata o índice (comprovado com EXPLAIN ANALYZE).
- **Nada derivado é armazenado.** Toda FK é `NOT NULL` e `ON DELETE RESTRICT`.
- Referência não se apaga: tem `ativo` (`ativa` em `tb_contas`).
- Chave primária é `id`, **menos onde o período é a chave**: `tb_orcamento_meses`
  (`ano_mes`) e `tb_resumos_anuais` (`ano`). Há no máximo uma linha por período,
  e um `id` ao lado exigiria um `UNIQUE` para dizer o mesmo.
- `NOT NULL` em `TEXT` aceita `''`. Quando o vazio não faz sentido, o `CHECK`
  vai junto: `texto ~ '[^[:space:]]'` (pelo menos um caractere visível) cobre
  vazio, espaços, tabulações e quebras de linha numa expressão só.
- `date_trunc(data) = ANY(...)` mata o índice; acumulado de vários meses é OR de
  intervalos com datas parametrizadas.
- Mudança de schema é feita com blocos idempotentes (`ADD/DROP COLUMN IF EXISTS`,
  `DO $$ IF NOT EXISTS (constraint)`), **nunca `DROP TABLE`**, e validada
  re-executando o script no banco com dados **e** num banco descartável do zero.

## 6. Regras de domínio (decididas, não reabrir)

- Cartão de crédito: **só data da compra**, sem parcelas nem faturas.
- **Sem controle de saldo**: o sistema categoriza fluxos; não há saldo inicial nem
  transferências.
- **Movimento se exclui, referência se desativa.** Lançamento errado é apagado de
  verdade (DELETE físico em `tb_despesas`); tabela de referência nunca.
  Configuração, linha de orçamento e **resumo anual** também se excluem (são
  entrada do usuário). Nenhum dos três tem `ativo`.
- Despesas compartilhadas da casa vão para uma pessoa chamada **Casa**.
- Consulta de despesas é tela separada da de lançamento. **Receitas são tela
  única.** A assimetria é intencional.
- **Ano/mês inválido na URL cai no período corrente**, sem erro e sem tela vazia.
- Prioridade (1–4) só existe quando a essencialidade efetiva é "Não Essencial" —
  isso é regra da aplicação, não do banco, e é limpa no servidor mesmo que o POST
  traga valor.
- Orçamento é por subcategoria, mês a mês, com uma receita planejada global.
  **Zero é planejado legítimo** ("está no plano, não pretendo gastar") — assimetria
  deliberada com lançamento, que exige `> 0`. Mês **encerrado** não recebe
  INSERT/UPDATE/DELETE; reabrir só se não existir mês orçado posterior. Criar um
  mês copia o anterior se existir, senão usa a média de 12 meses — `criar()`
  escolhe, o usuário só aperta "Criar". A recusa por mês encerrado é **409** com
  faixa vermelha (`flash--erro` em `#orcamento-aviso`) que fica até a próxima
  ação — da 23 à 28 ela era verde e sumia em 4,5 s, por colisão de nome com
  `.aviso-inline`. Modo (Montagem | Acompanhamento) e período (Mês | Acumulado
  no ano) são `.segmentado`; a URL é o estado. A montagem não tem cards.
- Nos painéis, só categorias e pessoas **com despesa no período** aparecem. Na
  tabela mensal da Anual os 12 meses aparecem sempre.
- **Análise por subcategoria** (`/analise/subcategoria`, rodada 24): no grupo
  Painel, uma subcategoria por vez, **sem olho**. Tudo por GET — **a URL é o
  estado**, recarga inteira, sem HTMX: a tela é reproduzível por link. Período
  (3, 6, 12 meses terminando no mês corrente, série inteira do **acervo** ou
  personalizado), agrupamento (mensal, trimestral, anual, 12 meses móveis) e
  correção pelo IPCA. Valor inválido cai no padrão; só o personalizado com mês
  invertido ou malformado dá erro de formulário, e aí **nada é desenhado**.
  **Zero é zero**: mês sem lançamento vira ponto zero com quantidade 0, nunca
  buraco interpolado — e o gráfico não suaviza, porque curva entre zeros
  desenharia gasto negativo. **Base da correção = último mês carregado** de
  `tb_ipca`; mês posterior a ela usa fator 1. A deflação é por lançamento, em
  SQL, e a soma vem depois: deflacionar a soma do trimestre por um índice só
  daria outro número. Bucket que não cabe inteiro no período ou que contém o
  mês em curso é **parcial**. Ela soma a subcategoria INTEIRA e **continua
  sem ler `integra_ipca`**, de propósito: quem separa as duas coisas é a
  Análise por prioridade. Desde a rodada 26 o corpo da tela (barra de
  filtros do período para a direita, estados vazios, resumo, gráfico e
  tabela) mora em `templates/main/_analise.html`, que as duas estendem.
- **Tela do IPCA** (`/cadastros/ipca`, rodada 22): só leitura, no menu logo
  abaixo de "Resumos anuais" (ícone Lucide `percent`) e, desde que
  Configurações virou grupo próprio na rodada 25, o **último item de
  Cadastros**; sem olho — o
  IPCA é número público do IBGE, não quanto a casa gastou. Matriz ano × 12
  meses, ano mais recente em cima, com a coluna **"No ano"** = índice do
  último mês carregado do ano ÷ índice de dezembro do ano anterior − 1, a
  mesma nos dois modos e **nunca gravada**. Alternar Variação mensal |
  Número-índice é GET (`?modo=`), modo inválido cai em variação. Mês sem dado
  e variação não publicada viram travessão; 1993 só tem dezembro e "No ano"
  dele é travessão, porque não há dezembro de 1992.
- **Botão "Atualizar do IBGE"** (rodada 23): POST com CSRF por HTMX, na mesma
  tela, com o **mesmo `ipca.carregar`** do comando — o que muda é só a espera
  (**20 s** na web, porque quem clicou está olhando a tela; 60 s no terminal)
  e o formato do relato. O `--timeout` do gunicorn, decidido na rodada 33, é
  150 s — quem o dita é o backup, não o IPCA, e os 20 s cabem folgados. A resposta traz o cartão inteiro (faixa,
  dica, nota, tabela) e o subtítulo fora de banda, no modo em que a pessoa
  estava. A **faixa** é texto de servidor e não é estado: some ao recarregar.
  Diz "Nenhum mês novo", "<Mês> carregado: índice e variação" ou "N meses
  carregados (<intervalo>)", e acrescenta "N mês(es) revisado(s) pelo IBGE" e
  a frase de variação nula quando houver. A **dica** ("O IBGE já deve ter
  publicado <mês>") sai de `mes_esperado`: a partir do **dia 12** espera-se o
  mês anterior, antes disso o retrasado. Dois cliques não viram duas buscas —
  o botão se desabilita —, e mesmo que virassem a gravação é upsert.
- **Resposta de erro que a tela mostra é 409, 502 ou 503**, e só. 409 é regra
  de estado recusada (mês de orçamento encerrado), 502 é o IBGE que não
  respondeu ou respondeu torto, 503 é o banco que recusou a gravação. O
  `<meta name="htmx-config">` do `base.html` manda o HTMX trocar **só esses
  três**; qualquer outro 4xx/5xx segue o padrão dele e não troca nada, porque
  um 500 não tratado traz a página de erro do Flask (com `--debug`, o
  traceback do Werkzeug) e ela não pode cair dentro de um cartão ou de uma
  `<tr>`. Sem essa configuração o HTMX 2 descarta todo 4xx/5xx em silêncio —
  foi o que aconteceu com o 409 do orçamento, escrito na rodada 15 e invisível
  até a 23.
- **Resumo anual**: um texto livre por ano, sem tamanho máximo, sem formatação
  (quebras de linha preservadas, nada de Markdown). O ano é a chave — há no
  máximo um resumo por ano, e a edição não troca o ano. Só se oferece ano que a
  Visão Anual mostra e que ainda não tem resumo. Na Anual, **ano sem resumo não
  mostra card, aviso nem convite para escrever um**.
- **Análise por prioridade** (`/analise/prioridade`, rodada 26): no grupo
  Painel, logo abaixo da Análise por subcategoria (ícone `chart-column`), sem
  olho. Divide com ela tudo menos o recorte — período, agrupamento, correção,
  resumo, gráfico e tabela são o mesmo código. Uma **faixa** por vez, sem
  mistura: Essencial, P1, P2, P3 ou P4. "Essencial" é a essencialidade
  **efetiva** da view e **ignora a prioridade gravada** — o banco não impede
  que uma despesa essencial carregue prioridade de um registro antigo, e isso
  não a move de faixa. P1–P4 são `Não Essencial` com aquela prioridade, e
  quem não tem prioridade **não cai em faixa nenhuma**: é desprezada, sem
  sexta faixa e sem engordar a P4 (não precisa de cláusula — `prioridade = 4`
  sobre NULL não é verdadeiro). Faixa ausente ou desconhecida é convite,
  **nunca um padrão**: as cinco respondem perguntas diferentes.
  É o **único lugar do sistema que lê `integra_ipca`**: só entra o que
  integra a série histórica, inclusive com a correção desligada. Daí o aviso
  fixo abaixo da barra de filtros, visível até no convite e no "nenhum
  lançamento", e a nota de rodapé que diz quantos lançamentos e quanto
  ficaram de fora **no período exibido** — um número do período inteiro, não
  por ponto, e vindo da MESMA consulta, por `GROUPING SETS ((mês), ())`.
  Quando TODAS as despesas de um período foram desprezadas, a tela desenha a
  série em zero e explica na nota, em vez de dizer "nenhum lançamento" sobre
  um mês em que se gastou.
- **Resumo das análises** (média, mediana e total): três cards `kpi` antes do
  gráfico, nas duas telas. Saem dos pontos já compostos — sem consulta nova,
  e dos MESMOS números que a tabela imprime, para somar a coluna à mão dar o
  total do card. **Só períodos completos**: parcial fica de fora, porque o
  mês em curso arrasta a média sem que nada na tela explique por quê (nos 12
  meses de "Essencial" tirava R$ 300). Com menos de **dois** completos o card
  não aparece — é o que acontece com agrupamento anual numa janela de 12
  meses, onde os dois anos estão recortados. Com a correção ligada o resumo é
  dos valores reais; sem ela, dos nominais. Nunca dos dois.
- **Independência financeira** (`/independencia`, rodada 29): a **única** tela
  que lê TSR, S e R de `tb_configuracoes`. Modelo do Mr. Money Mustache —
  `n = ln(1 + r·(1−s)/(s·TSR)) / ln(1+r)` —, e a **simulação entra pela
  querystring** (`?s=&r=&tsr=`), sem gravar nada: o vigente continua sendo o do
  banco e a tela diz quando está simulando. Premissa ausente ou impossível
  (`s ≤ 0`, `TSR ≤ 0`, `r < 0`) vira travessão, **nunca um padrão inventado**.
  Desde a rodada 31 há uma segunda fileira de cards, **Ponto de partida**, que
  conta os anos restantes a partir da última foto de patrimônio em vez de zero:
  `n = ln((G/TSR + A/r)/(P₀ + A/r)) / ln(1+r)`. As duas são a MESMA fórmula (a
  primeira é a segunda com `P₀ = 0`), e o invariante prova. A taxa de poupança
  realizada e o gasto anual saem dos **últimos 12 meses fechados** — o mês em
  curso entraria pela metade e puxaria a meta para baixo. Sem foto de
  patrimônio, a segunda fileira não aparece.
- **Ativos e foto de patrimônio** (rodada 30): `tb_ativos` é cadastro comum
  (Cadastros › Ativos; `classe` é texto livre pela macro `combobox`, e inativo
  aqui lê-se "posição encerrada"). A **foto** é mensal e mora em
  `/lancamentos/patrimonio`: uma data, sempre **fim de mês**, e o valor de cada
  ativo naquela data. A grade **é** o editor — gravar é um POST só que faz
  upsert do que foi preenchido e **DELETE do que foi esvaziado**, numa
  transação. Campo vazio quer dizer "não havia esse ativo nessa data", e daí
  decorre que **gravar uma grade inteiramente vazia apaga a foto daquela
  data**: é o contrato, não um defeito. **Zero é valor legítimo** (posição
  zerada), como no orçamento. Data futura o servidor recusa, com texto no
  campo. Trocar de mês é por **link** (as setas ao lado da data), nunca pelo
  campo — ver a armadilha do `<input type="date">` na seção HTMX.
- **Tendência e projeção** (rodada 31 e ajustes posteriores): abaixo da
  evolução, um segundo gráfico com a série observada e a curva **exponencial
  ajustada**, esticada por **cinco anos** (`MESES_PROJETADOS = 60`). Pede pelo
  menos **seis** fotos; foto zerada fica de fora do ajuste (não há `ln(0)`) e o
  rodapé diz quantas. O eixo é uma grade **mensal contínua**: mês sem foto é
  buraco na série observada e a curva não ganha degrau falso. Ali o buraco se
  liga (`spanGaps`) — "não medi" não é "valia zero", ao contrário das
  Análises, onde o zero é resposta e a linha tem de encostar no eixo. Com a
  caixa do IPCA ligada, o ajuste é sobre a série corrigida e a projeção sai em
  poder de compra do mês base, que é o que se compara com o número de
  independência. **Não há outra projeção**: nem aporte previsto, nem meta, nem
  cenário. A curva diz só o que a série vem fazendo.
- **Backup** (`/configuracoes/backup`, rodada 25): a página **só exporta**.
  Não há restauração pela interface — a tela mostra o comando do `psql` e
  quem o roda é o dono —, não há histórico de backup (nem tabela, nem log,
  nem "último backup em", que mentiria assim que o arquivo fosse apagado) e
  não há agendamento: o dump sai por clique, e por mais nada. Desde a rodada
  33 o `pg_dump` é o da **própria máquina que serve o app** e fala com o banco
  **por TCP**: host, porta, usuário, banco e senha saem do `DATABASE_URL` por
  `conninfo_to_dict`, e a senha vai em **`PGPASSWORD` no `env=` do
  subprocesso** — nenhuma credencial na linha de comando, que é visível a
  quem liste os processos. O executável é o `PG_DUMP` do ambiente ou o
  `pg_dump` do PATH: no Windows do desenvolvimento a variável aponta para o
  `.exe`; na imagem de produção o `postgresql-client` já o põe no PATH.
  `--no-password` está lá para o erro não virar espera: sem ele o `pg_dump`
  PERGUNTA a senha no terminal e o worker fica parado até o `TEMPO_LIMITE`,
  e a tela diria "tempo esgotado" onde houve credencial errada. Um `pg_dump`
  mais novo que o servidor funciona; o contrário, não. O dump é
  **bufferizado inteiro** e só vira resposta com `returncode == 0` e stdout não vazio: streamar daria
  200 antes de saber o desfecho, e uma falha no meio deixaria um `.sql`
  truncado com cara de backup. Nada em disco do servidor. Em qualquer falha,
  **nenhum download**: `flash` de erro com as últimas linhas do stderr e
  volta para a tela.
- **Troca de senha** (`/conta/senha`, rodada 32): o usuário troca a própria
  senha pela interface, e chega lá pelo **nome no rodapé da sidebar** — não
  há item de menu, e não deve haver. POST comum com redirect para a própria
  página (PRG), **sem HTMX** e sem `?retorno=`. Quatro recusas, cada uma com
  o texto no campo que errou: senha atual que não confere, nova com menos de
  **8 caracteres**, confirmação diferente e nova igual à atual. Recusa não
  grava nada e os três campos voltam vazios. **Trocar a senha não invalida
  sessão nenhuma** — nem as outras do mesmo usuário, nem a de quem trocou: é
  decisão desta rodada, e o motivo é o tamanho do que há a proteger (sistema
  doméstico, fora da internet, dois usuários). Não existe "esqueci a senha",
  recuperação por e-mail, medidor de força nem tela de perfil: quem perdeu a
  senha usa `flask set-password`, que é o caminho administrativo. **Um lugar
  só gera hash de senha**: `auth/servico.py`, por onde passam a tela e o
  comando; conferir a senha atual é da rota, porque o comando existe
  justamente para quem não a tem.
- **Versão e histórico de versões** (rodada 32): a versão do sistema é o
  **primeiro título de nível 2 do `CHANGELOG.md`** da raiz (`^## (\S+)`, na
  primeira linha que casar), e **não existe constante de versão em Python**.
  O arquivo é lido UMA vez, no `create_app`; mudar o changelog exige
  reiniciar, o que é aceitável para algo que muda uma vez por versão.
  Changelog ausente ou sem título **derruba a subida** — a mesma regra da
  Independência, onde premissa que falta vira travessão em vez de padrão
  inventado; aqui nem travessão serve. O número aparece no rodapé da sidebar
  (discreto, sem acento) e leva a `/changelog`, que mostra o arquivo
  renderizado por Python-Markdown **no servidor**, dentro de um `.card
  prosa`. O HTML é marcado como seguro porque é arquivo do repositório, e
  não entrada de usuário.
  Foi ele que fez **Configurações virar grupo próprio** na sidebar (fechado
  por padrão, como Cadastros), com "Parâmetros" e "Backup" — até a 24 era um
  item só no fim de Cadastros. O rótulo da tela de parâmetros mudou; o
  endpoint e a URL `/configuracoes`, não.

## 7. Convenções de código que o projeto exige

### Servidor

- **Nada é decidido em Jinja.** Cor, travessão, estado de estouro, classe CSS,
  plural, contador — tudo vem pronto do Python. O template escolhe o formato
  (macro `reais`, filtro `numero`) e emite o nome da classe que recebeu.
- **Agregados vêm de consulta própria**, nunca de soma em Python sobre a página.
  A exceção prevista é composição em `Decimal` sobre conjunto **pequeno e
  completo** cuja definição É "estas linhas", e ela tem exatamente dois usos:
  o `total_exibido` das 15 recentes e a média, a mediana e o total do resumo
  das análises, que saem dos pontos já compostos. Um terceiro uso é sinal de
  que faltou uma consulta.
- **Dois lugares que mostram o mesmo número leem da mesma origem.**
- Formatação: `moeda`; percentual pelo filtro `numero` (vírgula, uma casa); sem
  denominador → travessão (`fracao` devolve `None`); **negativo em vermelho no
  `<span>`**, travessão nunca vermelho.
- Valor monetário entra com vírgula (`converter_valor`). `UniqueViolation` vira
  erro de campo legível. Transação por request; rollback em erro.
- Ordenação alfabética pt-BR em Python com `chave_alfabetica` (NFD), nunca `locale`.
- Busca textual escapa `%` e `_` (`ESCAPE '\'` em **raw string**), sem `unaccent`.
- `destino_interno` em todo redirect que aceita `?next=` / `?retorno=`.
- **Helper duplicado é contradição**: promova para `util.py` na hora e aponte
  todos os módulos para lá.
- **O cookie de sessão tem nome próprio**: `SESSION_COOKIE_NAME =
  "freedom_session"`, em `config.py` (rodada 35). O servidor de produção
  hospeda outros sistemas web na mesma máquina, em portas diferentes, e
  **cookie de navegador ignora porta** — mesmo host, mesmo pote. Outro app
  Flask de lá gravava `session`, o nome padrão, e os dois se sobrescreviam: o
  Freedom deslogava sozinho segundos depois do login, sem nenhum `/logout` no
  meio, e o outro sistema caía quando o Freedom abria. Trocar o nome é o
  conserto inteiro; não há nada a fazer no `.env`, no compose nem na imagem.
- **Requisição do HTMX sem sessão manda o navegador embora, nunca devolve a
  tela de login como fragmento.** É o `unauthorized_handler` de
  `create_app`, e ele tem dois caminhos porque são duas perguntas. Com
  `HX-Request`: **204 sem corpo** mais `HX-Redirect`, que o HTMX trata ANTES
  de qualquer troca (conferido no `htmx.min.js` 2.0.4: o `location.href` sai e
  a função retorna, sem passar pelo `responseHandling`). O `?next=` vem do
  `HX-Current-URL` reduzido por `util.caminho_interno` — `request.url` ali é a
  rota do fragmento, que não é lugar de voltar —, e cabeçalho ausente ou de
  fora vira login sem `next`, nunca um `next` inventado. Sem `HX-Request`:
  exatamente o que o Flask-Login fazia, pelo mesmo `login_url`, com o mesmo
  flash e o mesmo `?next=` (provado igual na rodada 35, contra o manipulador
  padrão). Sem isso, o 302 era seguido pelo XHR e a página de login inteira
  caía dentro do formulário de despesa, no lugar das sugestões.

### HTMX

- Filtros são GET na URL com `hx-push-url`; a mesma rota devolve página ou
  fragmento conforme `HX-Request`, com exceção para `HX-History-Restore-Request`.
  **Exceção deliberada**: seletores de painel e de orçamento recarregam a página
  inteira.
- **`<template>` em resposta out-of-band que comece com `<tr>`.** Misturar `<tr>`
  e `<div>` soltos põe o parser em contexto de tabela e expulsa os `<div>`.
- **Swap OOB que não seja `outerHTML`/`true` insere o CONTEÚDO do elemento
  marcado, não o elemento.** Para inserir uma `<tr>` com
  `hx-swap-oob="beforeend:#alvo"`, embrulhe-a num `<tbody>` que carregue o
  atributo — senão chegam `<td>` soltos, que o parser descarta.
- **Alvo de troca OOB que às vezes não aparece continua no DOM, com `hidden`.**
  Elemento que some não pode ser trocado (é a razão do `#bloco-prioridade` e,
  desde a rodada 20, do `#botao-novo-resumo`). Cuidado com o par disso no CSS:
  `display` de folha de autor vence o `[hidden]` do navegador — já resolvido
  para `.btn`.
- Uma ação que muda duas regiões da tela devolve as duas de uma vez: o alvo
  principal e o resto fora de banda. Excluir um resumo anual troca a lista
  **e** o botão da barra superior, porque os dois dependem do mesmo fato.
- Estado de UI que sobrevive ao re-render vai em `<input type="hidden">`; filtro
  fora do formulário vai por `hx-include`.
- `hx-vals` para renomear parâmetro; `hx-params="none"` cancela. O gatilho
  `changed` **ignora preenchimento por JavaScript** (`fill` não dispara `keyup`) —
  isso vale inclusive para escrever teste.
- `HX-Retarget` quando o alvo natural do disparador não é onde a resposta cai.
- Rota só de fragmento: sem `HX-Request` → redirect para a página-mãe com os
  mesmos parâmetros, **antes** de qualquer 404. Regra de estado recusada → **409**.
- **`<input type="date">` trava a tela inteira numa combinação impossível.**
  Quem está em 31/01 e mexe só no segmento do mês para 02 põe o campo em
  31/02: o Chrome zera o controle (`value` vazio, `validity.badInput`), o
  formulário passa a falhar na validação do HTML e **nenhum botão responde
  mais, sem mensagem** — o `hx-post` inclusive, porque o HTMX valida o que o
  `hx-include` traz e aborta (`htmx:validation:halted`). O campo **não se
  recupera editando**: só recarregando. `novalidate` destrava o submit comum,
  mas **não** o HTMX. Onde a data é sempre fim de mês, a saída é navegar por
  **link** (as setas de mês da foto de patrimônio): link não passa por
  validação de formulário, e por isso é também a saída quando o campo já
  travou.
- **HTMX troca DOM, não dispara download.** Uma resposta com
  `Content-Disposition` chegando por `hx-post` é engolida pelo swap e o
  arquivo nunca aparece. Quem baixa arquivo é `<form method="post">` comum,
  **sem nenhum atributo `hx-`**, e aí o token CSRF precisa ir num
  `<input type="hidden">`: o `hx-headers` do `<body>` não vale para um POST
  que o navegador faz sozinho. Único caso hoje: "Confirmar e baixar" da
  página de Backup. Por ser POST comum, a falha também segue o caminho
  comum — `flash` mais redirect, e não fragmento com status de erro.

### CSS (`static/css/app.css`, ~5.030 linhas, seções numeradas)

```
1 Variáveis   2 Reset   3 Fundo   4 Layout   5 Componentes   6 Login
7 Responsivo (< 768px)   8 Utilitários

Dentro de 5: 5.1 Card, 5.2 Botão, 5.3 Formulário, 5.4 Tabela, 5.5 Badge,
5.6 Flash, 5.8 Estado vazio, 5.9 Lançamento, 5.10 Consulta, 5.11 Autocomplete,
5.12 Parâmetros, 5.13 Painéis (5.13.1 Gráficos, 5.13.2 Tabelas, 5.13.3 Visão
Anual), 5.14 Visão Mensal (5.14.1 Detalhe), 5.15 Orçamento (5.15.1 faixas),
5.16 Valores sensíveis, 5.17 IPCA, 5.18 Análises, 5.19 Backup,
5.20 Edição em linha, 5.21 Independência financeira, 5.22 Patrimônio,
5.23 Prosa (o HTML que veio de Markdown: só o histórico de versões, e o
único do sistema que chega ao template sem classe em elemento nenhum — daí
a classe de componente, que impede `h2`/`ul`/`code` soltos de alcançarem
toda tela).
5.7 é lacuna (modal removido na 17) e fica lacuna; 5.18 virou só comentário
na rodada 31, quando as duas classes dela foram adotadas por outras telas e
subiram (`.marca-parcial` para 5.13.2, `.filtro-caixa` para 5.10):
componente novo entra no fim.
```

- A seção 1 tem **uma camada só**: os tokens do design system (`--bg`, `--ink-*`,
  `--accent`, `--control-h`, `--green-ink`…). Os apelidos do tema roxo antigo
  (`--cor-*`, `--vidro*`, `--solido*`, `--linha*`, `--raio-*`, `--sombra-*`)
  viveram numa camada (b) da rodada 17 à 28 e **não existem mais**: um deles
  reaparecendo é código velho sem definição, e o navegador o ignora em silêncio.
  `card--solido` também não existe.
- Tema: fundo `#F5F5F7`, cartão branco raio 14, sidebar escura, acento teal
  `#30B0C7`. **Verde e vermelho são reservados** a receita, despesa e valor
  negativo — não servem de decoração. O único `backdrop-filter` do sistema é o da
  `.pagina-cabecalho` (desktop); a `.topo-mobile` não tem, e tirar o dela mudou o
  antialiasing da marca (ver seção 9).
- `font-variant-numeric: tabular-nums` é global (no `body`).
- Utilitário nasce **global**, na seção 8. Classe utilitária criada dentro de um
  seletor de tela não funciona fora dela e o erro é silencioso.
- Componente que uma segunda tela adota **sai da seção da primeira** e perde o
  nome que falava daquela tela. Já aconteceu três vezes: o seletor segmentado
  era `.anos`, dentro do bloco da Visão Anual, e virou `.segmentado` na seção
  5.2 quando a tela do IPCA passou a alternar variação e número-índice com o
  mesmo desenho; a nota de rodapé do cartão de tabela era `.ipca-nota` e virou
  `.nota-rodape` na 5.1 quando a análise por subcategoria passou a fechar o
  cartão do mesmo jeito; e a dica de mês provável era `.ipca-dica` e virou
  `.nota-topo` na 5.1, ao lado da irmã, quando a análise por prioridade
  passou a abrir com um aviso no mesmo lugar. Copiar teria criado a segunda
  cópia; deixar o nome teria criado o comentário que mente. Renomear não mexe
  em pixel, e o SHA prova. Nas rodadas 27 e 28 foram mais quatro: o `.kpi`
  saiu de 5.13.3 para 5.13 quando as Análises já o usavam; `.tabela--anual`
  virou `.tabela--painel` em 5.13.2 quando a Mensal a adotou; `.linha-subgrupo`
  subiu de 5.14.1 para 5.13.2 (três telas); e `.linha-edicao`/`.config-edicao*`,
  que o Orçamento escrevia desde a 15 sem ser configuração, virou `.edicao-linha`
  na 5.20. A tabela mês a mês da Anual chama-se `.tabela--meses` — o nome antigo
  (`.tabela--mensal`) era o da outra tela.
- **Tokens em pares**: `--orange-ink`/`--orange`, `--green-ink`/`--green` — o
  `-ink` é tinta de texto, o puro é preenchimento. Um apelido só para os dois
  deixou a barra do alerta do orçamento marrom até a 28. Lavagem neutra de
  estrutura (coluna fixa da matriz, linha de subtotal) é `--ink-ghost` (`--ink` a
  2,5%); teal, verde e vermelho contam alguma coisa e não servem para separar.
- **Seletor de descendência alcança tabela aninhada e linha especial**:
  `.tabela--painel td:first-child` chega ao detalhe da Mensal e à célula da
  edição em linha. Quem não é ponta de cartão se protege com regra de mesmo peso
  declarada depois (`.tabela--painel .linha-detalhe > td`, as guardas de 5.14.1)
  ou com classe própria (`.edicao-linha__celula`) — nunca subindo o peso da regra
  de que a Anual depende.
- **Todo card vem do helper `card` de `main/servico.py`** (Anual, Mensal,
  análises, acompanhamento do Orçamento). O template `.kpi` lê `c.classe`,
  `c.apoio_rotulo`, `c.apoio_classe` e `c.nota`; cor, travessão e texto nascem
  lá. `apoio_rotulo` existe porque a classe pinta o número, não a palavra
  "planejado".
- **Sidebar**: preferência das seções em `localStorage`
  (`freedom.sidebar.<secao>`; Cadastros e Configurações fechadas por padrão). O
  grupo do item ativo abre sozinho pelo `temAtivo()` do script colado às seções,
  antes de pintar e **sem gravar** — a preferência é do usuário; fechar à mão
  grava, e a próxima tela do mesmo grupo reabre.
- **O vão entre os blocos de uma tela é o `.painel` da seção 4**, e não
  `margin-top` em cada bloco: quem conhece a distância é o arranjo da página.
  As duas Análises passaram a usá-lo na rodada 26 — até ali os cartões se
  tocavam (base do gráfico 628, topo da tabela 628) e ninguém tinha
  reparado, porque o cabeçalho da tabela tem fundo próprio.
- A `.painel-grade` é a grade de cards do projeto (4 colunas, 2 abaixo de
  1100px, 1 abaixo de 768px). `.painel-grade--tres` é a mesma com três, do
  resumo das análises; o modificador mora junto da grade, e não na seção da
  tela, porque é a mesma grade com outra contagem.
- **O mesmo vale para o JavaScript**: `graficos.js` nasceu na rodada 24 com o
  que a Visão Anual e a Análise repetiriam. Nenhum hexadecimal nele — cor
  continua saindo de variável CSS por `getComputedStyle`.
- `1fr` tem mínimo `min-content`: em grade com canvas ou tabela larga, use
  `minmax(0, 1fr)`.
- **Texto de cartão ocupa a largura do cartão.** Nada de `max-width` em `ch`
  para "encurtar a linha de leitura": num monitor largo isso quebra o parágrafo
  no meio do cartão e estica a altura à toa. Quem decide o comprimento da linha
  é a largura da tela, como no resto do painel. (Tentado e desfeito no card de
  resumo anual, rodada 20.)
- Texto livre do usuário: `white-space: pre-wrap` preserva as quebras sem
  interpretar formatação, e `overflow-wrap: anywhere` impede que uma URL sem
  espaço alargue a página no celular. Os dois andam juntos.
- `.so-leitor` é absoluto: dentro de contêiner que rola precisa de ancestral
  `position: relative`, senão ele estica a página inteira.
- `display` de folha de autor vence o `[hidden]` do navegador (regra de user
  agent). Todo componente com `display:` próprio precisa de
  `.componente[hidden] { display: none }` — feito para `.btn` na rodada 20,
  quando um botão passou a sumir da barra superior.
- `white-space: nowrap` herdado estica tabela no celular — sempre desfaça na
  seção 7.
- Chart.js: contêiner com **altura fixa** e `maintainAspectRatio: false`; eixo sem
  centavos, tooltip com centavos; **cores lidas de variáveis CSS por
  `getComputedStyle`** — nenhum hexadecimal no JS.
- O rótulo do eixo Y tem **três faixas** (`naEscala` do `graficos.js`): reais
  cheios, `mil` e `mi`. A **unidade** de milhão sai do MAIOR valor do eixo, e
  não do passo — com marcações de 400 em 400 mil o passo não chega ao milhão,
  mas os rótulos sim, e saía "R$ 1200 mil". As **casas decimais** saem do
  passo, e são iguais no eixo inteiro: é o que impede duas marcações vizinhas
  de virarem o mesmo texto. Abaixo de um milhão nada mudou, e o SHA da Visão
  Anual e das Análises prova.
- **Linha de tendência**: `ajuste_exponencial` faz mínimos quadrados sobre
  `ln(y)` em `Decimal`, que é o mesmo cálculo da "linha de tendência
  exponencial" do Excel. O **R², porém, não segue a reta do logaritmo**: o
  Excel mostra o quadrado da correlação entre observado e ajustado, de volta
  na escala original, e é isso que a tela exibe. Não é detalhe — na série do
  dono a mesma curva dá 0,833 pela primeira definição e 0,956 pela segunda, e
  é a segunda que está na planilha dele (0,954 até julho de 2026, conferido
  contra o CSV). O eixo da tendência é uma grade MENSAL contínua (e não uma
  marca por foto), senão um mês sem foto daria um degrau falso na curva.
- **Eixo X de uma série que cresce sem teto** (uma marca por foto, na evolução
  do patrimônio) precisa de `maxRotation: 0` e `maxTicksLimit`: sem isso o
  Chart.js gira as datas a 50° e elas comem mais altura que o desenho (154 px
  de plotagem em 230). A data exata de cada ponto fica no tooltip.

### Ocultar valores — o olho (rodada 19)

O dono às vezes abre o sistema com alguém olhando a tela. O botão olho da Visão
Anual apaga **todo número da tela**. A proteção é **visual**: os números
continuam no HTML e no JSON dos gráficos, e isso é aceitável.

**Como marcar.** Nada de servidor: nenhuma rota, nenhum cookie, nenhuma sessão
Flask, nenhum Python. Só quatro classes, globais, na seção **5.16** do CSS:

| Marca | Onde vai | O que faz oculto |
|---|---|---|
| `.sensivel` | no elemento **mais interno**, o que embrulha o valor | vira bloco cinza da largura do texto |
| `.sensivel-bloco` | na caixa toda | a caixa inteira vira o bloco, com o que houver dentro |
| `.sensivel-barra` | no trilho (ou na célula que contém a barra) | o sulco fica, a fatia colorida some |
| `.sensivel-area` | na área do gráfico | a área vira bloco neutro e o conteúdo fica invisível |

- Marcar não pode mudar a tela com os valores à mostra: `.sensivel` sozinha não
  declara nada. Mas **um `<span>` a mais no meio de uma frase muda o
  arredondamento das letras seguintes** — o diff de pixels da rodada 19 pegou
  isso na linha de apoio da tabela mês a mês em 390px. Por isso valor no meio de
  texto se esconde pela caixa em volta (`.sensivel-bloco`), nunca por um `<span>`
  no meio da frase.
- Os seletores começam em `:root[data-valores=...]`: sem o `:root` o peso perde
  para regra de tela (duas classes mais um elemento) e o texto continua pintado.
- `display: none` no canvas está **proibido**: o Chart.js mede o pai a cada
  redimensionamento. Use `visibility`, que também tira o canvas do ponteiro e
  mata o tooltip.
- `user-select: none` é o que impede o Ctrl+A de revelar — sem ele o realce da
  seleção pinta o texto por cima do bloco.
- Continuam visíveis: barra superior, rótulos, títulos de cartão, cabeçalhos de
  tabela, nomes de mês e de categoria, e "Total".

**Onde mora o estado.** Em `data-valores` (`ocultos` | `visiveis`) no `<html>`,
escrito por um script inline no bloco `cabeca` de `templates/layout_app.html` —
o único dono. O CSS lê dali e o `aria-pressed` do botão sai da mesma função:
os dois nunca divergem. O estado pertence à **aba**, não à tela nem ao usuário.
**O servidor sempre manda a página oculta**: sem JavaScript ela fica oculta
(falha fechada) e não há um quadro sequer com valor à mostra.

**As regras, todas verificadas em navegador:**

- **(a)** aba nova, ou entrar de novo depois de sair → oculto;
- **(b)** o olho alterna;
- **(c)** com valores à mostra, continuam à mostra ao trocar de ano, ir a outra
  tela e voltar (link ou Voltar do navegador) e recarregar com F5;
- **(d)** sair da aba (outra aba, janela minimizada, trocar de app no celular) →
  ao voltar, oculto, sem recarregar;
- **(e)** fechar a aba → oculto na próxima vez, **inclusive** se o navegador
  restaurar a aba ou duplicá-la copiando o `sessionStorage`.

**Como (c), (d) e (e) convivem:** um **bastão** no `sessionStorage`, entregue no
`pagehide` de quem sai e **consumido na leitura** por quem entra — enquanto a
página vive não há nada guardado, então aba duplicada copia um armazém vazio. O
bastão leva a hora e só vale por **300 ms**, e esse prazo tem um único trabalho:
fechar a aba e navegar são a mesma sequência de eventos, e o prazo é o que
impede uma aba **reaberta** de herdar o bastão do fechamento. Navegação real
chega com 2–4 ms (13 ms com a CPU 4× freada, 101 ms com 20×); reabrir aba à mão
leva muito mais.

> **Armadilha:** `visibilitychange` com `hidden` dispara também quando a
> **própria aba navega** — trocar de ano, clicar no menu, F5 — e não só quando o
> usuário sai dela. Tratar todo `hidden` como "saiu da aba" transforma (c) em
> (d). O que separa os dois é a **ordem**, não o relógio: **quando a aba navega,
> o `pagehide` vem sempre antes do `hidden`** (medido em F5, troca de ano, link,
> Voltar e ida para o bfcache). `hidden` depois do `pagehide` deste documento é
> navegação; `hidden` sozinho é saída de aba. Validação que não prova os dois
> lados não prova nada.

> **Segunda armadilha, a que só aparece no navegador de verdade:** Voltar pode
> devolver o documento **inteiro** do cache de ida e volta (bfcache), vivo, sem
> carregar nada — e o `pageshow` de quem volta dispara **antes** do `pagehide` de
> quem sai (medido: 1 ms antes), então ali o bastão ainda nem foi entregue. Quem
> volta do cache é o mesmo documento e volta como estava; a única coisa que pode
> ter tirado dele o direito de ver é o usuário ter saído da aba enquanto ele
> dormia, e isso a outra tela anota na marca `freedom.valores.saiu` no momento em
> que a saída acontece — já gravada quando o `pageshow` lê. A marca morre quando
> a aba reconquista o direito. O Playwright **desliga o bfcache** (página com
> depurador atado não entra no cache), então essa falha não aparece em teste
> automatizado comum: foi preciso soltar o CDP e mandar Alt+Seta esquerda pela
> janela do Windows.

A detecção de saída de aba roda em **toda tela autenticada** — sem isso (d)
falha quando o usuário sai estando em "Lançar despesa". Mas **o olho e as
marcações existem só na Visão Anual, por decisão do dono**: as outras telas não
o ganham, nem a de cadastro de resumos anuais, onde o texto é escrito. O
mecanismo continua pronto para outra tela aderir (basta marcar os elementos e
repetir o botão) — só não é para fazer isso sem ele pedir.

Marcado na Anual desde a rodada 20: o **texto do card de resumo do ano**
(`.resumo-ano__texto`, com `.sensivel`). Explicar os números é falar deles.
Título do card e link "Editar" continuam visíveis.

### Celular (< 768px) — preservar sempre

- A sidebar vira barra superior com botão de menu; as seções recolhíveis do menu
  não se aplicam ali (tudo visível).
- Grades de cards 1/2/4 colunas (quebras em 768 e 1100); gráficos 1/2.
- Coluna principal larga (descrição) → texto de apoio **dentro da célula**;
  coluna principal estreita (mês) → `<tr class="linha-apoio">` com `colspan`.
- Rolagem interna (`.tabela-caixa`) é aceitável e é o padrão; **rolagem horizontal
  da página não é**. As duas tabelas do Orçamento rolam por dentro e repõem o
  `min-width: 560px` que `.tabela--painel` larga; Parâmetros não rola (é
  `.tabela--cadastro`). O Orçamento não tem layout de celular, e isso é decisão.
- Ações viram ícone com `aria-label` só onde o padrão já existe (detalhe da
  Mensal); nas demais tabelas os botões empilham com texto.
- Botão da barra superior cresce por `flex: 1 1 auto`, e não por `width: 100%`:
  onde há um botão só o resultado é o mesmo, e onde há dois (Anual: "Lançar
  despesa" mais o olho, que é `.btn--icone` com `flex: none`) eles dividem a
  linha em vez de empilhar.

## 8. Trabalhando com dado real

O banco de desenvolvimento **é** o banco de produção do dono. Portanto:

- **Nenhuma rodada apaga linha que não criou.** Faxina de teste sempre por id
  (ou pela chave, onde a chave não é `id`: o ano, em `tb_resumos_anuais`), e a
  chave é relatada. Onde a linha é texto do dono, confira o prefixo `zz teste`
  **antes** de apagar.
- **O dono escreve enquanto você trabalha.** Ele lança despesa, e desde a
  rodada 20 também escreve resumo anual. Antes de criar, confira que o ano (ou
  o registro) ainda está livre; se não estiver, não toque e relate.
- Edição de registro real feita para validar é **revertida pelo mesmo caminho** e
  relatada. Repare que editar carimba `atualizado_em` (trigger
  `fn_set_atualizado_em`) e isso não volta atrás — quando incomodar, crie e apague
  a própria despesa de teste.
- Referência de teste (pessoa, categoria) **não se apaga**: cria, exercita e deixa
  **inativa**, relatando qual é.
- Prefixo `zz_teste` / `zz teste` para o que for criado por validação.

## 9. Como validar uma entrega

O projeto não tem suíte de testes automatizados. A validação é feita em
**navegador real, logado**, com o servidor em `--debug`, e o resultado é relatado
passo a passo. Instale as dependências de desenvolvimento:

```powershell
pip install -r requirements-dev.txt
playwright install chromium
```

O que se espera de uma validação:

- **Números conferidos lidos do DOM**, comparados com a outra tela ou com SQL —
  não com o que o código "deveria" produzir.
- **Refatoração sem mudança visual se prova por SHA-256 de captura**, com a
  referência capturada **duas vezes** para provar que o instrumento é
  determinístico (viewport e `device_scale_factor` fixos, espera pelos gráficos,
  expansão por `element.click()`). Se o SHA mudar, faça o diff de pixels antes de
  culpar o CSS: **o dono pode ter lançado uma despesa — ou escrito um resumo
  anual — enquanto você trabalhava**, e aí a diferença é dado, não regressão.
  Compare também as dimensões: mesma largura e altura crescida no tamanho exato
  de um bloco novo é a assinatura de "apareceu conteúdo", não de layout mexido.
- **Captura de página inteira não serve quando a rodada mexe na sidebar.** Um
  item novo no menu muda o SHA de TODA tela do sistema sem que o conteúdo
  tenha se mexido. Capture a coluna de conteúdo por elemento
  (`main.conteudo`), que é o que precisa ser provado. E quando a referência
  "antes" exigir o código anterior, `git stash push -u` / `git stash pop`
  resolve — conferindo os SHA-256 dos arquivos no fim, porque o checkout
  normaliza o fim de linha (compare o conteúdo com `
` trocado por
  `
`, senão todo arquivo LF parece ter mudado).
- Quando a rodada **não** mexe na sidebar mas troca token em seção global
  (reset, layout, responsivo, utilitários), a captura de página inteira volta a
  valer — com o `localStorage` das seções **fixado** pelo instrumento (os quatro
  grupos abertos), senão o grupo do item ativo muda o quadro.
- **A referência da Visão Anual tem quatro estados por largura**, não um: cada
  ano relevante × olho fechado e aberto. Capturar só o estado aberto esconde
  metade da tela desde a rodada 19.
- **Zero pixel se prova em etapas** — visual (referência nova das telas que
  mudam), limpeza (tudo idêntico), mudança de propósito (diff delimitado) — e o
  diff delimitado só prova se o seletor cobre **todos** os alvos: na 28 faltou a
  coluna fixa da matriz da Mensal e 7.444 px pareceram "fora". Antialiasing muda
  sem cor nem layout mudar: camada de `background-image` a menos (27, 822 px)
  e `backdrop-filter` a menos (28, 335 px). Diff de pixels, não SHA, é o que
  decide se foi regressão.
- **Texto do DOM antes e depois** é a prova de que refatoração visual não mudou
  número: cards, células, rodapés, valores de input, `href`s e atributos `hx-*`,
  comparados recursivamente; o "antes" sai de `git stash push -u`.
- Grep de nome de token com fronteira: `--solido` casa dentro de `card--solido`.
- Console limpo e **aba Rede só com `/static/...`**.
- Celular conferido em 390px (e 900px quando houver grade intermediária):
  `scrollWidth === clientWidth`.
- Ramo sem dado real exercitado por função pura.
- O relatório termina com a lista de **"pontos que precisei interpretar"**.

- **Validação nunca aponta escrita para registro do dono.** Na rodada 31 um
  teste de CSRF mandou um POST de foto **sem nenhum campo `valor_*`** para a
  data que tinha a foto real — e, pelo contrato da grade, apagou-a. Foi
  restaurada na hora e relatada, mas o que evita isso não é cuidado: é
  escolher, antes de escrever o teste, uma data (ou uma chave) **que não
  existe**, e afirmar no fim que o registro real continua lá. Vale para todo
  POST que uma tela interpreta como "o estado desta chave agora é este".
- **Número que veio de planilha do dono se confere contra a planilha**, não
  contra a definição de livro: o R² da linha de tendência exponencial do Excel
  é o quadrado da correlação entre observado e ajustado, e não o `1 − SSE/SST`
  da reta do logaritmo. A diferença na série real é de 0,833 para 0,956. Onde
  a tela existe para espelhar uma planilha, quem decide a definição é a
  planilha.

Dois detalhes de instrumento:

- O botão de sair da sidebar é o **primeiro** `button[type=submit]` do DOM. Um
  seletor genérico faz logout no meio do teste — escopo sempre em
  `.conteudo__corpo` ou no id do formulário.
- **O Playwright mente sobre duas coisas do navegador**, e as duas foram
  necessárias na rodada 19: página com depurador atado nunca vai para segundo
  plano (`document.visibilityState` fica em `visible` mesmo com outra aba na
  frente, outra janela por cima, `window.open`, `Browser.setWindowBounds`
  minimizando ou `Page.setWebLifecycleState`) e nunca entra no **bfcache**. Para
  exercitar troca de aba e Voltar-do-cache: suba o Chrome à mão com
  `--remote-debugging-port`, prepare a tela pelo CDP, **solte o CDP**, mexa na
  janela pelo Windows (`ShowWindow` para minimizar, `SendKeys` `%{LEFT}` para
  voltar) e só então reate o CDP para ler o que a própria página gravou.
  Adicionar um `<span>` no meio de um texto muda o **subpixel** das letras
  seguintes: se o SHA mudar sem o layout mudar, é isso — esconda pela caixa em
  volta em vez de embrulhar o valor.

## 10. Estado e roteiro

Consolidado em `docs/Freedom - Histórico e Estado do Projeto.md` (rodadas,
decisões, lições aprendidas). Resumo:

- **Pronto**: login; cadastros; lançamento de despesas em série; consulta com
  filtros; receitas em página única; configurações com vigência; Visão Anual (13
  cards, 4 gráficos, 2 tabelas); Visão Mensal com detalhe por categoria; orçamento
  (montagem + acompanhamento). Refatoração visual: rodada 17 (tokens, layout,
  Visão Anual) e rodada 18 (lançamentos e cadastros) concluídas. Rodada 19:
  botão olho da Visão Anual, que esconde todo número da tela (ver "Ocultar
  valores" na seção 7). Rodada 20: **resumo anual** — `tb_resumos_anuais`,
  cadastro em `/cadastros/resumos-anuais` e card na Visão Anual. Rodada 21:
  **carga do IPCA** — `freedom/ipca.py` e `flask carregar-ipca` enchem
  `tb_ipca` com a série do SIDRA/IBGE desde dez/1993. Rodada 22: **tela do
  IPCA** em `/cadastros/ipca` — matriz ano × 12 meses mais "No ano", com
  alternância Variação mensal | Número-índice por GET; mais três limpezas
  (nome do mês e `MESES_CURTOS` promovidos para `util.py`, mensagens de
  `create-user`/`set-password` acentuadas, aviso de variação nula no
  `carregar-ipca`). Rodada 23: **botão "Atualizar do IBGE"** na tela do IPCA —
  comando e botão pela mesma `ipca.carregar`, faixa de resultado, dica de mês
  provável e o `htmx-config` que faz 409/502/503 aparecerem; limpeza do
  `nome_do_mes` (três cópias). Rodada 24: **Análise por subcategoria** —
  série temporal de uma subcategoria com agrupamento e correção pelo IPCA,
  gráfico de linha e tabela dos pontos; `static/js/graficos.js` extraído da
  Anual; `somar_meses` e `intervalo_de_meses` promovidos para `util.py`.
  Rodada 25: **página de Backup** em `/configuracoes/backup` — dump do banco
  inteiro pelo `pg_dump`, confirmação em dois passos e download;
  Configurações virou o quarto grupo da sidebar, com "Parâmetros" e "Backup".
  Rodada 26: **Análise por prioridade** em `/analise/prioridade` — faixa
  (Essencial ou P1–P4) em vez de subcategoria, filtro permanente por
  `integra_ipca` (o primeiro e único uso da flag) e a nota do que ficou de
  fora; o corpo das duas análises saiu para `main/_analise.html` e
  `servico_analise.py` virou o serviço das duas, com `Recorte` e `painel()`;
  `.ipca-dica` promovida a `.nota-topo`. Depois da 26, a pedido do dono:
  **resumo de média, mediana e total** antes do gráfico, nas duas análises.
  Rodada 27: **refatoração visual, parte I** — Visão Mensal e login no design
  system, sidebar abrindo o grupo do item ativo, `.kpi` e `.tabela--painel`
  compartilhados. Rodada 28: **parte II** — Orçamento (modo e período em
  `.segmentado`, `card()` estendido, faixa do 409 corrigida) e Parâmetros,
  componente `.edicao-linha`, **seção 1(b) apagada**, `card--solido` fora,
  `--ink-ghost` nos últimos literais roxos. Rodada 29: **Independência
  financeira** em `/independencia` — a primeira leitura de TSR, S e R, quatro
  cards, tabela ano a ano, curva do patrimônio e simulação por querystring.
  Rodada 30: **patrimônio** — cadastro de ativos e a foto mensal em
  `/lancamentos/patrimonio`, com cards, alocação por classe, histórico e
  gráfico de evolução. Rodada 31: **anos restantes** na Independência (a
  mesma fórmula partindo da última foto), **correção do patrimônio pelo
  IPCA** e quatro limpezas (CSRF em campo oculto, `com_sinal` promovido,
  nota de vigência fora da faixa, Parâmetros recusando zero em TSR e S).
  Depois da 31, a pedido do dono: **setas de mês** na foto (o
  `<input type="date">` travava a tela inteira numa data impossível), **eixo
  Y em milhões** no `graficos.js`, **gráfico de tendência** com projeção de
  cinco anos e a **carga da série de patrimônio** por CSV (161 fotos, de
  abril de 2013 a agosto de 2026). Rodada 32: **troca de senha** pela
  interface (`/conta/senha`, alcançada pelo nome no rodapé da sidebar) e
  **histórico de versões** (`/changelog`), com o número da versão no rodapé
  saindo do `CHANGELOG.md` da raiz — que passa a ser a fonte única dela.
  A gravação da senha virou uma função só (`auth/servico.py`), por onde
  passam a tela e o `flask set-password`. Rodada 33: **deploy** — `Dockerfile`
  com gunicorn, o serviço `app` no compose (três serviços, nenhum com
  `container_name`), o backup por `pg_dump` via TCP, as três mensagens do
  auth acentuadas e o roteiro do servidor em `docs/Freedom - Deploy.md`. A
  versão passou a **1.0**.
- **Não há refatoração visual pendente.** O tema antigo não existe no
  repositório; comentário que diga o contrário é velho.
- **Depois**: o **deploy saiu da lista** na rodada 33 — os arquivos e o
  roteiro estão prontos (`docs/Freedom - Deploy.md`), e quem os roda no
  servidor é o dono. Ficaram, fora desta linha do tempo e sem data: o
  **segundo usuário** (o mecanismo já existe — `flask create-user` —, falta a
  decisão) e o **usuário não-root na imagem**. O Tailscale já funciona e
  nunca foi trabalho do sistema. Os dois itens que vinham antes do deploy
  saíram da lista porque foram feitos: metas de independência na rodada 29 e
  patrimônio na 30 — `tb_ativos` e `tb_patrimonio_snapshots` não estão mais
  vazias. O item que abria a lista original — a tela de despesas mensais
  somadas por `integra_ipca` — saiu na 26, quando a flag ganhou o uso que
  faltava. Backlog de deflação: ticket médio deflacionado na análise e série
  real do ano na Visão Anual.

Referência visual: `design_handoff_freedom_visao_anual/` e
`design_handoff_freedom_lancamentos_cadastros/`. **Cuidado**: os README desses
handoffs foram escritos por uma ferramenta de design e erram sobre a stack (falam
em Java, CDN, unpkg, biblioteca de ícones, "sem celular"). Onde divergirem deste
arquivo, **este arquivo vale**. Os `support.js` são runtime da ferramenta e não
fazem parte da aplicação.

## 11. O que não fazer

- Não instale framework de CSS ou de front-end. Não troque Chart.js/HTMX por CDN.
- Não introduza ORM nem ferramenta de migração.
- Não use `float` para dinheiro.
- Não decida cor, texto ou estado dentro do template.
- Não some linhas em Python quando existe consulta agregada.
- Não apague dado que você não criou.
- Não leve o olho da Visão Anual para outra tela sem o dono pedir: o mecanismo
  é reutilizável, a decisão de onde usá-lo não é sua.
- **`tb_despesas.integra_ipca` é lida em um lugar só**: o recorte da Análise
  por prioridade (rodada 26). Nenhuma outra tela a lê, e a Análise por
  subcategoria **continua somando tudo**, de propósito — não a "corrija" por
  coerência. Tela nova que precise da flag herda junto a obrigação de avisar
  na tela que os totais dela não batem com os das outras.
- Não implemente **restauração** de backup pela interface, nem parcial nem
  "só dados", nem histórico de backups, nem agendamento do dump.
- **Nenhum service worker, nenhum cache offline, nenhuma PWA de verdade.** O
  banco é a fonte da verdade e toda tela é servida na hora; um service worker
  interceptando o HTMX é exatamente o que não se quer. O que a rodada 34
  entregou é ícone, nome e modo autônomo — o manifesto e as seis tags do
  `<head>` do `base.html` —, e para por aí. Não acrescente `serviceWorker`,
  `caches`, tela de instalação, `beforeinstallprompt`, nem `purpose:
  "maskable"` nos ícones: o desenho encosta na zona segura da máscara circular
  (medido: 0,982 do raio), e declará-lo `maskable` o faria ser cortado.
- Não ponha senha em argumento do `pg_dump` (nem `PGPASSWORD=` inline, nem
  `--password`): ela iria para a linha de comando, que qualquer um que liste
  processos vê. O lugar é o `env=` do subprocesso.
- Não volte o backup para `docker exec`, e não devolva `container_name` ao
  compose: um exige daemon do Docker ao alcance do processo do Flask, o outro
  impede dois projetos compose lado a lado.
- **Não devolva o cookie de sessão ao nome padrão** (`session`), nem apague o
  `SESSION_COOKIE_NAME` do `config.py` "por simplicidade": o servidor divide o
  host com outros sistemas, e o nome padrão faz os dois se derrubarem. O
  mesmo vale para qualquer app novo que venha a rodar ali.
- **Não reabra `GET` no `/logout`.** Ele é POST com CSRF desde a rodada 35, e
  o único caminho é o botão da sidebar. Com GET, um `<img>` ou um pre-fetch
  de qualquer página derruba a sessão sem clique nenhum. `GET` responde 405, e
  é para continuar assim.
- Não mexa no `--timeout` do gunicorn sem olhar o `TEMPO_LIMITE` do backup —
  o primeiro tem de ser maior que o segundo.
- Não crie **constante de versão em Python**, nem leia o `CHANGELOG.md` a
  cada request: a fonte é o arquivo, lido uma vez na subida. E não invente
  versão "—" quando ele faltar — é erro de subida, de propósito.
- Não acrescente à troca de senha o que ela não tem: "esqueci a senha",
  recuperação por e-mail, medidor de força, tela de perfil com outros campos
  ou invalidação das outras sessões. Quem perdeu a senha usa
  `flask set-password`.
- Não gere hash de senha fora de `auth/servico.trocar_senha`, e não ponha a
  conferência da senha atual dentro dela: o comando é o caminho de quem não
  tem a senha.
- Não aponte POST de validação para data que já tem foto de patrimônio: grade
  vazia **apaga** a foto daquela data, e isso é o contrato.
- Não preencha a foto de patrimônio sozinho — nem por cotação, nem por
  interpolação entre dois meses. O valor é digitado por quem olhou o extrato.
- **Não troque o R² da tendência pela definição da escala do logaritmo.** Ele é
  o do Excel (quadrado da correlação entre observado e ajustado) porque a tela
  existe para espelhar a planilha do dono; "corrigir por rigor" faz o número
  deixar de bater com o que ele confere.
- Não acrescente cenário, aporte previsto ou meta à curva de tendência: ela
  diz o que a série vem fazendo, e mais nada.
- Não classifique subcategoria (coluna, flag ou heurística de "contínua" ou
  "esporádica"): quem escolhe a granularidade é quem olha, pelo agrupamento.
- Não agende a chamada ao SIDRA (cron, thread, Agendador de Tarefas dentro do
  app). O disparo é o comando ou o botão.
- Não reintroduza apelido de tema (`--cor-*`, `--vidro*`…) nem `card--solido`:
  são código velho sem definição.
- Não cite trabalho adiado por número de rodada; pelo nome do que é.
- Não escreva valor de senha, chave ou token em lugar nenhum.
- Não faça commit nem push sem o dono pedir.
