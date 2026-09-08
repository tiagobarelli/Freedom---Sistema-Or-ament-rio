# Freedom — Histórico e Estado do Projeto

Documento de contexto para o projeto orquestrador e para o agente. Resume o que foi decidido, o que existe e o que falta. Consolidado após a rodada 12 (09/09/2026). Fica em `docs/` no repositório e na base de conhecimento do orquestrador; se um muda, o outro muda.

## 1. O que é o Freedom

Sistema web pessoal de controle financeiro. Roda localmente em Windows via Docker; no futuro, outros membros da casa acessam pela rede Tailscale (nada exposto na nuvem). Um usuário master hoje; a esposa entra depois. Interface em português do Brasil.

Objetivo de longo prazo: além de registrar despesas e receitas, medir crescimento real das despesas (deflação por IPCA), orçamento mensal por categoria, evolução do patrimônio e metas de independência financeira (TSR, retorno real, taxa de poupança).

## 2. Modelo de trabalho

Três papéis:

- **Tiago** (dono do projeto): decide, cadastra dados pela interface, executa comandos, cola aqui as saídas do agente.
- **Orquestrador** (projeto no Claude web): escreve os prompts de cada rodada, revisa as entregas do agente, responde às dúvidas técnicas que ele levanta, mantém a documentação alinhada.
- **Agente** (Claude Opus 5 no VS Code): implementa. Recebe um prompt por rodada, executa, valida de verdade e devolve um relatório com "pontos que precisei interpretar".

O ciclo que funcionou: orquestrador faz poucas perguntas de decisão antes do prompt → prompt fechado por rodada → agente pergunta quando há ambiguidade → entrega com validação executada → orquestrador revisa as interpretações e ajusta docs → próxima rodada.

## 3. Decisões de escopo (fechadas)

- Cartão de crédito: **só data da compra**, sem parcelas nem faturas.
- **Sem controle de saldo**: o sistema categoriza fluxos; não há saldo inicial nem transferências.
- Categorias, subcategorias, contas, pessoas e fontes de receita são cadastradas **pela interface**, não por seed. O mesmo vale para os parâmetros de configuração.
- IPCA: tabela existe, **carga fica para o futuro**.
- Despesas compartilhadas da casa são atribuídas a uma pessoa chamada **Casa**.
- **Movimento se exclui, referência se desativa** (rodada 4): lançamento errado é apagado de verdade; tabela de referência nunca, nem em teste.
- **Configuração também se exclui** (rodada 8): `tb_configuracoes` admite `UPDATE` e `DELETE` físico — uma vigência digitada errada é lixo, não histórico. A chave não muda na edição.
- Consulta de despesas é **tela separada** da de lançamento: uma é digitação rápida, a outra é leitura e conferência.
- **Receitas são tela única** (rodada 7): formulário no topo, filtros e lista abaixo, na mesma página. A assimetria com despesas é intencional.
- **A página inicial é a Visão Anual** (rodadas 9–11): seleciona-se o ano; cards, gráficos e tabelas são do ano inteiro. **A Visão Mensal é página própria** (rodada 12), no mesmo grupo do menu.
- **Ano/mês inválido na URL cai no período corrente**, sem erro e sem tela vazia. Só anos com pelo menos um lançamento aparecem no seletor; meses aparecem sempre os 12.
- **TSR, S e R não entram nos painéis.** Servem a uma página própria de metas de independência, futura. Os painéis mostram o realizado.
- Nos painéis, **só categorias e pessoas com despesa no período** aparecem nas tabelas; o zero não é listado. Na tabela mensal da Anual, por outro lado, os 12 meses aparecem sempre.

## 4. Banco de dados

Fonte da verdade: `docs/Freedom - Estrutura do Banco de Dados.md` e `db/init/01_schema.sql`. Regra: se um muda, o outro muda. **O DDL mudou uma única vez desde a rodada 1**: a view `vw_receitas`, na rodada 7. As rodadas 4 a 6 e 8 a 12 não tocaram no schema.

