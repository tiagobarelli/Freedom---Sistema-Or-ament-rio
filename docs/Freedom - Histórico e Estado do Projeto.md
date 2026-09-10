# Freedom — Histórico e Estado do Projeto

Documento de contexto para o projeto orquestrador e para o agente. Resume o que foi decidido, o que existe e o que falta. Consolidado após a rodada 16 (09/09/2026), antes da refatoração visual. Fica em `docs/` no repositório e na base de conhecimento do orquestrador; se um muda, o outro muda.

## 1. O que é o Freedom

Sistema web pessoal de controle financeiro. Roda localmente em Windows via Docker; no futuro, outros membros da casa acessam pela rede Tailscale (nada exposto na nuvem). Um usuário master hoje; a esposa entra depois. Interface em português do Brasil.

Objetivo de longo prazo: além de registrar despesas e receitas, medir crescimento real das despesas (deflação por IPCA), orçamento mensal por subcategoria, evolução do patrimônio e metas de independência financeira (TSR, retorno real, taxa de poupança).

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
- **Configuração se exclui** (rodada 8) e **orçamento se exclui** (rodada 15): vigência digitada errada e linha de plano são entrada do usuário, não histórico. Mês de orçamento **encerrado** não se altera nem se exclui.
- Consulta de despesas é **tela separada** da de lançamento. **Receitas são tela única** (rodada 7). A assimetria é intencional.
- **A página inicial é a Visão Anual** (rodadas 9–11); **a Visão Mensal é página própria** (rodada 12) com detalhamento por categoria (rodada 13); **o Orçamento é página própria** (rodada 15). Todas no grupo Painel.
- **Ano/mês inválido na URL cai no período corrente**, sem erro e sem tela vazia. Só anos com lançamento aparecem no seletor dos painéis; no orçamento, só meses que têm orçamento.
- **TSR, S e R não entram nos painéis nem no orçamento.** Servem a uma página própria de metas, futura.
- Nos painéis, **só categorias e pessoas com despesa no período** aparecem nas tabelas. Na tabela mensal da Anual os 12 meses aparecem sempre.
- **Orçamento é por subcategoria**, mês a mês, com uma **receita planejada global** por mês (um número, não por fonte) para a taxa de poupança planejada. O planejado é entrada do usuário; a média dos 12 meses anteriores é **sugestão de tela**, nunca gravada como derivado. **Encerrar congela o planejado**; o realizado nunca é gravado — vem sempre de `vw_despesas`. Despesa anual (IPVA) é provisionada por ÷12 e o desequilíbrio mês a mês se resolve na visão **acumulada** do acompanhamento (rodada 16), não no plano.
- Orçamento **não bloqueia o celular**, mas não tem layout dedicado: a tabela rola por dentro e a página não pode quebrar.
- **Acompanhamento do orçamento** (rodada 16): modo Montagem | Acompanhamento e período Mês | Acumulado no ano, ambos GET. O acumulado considera só os meses do ano **com orçamento**, do primeiro até o selecionado. % consumido: neutro < 90%, âmbar de 90% a 100% (inclusive), vermelho acima de 100%. Planejado zero com realizado > 0 é estouro. Subcategoria sem linha com despesa vai para o bloco "fora do orçamento"; entra no rodapé e nos cards, não nos subtotais.
- **Visual em transição** (decisão de setembro/2026): o tema Glassmorphism roxo será substituído por um design system sóbrio (fundo `#F5F5F7`, fonte do sistema, cinzas neutros, acento teal `#30B0C7`, verde/vermelho reservados a receita/despesa/negativo, sidebar escura recolhível). Referência: `design_handoff_freedom_visao_anual/` (README + protótipo `Freedom - Visão Anual v2.dc.html`). O protótipo manda no **desktop**; os padrões de celular atuais (sidebar vira barra, linha de apoio, grades 1/2/4) se mantêm.

## 4. Banco de dados

