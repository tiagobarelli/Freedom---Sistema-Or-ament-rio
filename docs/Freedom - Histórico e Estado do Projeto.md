# Freedom — Histórico e Estado do Projeto

Documento de contexto para o projeto orquestrador e para o agente. Resume o que foi decidido, o que existe e o que falta. Consolidado após a rodada 19 (10/09/2026), com as decisões da rodada 20 (resumo anual) já fechadas. Fica em `docs/` no repositório e na base de conhecimento do orquestrador; se um muda, o outro muda.

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
- **Visual** (rodadas 17–18): o Glassmorphism roxo saiu e entrou o design system sóbrio — fundo `#F5F5F7`, fonte do sistema, cinzas neutros, acento teal `#30B0C7`, verde/vermelho reservados a receita/despesa/negativo, sidebar escura recolhível, barra superior sticky, cartão padrão. Referências: `design_handoff_freedom_visao_anual/` e `design_handoff_freedom_lancamentos_cadastros/`. O protótipo manda no **desktop**; os padrões de celular (sidebar vira barra, linha de apoio, grades 1/2/4) se mantêm. Já refeitos: layout, Visão Anual, lançamento, edição e consulta de despesas, receitas e os cinco cadastros. **Pendente**: Visão Mensal, Orçamento, configurações e login, que ainda rodam sobre os apelidos da seção 1(b) do CSS. O contraste do botão primário (branco sobre `#30B0C7`, 2,6:1) foi aceito pelo dono na rodada 17.
- **Refatoração visual não muda comportamento** (rodada 18): editar despesa continua em página própria (é o destino de `?retorno=`), cadastros continuam com página de formulário, sem busca client-side nem paginação nos recentes — edição em linha nessas telas foi para o backlog. Prioridade virou quatro radios P1–P4 mais "—" (sem prioridade), escondidos quando a essencialidade efetiva é Essencial. O total do mês subiu para a barra superior (`#total-mes`, mesmo swap out-of-band).
- **Ocultar valores na Visão Anual** (rodada 19): botão olho na barra superior, e a página abre oculta. Some todo número do corpo — valores e notas dos cards, trilhos e barras, os quatro gráficos inteiros, as tabelas (menos nomes de mês e de categoria), travessões e a frase de ano sem despesa; ficam rótulos, títulos e nomes. Oculto é esqueleto neutro: bloco cinza, sem cor semântica, não selecionável, layout imóvel. O estado é da **aba**: trocar de ano, navegar no app, Voltar e F5 mantêm; sair da aba ou do app, fechar a aba e fazer logout voltam a ocultar. Proteção só visual: os números continuam no HTML e no JSON dos gráficos. **Só a Visão Anual tem o olho** (decisão do dono depois da 19); a detecção de saída de aba roda em toda tela autenticada, porque é ela que encerra o estado quando o usuário sai estando em outra tela.
- **Resumo anual** (decidido para a rodada 20): um texto livre por ano que explica os números daquele ano, **sem limite de tamanho**. Tabela própria com o **ano como chave**. Cadastro em página dedicada no grupo Cadastros ("Resumos anuais", antes de Configurações): criar escolhendo um ano que a Visão Anual mostra e que ainda não tem resumo; editar só o texto (o ano não muda); **excluir** com confirmação — é entrada do usuário, como configuração e orçamento, e não tem `ativo` nem autoria. Texto simples com quebras de linha preservadas, sem Markdown. Na Visão Anual, card entre os nove indicadores e os gráficos, com o texto inteiro e link "Editar"; **ano sem resumo não mostra card**; com o olho fechado o texto também some. A página de cadastro não tem olho.

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
| Interatividade | HTMX 2.0.4, arquivo local, mais JS próprio pontual (menu do celular, sidebar recolhível, limpar filtros, autocomplete, gráficos, linha expansível, ocultar valores) |
| Gráficos | Chart.js 4.5.1, UMD local, só na Visão Anual via `{% block scripts %}`. Núcleo, sem plugins. Barras proporcionais em tabela são CSS (`barra_pct`). Continuou local na refatoração visual (o handoff pedia CDN 4.4.1) |
| CSS | Um arquivo escrito à mão (`static/css/app.css`), tokens do design system neutro/teal em `:root` (rodada 17); apelidos do tema antigo na seção 1(b) até a refatoração visual pendente. Sem Tailwind, sem biblioteca de ícones: Lucide (ISC) em **SVG inline** pela macro `icone`. Favicon SVG próprio em `static/` |
| Dinheiro | `Decimal` em todo cálculo (`ROUND_HALF_UP` onde arredonda); `float` só na serialização final para JSON de gráfico |
| Ambiente | Windows, PowerShell, venv em `venv/`, Python 3.14. Validação em navegador com Playwright (`requirements-dev.txt`, rodada 18) |