Resumo do que importa para escrever prompts:

- PostgreSQL 16 em Docker (`docker-compose.yml`, serviço `postgres`, container `freedom_postgres`), pgAdmin em `localhost:5050`. Credenciais e `DATABASE_URL` no `.env`.
- 13 tabelas: `tb_categorias`, `tb_subcategorias`, `tb_ref_receitas`, `tb_pessoas`, `tb_usuarios`, `tb_contas`, `tb_ipca`, `tb_configuracoes`, `tb_despesas`, `tb_receitas`, `tb_orcamentos`, `tb_ativos`, `tb_patrimonio_snapshots`. Duas views: `vw_despesas` e `vw_receitas`.
- `vw_despesas`: despesa + subcategoria + categoria + **essencialidade efetiva** (`COALESCE(despesa, subcategoria)`) + `prioridade` + `pessoa_id` (não o nome — para o nome, JOIN com `tb_pessoas`; a FK é `NOT NULL`, o JOIN não perde linha) + `ano_mes` inteiro `AAAAMM`.
- `vw_receitas`: receita + categoria + subcategoria da fonte + `ref_receita_ativo` + `ano_mes`. Leitura sempre pelas views; escrita nas tabelas base. Vale inclusive para listas auxiliares (anos com lançamento).
- **`ano_mes` serve para exibir e agrupar, não para filtrar**: filtro mensal e anual usam `data >= início AND data < início do período seguinte`, o que faz `ix_despesas_data` / `ix_receitas_data` serem usados (confirmado por EXPLAIN ANALYZE na rodada 12: Index Scan, 0,2 ms).
- Nada derivado é armazenado. Toda FK é `NOT NULL` e `ON DELETE RESTRICT`. Referência não é apagada: tem `ativo` (em `tb_contas`, `ativa`).
- CHECKs: essencialidade em `Essencial` / `Não Essencial`; `tb_contas.tipo` em `corrente, cartao, dinheiro, outro`; `prioridade` 1–4; `valor > 0`; dia 1 em `tb_ipca.mes` e `tb_orcamentos.ano_mes`; `>= 0` em orçamento e patrimônio. `tb_ativos.classe` e `tb_configuracoes.chave` sem CHECK, de propósito.
- `prioridade` é nula quando a despesa é essencial e pode ser nula em não essencial antiga; o banco não impede. A Visão Anual trata NULL em não essencial como faixa "Sem prioridade", exibida só se existir.
- `tb_configuracoes` tem `vigente_desde`; o valor vigente numa data é o registro com maior `vigente_desde ≤ data`, e todas as chaves de uma vez saem com `DISTINCT ON (chave)`.
- Trigger `fn_set_atualizado_em()` em despesas e receitas; `atualizado_em` fica NULL até o primeiro UPDATE.
- **Collation**: a ordenação alfabética pt-BR (acentos junto das letras-base) é feita em Python com chave NFD, nunca com `locale`. O `ORDER BY` por nome no SQL segue a collation do banco, que ainda não foi conferida (pendência da rodada 13).
- **Regras da aplicação, não do banco**: prioridade só quando a essencialidade efetiva é "Não Essencial"; autoria nunca muda na edição; referência inativa continua visível na edição e nos filtros mas nunca é gravada em lançamento novo; receita pré-seleciona a pessoa do usuário logado; configuração não aceita negativo e tem limite de casas decimais; catálogo de chaves de configuração vive em Python.

Estado dos dados: **725 despesas reais e 61 receitas reais, todas de 2026**; 24 categorias, 82 subcategorias, 3 contas, 5 pessoas, 8 fontes de receita. `tb_configuracoes` tem TSR, S e R cadastrados (nada os lê ainda). Usuário `tiago` ativo, `zz_consulta` desativado, `zz_teste` ativo para o agente validar em navegador — **senha na variável `senha_teste` do `.env`**. **Há dado real em produção: nenhuma rodada pode apagar linha que não tenha criado, e a faxina de teste é sempre por id.**