Fonte da verdade: `docs/Freedom - Estrutura do Banco de Dados.md` e `db/init/01_schema.sql`. Regra: se um muda, o outro muda. O DDL mudou duas vezes desde a rodada 1: `vw_receitas` (rodada 7) e o **orçamento** (rodada 15: `tb_orcamento_meses` nova; `tb_orcamentos` trocou `categoria_id` por `subcategoria_id` e ganhou FK para o mês). A mudança da rodada 15 foi feita com blocos idempotentes (`ADD/DROP COLUMN IF EXISTS`, `DO $$ IF NOT EXISTS (constraint)`), sem `DROP TABLE`, e validada re-executando o script no banco com dados e num banco descartável criado do zero.

Resumo do que importa para escrever prompts:

- PostgreSQL 16 em Docker (`docker-compose.yml`, serviço `postgres`, container `freedom_postgres`), pgAdmin em `localhost:5050`. Credenciais e `DATABASE_URL` no `.env`. Collation `en_US.utf8` (provider libc) — `SHOW lc_collate` não existe mais no PG 16; ler `pg_database.datcollate`.
- 14 tabelas: `tb_categorias`, `tb_subcategorias`, `tb_ref_receitas`, `tb_pessoas`, `tb_usuarios`, `tb_contas`, `tb_ipca`, `tb_configuracoes`, `tb_despesas`, `tb_receitas`, `tb_orcamento_meses`, `tb_orcamentos`, `tb_ativos`, `tb_patrimonio_snapshots`. Duas views: `vw_despesas` e `vw_receitas`.
- `vw_despesas`: despesa + subcategoria + categoria + **essencialidade efetiva** (`COALESCE(despesa, subcategoria)`) + `prioridade` + `pessoa_id` (não o nome; JOIN com `tb_pessoas` não perde linha, FK `NOT NULL`) + `ano_mes` inteiro `AAAAMM`. `vw_receitas`: receita + categoria + subcategoria da fonte + `ref_receita_ativo` + `ano_mes`. Leitura sempre pelas views; escrita nas tabelas base.
- **`ano_mes` serve para exibir e agrupar, não para filtrar**: todo filtro de período usa `data >= início AND data < início do período seguinte`, o que faz `ix_despesas_data` / `ix_receitas_data` serem usados (EXPLAIN ANALYZE na rodada 12: Index Scan, 0,2 ms).
- Nada derivado é armazenado. Toda FK é `NOT NULL` e `ON DELETE RESTRICT`. Referência não é apagada: tem `ativo` (em `tb_contas`, `ativa`).
- CHECKs: essencialidade em `Essencial` / `Não Essencial`; `tb_contas.tipo` em `corrente, cartao, dinheiro, outro`; `prioridade` 1–4; `valor > 0` em despesas e receitas; dia 1 em `tb_ipca.mes`, `tb_orcamento_meses.ano_mes` e `tb_orcamentos.ano_mes` (redundante com a FK, mantido para documentar); `>= 0` em `valor_planejado`, `receita_planejada` e patrimônio. `tb_ativos.classe` e `tb_configuracoes.chave` sem CHECK, de propósito.
- **Orçamento**: `tb_orcamento_meses (ano_mes PK dia 1, receita_planejada NOT NULL DEFAULT 0, criado_em NOT NULL DEFAULT now(), encerrado_em NULL = aberto, observacoes)`; `tb_orcamentos (id, subcategoria_id FK, ano_mes FK → tb_orcamento_meses, valor_planejado >= 0, UNIQUE (subcategoria_id, ano_mes))`. Linha ausente = subcategoria não orçada. **Zero é planejado legítimo** ("está no plano, não pretendo gastar") — assimetria deliberada com lançamento, que exige `> 0`.
- `prioridade` é nula quando a despesa é essencial e pode ser nula em não essencial antiga; o banco não impede. A Visão Anual trata NULL em não essencial como faixa "Sem prioridade".
- `tb_configuracoes` tem `vigente_desde`; vigente numa data = maior `vigente_desde ≤ data`; todas as chaves de uma vez com `DISTINCT ON (chave)`.
- Trigger `fn_set_atualizado_em()` em despesas e receitas; `atualizado_em` fica NULL até o primeiro UPDATE — e uma edição de validação **carimba** a linha (ficou registrado na despesa 613, rodada 13).
- **Regras da aplicação, não do banco**: prioridade só quando a essencialidade efetiva é "Não Essencial"; autoria nunca muda; referência inativa visível na edição e nos filtros mas nunca gravada em lançamento novo; receita pré-seleciona a pessoa do usuário logado; configuração não aceita negativo; catálogo de chaves em Python; **mês de orçamento encerrado não recebe INSERT/UPDATE/DELETE em linhas nem na receita; reabrir só se não existir mês de orçamento posterior; mês criável = sem orçamento e (corrente ou futuro, ou seguinte a um mês orçado)**; sugestão de linhas exclui subcategoria inativa e subcategoria de categoria inativa.