## 6. Estrutura atual do código

```
freedom/
  __init__.py      create_app: CSRF, pool, Flask-Login, blueprints, CLI, filtros Jinja `moeda` e `numero`
  config.py        lê .env; template_folder/static_folder apontam para a raiz
  db.py            ConnectionPool, dict_row, get_connection(), executar()
  util.py          destino_interno(); ValorInvalido, converter_valor, converter_numero(percentual=),
                   formatar_valor, formatar_numero, escapar_like; MESES; so_fragmento (rodada 13);
                   chave_alfabetica (NFD, rodada 15) — nunca `locale`; fracao (rodada 17)
  cli.py           flask create-user, flask set-password
  auth/            forms.py, models.py, routes.py (/login, /logout)
  main/            routes.py  "/" Visão Anual, "/mensal" Visão Mensal, "/mensal/categoria/<id>" fragmento
                   servico.py Anual: anos_com_lancamento, ano_valido, MESES_CURTOS (derivada de MESES),
                              painel_do_ano, _totais_do_ano (origem única dos totais), _tabela_mensal,
                              _tabela_categorias, _cards ({kpis: 4, indicadores: 9}), _graficos; helpers
                              compartilhados card, percentual;
                              _serie é o único ponto onde Decimal vira número JSON
                   servico_mensal.py Mensal: intervalo_do_mes, nome_do_periodo, painel_do_mes (cards e três
                              tabelas de UMA consulta agrupada por categoria × pessoa), categoria(),
                              lancamentos_da_categoria(), detalhe_da_categoria()
  cadastros/       um módulo por entidade (categorias, subcategorias, contas, pessoas, ref_receitas),
                   forms.py, servico.py (contagem agregada "N ativas · M inativas", alternar_ativo,
                   erro de UNIQUE pendurado no campo pelo nome da constraint)
  lancamentos/     despesas.py (lançar, editar com ?retorno= validado por destino_interno, excluir,
                   classificação reativa, sugestões), consulta.py, receitas.py, servico_receitas.py,
                   forms.py, servico.py (consultas/agregados, id_valido, pagina_pedida)
  configuracoes/   rotas.py, forms.py, servico.py (CATALOGO, valor_vigente) — padrão de edição em linha
  orcamento/       __init__.py (prefixo /orcamento), rotas.py (modo/periodo), forms.py,
                   servico.py (montagem: criar mês por cópia do anterior ou por média 12m, linhas,
                   receita, encerrar/reabrir/excluir, predicado de mês criável, cabecalho_do_mes),
                   acompanhamento.py (só leitura: realizado por subcategoria, acumulado por OR de
                   intervalos, faixa de cor ok/alerta/estouro, fora do orçamento).
                   URLs do mês em AAAA-MM; da linha só por id; encerrar/reabrir carregam o modo
templates/
  base.html        blocos `atributos_html` (no <html>), `cabeca` (fim do <head>) e `scripts`; favicon
  layout_app.html  sidebar escura com o menu numa estrutura só (`navegacao`: Painel, Lançamentos,
                   Cadastros — Configurações por último), seções recolhíveis (`freedom.sidebar.<secao>`
                   em localStorage), rodapé com usuário e logout POST; barra superior com os blocos
                   `titulo_pagina`, `subtitulo_pagina`, `acoes_pagina`; `data-valores="ocultos"` e o
                   script dono do estado do olho no bloco `cabeca` (rodada 19)
  _macros.html     icone (_CAMINHOS_ICONE, Lucide inline), campo, campo_selecao, campo_area,
                   badge_ativo, acoes_linha, cabecalho_tabela, vazio, lista_cadastro, filtro_inativos,
                   filtros_cadastro, acoes_formulario, reais, barra_pct, badge_essencialidade,
                   bloco_prioridade, campos_despesa (grade de 12 colunas), campos_receita,
                   combobox (<input list> + datalist — lista ABERTA)
  main/index.html  (marcas sensivel* em todo número), main/mensal.html, main/_detalhe_categoria.html
  lancamentos/*    (_total_oob.html: total do mês na barra superior), configuracoes/*
  cadastros/       <entidade>_lista.html, <entidade>_form.html, _linha_<entidade>.html, _rotulos.html
  orcamento/       orcamento.html, _cabecalho.html (estado do mês, nos dois modos), _corpo.html
                   (montagem), _acompanhamento.html, _linha.html, _linha_edicao.html, _receita.html,
                   _receita_edicao.html, _nova_linha.html, _aviso.html
static/
  css/app.css      seção 1 tokens do design system (paleta --grafico-*, --esqueleto) e 1(b) apelidos do
                   tema antigo; 4 layout (sidebar escura, barra superior); 5.2 botões (.btn--icone,
                   rodada 19); componente .barra (após 5.4); 5.9 lançamento, 5.10 consulta,
                   5.11 autocomplete, 5.12 configurações, 5.13 "Painéis: o que a Anual e a Mensal
                   compartilham" (5.13.1 gráficos, 5.13.2 tabelas dos painéis, 5.13.3 Visão Anual
                   refeita), 5.14 Mensal (5.14.1 .tabela--detalhe), 5.15 Orçamento (5.15.1
                   acompanhamento), 5.16 ocultar valores (rodada 19), 7 responsivo, 8 utilitários
                   (.negativo global desde a 16). Seção 5.7 (modal) removida; lacuna intencional
  js/htmx.min.js, js/chart.umd.js, js/visao_anual.js (os scripts de layout — sidebar, menu do
                   celular, olho — são inline em layout_app.html)
  favicon.svg      teal; única cópia do hex da cor primária fora do CSS (SVG estático não lê variáveis)
db/init/01_schema.sql
docs/            Freedom - Estrutura do Banco de Dados.md, Freedom - Histórico e Estado do Projeto.md
design_handoff_freedom_visao_anual/, design_handoff_freedom_lancamentos_cadastros/
                 referência visual; os README erram sobre a stack e os support.js não são da aplicação
CLAUDE.md        instruções permanentes do agente (onde divergir de um handoff, vale o CLAUDE.md)
run.py, requirements.txt, requirements-dev.txt (Playwright), .gitignore,
README.md ("Dependências de front-end", com a licença do Lucide), .env, .flaskenv
```