## 5. Stack da aplicação (fechada, não reabrir)

| Camada | Escolha |
|---|---|
| Web | Flask 3, application factory (`create_app` em `freedom/__init__.py`), Blueprints |
| Banco | psycopg 3 + `psycopg_pool`, SQL direto parametrizado, `row_factory=dict_row`. **Sem ORM, sem migrações** |
| Auth | Flask-Login; hash com `werkzeug.security` (scrypt) |
| Formulários | Flask-WTF (CSRF em todo POST) |
| Interatividade | HTMX 2.0.4, arquivo local em `static/js/`, mais JS próprio pontual (menu, limpar filtros, autocomplete, gráficos) |
| Gráficos | Chart.js 4.5.1, build UMD local em `static/js/chart.umd.js`, carregado só na Visão Anual via `{% block scripts %}`. Núcleo apenas, sem plugins. Barras proporcionais em tabela são CSS (`barra_pct`), não Chart.js |
| CSS | Escrito à mão, variáveis CSS, Glassmorphism tema claro. Sem Tailwind, sem bibliotecas de ícones |
| Dinheiro | `Decimal` em todo cálculo; `float` só na serialização final para JSON de gráfico |
| Ambiente | Windows, PowerShell, venv em `venv/`, Python 3.14 |

## 6. Estrutura atual do código

```
freedom/
  __init__.py      create_app: CSRF, pool, Flask-Login, blueprints, CLI, filtros Jinja
                   `moeda` e `numero` (ambos de util.py)
  config.py        lê .env; template_folder/static_folder apontam para a raiz
  db.py            ConnectionPool, dict_row, get_connection(), executar()
  util.py          destino_interno(); parser e formatação de número: ValorInvalido, converter_valor,
                   converter_numero(percentual=), formatar_valor, formatar_numero, escapar_like;
                   MESES (nomes dos meses em português — nunca `locale`)
  cli.py           flask create-user, flask set-password
  auth/            forms.py, models.py, routes.py (/login, /logout)
  main/            routes.py  "/" Visão Anual e "/mensal" Visão Mensal — só orquestram
                   servico.py Visão Anual: anos_com_lancamento, ano_valido, MESES_CURTOS (derivada
                              de util.MESES), painel_do_ano (consultas mensais por essencialidade,
                              receitas, não essenciais por prioridade, pico, categorias do ano),
                              _totais_do_ano (origem única dos totais lidos por cards e rodapés),
                              _tabela_mensal, _tabela_categorias, _graficos; helpers compartilhados
                              com a Mensal: card, fracao (percentual como número ou None), percentual;
                              _serie é o único ponto onde Decimal vira número JSON
                   servico_mensal.py Visão Mensal: intervalo_do_mes, nome_do_periodo, painel_do_mes
                              (cards, e as três tabelas derivadas de UMA consulta agrupada por
                              categoria × pessoa), _chave_alfabetica (NFD)
  cadastros/       um módulo por entidade + servico.py (alternar_ativo, UniqueViolation → mensagem)
  lancamentos/     __init__.py (blueprint, prefixo /lancamentos)
                   despesas.py  lançar, editar, excluir, classificação reativa, sugestões
                   consulta.py  consulta de despesas (mesma rota serve página e fragmento)
                   receitas.py  página única de receitas
                   servico_receitas.py  leituras sobre vw_receitas
                   forms.py     inclui ReceitaForm
                   servico.py   consultas e agregados de despesa, sugestões; helpers compartilhados
                                id_valido, pagina_pedida, so_fragmento (a promover para util.py na 13)
  configuracoes/   __init__.py (prefixo /configuracoes), rotas.py, forms.py,
                   servico.py (CATALOGO de chaves, valor_vigente(), valores vigentes de todas)
templates/
  base.html        inclui `{% block scripts %}` para script por tela
  layout_app.html  3 grupos de menu: Painel ("Visão Anual", "Visão Mensal"), Lançamentos,
                   Cadastros ("Configurações" no fim)
  _macros.html     campo, campo_area, badge, ações, `reais`, `badge_essencialidade`,
                   `campos_despesa`, `campos_receita`, `combobox`, `barra_pct`
  auth/, cadastros/
  main/index.html  Visão Anual: seletor de ano (GET), 13 cards, ilha JSON `#dados-graficos`,
                   4 cards com canvas, tabela mês a mês (12 linhas + tfoot), tabela por categoria,
                   macros locais dinheiro/percentual/linha_mensal, bloco scripts
  main/mensal.html Visão Mensal: seletores ano/mês/ordem (GET), 6 cards, tabelas por categoria e
                   por pessoa (com barra_pct), matriz pessoa × categoria com rolagem interna e
                   primeira coluna fixa
  lancamentos/     despesas.html, despesa_editar.html, consulta.html, receitas.html,
                   receita_editar.html, _linha_*.html, _resultados.html (usa barra_pct),
                   _receitas_resultados.html (usa barra_pct), _formulario_oob.html,
                   _receita_formulario.html, _gravado.html, _receita_gravada.html,
                   _receita_erro.html, _total_oob.html, _classificacao*.html, _sugestoes.html
  configuracoes/   configuracoes.html, _formulario.html, _formato.html, _lista.html,
                   _linha.html, _linha_edicao.html, _gravada.html, _erro.html