Estado dos dados: **1.770 despesas e 145 receitas reais, de 2025 e 2026**; 24 categorias, 82 subcategorias, 3 contas, 5 pessoas, 8 fontes de receita. **Orçamento de setembro/2026 aberto com 66 linhas**, já revisado pelo Tiago (receita planejada R$ 31.000,00, total planejado R$ 38.107,20). `tb_configuracoes` tem TSR, S e R (nada os lê). Usuário `tiago` ativo, `zz_consulta` desativado, `zz_teste` ativo — **senha na variável `senha_teste` do `.env`**. **Há dado real em produção: nenhuma rodada apaga linha que não criou; faxina de teste sempre por id; edição real de validação é revertida pelo mesmo caminho e relatada.**

## 5. Stack da aplicação (fechada, não reabrir)

| Camada | Escolha |
|---|---|
| Web | Flask 3, application factory (`create_app` em `freedom/__init__.py`), Blueprints |
| Banco | psycopg 3 + `psycopg_pool`, SQL direto parametrizado, `row_factory=dict_row`. **Sem ORM, sem migrações** |
| Auth | Flask-Login; hash com `werkzeug.security` (scrypt) |
| Formulários | Flask-WTF (CSRF em todo POST) |
| Interatividade | HTMX 2.0.4, arquivo local, mais JS próprio pontual (menu, limpar filtros, autocomplete, gráficos, linha expansível) |
| Gráficos | Chart.js 4.5.1, UMD local, só na Visão Anual via `{% block scripts %}`. Núcleo, sem plugins. Barras proporcionais em tabela são CSS (`barra_pct`). **Continua local na refatoração visual** — o handoff pede CDN 4.4.1; não seguir |
| CSS | Escrito à mão, variáveis CSS. Tema atual Glassmorphism claro, **em substituição pelo design system neutro/teal** (rodadas 17–19). Sem Tailwind, sem bibliotecas de ícones — ícones Lucide entram como **SVG inline** copiado do protótipo (macro Jinja), não via unpkg. Favicon SVG próprio em `static/` |
| Dinheiro | `Decimal` em todo cálculo (`ROUND_HALF_UP` onde arredonda); `float` só na serialização final para JSON de gráfico |
| Ambiente | Windows, PowerShell, venv em `venv/`, Python 3.14 |

## 6. Estrutura atual do código

