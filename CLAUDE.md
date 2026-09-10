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
financeira — nada disso está implementado.

**Há dado real em produção** (mais de 1.800 despesas e 145 receitas, de 2025 e
2026). Ver a seção 8 antes de escrever qualquer coisa no banco.

## 2. Rodar

Pré-requisitos: Docker Desktop, Python 3.12 (o `venv/` já vem criado na máquina do
dono; Python 3.14 não tem wheel para tudo).

```powershell
docker compose up -d                     # Postgres 16 + pgAdmin
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m flask --app freedom --debug run --port 5000
```

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

### `.env` (não versionado)

O `.env` fica na raiz e **nunca** vai para o git. Chaves usadas:

| Chave | Função |
|---|---|
| `DATABASE_URL` | String de conexão do psycopg. |
| `SECRET_KEY` | Assina o cookie de sessão e os tokens CSRF. |
| `DB_POOL_MIN` / `DB_POOL_MAX` | Tamanho do pool (padrão 1 e 5). |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_PORT` | Lidos pelo `docker-compose.yml`. |
| `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` / `PGADMIN_PORT` | idem. |
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
| Gráficos | Chart.js 4.5.1, UMD **local**, só na Visão Anual. Núcleo, sem plugins |
| CSS | Um arquivo escrito à mão (`static/css/app.css`), tokens em `:root`. **Sem Tailwind, sem React, sem biblioteca de ícones** |
| Ícones | Lucide (ISC), **SVG inline** pela macro `icone` em `templates/_macros.html` |
| Dinheiro | `Decimal` em todo cálculo; `float` só na serialização final para JSON de gráfico |
| Testes/validação | Playwright (`requirements-dev.txt`), navegador real |

**Nenhuma requisição a domínio externo, em nenhuma tela.** Sem CDN, sem unpkg, sem
fonte web. A tipografia é a fonte do sistema. Isso é verificável e é verificado: a
validação de cada rodada confere que a aba Rede só tem `/static/...`.

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
                   formatar_numero, escapar_like; MESES; so_fragmento;
                   chave_alfabetica (NFD — nunca `locale`); fracao
  cli.py           flask create-user, flask set-password
  auth/            /login, /logout (POST com CSRF)
  main/            "/" Visão Anual, "/mensal" Visão Mensal,
                   "/mensal/categoria/<id>" fragmento
                   servico.py        Anual: painel_do_ano, _totais_do_ano
                                     (origem única dos totais), _tabela_mensal,
                                     _tabela_categorias, _graficos;
                                     helpers card, percentual
                   servico_mensal.py Mensal: painel_do_mes e as três tabelas
  cadastros/       /cadastros — um módulo por entidade + servico.py
                   (alternar_ativo, traduzir_unique, contagem)
  lancamentos/     /lancamentos — despesas.py, consulta.py, receitas.py,
                   servico.py, servico_receitas.py, forms.py
  configuracoes/   /configuracoes — parâmetros com vigência (CATALOGO em Python)
  orcamento/       /orcamento — servico.py (montagem) e acompanhamento.py (leitura)
templates/         base.html, layout_app.html, _macros.html + uma pasta por blueprint
static/css/app.css seções numeradas 1–8 (ver seção 7 deste arquivo)
static/js/         htmx.min.js, chart.umd.js, visao_anual.js
db/init/01_schema.sql
docs/              Freedom - Estrutura do Banco de Dados.md   (fonte da verdade)
                   Freedom - Histórico e Estado do Projeto.md (decisões e lições)
```

**Camadas**: a rota só orquestra (valida entrada, escolhe o template). Toda
consulta e toda composição de tela moram em `servico.py`. O template só formata.

## 5. Banco

Fonte da verdade: `docs/Freedom - Estrutura do Banco de Dados.md` e
`db/init/01_schema.sql`. **Se um muda, o outro muda.**

14 tabelas (`tb_categorias`, `tb_subcategorias`, `tb_ref_receitas`, `tb_pessoas`,
`tb_usuarios`, `tb_contas`, `tb_ipca`, `tb_configuracoes`, `tb_despesas`,
`tb_receitas`, `tb_orcamento_meses`, `tb_orcamentos`, `tb_ativos`,
`tb_patrimonio_snapshots`) e duas views (`vw_despesas`, `vw_receitas`).

Regras que se aplicam a todo código novo:

- **Leitura sempre pelas views; escrita nas tabelas base.** `vw_despesas` já
  resolve a essencialidade efetiva (`COALESCE(despesa, subcategoria)`).
- **`ano_mes` serve para exibir e agrupar, nunca para filtrar.** Todo filtro de
  período usa `data >= início AND data < início do período seguinte` — é o que
  faz os índices `ix_despesas_data` / `ix_receitas_data` serem usados. Filtrar por
  coluna derivada de view mata o índice (comprovado com EXPLAIN ANALYZE).
- **Nada derivado é armazenado.** Toda FK é `NOT NULL` e `ON DELETE RESTRICT`.
- Referência não se apaga: tem `ativo` (`ativa` em `tb_contas`).
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
  Configuração e linha de orçamento também se excluem (são entrada do usuário).
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
  INSERT/UPDATE/DELETE; reabrir só se não existir mês orçado posterior.
- Nos painéis, só categorias e pessoas **com despesa no período** aparecem. Na
  tabela mensal da Anual os 12 meses aparecem sempre.

## 7. Convenções de código que o projeto exige

### Servidor

- **Nada é decidido em Jinja.** Cor, travessão, estado de estouro, classe CSS,
  plural, contador — tudo vem pronto do Python. O template escolhe o formato
  (macro `reais`, filtro `numero`) e emite o nome da classe que recebeu.