static/
  css/app.css      seção 1 (variáveis, inclusive paleta --grafico-*), seções 2–8;
                   componente .barra/.barra__preenchimento (depois de 5.4); 5.9 lançamento,
                   5.10 consulta, 5.11 autocomplete, 5.12 configurações,
                   5.13 Visão Anual (5.13.1 gráficos, 5.13.2 tabelas), 5.14 Visão Mensal
                   (.filtro-ano--mensal, .tabela--mes, modificador de primeira coluna fixa em
                   .tabela-caixa). Seção 5.7 (modal) foi removida; a lacuna é intencional
  js/htmx.min.js, js/chart.umd.js, js/visao_anual.js
db/init/01_schema.sql
docs/            Freedom - Estrutura do Banco de Dados.md, Freedom - Histórico e Estado do Projeto.md
run.py, requirements.txt, .gitignore, README.md ("Dependências de front-end"), .env, .flaskenv
```

Padrões já estabelecidos no código (o agente deve mantê-los):

- Subir: `python -m flask --app freedom --debug run --port 5000` ou `flask run` com `.flaskenv`.
- Cadastros: lista + criar + editar + ativar/desativar (HTMX troca só a `<tr>`); filtro "mostrar inativos"; sem excluir.
- Lançamento em série: grava por HTMX sem recarregar, limpa os campos que mudam, mantém os que se repetem, devolve o foco ao primeiro campo variável e atualiza lista e agregados por swap out-of-band.
- **Swap out-of-band em contexto de tabela vai dentro de `<template>`** quando a resposta **começa** com `<tr>`. Resposta que começa com `<form>` não precisa.
- Estado de UI que precisa sobreviver ao re-render vai em `<input type="hidden">`; filtros fora do formulário vão por `hx-include`.
- Filtros são GET na URL, com `hx-push-url`; a mesma rota devolve página inteira ou fragmento conforme `HX-Request`, com exceção explícita para `HX-History-Restore-Request`. **Exceção deliberada: os seletores dos painéis (ano, mês, ordem) recarregam a página inteira, sem HTMX**, submetendo em `onchange`.
- Quando gravar ou excluir pode reordenar a lista ou mudar a paginação, devolver o bloco inteiro (`HX-Retarget` se preciso).
- Agregados vêm de consulta própria sobre o filtro inteiro, nunca de soma em Python sobre a página. Exceção prevista: os painéis compõem cards, séries e tabelas em Python (`Decimal`) a partir de conjuntos **pequenos e completos** que o SQL já agregou (12 linhas mensais; o cubo categoria × pessoa de um mês). Quando dois lugares mostram o mesmo total, eles leem da **mesma origem** (`_totais_do_ano`), para "idênticos" ser estrutural, não coincidência.
- **Gráficos**: o servidor entrega séries prontas (inclusive acumulados) em JSON no template (`<script type="application/json">` via `tojson`); o JS só desenha. Rótulos e textos vêm do servidor. Cores por variáveis CSS lidas com `getComputedStyle`, nunca hex no JS. Canvas em contêiner com altura fixa e `maintainAspectRatio: false`; grade que contém canvas usa `minmax(0, 1fr)`. Eixo Y sem centavos, tooltip com centavos, ambos `Intl.NumberFormat('pt-BR')`.
- **Barras proporcionais em tabela**: macro `barra_pct`; largura em `style=` com ponto (é CSS). Rodapé de 100% não leva barra. O denominador da barra é o total do próprio conjunto exibido, não o card — assim o rodapé fecha por construção e a conferência contra o card continua sendo conferência. A soma dos percentuais exibidos pode dar 100,2% com 20+ linhas arredondadas; isso é aceito e não se corrige por maior resto.
- Busca textual escapa `%` e `_` (`ESCAPE '\'` em string *raw*), sem `unaccent`. Ordenação alfabética em Python com chave NFD, não `locale`.
- `UniqueViolation` vira erro de campo legível, nunca 500. Transação por request, rollback em erro.
- Mensagem de login única para login inexistente / inativo / senha errada. Redirecionamento sempre por `destino_interno`. Logout via POST com CSRF.
- Selects com valores de CHECK exibem rótulo amigável mas gravam o valor exato. Subcategoria e fonte de receita têm opção em branco e nunca vêm pré-selecionadas.
- Conhecimento que a tela precisa fica no servidor e chega por fragmento HTMX ou por JSON embutido, sem cópia em JavaScript.
- **Formatação**: dinheiro pelo filtro `moeda`; percentual visível pelo filtro `numero` (vírgula, uma casa). Percentual sem denominador exibe "—", nunca "0%" (`fracao` devolve `None`). Valor negativo em vermelho **no `<span>`, não na célula**, para o travessão nunca sair vermelho. Nome de mês com inicial maiúscula como rótulo solto ("Janeiro", cards, tabelas), minúscula dentro de frase ("fevereiro de 2026", subtítulos); abreviado (`MESES_CURTOS`) onde não cabe.
- Script só de uma tela entra pelo `{% block scripts %}` do `base.html`.
- Destaque do item de menu vence pelo caminho mais específico.
- **Linha de apoio no celular, duas variantes**: coluna principal larga (Descrição) → texto de apoio dentro da célula principal (consulta, receitas); coluna principal estreita (Mês) → segunda `<tr class="linha-apoio">` com `colspan`, escondida no desktop (tabela mensal da Anual).
- Responsivo: abaixo de 768px a sidebar vira barra superior; tabelas escondem colunas secundárias e as realocam na linha de apoio, sem rolagem horizontal na página. Grade de cards: 1 coluna até 767px, 2 até 1099px, 4 acima; grade de gráficos: 1 até 1099px, 2 acima. **Exceção deliberada**: a matriz pessoa × categoria da Mensal rola horizontalmente **por dentro** (`.tabela-caixa`), com a primeira coluna fixa (`position: sticky`, teto de 130px no celular). Tabelas simples dos painéis têm `min-width: 0` para não rolar por dentro.
- Validação de entrega inclui **navegador real com login**, não só HTTP nem headless com tempo virtual. Refatoração de componente compartilhado se prova com screenshot antes/depois idêntico (mesmo SHA-256). Ramo sem dado real (empate, "Sem prioridade") se exercita com leitura sintética sobre função pura, sem escrever no banco.