```
freedom/
  __init__.py      create_app: CSRF, pool, Flask-Login, blueprints, CLI, filtros Jinja `moeda` e `numero`
  config.py        lê .env; template_folder/static_folder apontam para a raiz
  db.py            ConnectionPool, dict_row, get_connection(), executar()
  util.py          destino_interno(); ValorInvalido, converter_valor, converter_numero(percentual=),
                   formatar_valor, formatar_numero, escapar_like; MESES; so_fragmento (rodada 13);
                   chave_alfabetica (NFD, rodada 15) — nunca `locale`
  cli.py           flask create-user, flask set-password
  auth/            forms.py, models.py, routes.py (/login, /logout)
  main/            routes.py  "/" Visão Anual, "/mensal" Visão Mensal, "/mensal/categoria/<id>" fragmento
                   servico.py Anual: anos_com_lancamento, ano_valido, MESES_CURTOS (derivada de MESES),
                              painel_do_ano, _totais_do_ano (origem única dos totais), _tabela_mensal,
                              _tabela_categorias, _graficos; helpers compartilhados card, fracao, percentual;
                              _serie é o único ponto onde Decimal vira número JSON
                   servico_mensal.py Mensal: intervalo_do_mes, nome_do_periodo, painel_do_mes (cards e três
                              tabelas de UMA consulta agrupada por categoria × pessoa), categoria(),
                              lancamentos_da_categoria(), detalhe_da_categoria()
  cadastros/       um módulo por entidade + servico.py
  lancamentos/     despesas.py (lançar, editar com ?retorno= validado por destino_interno, excluir,
                   classificação reativa, sugestões), consulta.py, receitas.py, servico_receitas.py,
                   forms.py, servico.py (consultas/agregados, id_valido, pagina_pedida)
  configuracoes/   rotas.py, forms.py, servico.py (CATALOGO, valor_vigente) — padrão de edição em linha
  orcamento/       __init__.py (prefixo /orcamento), rotas.py (modo/periodo), forms.py,
                   servico.py (montagem: criar mês por cópia do anterior ou por média 12m, linhas,
                   receita, encerrar/reabrir/excluir, predicado de mês criável, cabecalho_do_mes;
                   _fracao — cópia de main.fracao, a promover para util.py),
                   acompanhamento.py (só leitura: realizado por subcategoria, acumulado por OR de
                   intervalos, faixa de cor ok/alerta/estouro, fora do orçamento).
                   URLs do mês em AAAA-MM; da linha só por id; encerrar/reabrir carregam o modo
templates/
  base.html        `{% block scripts %}`, `<link rel="icon" href="static/favicon.svg">`
  layout_app.html  menu: Painel ("Visão Anual", "Visão Mensal", "Orçamento"), Lançamentos, Cadastros
  _macros.html     campo, campo_area, badge, ações, reais, badge_essencialidade, campos_despesa,
                   campos_receita, combobox (<input list> + datalist — lista ABERTA), barra_pct
  main/index.html, main/mensal.html, main/_detalhe_categoria.html
  lancamentos/*, configuracoes/*
  orcamento/       orcamento.html, _cabecalho.html (estado do mês, nos dois modos), _corpo.html
                   (montagem), _acompanhamento.html, _linha.html, _linha_edicao.html, _receita.html,
                   _receita_edicao.html, _nova_linha.html, _aviso.html
static/
  css/app.css      seção 1 (variáveis, paleta --grafico-*), seções 2–8; componente .barra (após 5.4);
                   5.9 lançamento, 5.10 consulta, 5.11 autocomplete, 5.12 configurações,
                   5.13 "Painéis: o que a Anual e a Mensal compartilham" (5.13.1 gráficos,
                   5.13.2 tabelas dos painéis: .tabela--resumo + modificadores --mensal, --estreita,
                   --matriz; .filtro-barra), 5.14 Mensal (5.14.1 .tabela--detalhe), 5.15 Orçamento
                   (5.15.1 acompanhamento), seção 8 utilitários (.negativo é global desde a 16).
                   Seção 5.7 (modal) removida; lacuna intencional. Sete utilitários sem uso removidos na 16
  js/htmx.min.js, js/chart.umd.js, js/visao_anual.js
  favicon.svg      (única cópia do hex da cor primária fora do CSS — SVG estático não lê variáveis)
db/init/01_schema.sql
docs/            Freedom - Estrutura do Banco de Dados.md, Freedom - Histórico e Estado do Projeto.md
run.py, requirements.txt, .gitignore, README.md ("Dependências de front-end"), .env, .flaskenv
```

Padrões já estabelecidos no código (o agente deve mantê-los):