Padrões já estabelecidos no código (o agente deve mantê-los):

- Subir **sempre com `--debug`**: `python -m flask --app freedom --debug run --port 5000`. Sem ele o Jinja não recarrega template e Python não recarrega — duas rodadas perderam validação por isso. Reiniciar depois de mexer em código, antes de validar.
- Cadastros: lista + criar + editar + ativar/desativar (HTMX troca só a `<tr>`); sem excluir. Lista em `lista_cadastro` (cabeçalho `.so-leitor`), barra `filtros_cadastro` com contagem agregada e interruptor "Mostrar inativos", formulário em página própria com `acoes_formulario`. O resumo anual (rodada 20) usa a tela de cadastro, mas se exclui e não tem `ativo`.
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
- **Script que decide o primeiro quadro roda antes de pintar**: colado no elemento (seções da sidebar) ou no `<head>` pelo bloco `cabeca` (olho), nunca no fim do corpo.
- **Controle segmentado é grupo de links** com `aria-current="page"` (seletor de ano da Anual): GET com recarga inteira, sem JS, e o estado visual é o mesmo atributo que o anunciado.
- **Ícones**: macro `icone(nome)` com os caminhos em `_CAMINHOS_ICONE`, Lucide copiado do oficial, `currentColor`, `aria-hidden`. Botão só de ícone leva nome acessível (`.so-leitor` ou `aria-label`) e `title`.
- **Barra superior**: cada tela preenche `titulo_pagina`, `subtitulo_pagina` e `acoes_pagina`. Sticky no desktop, estática no celular, onde os botões da barra dividem a linha por `flex` (um botão sozinho ocupa 100%).
- **Ocultar valores (Visão Anual, rodada 19)**: o servidor manda `data-valores="ocultos"` no `<html>`; o script em `cabeca` do `layout_app.html` é o dono único do estado, guardado por aba (`sessionStorage`, chaves `freedom.valores…`). Navegação é `pagehide` antes de `hidden`; saída de aba é `hidden` sozinho; um prazo de 300 ms separa fechar a aba de navegar. Marcas: `sensivel` (valor em linha), `sensivel-bloco` (célula ou bloco inteiro — use quando um `<span>` mudaria o subpixel do texto), `sensivel-barra` (preenchimento), `sensivel-area` (gráfico, com `visibility: hidden` para o Chart.js não perder a medida). Os dois ícones vão no botão e o CSS escolhe; `aria-pressed` sai `false` do servidor e é corrigido no `DOMContentLoaded` (exceção conhecida à regra de estado único).
- **Linha de apoio no celular**: coluna principal larga → texto dentro da célula; coluna principal estreita → `<tr class="linha-apoio">` com `colspan`. Ação vira ícone com `aria-label` descritivo.
- Responsivo: < 768px sidebar vira barra; grades de cards 1/2/4 colunas (768/1100); gráficos 1/2. **Exceções deliberadas de rolagem interna** (`.tabela-caixa`): matriz pessoa × categoria (primeira coluna `sticky`, teto 130px no celular) e todas as tabelas do orçamento (tela desktop-first). `.so-leitor` absoluto dentro de contêiner que rola precisa de ancestral `position: relative`.
- Validação de entrega: **navegador real com login** (`--debug` ligado); números conferidos **lidos do DOM** contra a outra tela ou SQL; refatoração de CSS provada por **SHA-256 de capturas** com referência capturada duas vezes (instrumento determinístico: viewport e `device_scale_factor` fixos, espera pelos gráficos, expansão por `element.click()` sem `:hover`); ramo sem dado real exercitado por função pura (ou montado pelas funções puras e servido ao navegador); mudança de schema validada re-executando o script no banco com dados e num banco descartável. Na Visão Anual com o olho fechado: nenhum nó de texto visível com dígito em `.conteudo__corpo`. Cenários de visibilidade de aba e de bfcache pedem Chrome real via CDP — o Playwright não esconde aba nem usa bfcache.

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
| 17 | **Refatoração visual I — tokens, layout e Visão Anual**: design system em `:root` com apelidos do tema antigo (seção 1(b)); macro `icone` (Lucide inline); sidebar escura recolhível com `localStorage`; barra superior sticky; cartão padrão; Visão Anual com 4 KPIs + 9 indicadores, seletor de ano em links com `aria-current`, gráficos 2×2; tokens de contraste `--accent-texto` e `--green-texto`; `fracao` promovida a `util.py` (três cópias removidas); favicon teal | ✅ |
| 18 | **Refatoração visual II — lançamentos e cadastros**: controles de formulário e botões; lançar despesa em grade de 12 colunas com `#total-mes` na barra, prioridade em radios, aviso inline e linha recém-gravada piscando; editar despesa, consulta e receitas no visual novo; cinco cadastros com lista em cartão, badge e interruptor de inativos com contagem agregada; `requirements-dev.txt` com Playwright | ✅ |
| 19 | **Ocultar valores na Visão Anual**: botão olho, esqueleto neutro sobre todo número, barras e gráficos; estado por aba distinguido pela ordem `pagehide`/`hidden` (bug de bfcache achado e corrigido na validação); blocos `atributos_html` e `cabeca` em `base.html`; `.btn--icone`, `--esqueleto`, seção 5.16; `.pagina-acoes .btn` por `flex` | ✅ |