## 7. Rodadas concluídas

| Rodada | Entrega | Estado |
|---|---|---|
| 0 | Docker (Postgres + pgAdmin), `.env` | ✅ |
| 1 | `01_schema.sql` idempotente, view, trigger, comentários | ✅ |
| 2 | Esqueleto Flask, pool, login, `create-user` | ✅ |
| 3 | CSS Glassmorphism, layout com sidebar, cadastros das 5 entidades, `set-password` | ✅ |
| 4 | Lançamento de despesas (série, classificação reativa, edição, exclusão física), blueprint `lancamentos`, `executar` em `db.py` | ✅ |
| 5 | Consulta de despesas: filtros GET, totais, resumo por categoria, paginação 50, editar/excluir cientes da origem, `util.destino_interno` | ✅ |
| 6 | Regra de vírgula, filtro mensal por intervalo de datas (Index Scan), autocomplete de descrição | ✅ |
| 7 | Receitas em página única, view `vw_receitas`, parser de valor em `util.py` | ✅ |
| 8 | Configurações com vigência, promoção de helpers, correção do `query_string` e do `<details>` | ✅ |
| 9 | **Visão Anual** (`/`): seletor de ano, 13 cards, `main/servico.py`, `MESES` em `util.py`, remoção de `.modal` e `.card--sem-padding` | ✅ |
| 10 | **Gráficos** da Anual com Chart.js local (4 gráficos), `{% block scripts %}`, filtro `numero`, percentuais com vírgula, `minmax(0, 1fr)` | ✅ |
| 11 | **Tabelas** da Anual: mês a mês (12 linhas + totais) e por categoria com barra; macro `barra_pct` extraída e aplicada também aos resumos de consulta e receitas; `_totais_do_ano`; variante `<tr class="linha-apoio">` | ✅ |
| 12 | **Visão Mensal** (`/mensal`): seletores ano/mês/ordem, 6 cards, tabelas por categoria e por pessoa, matriz pessoa × categoria com rolagem interna e coluna fixa; `servico_mensal.py`; helpers `card`/`fracao`/`percentual` promovidos; ordenação pt-BR por chave NFD | ✅ |