- Subir **sempre com `--debug`**: `python -m flask --app freedom --debug run --port 5000`. Sem ele o Jinja não recarrega template e Python não recarrega — duas rodadas perderam validação por isso. Reiniciar depois de mexer em código, antes de validar.
- Cadastros: lista + criar + editar + ativar/desativar (HTMX troca só a `<tr>`); sem excluir.
- Lançamento em série: grava por HTMX sem recarregar, limpa os campos variáveis, mantém os repetidos, devolve o foco, atualiza lista e agregados por swap out-of-band.
- **`<template>` em resposta out-of-band que comece com `<tr>`**. Swap direto (`afterend`, `outerHTML`) de `<tr>` não precisa: o htmx 2 embrulha toda resposta em `<template>` antes de parsear.
- Estado de UI que sobrevive ao re-render vai em `<input type="hidden">`; filtros fora do formulário vão por `hx-include`.
- Filtros são GET na URL com `hx-push-url`; mesma rota devolve página ou fragmento conforme `HX-Request`, com exceção para `HX-History-Restore-Request`. **Exceção deliberada: seletores de painéis e orçamento (ano, mês, ordem, modo) recarregam a página inteira** em `onchange`.
- Quando gravar/excluir pode reordenar lista, mudar paginação ou **mudar subtotal e rodapé**, devolver o bloco inteiro necessário; `HX-Retarget` quando o alvo natural do disparador não é onde a resposta deve cair (formulário de acréscimo → tabela; erro de estado → `#orcamento-aviso`).
- **Linha expansível**: `<button>` na primeira célula carrega `aria-expanded`/`aria-controls` e o clique é delegado à tabela; a `<tr>` continua `<tr>`. Abrir dispara evento próprio (`htmx.trigger(linha, 'abrir')`); fechar é `detalhe.remove()` sem requisição; `htmx:responseError` devolve o estado. Reabrir refaz a requisição (sem cache no cliente).
- Rota só de fragmento: sem `HX-Request` → redirect para a página-mãe com os mesmos parâmetros, **antes** de qualquer 404. Regra de estado recusada → **409** com faixa de aviso.
- Agregados vêm de consulta própria, nunca de soma em Python sobre a página. Exceção prevista: composição em Python (`Decimal`) sobre conjuntos **pequenos e completos** que o SQL já agregou. Dois lugares que mostram o mesmo total leem da mesma origem.
- **Gráficos**: servidor entrega séries prontas em JSON no template (`tojson`); JS só desenha; textos do servidor; cores por variáveis CSS via `getComputedStyle`; contêiner com altura fixa e `maintainAspectRatio: false`; grade com `minmax(0, 1fr)`; eixo sem centavos, tooltip com centavos.
- **Barras proporcionais**: `barra_pct`; largura em `style=` com ponto; rodapé de 100% sem barra; denominador = total do conjunto exibido, não o card. Soma de percentuais exibidos pode dar 100,2% e não se corrige.
- Busca textual escapa `%` e `_` (`ESCAPE '\'` em raw string), sem `unaccent`. Ordenação alfabética pt-BR em Python com `chave_alfabetica` (NFD); o `ORDER BY` do SQL com `en_US.utf8` dá o mesmo resultado, conferido com empate sintético.
- **Lista aberta → `combobox`; cadastro fechado → `<select>`** (chave de configuração é aberta; subcategoria é fechada).
- Valor de dinheiro entra com vírgula (`converter_valor`); zero só onde o domínio admite (orçamento), tratado antes do parser.
- `UniqueViolation` vira erro de campo legível; transação por request; rollback em erro.
- Login: mensagem única; `destino_interno` em todo redirect; logout POST com CSRF. `?retorno=` aceita querystring completa (URL-encoded).
- Selects de CHECK exibem rótulo amigável e gravam o valor exato. Subcategoria e fonte têm opção em branco e nunca vêm pré-selecionadas.
- Conhecimento de tela fica no servidor e chega por fragmento ou JSON embutido; **nada decidido em Jinja** (cores, "—", estouro) — funções Python devolvem a classe/estado.
- **Formatação**: `moeda`; percentual pelo filtro `numero` (vírgula, uma casa); sem denominador → "—" (`fracao` devolve `None`); negativo em vermelho **no `<span>`**, travessão nunca vermelho; mês maiúsculo como rótulo, minúsculo em frase, `MESES_CURTOS` onde não cabe.
- Script de uma tela pelo `{% block scripts %}`. Destaque de menu pelo caminho mais específico.
- **Linha de apoio no celular**: coluna principal larga → texto dentro da célula; coluna principal estreita → `<tr class="linha-apoio">` com `colspan`. Ação vira ícone com `aria-label` descritivo.
- Responsivo: < 768px sidebar vira barra; grades de cards 1/2/4 colunas (768/1100); gráficos 1/2. **Exceções deliberadas de rolagem interna** (`.tabela-caixa`): matriz pessoa × categoria (primeira coluna `sticky`, teto 130px no celular) e todas as tabelas do orçamento (tela desktop-first). `.so-leitor` absoluto dentro de contêiner que rola precisa de ancestral `position: relative`.
- Validação de entrega: **navegador real com login** (`--debug` ligado); números conferidos **lidos do DOM** contra a outra tela ou SQL; refatoração de CSS provada por **SHA-256 de capturas** com referência capturada duas vezes (instrumento determinístico: viewport e `device_scale_factor` fixos, espera pelos gráficos, expansão por `element.click()` sem `:hover`); ramo sem dado real exercitado por função pura; mudança de schema validada re-executando o script no banco com dados e num banco descartável.