## 8. Roteiro (ordem sugerida)

1. **Rodada 20 — resumo anual** (prompt escrito): `tb_resumos_anuais` (DDL idempotente, com o `.md` do banco junto), página "Resumos anuais" em Cadastros e card na Visão Anual sujeito ao olho. Regras na seção 3.
2. **Refatoração visual pendente**: Visão Mensal, Orçamento, configurações e login; remover os apelidos da seção 1(b) e `card--solido` quando nada mais os usar. Citar sempre pelo nome: o número já mudou duas vezes.
3. **Metas de independência** (página própria): TSR, S e R vigentes, número de independência, taxa de poupança realizada × meta.
4. **Patrimônio**: ativos e snapshots.
5. **IPCA**: carga (API SIDRA/IBGE, `INSERT ... ON CONFLICT (mes) DO UPDATE`) e gráficos deflacionados.
6. **Deploy**: serviço `app` no `docker-compose` com gunicorn; Tailscale; segundo usuário. Com o celular na rede, conferir o olho no aparelho (ver seção 9).

Backlog consciente: exportação CSV/Excel, duplicar lançamento, edição em lote, intervalo livre de datas, ordenação por cabeçalho, sugestão que preencha valor, autocomplete em receitas, comparação entre anos/meses, links dos cards para a consulta, detalhe por categoria na Anual (subcategoria × mês), detalhe por pessoa, setas entre meses, exportação de gráfico, animação dos gráficos, orçamento por pessoa, cópia de orçamento entre anos, histórico de alterações do orçamento, integração dos painéis com o orçamento, decidir se o `letter-spacing` herdado no detalhe é desejado, edição em linha nos cadastros e na despesa, busca nos cadastros, paginação dos recentes (os três recusados como mudança funcional na rodada 18).