## 8. Roteiro (ordem sugerida)

1. **Rodada 13 — detalhamento por categoria na Mensal**: linha expansível via HTMX com lançamentos agrupados por subcategoria e link para editar; promoção de `so_fragmento` para `util.py`; favicon; conferência da collation. (Prompt já escrito.)
2. **Limpeza de CSS dos painéis** (pode ser rodada curta): renomear `.filtro-ano` → `.filtro-barra`, unificar `.tabela--categorias`/`.tabela--mes` em `.tabela--resumo`, com prova por screenshot idêntico.
3. **Orçamento** mensal por categoria e planejado × realizado; as consultas mensais de `servico_mensal.py` servem como realizado.
4. **Patrimônio**: ativos e snapshots.
5. **Metas de independência** (página própria): TSR, S e R vigentes, número de independência, taxa de poupança realizada × meta.
6. **IPCA**: carga (API SIDRA/IBGE, `INSERT ... ON CONFLICT (mes) DO UPDATE`) e gráficos deflacionados.
7. **Deploy**: serviço `app` no `docker-compose` com gunicorn; acesso via Tailscale; segundo usuário.

Backlog consciente (adiado, não esquecido): exportação CSV/Excel, duplicar lançamento, edição em lote, intervalo livre de datas, ordenação por cabeçalho, sugestão que preencha valor, aprendizado de descrição por usuário, autocomplete em receitas, comparação entre anos e entre meses, links dos cards para a consulta filtrada, detalhamento por categoria na Anual (por subcategoria × mês), detalhamento por pessoa, navegação por setas entre meses, exportação de gráfico, animação dos gráficos (no padrão do Chart.js).

## 9. Pendências e lembretes