## 7. Rodadas concluídas

| Rodada | Entrega | Estado |
|---|---|---|
| 0–3 | Docker, schema idempotente, esqueleto Flask, login, CSS Glassmorphism, cadastros | ✅ |
| 4–6 | Lançamento de despesas em série, consulta com filtros e agregados, intervalo de datas, autocomplete | ✅ |
| 7–8 | Receitas em página única (`vw_receitas`), configurações com vigência, promoção de helpers | ✅ |
| 9–11 | **Visão Anual**: 13 cards, 4 gráficos Chart.js local, tabelas mês a mês e por categoria, `barra_pct` | ✅ |
| 12 | **Visão Mensal**: seletores ano/mês/ordem, 6 cards, tabelas por categoria e pessoa, matriz com rolagem interna | ✅ |
| 13 | **Detalhe por categoria** na Mensal (linha expansível HTMX, agrupado por subcategoria, link para editar); `so_fragmento` em `util.py`; favicon; collation conferida | ✅ |
| 14 | **Limpeza de CSS**: `.filtro-barra`, `.tabela--resumo` unificando seis tabelas (−21 declarações duplicadas), sumário; cinco capturas com SHA idêntico; lista de seletores sem uso | ✅ |
| 15 | **Orçamento — schema e montagem**: `tb_orcamento_meses` + `tb_orcamentos` por subcategoria (DDL idempotente, `.md` do banco reescrito); blueprint `orcamento` com criar (cópia do anterior ou média 12m), edição em linha, acréscimo por `<select>`, receita planejada, encerrar/reabrir/excluir, 409 em conflito de estado; `chave_alfabetica` em `util.py` | ✅ |
| 16 | **Acompanhamento do orçamento**: modo e período, cards realizado × planejado, tabela com % consumido colorido (ok/alerta/estouro), bloco fora do orçamento, acumulado por OR de intervalos; limpezas (7 seletores, `--estreita` na Anual, `letter-spacing` explícito); `.negativo` promovido a global e correção do autoescape de classe | ✅ |

## 8. Roteiro (ordem sugerida)

1. **Refatoração visual, em três rodadas** (17: tokens em `:root`, layout — sidebar escura recolhível com estado em `localStorage`, barra superior sticky, cartão padrão — e Visão Anual com 4 KPIs + 9 indicadores secundários; 18: lançamentos e cadastros; 19: Mensal, Orçamento e configurações). Regras que o handoff não diz e valem: Chart.js **local** 4.5.1; ícones Lucide **inline** por macro; cores dos gráficos por variáveis CSS; celular preservado; barra da tabela por categoria proporcional ao **total** (decisão pendente — recomendação: manter); favicon muda com a paleta; `support.js` do handoff é runtime da ferramenta de design e não entra no repositório; promover `fracao` para `util.py` na 17. Validação: comparação lado a lado com o protótipo em 1440px, números lidos do DOM idênticos aos de antes, celular conferido em 390px.
2. **Metas de independência** (página própria): TSR, S e R vigentes, número de independência, taxa de poupança realizada × meta.
3. **Patrimônio**: ativos e snapshots.
4. **IPCA**: carga (API SIDRA/IBGE, `INSERT ... ON CONFLICT (mes) DO UPDATE`) e gráficos deflacionados.
5. **Deploy**: serviço `app` no `docker-compose` com gunicorn; Tailscale; segundo usuário.