## 9. Pendências e lembretes

- **Commitar até a rodada 19 antes da 20**, que muda o schema. Conferir no git se as rodadas 13 a 18 estão lá.
- O repositório anexado ao projeto do orquestrador só reflete o último sync: sincronizar depois de cada commit, senão revisão e prompt olham código velho (em 10/09 ele ainda não tinha a rodada 19).
- A revisão da entrega da rodada 18 não ficou registrada no orquestrador; o que está aqui sobre ela vem do prompt e do código.
- **Olho, a conferir no celular real** (quando houver acesso pela rede): se a miniatura do trocador de apps é capturada antes do `hidden`; alvo de toque de 30px, abaixo dos 44px recomendados; bfcache do Safari/iOS. Risco residual medido: aba reaberta em menos de 300 ms do fechamento volta à mostra. O logout limpa o estado interceptando o formulário de sair — redundante com o prazo, mantido.
- Apelidos do tema antigo (seção 1(b) do CSS) e `card--solido` vazio continuam até a refatoração visual pendente.
- Usuários: `tiago`, `zz_consulta` (desativado), `zz_teste` — senha em `senha_teste`. **Todo prompt nomeia a variável.** Validação que edita dado real carimba `atualizado_em`; se isso incomodar, o agente cria e apaga a própria despesa de teste.
- `favicon.svg` repete o hex da cor primária (`#30B0C7`); se a paleta mudar, são dois lugares.
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
- Chart.js: contêiner com altura fixa, `maintainAspectRatio: false`, eixo sem centavos. Para esconder um gráfico sem perder a medida, `visibility: hidden` no canvas; `display: none` zera o tamanho.
- Um `<span>` inserido no meio de uma frase muda o subpixel das letras seguintes e o SHA da captura; `display: contents` não resolve. Para marcar parte de um texto sem mudar pixel, marque o contêiner inteiro.
- `min-width` herdado de `.tabela` faz tabela pequena rolar por dentro; `min-width: 0` onde cabe. `sticky` precisa de teto no celular. `.so-leitor` absoluto dentro de contêiner rolável estica a página sem ancestral posicionado.
- Seletor de descendência (`.tabela--x th`) alcança tabela aninhada; efeito acidental que só o SHA da captura revelou (1px).
- Manter lacuna de numeração; modificador temporário para não tocar outra tela é aceitável, mas é dívida a pagar na rodada seguinte.