- **Agregados vêm de consulta própria**, nunca de soma em Python sobre a página.
  Exceção prevista e única: composição em `Decimal` sobre conjunto **pequeno e
  completo** cuja definição É "estas linhas" (ex.: `total_exibido` das 15 recentes).
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
- Estado de UI que sobrevive ao re-render vai em `<input type="hidden">`; filtro
  fora do formulário vai por `hx-include`.
- `hx-vals` para renomear parâmetro; `hx-params="none"` cancela. O gatilho
  `changed` **ignora preenchimento por JavaScript** (`fill` não dispara `keyup`) —
  isso vale inclusive para escrever teste.
- `HX-Retarget` quando o alvo natural do disparador não é onde a resposta cai.
- Rota só de fragmento: sem `HX-Request` → redirect para a página-mãe com os
  mesmos parâmetros, **antes** de qualquer 404. Regra de estado recusada → **409**.

### CSS (`static/css/app.css`, ~4.100 linhas, seções numeradas)

```
1 Variáveis   2 Reset   3 Fundo   4 Layout   5 Componentes   6 Login
7 Responsivo (< 768px)   8 Utilitários
```

- A seção 1 tem **duas camadas**: (a) tokens do design system (`--bg`, `--ink-*`,
  `--accent`, `--control-h`, `--green-ink`…) e (b) **apelidos do tema roxo antigo**
  (`--cor-destaque`, `--linha`, `--vidro*`…) apontando para eles. Os apelidos
  existem só até as telas antigas serem refeitas. **Nada de novo deve usar um
  apelido.**
- Tema: fundo `#F5F5F7`, cartão branco raio 14, sidebar escura, acento teal
  `#30B0C7`. **Verde e vermelho são reservados** a receita, despesa e valor
  negativo — não servem de decoração. O único `backdrop-filter` do sistema é o da
  barra superior.
- `font-variant-numeric: tabular-nums` é global (no `body`).
- Utilitário nasce **global**, na seção 8. Classe utilitária criada dentro de um
  seletor de tela não funciona fora dela e o erro é silencioso.
- `1fr` tem mínimo `min-content`: em grade com canvas ou tabela larga, use
  `minmax(0, 1fr)`.
- `.so-leitor` é absoluto: dentro de contêiner que rola precisa de ancestral
  `position: relative`, senão ele estica a página inteira.
- `display` de folha de autor vence o `[hidden]` do navegador (regra de user
  agent). Todo componente com `display:` próprio precisa de
  `.componente[hidden] { display: none }`.
- `white-space: nowrap` herdado estica tabela no celular — sempre desfaça na
  seção 7.
- Chart.js: contêiner com **altura fixa** e `maintainAspectRatio: false`; eixo sem
  centavos, tooltip com centavos; **cores lidas de variáveis CSS por
  `getComputedStyle`** — nenhum hexadecimal no JS.

### Celular (< 768px) — preservar sempre

- A sidebar vira barra superior com botão de menu; as seções recolhíveis do menu
  não se aplicam ali (tudo visível).
- Grades de cards 1/2/4 colunas (quebras em 768 e 1100); gráficos 1/2.
- Coluna principal larga (descrição) → texto de apoio **dentro da célula**;
  coluna principal estreita (mês) → `<tr class="linha-apoio">` com `colspan`.
- Rolagem interna (`.tabela-caixa`) é aceitável e é o padrão; **rolagem horizontal
  da página não é**.
- Ações viram ícone com `aria-label` só onde o padrão já existe (detalhe da
  Mensal); nas demais tabelas os botões empilham com texto.

## 8. Trabalhando com dado real

O banco de desenvolvimento **é** o banco de produção do dono. Portanto:

- **Nenhuma rodada apaga linha que não criou.** Faxina de teste sempre por id, e o
  id é relatado.
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
  culpar o CSS: **o dono pode ter lançado uma despesa enquanto você trabalhava.**
- Console limpo e **aba Rede só com `/static/...`**.
- Celular conferido em 390px (e 900px quando houver grade intermediária):
  `scrollWidth === clientWidth`.
- Ramo sem dado real exercitado por função pura.
- O relatório termina com a lista de **"pontos que precisei interpretar"**.

Um detalhe de instrumento: o botão de sair da sidebar é o **primeiro**
`button[type=submit]` do DOM. Um seletor genérico faz logout no meio do teste —
escopo sempre em `.conteudo__corpo` ou no id do formulário.

## 10. Estado e roteiro

Consolidado em `docs/Freedom - Histórico e Estado do Projeto.md` (rodadas,
decisões, lições aprendidas). Resumo:

- **Pronto**: login; cadastros; lançamento de despesas em série; consulta com
  filtros; receitas em página única; configurações com vigência; Visão Anual (13
  cards, 4 gráficos, 2 tabelas); Visão Mensal com detalhe por categoria; orçamento
  (montagem + acompanhamento). Refatoração visual: rodada 17 (tokens, layout,
  Visão Anual) e rodada 18 (lançamentos e cadastros) concluídas.
- **Pendente**: rodada 19 da refatoração visual — Visão Mensal, Orçamento,
  configurações e login ainda rodam sobre os apelidos da seção 1(b) do CSS.
- **Depois**: metas de independência (TSR/S/R já estão em `tb_configuracoes`, nada
  os lê); patrimônio; carga do IPCA (API SIDRA/IBGE) e gráficos deflacionados;
  deploy com gunicorn no docker-compose + Tailscale + segundo usuário.

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
- Não escreva valor de senha, chave ou token em lugar nenhum.
- Não faça commit nem push sem o dono pedir.