Backlog consciente: exportação CSV/Excel, duplicar lançamento, edição em lote, intervalo livre de datas, ordenação por cabeçalho, sugestão que preencha valor, autocomplete em receitas, comparação entre anos/meses, links dos cards para a consulta, detalhe por categoria na Anual (subcategoria × mês), detalhe por pessoa, setas entre meses, exportação de gráfico, animação dos gráficos, orçamento por pessoa, cópia de orçamento entre anos, histórico de alterações do orçamento, integração dos painéis com o orçamento, decidir se o `letter-spacing` herdado no detalhe é desejado.

## 9. Pendências e lembretes

- Conferir o estado de commit das rodadas 13 a 16 antes do próximo prompt (o histórico da 15 as registrava como pendentes).
- Base de conhecimento do orquestrador já tem o schema da rodada 15; precisa receber o handoff de design (README + protótipo v2) antes da rodada 17.
- Tiago está testando o sistema inteiro antes da refatoração visual; defeitos achados entram na rodada 17 ou numa rodada de correções antes dela.
- `orcamento/servico.py._fracao` duplica `main/servico.py.fracao` — promover para `util.py` na rodada 17.
- Usuários: `tiago`, `zz_consulta` (desativado), `zz_teste` — senha em `senha_teste`. **Todo prompt nomeia a variável.** Validação que edita dado real carimba `atualizado_em`; se isso incomodar, o agente cria e apaga a própria despesa de teste.
- `favicon.svg` repete o hex da cor primária (roxo); muda junto com a paleta na rodada 17.
- `tb_configuracoes` tem TSR, S e R; nada os lê até a página de metas. Configuração recusa negativo; `R` negativo exigiria uma linha em `converter_numero`.
- `<details>` no desktop usa `::details-content` (Chromium 131+ / Firefox 139+).
- Autocomplete: `changed` não reabre ao redigitar o mesmo trecho; JS ~75 linhas.
- Ano futuro no seletor só com lançamento futuro; média e "meses no azul" mostram "—"; tabela mensal mostra o que houver lançado e "—" em acumulado e taxa.
- `SECRET_KEY` no `.env`, documentada no README. Python 3.14: sem wheel, recriar venv com 3.12.
- Antes de citar arquivo, macro ou variável num prompt, conferir que existe onde o documento diz.

## 10. Lições aprendidas (para não repetir)

**Ambiente e Postgres**
- pgAdmin recente rejeita e-mail `.local`. `teardown_appcontext` não é lugar para fechar pool. psycopg conta `%s` em comentário. `ESCAPE '\'` precisa de raw string.
- Filtrar por coluna derivada de view mata o índice; intervalo pela coluna base resolve — e o EXPLAIN na validação prova.
- `sorted()` puro ordena por ponto de código ("Água" depois de "Zoo"); chave NFD resolve sem `locale`. `en_US.utf8` no banco dá a mesma ordem.
- Mudança de schema em tabela vazia é troca de coluna com blocos idempotentes, nunca `DROP TABLE`; validar no banco com dados, re-executar, e num banco descartável do zero.