- **Rodada 12 não foi commitada** (as rodadas 4 a 11 já foram).
- Existe **dado real** no banco (725 despesas, 61 receitas). Toda faxina de teste é por id; nenhuma rodada apaga o que não criou. Edição real feita em validação é restaurada pelo mesmo caminho e relatada com o id.
- Usuários: `tiago` ativo, `zz_consulta` desativado, `zz_teste` ativo, senha em `senha_teste` no `.env`. **Todo prompt nomeia a variável.** Usuário de teste se desativa, nunca se apaga.
- `favicon.ico` dá 404 em toda tela (rodada 13 resolve).
- Collation do banco não conferida; desempate por nome no SQL da Anual pode divergir da ordem pt-BR da Mensal (rodada 13 confere).
- Dívida de CSS nomeada: `.filtro-ano` (agora serve a ano, mês e ordem) e a duplicação `.tabela--categorias`/`.tabela--mes`.
- `MESES_CURTOS` mora em `main/servico.py`, não em `util.py`; sobe quando outro módulo precisar.
- `tb_configuracoes` já tem TSR, S e R, mas nada os lê; vão para a página de metas. Configuração recusa negativo por regra da aplicação; um `R` negativo exigiria uma linha em `converter_numero` — decisão a reabrir, não bug.
- A correção do `<details>` no desktop usa `::details-content` (Chromium 131+ / Firefox 139+). Em navegador antigo os filtros extras voltam a ficar inacessíveis fechados.
- Autocomplete: `changed` não reabre a lista ao redigitar exatamente o mesmo trecho após escolher uma sugestão. Digitação normal não esbarra nisso. O JS tem ~75 linhas; se crescer, extrair para `static/js/`.
- Ano futuro só aparece no seletor se houver lançamento futuro; nesse caso média e "meses no azul" mostram "—" e os gráficos mostram 12 meses zerados. Na tabela mensal, meses futuros do ano corrente mostram o que houver lançado (não zero forçado) e "—" em acumulado e taxa.
- `SECRET_KEY` está no `.env`, documentada no README.
- Python 3.14 é recente; se um pacote não tiver wheel, recriar o venv com 3.12.
- Antes de citar arquivo, macro ou variável num prompt, conferir que existe onde o documento diz (ver lições).

## 10. Lições aprendidas (para não repetir)

**Ambiente e Postgres**
- pgAdmin recente rejeita e-mail com domínio `.local`; usar `.com`.
- `teardown_appcontext` roda a cada request — não é lugar para fechar pool; usar `atexit`.
- psycopg conta `%s` dentro de comentário SQL como placeholder; `%s IS NULL` precisa de cast.
- `ESCAPE '\'` em string Python não-raw vira `ESCAPE ''` e quebra o SQL.
- Filtrar por coluna derivada de view mata o índice; filtrar pela coluna base com intervalo resolve. Pedir o EXPLAIN na validação transforma a regra em prova.
- `sorted()` puro ordena por ponto de código: "Água" vai para depois de "Zoo". Chave NFD resolve sem `locale`.

**Flask e Jinja**
- `flask run` só encontra o app com `app.py`/`wsgi.py`, `--app` ou `FLASK_APP` (por isso o `.flaskenv`).
- Comentário `{# #}` dentro de expressão Jinja quebra o arquivo inteiro.
- `{% include %}` dentro de macro enxerga o contexto do template, não os argumentos da macro; nesses casos, macro chamando macro.
- Helper com underscore importado de outro módulo é contradição: promover e tirar o underscore na mesma rodada. Ao renomear `_x` para `x`, conferir variáveis locais que passam a sombrear a função.
- Função de `util.py` não é filtro Jinja até ser registrada no factory.
- `locale` no Windows não é confiável; tuplas em Python resolvem.