**Navegador: ciclo de vida da página**
- `visibilitychange` com `hidden` dispara também quando a própria aba navega (troca de ano, clique no menu, F5), não só quando o usuário sai dela.
- Voltando do bfcache, o `pageshow` de quem volta pode disparar antes do `pagehide` de quem sai. Navegação é `pagehide` antes de `hidden`; saída de aba é `hidden` sozinho — distinguir pela ordem é mais robusto que por relógio. Fechar a aba e navegar geram a mesma sequência; ali só um prazo curto separa (300 ms, medido com CPU freada em 20×).
- O Playwright não esconde aba nem usa bfcache (nem `bring_to_front`, nem outra janela, nem `Page.setWebLifecycleState`): esses cenários pedem Chrome real via CDP com a janela mexida pelo sistema.

**Processo**
- **Navegador real** pegou os piores bugs (OOB expulso, vão branco, filtros inacessíveis, canvas travado, tabela duplicada, `.so-leitor` esticando). Edge headless com tempo virtual congela `requestAnimationFrame`.
- Nomear a variável da senha de teste no prompt; placeholder não pode ir para o agente.
- Pedir os números que devem bater e que sejam lidos do DOM. Faixa de tolerância em percentuais depende do número de linhas.
- Refatoração "sem mudança visual" se prova com capturas de referência tiradas duas vezes (instrumento determinístico) e comparação de pares (propriedade, valor), não com contagem de linhas.
- Quando duas regras do prompt colidem (criar o mês seguinte × meses passados não são criáveis), o agente que resolve com um predicado único e relata fez melhor do que perguntar — desde que a solução seja a única coerente.
- Regras assimétricas do domínio precisam ser escritas com o que deve falhar (parser de `.`/`,`; zero em orçamento × lançamento).
- Documentação que afirma coisas sobre o código precisa ser conferida: `combobox`/`tabela` (rodada 8), histórico ausente (9), `MESES_CURTOS` (12), placeholder da senha (12). Cada uma custa um ponto de interpretação.
- Rodada boa mistura entrega nova com duas ou três limpezas já identificadas; uma rodada só de limpeza, curta e com critério de aceite binário (SHA idêntico), zera dívida sem risco. Quando uma limpeza muda pixel de propósito, o diff pixel a pixel delimitado (caixa do diff dentro da caixa do elemento) é a prova.
- Handoff de ferramenta de design chega com premissas erradas sobre a stack (Java, CDN, biblioteca de ícones, sem celular). Ler o README do handoff contra a seção 5 deste documento antes de transformá-lo em prompt. O protótipo é referência, não contrato (rodada 17): gráficos 2×2 em vez do `auto-fit`, contraste corrigido por tokens `--*-texto`, celular preservado.
- Ramo sem dado real montado pelas funções puras do serviço e servido ao navegador pega o que a tela real não mostra: foi assim que apareceu o dígito em "Nenhuma despesa em <ano>" com o olho fechado.
- Trabalho adiado se cita pelo nome, não pelo número da rodada: a refatoração visual pendente já foi "19" e "20" em comentários do código.