**Flask, Jinja e HTMX**
- `flask run` precisa de `--app`/`FLASK_APP`. **Sem `--debug` nada recarrega**, e a captura "depois" compara HTML velho com CSS novo — custou uma rodada de teste em duas ocasiões.
- `{# #}` dentro de expressão Jinja quebra o arquivo. `{% include %}` em macro não vê os argumentos. Função de `util.py` não é filtro até ser registrada.
- Helper com underscore compartilhado é contradição: promover na hora; conferir locais que passam a sombrear.
- Swap OOB após `<tr>` precisa de `<template>`; swap direto não (htmx 2 embrulha a resposta). Filtro fora do formulário vai por `hx-include`. `hx-vals` para renomear; `hx-params="none"` cancela. `changed` ignora preenchimento por JS. `HX-History-Restore-Request` espera página inteira. Destaque por prefixo acende dois itens.
- Formulário com `hx-target` em si mesmo e resposta que é a tabela inteira duplica a tabela dentro do formulário — faltou `HX-Retarget`.
- `{{ 'class="x"' if cond }}` passa pelo autoescape e vira `class=&#34;x&#34;`; interpolar só o nome da classe dentro do atributo.
- Classe utilitária (`.negativo`) nascida dentro de um seletor de tela não funciona fora dela e o erro é silencioso (o texto só não fica vermelho). Utilitário nasce global, na seção 8.
- `date_trunc(data) = ANY(...)` mata o índice; acumulado de vários meses é OR de intervalos com datas parametrizadas.
- `role="button"` na `<tr>` tira dela o papel de linha; `<button>` na célula dá teclado de graça e mantém a semântica.

**CSS e Chart.js**
- `flex-basis` fixo vira altura em `column`. `<details>` fechado esconde conteúdo mesmo com `summary` oculto. `nowrap` herdado estica tabela no celular.
- `1fr` tem mínimo `min-content`: canvas ou tabela larga segura a coluna e a página rola; `minmax(0, 1fr)`.
- Chart.js: contêiner com altura fixa, `maintainAspectRatio: false`, eixo sem centavos.
- `min-width` herdado de `.tabela` faz tabela pequena rolar por dentro; `min-width: 0` onde cabe. `sticky` precisa de teto no celular. `.so-leitor` absoluto dentro de contêiner rolável estica a página sem ancestral posicionado.
- Seletor de descendência (`.tabela--x th`) alcança tabela aninhada; efeito acidental que só o SHA da captura revelou (1px).
- Manter lacuna de numeração; modificador temporário para não tocar outra tela é aceitável, mas é dívida a pagar na rodada seguinte.

**Processo**
- **Navegador real** pegou os piores bugs (OOB expulso, vão branco, filtros inacessíveis, canvas travado, tabela duplicada, `.so-leitor` esticando). Edge headless com tempo virtual congela `requestAnimationFrame`.
- Nomear a variável da senha de teste no prompt; placeholder não pode ir para o agente.
- Pedir os números que devem bater e que sejam lidos do DOM. Faixa de tolerância em percentuais depende do número de linhas.
- Refatoração "sem mudança visual" se prova com capturas de referência tiradas duas vezes (instrumento determinístico) e comparação de pares (propriedade, valor), não com contagem de linhas.
- Quando duas regras do prompt colidem (criar o mês seguinte × meses passados não são criáveis), o agente que resolve com um predicado único e relata fez melhor do que perguntar — desde que a solução seja a única coerente.
- Regras assimétricas do domínio precisam ser escritas com o que deve falhar (parser de `.`/`,`; zero em orçamento × lançamento).
- Documentação que afirma coisas sobre o código precisa ser conferida: `combobox`/`tabela` (rodada 8), histórico ausente (9), `MESES_CURTOS` (12), placeholder da senha (12). Cada uma custa um ponto de interpretação.
- Rodada boa mistura entrega nova com duas ou três limpezas já identificadas; uma rodada só de limpeza, curta e com critério de aceite binário (SHA idêntico), zera dívida sem risco. Quando uma limpeza muda pixel de propósito, o diff pixel a pixel delimitado (caixa do diff dentro da caixa do elemento) é a prova.
- Handoff de ferramenta de design chega com premissas erradas sobre a stack (Java, CDN, biblioteca de ícones, sem celular). Ler o README do handoff contra a seção 5 deste documento antes de transformá-lo em prompt.