**HTMX**
- Swap out-of-band depois de um `<tr>` só sobrevive dentro de `<template>` — a regra é sobre a resposta *começar* com `<tr>`.
- Filtro que vive fora do formulário vai por `hx-include`, não por campo oculto; isso obriga nomes distintos entre parâmetros de filtro e campos do formulário.
- Quando o que foi gravado pode reordenar a lista, devolver o bloco inteiro e usar `HX-Retarget`.
- O HTMX envia o campo com o `name` dele; para outro nome, `hx-vals` — e `hx-params="none"` junto cancela a requisição.
- `changed` compara com o último valor digitado; preenchimento por JS não conta.
- `HX-History-Restore-Request` vem junto com `HX-Request` e espera a página inteira.
- Destaque de menu por prefixo acende dois itens quando uma rota é prefixo da outra.

**CSS e Chart.js**
- `flex-basis` fixo vira altura quando o container passa a `column`.
- `<details>` fechado esconde o conteúdo mesmo com o `<summary>` em `display:none`.
- `nowrap` herdado numa coluna de data estica a tabela inteira no celular.
- Coluna de grade `1fr` tem mínimo `min-content`: um canvas ou uma tabela larga segura a coluna aberta e a página ganha rolagem horizontal. `minmax(0, 1fr)`, ou nenhuma grade, resolve.
- Chart.js precisa de contêiner com altura fixa e `maintainAspectRatio: false`. Eixo Y com centavos esconde marcações.
- `min-width` herdado de `.tabela` faz tabela pequena rolar por dentro em larguras intermediárias; `min-width: 0` onde a tabela cabe.
- Coluna fixa (`sticky`) precisa de teto de largura no celular, senão come a área útil.
- Remover seção numerada do CSS deixa lacuna; manter e registrar é melhor que renumerar.
- Reaproveitar bloco CSS com modificador (`.filtro-ano--mensal`) em vez de renomear é aceitável dentro de "não mexa na outra tela", mas cria dívida de nome que precisa ser paga na rodada seguinte que reabrir aquela tela.

**Processo**
- Suíte só de HTTP passa com bug de layout de pé; **validar no navegador real** pegou os piores bugs (OOB expulso da tabela, vão branco no celular, filtros inacessíveis, canvas travado no `1fr`).
- Edge headless com `--virtual-time-budget` congela o `requestAnimationFrame`; Chart.js nunca redimensiona. Navegador em tempo real, com login de verdade.
- Sem a variável da senha de teste nomeada no prompt, o agente ou adivinha ou cai em cookie assinado. Está em `senha_teste`; placeholder `<VARIÁVEL>` não pode ir para o agente.
- Pedir os números que devem bater (soma das barras = card; rodapé = card; matriz = tabela) transforma validação de tela em conferência objetiva — e pedir que sejam lidos do DOM, não do serviço, fecha o ciclo.
- Faixa de tolerância em soma de percentuais arredondados tem que considerar o número de linhas: 21 linhas a uma casa podem somar 100,2%.
- Prompts que funcionaram: escopo fechado ("SOMENTE isto"), regras negativas, validação executada, relatório de interpretações, "se algo estiver ambíguo, pergunte antes de decidir".
- Deixar o agente propor opções e decidir aqui com justificativa produz melhor resultado do que antecipar tudo no prompt. E quando a interpretação do agente é melhor que o prompt (mês futuro com lançamento mostra o valor; denominador pelo cubo), dizer isso e registrar.
- Regra escrita simétrica quando o domínio é assimétrico gera erro silencioso (parser de `.` e `,`). Escrever também o que deve **falhar**.
- Documentação que afirma coisas sobre o código precisa ser conferida: macros `combobox`/`tabela` inexistentes (rodada 8), histórico ausente de `docs/` (rodada 9), `MESES_CURTOS` no módulo errado (rodada 12). Cada uma custa um "ponto que precisei interpretar".
- Rodada boa mistura entrega nova com duas ou três limpezas pendentes já identificadas; a dívida não sobrevive a três rodadas assim.
