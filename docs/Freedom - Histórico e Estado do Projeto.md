# Freedom — Histórico e Estado do Projeto

Documento de contexto para o projeto orquestrador e para o agente. Resume o que foi decidido, o que existe e o que falta. Consolidado após a rodada 24 (13/09/2026). Fica em `docs/` no repositório e na base de conhecimento do orquestrador; se um muda, o outro muda.

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
- **IPCA** (rodada 21): a série oficial entra pelo comando `flask carregar-ipca`, que lê a API do SIDRA/IBGE (tabela 1737, variáveis 2266 = número-índice e 63 = variação mensal) e grava **desde dezembro/1993**, que é a base do índice (= 100); meses anteriores são descartados antes de qualquer conversão (moedas antigas, índice minúsculo que não cabe em `NUMERIC(14,6)`). Upsert por `mes` que **nunca apaga**; rodar de novo não faz mal. Ritual: depois do dia 10 de cada mês, quando o IBGE publica o mês anterior. **É a única chamada externa do sistema** e roda pelo comando ou pelo botão "Atualizar do IBGE" da tela (rodada 23) — nunca por agendamento dentro do app. O índice é gravado como publicado, nunca reconstruído encadeando variações. Leitura da série: tela "IPCA" em Cadastros (rodada 22). Primeiro uso do índice: Análise por subcategoria (rodada 24). **`tb_despesas.integra_ipca` está reservada para uma tela futura** (despesas mensais somadas só das marcadas, decisão do dono) e **não é lida** pela análise por subcategoria nem por nada ainda.
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
- **Resumo anual** (rodada 20): um texto livre por ano que explica os números daquele ano, **sem limite de tamanho**. Tabela própria com o **ano como chave** (`tb_resumos_anuais`, sem `id`, sem `ativo`, sem FK — o ano não é tabela; a interface só oferece anos com lançamento). Cadastro em página dedicada no grupo Cadastros ("Resumos anuais", antes de Configurações): criar escolhendo um ano que a Visão Anual mostra e que ainda não tem resumo; editar só o texto (o ano não muda); **excluir** com confirmação — é entrada do usuário, como configuração e orçamento, e não tem `ativo` nem autoria. Texto simples com quebras de linha preservadas, sem Markdown. Na Visão Anual, card "Resumo do ano" entre os nove indicadores e os gráficos, com o texto inteiro e link "Editar" (`?retorno=` para a Anual do mesmo ano); **ano sem resumo não mostra card**; com o olho fechado o texto também some. A página de cadastro não tem olho.
- **Tela do IPCA** (rodada 22): só leitura, em Cadastros entre "Resumos anuais" e "Configurações", sem olho. Matriz **ano × 12 meses**, ano mais recente primeiro, com alternância **Variação mensal | Número-índice** por GET (`?modo=`, grupo de links `.segmentado` com `aria-current`, modo inválido cai em variação) e coluna "No ano" nos dois modos = índice do último mês carregado do ano ÷ índice de dezembro do ano anterior − 1. **Calculada na função pura `matriz()` sobre a série completa** (composição em `Decimal` sobre conjunto pequeno e completo que o SQL entregou inteiro — a exceção prevista na seção 6), nunca gravada; conferida contra o acumulado publicado pelo IBGE (variável 69) em quatro anos com 0,00 pp de diferença. Duas casas, como o IBGE publica; o texto da célula (valor ou "—") sai pronto do servidor. 1993 só tem dezembro; ano incompleto ganha a nota "2026: acumulado até agosto". No celular a tabela rola por dentro na horizontal com a coluna do ano fixa, sem teto de altura.
- **Atualização do IPCA pela tela** (rodada 23): botão primário "Atualizar do IBGE" (ícone `refresh-cw`) em `acoes_pagina` da tela do IPCA (também no estado vazio), `POST /cadastros/ipca/atualizar` com CSRF via HTMX (campo oculto mesmo com `hx-headers`, para o caminho sem JavaScript virar redirect e não 400). Enquanto roda, o botão fica desabilitado com texto de espera; a resposta troca o cartão inteiro (faixa de resultado, nota, tabela) e o subtítulo da barra por swap fora de banda, mantendo o modo. Texto da faixa decidido em Python: "nenhum mês novo", "<mês> carregado: índice e variação", "N meses carregados", mais "M meses revisados pelo IBGE" quando houver atualização. Erro: faixa vermelha, nada gravado, botão volta — **502** quando o IBGE não responde ou a série vem torta (a mensagem distingue os dois), **503** quando o banco falha; 500 nunca no caminho previsto. Comando e botão passam pela **mesma função** (`ipca.carregar`) e produzem o mesmo resumo — a saída do comando não mudou um caractere; o caminho web usa timeout de 20 s (gunicorn mata a requisição em 30 s), o comando continua com 60 s. Dica calculada no servidor pela data: a partir do dia 12 espera-se o mês anterior, antes disso o retrasado; se o último mês carregado é mais velho que o esperado, a tela diz "O IBGE já deve ter publicado <mês>". Sem agendamento dentro do app; o Agendador de Tarefas do Windows rodando o comando fica como opção da rodada de deploy.
- **Análise por subcategoria** (rodada 24, entregue): página no grupo Painel, tudo por GET (URL é o estado, recarga inteira, sem HTMX), **sem olho** (decisão do dono: só a Anual tem). Uma subcategoria por vez (`<select>` com `<optgroup>` por categoria, só as que têm lançamento). Período: últimos 3, 6 ou 12 meses (janelas móveis terminando no mês corrente), série inteira (do primeiro ao último mês do acervo) e personalizado (mês inicial e final). **Agrupamento**: Mensal | Trimestral | Anual | 12 meses móveis — é a resposta às subcategorias descontínuas: **não se classifica subcategoria** (nenhuma coluna, nenhuma heurística); IPVA mês a mês é onze zeros e um pico, ano a ano é uma série comparável, e quem escolhe a granularidade é o usuário. Gráfico de linha (Chart.js, segunda tela a usá-lo) e, embaixo, a tabela dos pontos com a **quantidade de lançamentos** (distingue "mais compras" de "compras mais caras"). Mês sem lançamento é **zero**, nunca linha interpolada. **Correção pelo IPCA** é uma opção que acrescenta a linha real e mantém a nominal esmaecida — a distância entre elas é a inflação. Deflação por lançamento no mês (`valor × índice_base ÷ índice_do_mês`), em SQL sobre `vw_despesas × tb_ipca`, somada depois; **base = último mês carregado** ("a preços de agosto de 2026"), meses posteriores à base usam fator 1. Janela de 12 meses olha 11 meses para trás mesmo fora do período exibido; só janelas completas desde o primeiro mês do acervo. Bucket que não está inteiro no período ou contém o mês em curso é marcado "parcial". `integra_ipca` não é lida. Backlog: ticket médio deflacionado; deflação na Visão Anual.
  **O que a entrega acrescentou à decisão** (rodada 24): o gráfico **não suaviza** a linha (`tension: 0`, ao contrário da Anual) — entre dois meses com zero no meio, a curva passaria por baixo do zero e desenharia gasto negativo; a tela faz **quatro** consultas, não uma (a série é uma; as outras três são a lista do `<select>`, o intervalo do acervo e o mês base do IPCA, perguntas independentes da subcategoria); os campos "De" e "Até" ficam sempre visíveis e preenchidos com o período resolvido, mas **valor que não é um mês legível não volta** para eles, porque `<input type="month">` recusa e avisa no console; e a correção é calculada sempre — a caixa liga a **exibição** da segunda linha e da coluna, não um segundo caminho de código.

## 4. Banco de dados

Fonte da verdade: `docs/Freedom - Estrutura do Banco de Dados.md` e `db/init/01_schema.sql`. Regra: se um muda, o outro muda. O DDL mudou três vezes desde a rodada 1: `vw_receitas` (rodada 7), o **orçamento** (rodada 15: `tb_orcamento_meses` nova; `tb_orcamentos` trocou `categoria_id` por `subcategoria_id` e ganhou FK para o mês) e o **resumo anual** (rodada 20: `tb_resumos_anuais` nova, com trigger de `atualizado_em`). A mudança da rodada 15 foi feita com blocos idempotentes (`ADD/DROP COLUMN IF EXISTS`, `DO $$ IF NOT EXISTS (constraint)`), sem `DROP TABLE`, e validada re-executando o script no banco com dados e num banco descartável criado do zero; a da rodada 20 seguiu o mesmo rito. A rodada 21 **não mudou o schema**: só carregou `tb_ipca`.

Resumo do que importa para escrever prompts:

- PostgreSQL 16 em Docker (`docker-compose.yml`, serviço `postgres`, container `freedom_postgres`), pgAdmin em `localhost:5050`. Credenciais e `DATABASE_URL` no `.env`. Collation `en_US.utf8` (provider libc) — `SHOW lc_collate` não existe mais no PG 16; ler `pg_database.datcollate`.
- 15 tabelas: `tb_categorias`, `tb_subcategorias`, `tb_ref_receitas`, `tb_pessoas`, `tb_usuarios`, `tb_contas`, `tb_ipca`, `tb_configuracoes`, `tb_despesas`, `tb_receitas`, `tb_orcamento_meses`, `tb_orcamentos`, `tb_ativos`, `tb_patrimonio_snapshots`, `tb_resumos_anuais`. Duas views: `vw_despesas` e `vw_receitas`. Duas tabelas têm o **período como chave primária**, sem `id`: `tb_orcamento_meses` (`ano_mes`) e `tb_resumos_anuais` (`ano`).
- `vw_despesas`: despesa + subcategoria + categoria + **essencialidade efetiva** (`COALESCE(despesa, subcategoria)`) + `prioridade` + `pessoa_id` (não o nome; JOIN com `tb_pessoas` não perde linha, FK `NOT NULL`) + `ano_mes` inteiro `AAAAMM`. `vw_receitas`: receita + categoria + subcategoria da fonte + `ref_receita_ativo` + `ano_mes`. Leitura sempre pelas views; escrita nas tabelas base.
- **`ano_mes` serve para exibir e agrupar, não para filtrar**: todo filtro de período usa `data >= início AND data < início do período seguinte`, o que faz `ix_despesas_data` / `ix_receitas_data` serem usados (EXPLAIN ANALYZE na rodada 12: Index Scan, 0,2 ms).
- Nada derivado é armazenado. Toda FK é `NOT NULL` e `ON DELETE RESTRICT`. Referência não é apagada: tem `ativo` (em `tb_contas`, `ativa`).
- CHECKs: essencialidade em `Essencial` / `Não Essencial`; `tb_contas.tipo` em `corrente, cartao, dinheiro, outro`; `prioridade` 1–4; `valor > 0` em despesas e receitas; dia 1 em `tb_ipca.mes`, `tb_orcamento_meses.ano_mes` e `tb_orcamentos.ano_mes` (redundante com a FK, mantido para documentar); `>= 0` em `valor_planejado`, `receita_planejada` e patrimônio; em `tb_resumos_anuais`, `ano` entre 2000 e 2100 e `texto` com ao menos um caractere visível. `tb_ativos.classe` e `tb_configuracoes.chave` sem CHECK, de propósito.
- **`tb_ipca`** (`id`, `mes` dia 1 UNIQUE, `numero_indice NUMERIC(14,6)`, `variacao_mensal NUMERIC(6,4)` nula): carregada pela rodada 21 com **393 meses, dez/1993 (= 100) a ago/2026**. O índice vem com 13 casas da API e no máximo 2 significativas desde dez/1993, logo os 6 decimais guardam o valor exato. **`variacao_mensal` está em pontos percentuais como o IBGE publica (0,38 = 0,38 %), ao contrário de `tb_configuracoes.valor`, que guarda fração (0,04 = 4 %)**; fica `NULL` quando o IBGE não publica número. Deflacionar = `valor × indice_base / indice_mes`. O `id` não significa nada (a chave natural é `mes`) e pula ~393 por execução do comando, porque o upsert consome a sequência mesmo sem inserir — esperado. `tb_despesas.integra_ipca` (default `TRUE`) diz se a despesa entra no agregado deflacionado; nada o lê até a rodada 23.
- **Orçamento**: `tb_orcamento_meses (ano_mes PK dia 1, receita_planejada NOT NULL DEFAULT 0, criado_em NOT NULL DEFAULT now(), encerrado_em NULL = aberto, observacoes)`; `tb_orcamentos (id, subcategoria_id FK, ano_mes FK → tb_orcamento_meses, valor_planejado >= 0, UNIQUE (subcategoria_id, ano_mes))`. Linha ausente = subcategoria não orçada. **Zero é planejado legítimo** ("está no plano, não pretendo gastar") — assimetria deliberada com lançamento, que exige `> 0`.
- `prioridade` é nula quando a despesa é essencial e pode ser nula em não essencial antiga; o banco não impede. A Visão Anual trata NULL em não essencial como faixa "Sem prioridade".
- `tb_configuracoes` tem `vigente_desde`; vigente numa data = maior `vigente_desde ≤ data`; todas as chaves de uma vez com `DISTINCT ON (chave)`.
- Trigger `fn_set_atualizado_em()` em despesas, receitas e resumos anuais; `atualizado_em` fica NULL até o primeiro UPDATE — e uma edição de validação **carimba** a linha (ficou registrado na despesa 613, rodada 13).
- **Regras da aplicação, não do banco**: prioridade só quando a essencialidade efetiva é "Não Essencial"; autoria nunca muda; referência inativa visível na edição e nos filtros mas nunca gravada em lançamento novo; receita pré-seleciona a pessoa do usuário logado; configuração não aceita negativo; catálogo de chaves em Python; **mês de orçamento encerrado não recebe INSERT/UPDATE/DELETE em linhas nem na receita; reabrir só se não existir mês de orçamento posterior; mês criável = sem orçamento e (corrente ou futuro, ou seguinte a um mês orçado)**; sugestão de linhas exclui subcategoria inativa e subcategoria de categoria inativa.

Estado dos dados (12/09/2026): **1.778 despesas e 145 receitas reais, de 2025 e 2026** — o Tiago vai lançar retroativamente até 2012, e a carga do IPCA já cobre esse período; 24 categorias, 82 subcategorias, 3 contas, 5 pessoas, 8 fontes de receita. **`tb_ipca` com 393 meses (dez/1993 a ago/2026)**, sem variação nula. **Orçamento de setembro/2026 aberto com 66 linhas**, já revisado pelo Tiago (receita planejada R$ 31.000,00, total planejado R$ 38.107,20). Há resumo anual escrito para 2026 (a Anual mostra o card). `tb_configuracoes` tem TSR, S e R (nada os lê). Usuário `tiago` ativo, `zz_consulta` desativado, `zz_teste` ativo — **senha na variável `senha_teste` do `.env`**. **Há dado real em produção: nenhuma rodada apaga linha que não criou; faxina de teste sempre por id; edição real de validação é revertida pelo mesmo caminho e relatada.**

## 5. Stack da aplicação (fechada, não reabrir)

| Camada | Escolha |
|---|---|
| Web | Flask 3, application factory (`create_app` em `freedom/__init__.py`), Blueprints |
| Banco | psycopg 3 + `psycopg_pool`, SQL direto parametrizado, `row_factory=dict_row`. **Sem ORM, sem migrações** |
| Auth | Flask-Login; hash com `werkzeug.security` (scrypt) |
| Formulários | Flask-WTF (CSRF em todo POST) |
| Interatividade | HTMX 2.0.4, arquivo local, mais JS próprio pontual (menu do celular, sidebar recolhível, limpar filtros, autocomplete, gráficos, linha expansível, ocultar valores) |
| Gráficos | Chart.js 4.5.1, UMD local, carregado pelo `{% block scripts %}` só nas duas telas que desenham: Visão Anual e Análise por subcategoria (rodada 24). O que as duas fazem igual mora em `static/js/graficos.js`; cada tela tem o seu arquivo com o que é só dela. Núcleo, sem plugins. Barras proporcionais em tabela são CSS (`barra_pct`). Continuou local na refatoração visual (o handoff pedia CDN 4.4.1) |
| CSS | Um arquivo escrito à mão (`static/css/app.css`), tokens do design system neutro/teal em `:root` (rodada 17); apelidos do tema antigo na seção 1(b) até a refatoração visual pendente. Sem Tailwind, sem biblioteca de ícones: Lucide (ISC) em **SVG inline** pela macro `icone`. Favicon SVG próprio em `static/` |
| Dinheiro | `Decimal` em todo cálculo (`ROUND_HALF_UP` onde arredonda); `float` só na serialização final para JSON de gráfico |
| HTTP de saída | Só no comando do IPCA: `urllib.request` da stdlib, timeout 60 s, sem nova tentativa. Nada de `requests`, `sidrapy` ou `pandas` (rodada 21) |
| Ambiente | Windows, PowerShell, venv em `venv/`, Python 3.14. Validação em navegador com Playwright (`requirements-dev.txt`, rodada 18) |

## 6. Estrutura atual do código

```
freedom/
  __init__.py      create_app: CSRF, pool, Flask-Login, blueprints, CLI, filtros Jinja `moeda` e `numero`
  config.py        lê .env; template_folder/static_folder apontam para a raiz
  db.py            ConnectionPool, dict_row, get_connection(), executar()
  util.py          destino_interno(); ValorInvalido, converter_valor, converter_numero(percentual=),
                   MESES_CURTOS, nome_do_periodo(ano, mes | date) → "agosto de 2026", nome_do_mes(mes)
                   → "Janeiro" (rodada 23), dobrar (NFD, rodada 22 — chave_alfabetica e ipca.py usam);
                   somar_meses(mes, passos) e intervalo_de_meses(a, b) (rodada 24, vindos do
                   orcamento e do ipca.py);
                   formatar_valor, formatar_numero, escapar_like; MESES; so_fragmento (rodada 13);
                   chave_alfabetica (NFD, rodada 15) — nunca `locale`; fracao (rodada 17)
  cli.py           flask create-user, flask set-password, flask carregar-ipca (rodada 21; imprime a partir
                   de ipca.carregar desde a 23; erro vira click.ClickException com código de saída 1)
  ipca.py          (rodada 21) tudo de tb_ipca: buscar (único ponto com rede), interpretar (função pura:
                   JSON do SIDRA → lista (mes, numero_indice, variacao_mensal); descarta antes de dez/1993;
                   recusa a série se dez/1993 ≠ 100, mês faltando, índice não positivo ou mês duplicado),
                   gravar (única transação, upsert que só atualiza o que mudou, contagens do banco via
                   RETURNING (xmax = 0)), casas_decimais, ErroIpca. Leitura (rodada 22): serie() é a única
                   consulta; matriz(serie, modo) é pura e devolve linhas por ano, nota e subtítulo prontos;
                   modo_valido, VARIACAO/INDICE/MODOS. Rodada 23: carregar (buscar → interpretar →
                   gravar, resultado estruturado com meses_inseridos via array_agg FILTER (xmax = 0)),
                   TEMPO_LIMITE_WEB = 20, ErroIpca com etapa (ibge/dados/banco) e motivo curto,
                   texto_da_faixa / texto_do_erro / texto_das_nulas, mes_esperado / pendente / texto_da_dica
                   (puras; a data entra por parâmetro; corte no dia 12). Rodada 24: base_de_correcao()
                   (último mês carregado e o índice dele, numa linha) para quem deflaciona
  auth/            forms.py, models.py, routes.py (/login, /logout)
  main/            routes.py  "/" Visão Anual, "/mensal" Visão Mensal, "/mensal/categoria/<id>" fragmento
                   servico.py Anual: anos_com_lancamento, ano_valido (MESES_CURTOS vem de util desde a 22),
                              painel_do_ano, _totais_do_ano (origem única dos totais), _tabela_mensal,
                              _tabela_categorias, _cards ({kpis: 4, indicadores: 9}), _graficos; helpers
                              compartilhados card, percentual;
                              _serie é o único ponto onde Decimal vira número JSON
                   servico_mensal.py Mensal: intervalo_do_mes, painel_do_mes (cards e três
                              tabelas de UMA consulta agrupada por categoria × pessoa), categoria(),
                              lancamentos_da_categoria(), detalhe_da_categoria()
                   analise.py (rodadas 24 e 26) as DUAS rotas GET, e só elas: /analise/subcategoria
                              e /analise/prioridade. Cada uma lê da URL o que é dela (o id da
                              subcategoria ou a chave da faixa), monta o Recorte e passa o resto
                              para servico_analise.painel()
                   servico_analise.py o serviço das duas análises (era só da primeira até a 26).
                              Recorte(nome, condicao, params, so_integrantes) é a única coisa que
                              as separa; painel(args, recorte, hoje) é o caminho inteiro da URL à
                              tela. Recorte de cada uma: recorte_da_subcategoria e, na 26,
                              FAIXAS / faixa_valida / recorte_da_faixa (Essencial pela
                              essencialidade efetiva, ignorando prioridade; P1–P4 por
                              `prioridade = N`, que sobre NULL não é verdadeiro e por isso já
                              despreza a não essencial sem prioridade). subcategorias_com_lancamento
                              (optgroup por categoria), intervalo_do_acervo, resolver_periodo;
                              consultar() é a consulta ÚNICA (nominal, corrigido e COUNT por mês;
                              com so_integrantes as somas ganham FILTER (WHERE v.integra_ipca) e
                              GROUPING SETS ((mês), ()) devolve, na mesma varredura, o total do
                              que ficou de fora no período exibido). Puras: montar_pontos, montar,
                              _nota_fora, _resumo (média, mediana e total dos períodos COMPLETOS,
                              via statistics sobre Decimal) e para_grafico (o único lugar onde
                              Decimal vira float)
  cadastros/       um módulo por entidade (categorias, subcategorias, contas, pessoas, ref_receitas e,
                   desde a rodada 20, resumos anuais — nomes exatos dos arquivos no CLAUDE.md §4;
                   serie_ipca.py: GET /cadastros/ipca?modo= e POST /cadastros/ipca/atualizar — _contexto
                   compartilhado, 502 IBGE/dados, 503 banco, sem HX-Request → redirect),
                   forms.py, servico.py (contagem agregada "N ativas · M inativas", alternar_ativo,
                   erro de UNIQUE pendurado no campo pelo nome da constraint). O resumo anual foge do
                   padrão: <select> de ano só com anos de anos_com_lancamento() sem resumo, edição só do
                   texto, exclusão com confirmação, ?retorno= validado por destino_interno
  lancamentos/     despesas.py (lançar, editar com ?retorno= validado por destino_interno, excluir,
                   classificação reativa, sugestões), consulta.py, receitas.py, servico_receitas.py,
                   forms.py, servico.py (consultas/agregados, id_valido, pagina_pedida)
  configuracoes/   rotas.py, forms.py, servico.py (CATALOGO, valor_vigente) — padrão de edição em linha;
                   a tela chama-se "Parâmetros" desde a rodada 25 (endpoint e URL inalterados).
                   backup.py (rodada 25) a página de backup: CONTAINER (o container_name literal do
                   docker-compose), TEMPO_LIMITE = 120, ErroBackup, _identificacao (usuário e banco do
                   DATABASE_URL por conninfo_to_dict), _comando (lista, shell=False, SEM senha),
                   _ultimas_linhas, nome_do_arquivo(agora) pura e gerar_dump() -> (bytes, nome).
                   Quatro rotas: a tela, o fragmento de confirmação, o de cancelar e o POST que baixa
  orcamento/       __init__.py (prefixo /orcamento), rotas.py (modo/periodo), forms.py,
                   servico.py (montagem: criar mês por cópia do anterior ou por média 12m, linhas,
                   receita, encerrar/reabrir/excluir, predicado de mês criável, cabecalho_do_mes),
                   acompanhamento.py (só leitura: realizado por subcategoria, acumulado por OR de
                   intervalos, faixa de cor ok/alerta/estouro, fora do orçamento).
                   URLs do mês em AAAA-MM; da linha só por id; encerrar/reabrir carregam o modo
templates/
  base.html        <meta name="htmx-config"> liberando swap em 409/502/503 (rodada 23); blocos
                   `atributos_html` (no <html>), `cabeca` (fim do <head>) e `scripts`; favicon
  layout_app.html  sidebar escura com o menu numa estrutura só (`navegacao`, QUATRO grupos desde a
                   rodada 25: Painel — Visão Anual, Visão Mensal, Análise por subcategoria,
                   Análise por prioridade, Orçamento —, Lançamentos, Cadastros — terminando em
                   "Resumos anuais" e "IPCA" — e Configurações — "Parâmetros" e "Backup",
                   fechado por padrão), seções recolhíveis (`freedom.sidebar.<secao>`
                   em localStorage), rodapé com usuário e logout POST; barra superior com os blocos
                   `titulo_pagina`, `subtitulo_pagina`, `acoes_pagina`; `data-valores="ocultos"` e o
                   script dono do estado do olho no bloco `cabeca` (rodada 19)
  main/_analise.html  (rodada 26) o corpo COMUM das duas análises: formulário GET na .filtro-barra
                   (do período para a direita — de/até, agrupamento, caixa do IPCA e botão "Ver"),
                   os três estados vazios, o resumo em .painel-grade--tres, o gráfico de linha e a
                   tabela dos pontos, tudo dentro de um .painel; sem olho. Blocos que cada tela
                   preenche: title, titulo_pagina, filtro_proprio, convite e nota_fixa
  main/analise.html  estende o acima: <select> de subcategoria e o convite
  main/analise_prioridade.html  estende o acima: <select> de faixa, o convite e o aviso fixo
                   (.nota-topo) que explica por que os totais desta tela não batem com os das outras
  _macros.html     icone (_CAMINHOS_ICONE, Lucide inline), campo, campo_selecao, campo_area,
                   badge_ativo, acoes_linha, cabecalho_tabela, vazio, lista_cadastro, filtro_inativos,
                   filtros_cadastro, acoes_formulario, reais, barra_pct, badge_essencialidade,
                   bloco_prioridade, campos_despesa (grade de 12 colunas), campos_receita,
                   combobox (<input list> + datalist — lista ABERTA)
  main/index.html  (marcas sensivel* em todo número; card "Resumo do ano" entre os nove indicadores e os
                   gráficos, rodada 20), main/mensal.html, main/_detalhe_categoria.html
  lancamentos/*    (_total_oob.html: total do mês na barra superior)
  configuracoes/   configuracoes.html (parâmetros) e os parciais da edição em linha;
                   backup.html (rodada 25) com a prosa e o #backup-acao, mais _backup_botao.html e
                   _backup_confirmar.html — o segundo traz o <form method="post"> SEM atributo hx-,
                   que é como se baixa arquivo, e o "Cancelar" por HTMX fora do formulário
  cadastros/       <entidade>_lista.html, <entidade>_form.html, _linha_<entidade>.html, _rotulos.html,
                   serie_ipca.html (card--tabela + .tabela-caixa + .tabela--matriz, caption .so-leitor;
                   botão em acoes_pagina com hx-post, modo e CSRF ocultos, hx-disabled-elt, dois rótulos),
                   _cartao_ipca.html (#ipca-cartao: faixa, dica, tabela ou m.vazio — o que o botão troca),
                   _subtitulo_ipca.html (hx-swap-oob, sempre no DOM, hidden sem série),
                   _resposta_ipca.html (cartão no alvo + subtítulo fora de banda)
  orcamento/       orcamento.html, _cabecalho.html (estado do mês, nos dois modos), _corpo.html
                   (montagem), _acompanhamento.html, _linha.html, _linha_edicao.html, _receita.html,
                   _receita_edicao.html, _nova_linha.html, _aviso.html
static/
  css/app.css      seção 1 tokens do design system (paleta --grafico-*, --esqueleto) e 1(b) apelidos do
                   tema antigo; 4 layout (sidebar escura, barra superior); 5.2 botões (.btn--icone,
                   rodada 19) e .segmentado (era .anos da Anual; generalizado na 22); componente .barra (após 5.4); 5.9 lançamento, 5.10 consulta,
                   5.11 autocomplete, 5.12 configurações, 5.13 "Painéis: o que a Anual e a Mensal
                   compartilham" (5.13.1 gráficos, 5.13.2 tabelas dos painéis, 5.13.3 Visão Anual
                   refeita), 5.14 Mensal (5.14.1 .tabela--detalhe), 5.15 Orçamento (5.15.1
                   acompanhamento), 5.16 ocultar valores (rodada 19), 5.17 IPCA (só os rótulos do
                   botão: a nota do ano incompleto virou .nota-rodape na 5.1 na rodada 24 e a dica
                   virou .nota-topo na 5.1 na 26), 5.18 as duas análises (.filtro-campo--caixa,
                   .analise-caixa, .analise-parcial), 5.19 backup (.backup-comando, .backup-nota e
                   a .backup-envio, que só tem regra na seção 7), 7 responsivo, 8 utilitários
                   (.negativo global desde a 16). Em 5.1 moram as duas notas irmãs, .nota-rodape
                   (fecha o cartão; desde a 26 pode embrulhar duas) e .nota-topo (abre o conteúdo);
                   em 5.13, .painel-grade--tres, a grade de cards com três colunas do resumo das
                   análises. Seção 5.7 (modal) removida; lacuna intencional
  js/htmx.min.js, js/chart.umd.js, js/graficos.js (o comum às telas com gráfico, rodada 24),
                   js/visao_anual.js, js/analise.js (serve às DUAS análises sem ramificar por
                   página — os ids do gráfico estão no template comum). Os scripts de layout —
                   sidebar, menu do celular, olho — são inline em layout_app.html
  favicon.svg      teal; única cópia do hex da cor primária fora do CSS (SVG estático não lê variáveis)
db/init/01_schema.sql
docs/            Freedom - Estrutura do Banco de Dados.md, Freedom - Histórico e Estado do Projeto.md
design_handoff_freedom_visao_anual/, design_handoff_freedom_lancamentos_cadastros/
                 referência visual; os README erram sobre a stack e os support.js não são da aplicação
CLAUDE.md        instruções permanentes do agente (onde divergir de um handoff, vale o CLAUDE.md)
run.py, requirements.txt, requirements-dev.txt (Playwright), .gitignore,
README.md ("Comandos flask" — criar usuário, carregar IPCA e quando rodar; "Dependências de
                 front-end", com a licença do Lucide). **README.md está no .gitignore de propósito**
                 (decisão do dono): o que se escreve nele não é versionado
.env, .flaskenv
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
- Rota só de fragmento: sem `HX-Request` → redirect para a página-mãe com os mesmos parâmetros, **antes** de qualquer 404. Resposta de erro **exibível**: **409** regra de estado recusada, **502** falha do IBGE, **503** falha do banco, sempre com faixa. **O HTMX 2 não troca 4xx/5xx por padrão** — o `<meta name="htmx-config">` do `base.html` libera só esses três (rodada 23); 400, 404, 500 e o resto seguem sem troca e disparam `htmx:responseError`, que a linha expansível da Mensal usa para restaurar o estado. Um 500 não tratado traz a página de erro do Flask e nunca pode cair dentro de um cartão.
- Agregados vêm de consulta própria, nunca de soma em Python sobre a página. Exceção prevista: composição em Python (`Decimal`) sobre conjuntos **pequenos e completos** que o SQL já agregou — hoje são dois usos, o `total_exibido` das 15 recentes e a média/mediana/total do resumo das análises. Dois lugares que mostram o mesmo total leem da mesma origem.
- **HTMX troca DOM, não dispara download**: resposta com `Content-Disposition` chegando por `hx-post` é engolida pelo swap. Arquivo se baixa com `<form method="post">` comum, sem nenhum `hx-`, e aí o CSRF vai em `<input type="hidden">` (o `hx-headers` do `<body>` não alcança um POST que o navegador faz sozinho). Único caso: "Confirmar e baixar" do backup (rodada 25).
- **O vão entre blocos de uma tela é o `.painel`** (seção 4 do CSS), não `margin-top` em cada bloco. As duas análises passaram a usá-lo na rodada 26; até ali o gráfico e a tabela se tocavam (628/628) e ninguém tinha reparado.
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
- **Controle segmentado é grupo de links** `.segmentado` com `aria-current="page"` (seletor de ano da Anual, modo da tela do IPCA): GET com recarga inteira, sem JS, e o estado visual é o mesmo atributo que o anunciado.
- **Comando com fonte externa** (rodada 21): três funções separadas — I/O de rede, interpretação **pura** (testável com arquivo adulterado, sem rede e sem banco) e gravação em **uma transação** (erro no meio desfaz tudo). Valor numérico nasce `Decimal(texto)`, nunca `float`; `converter_numero` é para entrada do usuário com vírgula, não para API com ponto. Contagens de inserido/atualizado saem do banco (`RETURNING (xmax = 0)`), não do Python. Mensagens do CLI em português acentuado; erro é `click.ClickException` (prefixo "Error:" é do Click).
- **Ícones**: macro `icone(nome)` com os caminhos em `_CAMINHOS_ICONE` (Lucide copiado do oficial, `currentColor`, `aria-hidden`); `notebook-pen` entrou na rodada 20, `percent` na 22, `refresh-cw` na 23, `chart-line` na 24, `database` na 25 e `chart-column` na 26 (26 caminhos). Todo botão primário tem ícone. Botão só de ícone leva nome acessível (`.so-leitor` ou `aria-label`) e `title`.
- **Barra superior**: cada tela preenche `titulo_pagina`, `subtitulo_pagina` e `acoes_pagina`. Sticky no desktop, estática no celular, onde os botões da barra dividem a linha por `flex` (um botão sozinho ocupa 100%).
- **Ocultar valores (Visão Anual, rodada 19)**: o servidor manda `data-valores="ocultos"` no `<html>`; o script em `cabeca` do `layout_app.html` é o dono único do estado, guardado por aba (`sessionStorage`, chaves `freedom.valores…`). Navegação é `pagehide` antes de `hidden`; saída de aba é `hidden` sozinho; um prazo de 300 ms separa fechar a aba de navegar. Marcas: `sensivel` (valor em linha), `sensivel-bloco` (célula ou bloco inteiro — use quando um `<span>` mudaria o subpixel do texto), `sensivel-barra` (preenchimento), `sensivel-area` (gráfico, com `visibility: hidden` para o Chart.js não perder a medida). Os dois ícones vão no botão e o CSS escolhe; `aria-pressed` sai `false` do servidor e é corrigido no `DOMContentLoaded` (exceção conhecida à regra de estado único).
- **Linha de apoio no celular**: coluna principal larga → texto dentro da célula; coluna principal estreita → `<tr class="linha-apoio">` com `colspan`. Ação vira ícone com `aria-label` descritivo.
- Responsivo: < 768px sidebar vira barra; grades de cards 1/2/4 colunas (768/1100); gráficos 1/2. **Exceções deliberadas de rolagem interna** (`.tabela-caixa`): matriz pessoa × categoria (primeira coluna `sticky` com `max-width` de 130px no celular — não é teto de altura; a matriz do IPCA rola só na horizontal) e todas as tabelas do orçamento (tela desktop-first). `.so-leitor` absoluto dentro de contêiner que rola precisa de ancestral `position: relative`.
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
| 20 | **Resumo anual**: `tb_resumos_anuais` (ano PK com CHECK 2000–2100, texto com caractere visível, trigger de `atualizado_em`; DDL idempotente); página "Resumos anuais" em Cadastros (criar por `<select>` de anos sem resumo, editar só o texto, excluir com confirmação, `?retorno=`); card "Resumo do ano" na Anual sujeito ao olho; ícone `notebook-pen`. Revisão não registrada no orquestrador — o que está aqui vem do prompt e do schema | ✅ |
| 21 | **Carga do IPCA**: `freedom/ipca.py` (buscar / interpretar pura / gravar em transação única) e `flask carregar-ipca`; 393 meses gravados (dez/1993 a ago/2026) sem perda de precisão; idempotência, correção de linha adulterada e atomicidade provadas; falha de rede com código de saída 1; README ganhou "Comandos flask"; sem mudança de schema e sem dependência nova | ✅ |
| 22 | **Tela do IPCA**: matriz ano × 12 meses com alternância Variação \| Índice (`.segmentado`), "No ano" conferido contra a variável 69 do IBGE (0,00 pp), nota de ano incompleto, rolagem horizontal com ano fixo no celular; ícone `percent`. Limpezas: `nome_do_periodo` e `MESES_CURTOS` em `util.py` (quatro cópias removidas, não duas), `dobrar` promovida (a dívida de `unicodedata` estava em `_dobrar`, não em `_rotulo`), comandos antigos acentuados, aviso de variação nula. Dez capturas com SHA idêntico | ✅ |
| 23 | **Botão "Atualizar do IBGE"**: `ipca.carregar` compartilhada por comando e botão, POST HTMX com cartão inteiro + subtítulo fora de banda, faixa de resultado com três formas de erro (502/502/503), dica de mês provável (corte no dia 12), `<meta htmx-config>` para 409/502/503 — que revelou e corrigiu o **409 do orçamento nunca exibido desde a 15**. Cenário de outubro provado num banco descartável com a série menos agosto: o clique buscou agosto no IBGE em 0,77 s e a tela mudou sem recarregar. Limpeza: `nome_do_mes` em `util.py` (três cópias) | ✅ |
| 24 | **Análise por subcategoria**: `/analise/subcategoria` com subcategoria × período × agrupamento (mensal, trimestral, anual, 12 meses móveis) × correção pelo IPCA; uma consulta por requisição, composição pura, zero é zero, "No ano" dos buckets parciais marcado. Números do DOM iguais ao SQL independente e à Visão Mensal (zero divergências). `static/js/graficos.js` extraído do `visao_anual.js` (cor por variável CSS, moeda, eixo, opções, linha) e o rótulo do eixo corrigido para olhar o **passo** entre marcações — escrevia "R$ 2 mil" duas vezes com valores de mil. Limpezas: `somar_meses` e `intervalo_de_meses` para `util.py`, `.ipca-nota` → `.nota-rodape`. Doze capturas com SHA idêntico | ✅ |
| 25 | **Página de Backup** (`/configuracoes/backup`): dump do banco inteiro por `docker exec pg_dump --no-owner --no-privileges`, bufferizado (`capture_output`, `timeout=120`) e entregue como anexo `freedom_AAAAMMDD-HHMM.sql`; confirmação em dois passos por HTMX, mas o "Confirmar e baixar" é `<form method="post">` **sem `hx-`** — HTMX não dispara download. Sem senha (socket local, `trust` na imagem oficial) e sem credencial na linha de comando. Sem restauração, sem histórico, sem agendamento. **Configurações virou o quarto grupo da sidebar** ("Parâmetros" + "Backup", ícone `database`, fechado por padrão). Validado de verdade: 448.379 bytes em 0,17 s, `COPY public.tb_despesas` com **3.535 linhas contra 3.535 no `count(*)`**; caminho de erro provocado com container inexistente (nenhum download, faixa `flash--erro` na tela) e os outros três ramos exercitados por função pura. CSS novo: seção 5.19 | ✅ |
| 26 | **Análise por prioridade** (`/analise/prioridade`): faixa (Essencial ou P1–P4) em vez de subcategoria, **o primeiro e único uso de `integra_ipca`**, aviso fixo e nota do que ficou de fora — tudo na mesma consulta, por `GROUPING SETS ((mês), ())`. Sem duplicação: o corpo saiu para `main/_analise.html` e `servico_analise.py` virou o serviço das duas, com `Recorte` e `painel()`; `analise.js` serve às duas sem ramificar. `.ipca-dica` promovida a `.nota-topo`. DOM contra psql escrito à mão: **0 divergências** em duas faixas e dois agrupamentos; correção conferida em **36 lançamentos** de três meses (um deles posterior à base, fator 1); a flag provada desmarcando e remarcando uma despesa real (queda exata de R$ 299,90 e de 1 lançamento); despesa não essencial sem prioridade e despesa essencial com prioridade criadas, conferidas e apagadas. As dez capturas da subcategoria e do IPCA com **SHA idêntico** — por captura de ELEMENTO, porque o item novo no menu muda o SHA de página inteira de toda tela | ✅ |
| 26+ | **Resumo das análises**, a pedido do dono depois da entrega: média, mediana e total em três cards `kpi` antes do gráfico, nas duas telas, só dos períodos **completos** (parcial fica de fora; com menos de dois completos o card não aparece) e da coluna em destaque (real com IPCA ligado, nominal sem). Sem consulta nova — sai dos pontos já compostos. Oito combinações refeitas a partir da tabela da própria página: 0 divergências. As duas análises ganharam o `.painel`, que revelou e corrigiu cartões que se tocavam desde a 24 | ✅ |

## 8. Roteiro (ordem sugerida)

1. ~~**Despesas mensais somadas com `integra_ipca`**~~ — **feito de outra forma na rodada 26**: a flag ganhou o uso que faltava na Análise por prioridade, que soma só as marcadas e avisa na tela quanto ficou de fora. Se um dia o dono quiser a tela como fora imaginada (despesas mensais somadas, sem recorte de faixa), o mecanismo está pronto e é um `Recorte` a mais.
2. **Refatoração visual pendente**: Visão Mensal, Orçamento, configurações e login; remover os apelidos da seção 1(b) e `card--solido` quando nada mais os usar; abrir sozinho o grupo da sidebar que contém o item ativo (hoje um grupo recolhido esconde o item aceso). Citar sempre pelo nome: o número já mudou duas vezes.
3. **Metas de independência** (página própria): TSR, S e R vigentes, número de independência, taxa de poupança realizada × meta.
4. **Patrimônio**: ativos e snapshots.
5. **Deploy**: serviço `app` no `docker-compose` com gunicorn (`--timeout` compatível com o botão do IPCA) e `TZ=America/Sao_Paulo` (a dica de mês provável usa a data local); Tailscale; segundo usuário; decidir se o Agendador de Tarefas do Windows roda `carregar-ipca` nos dias 12 e 15 como rede de segurança. Com o celular na rede, conferir o olho no aparelho (ver seção 9).

Backlog consciente: exportação CSV/Excel, duplicar lançamento, edição em lote, intervalo livre de datas, ordenação por cabeçalho, sugestão que preencha valor, autocomplete em receitas, comparação entre anos/meses, links dos cards para a consulta, detalhe por categoria na Anual (subcategoria × mês), detalhe por pessoa, setas entre meses, exportação de gráfico, animação dos gráficos, orçamento por pessoa, cópia de orçamento entre anos, histórico de alterações do orçamento, integração dos painéis com o orçamento, decidir se o `letter-spacing` herdado no detalhe é desejado, edição em linha nos cadastros e na despesa, busca nos cadastros, paginação dos recentes (os três recusados como mudança funcional na rodada 18), acumulado em 12 meses na tela do IPCA, ticket médio deflacionado na análise por subcategoria, deflação na Visão Anual (série real do ano).

## 9. Pendências e lembretes

- **Estado dos commits em 20/09/2026**: `0.15` e `0.16` cobriram as rodadas 22 a 24 e ajustes do lançamento; `0.17` cobriu exatamente a rodada 25 (backup). A **rodada 26 e o resumo das análises não estão commitados** — dois arquivos novos (`templates/main/_analise.html`, `templates/main/analise_prioridade.html`) e sete alterados. Commitar antes da rodada seguinte.
- O repositório anexado ao projeto do orquestrador só reflete o último sync: sincronizar depois de cada commit, senão revisão e prompt olham código velho (em 12/09 o orquestrador não tinha o código das rodadas 16 a 21).
- **`docs/Freedom - Estrutura do Banco de Dados.md`** foi posto em dia em 13/09/2026 (depois da rodada 24) e recebeu em 20/09/2026 as duas únicas correções que a rodada 26 exigiu: a descrição de `integra_ipca` (que dizia "nada lê esta coluna") e a linha "Despesa deflacionada" dos padrões de acesso, que agora nomeia as duas análises. O resto daquele arquivo continua valendo: o roteiro saiu dele (fica só aqui, seções 7 e 8), `tb_ipca` diz quem a alimenta e quem a lê, o cruzamento com o IPCA é pelo **mês da data** (nunca pelo `ano_mes`) e os padrões de acesso trazem o upsert, a deflação por lançamento e a consulta da análise. **O DDL não muda desde a rodada 20** — as rodadas 25 e 26 não tocaram em tabela, coluna, view, índice nem trigger.
- As revisões das entregas das rodadas 18 e 20 não ficaram registradas no orquestrador; o que está aqui sobre elas vem dos prompts, do código e do schema.
- ~~Conferir a mensagem de erro do comando depois da refatoração de `ErroIpca`~~ — feito na rodada 24: com a URL inválida a saída continua `Não foi possível falar com a API do SIDRA: [Errno 11001] getaddrinfo failed. Confira a conexão e tente de novo.`, legível e em português. Nenhum ajuste foi preciso.
- Grupo recolhido da sidebar esconde o item aceso (comportamento desde a 18); vai para a refatoração visual pendente.
- Ritual mensal: depois do dia 10, `python -m flask --app freedom carregar-ipca` (ou, a partir da 23, o botão da tela) e conferir o último mês com o site do IBGE. Se o IBGE revisar um mês passado, a recarga corrige sozinha (é upsert). Nenhum dos dois caminhos precisa do agente.
- **Olho, a conferir no celular real** (quando houver acesso pela rede): se a miniatura do trocador de apps é capturada antes do `hidden`; alvo de toque de 30px, abaixo dos 44px recomendados; bfcache do Safari/iOS. Risco residual medido: aba reaberta em menos de 300 ms do fechamento volta à mostra. O logout limpa o estado interceptando o formulário de sair — redundante com o prazo, mantido.
- Apelidos do tema antigo (seção 1(b) do CSS) e `card--solido` vazio continuam até a refatoração visual pendente.
- Usuários: `tiago`, `zz_consulta` (desativado), `zz_teste` — senha em `senha_teste`. **Todo prompt nomeia a variável.** Validação que edita dado real carimba `atualizado_em`; se isso incomodar, o agente cria e apaga a própria despesa de teste.
- `favicon.svg` repete o hex da cor primária (`#30B0C7`); se a paleta mudar, são dois lugares.
- `tb_configuracoes` tem TSR, S e R; nada os lê até a página de metas. Configuração recusa negativo; `R` negativo exigiria uma linha em `converter_numero`.
- `<details>` no desktop usa `::details-content` (Chromium 131+ / Firefox 139+).
- Autocomplete: `changed` não reabre ao redigitar o mesmo trecho; JS ~75 linhas.
- Ano futuro no seletor só com lançamento futuro; média e "meses no azul" mostram "—"; tabela mensal mostra o que houver lançado e "—" em acumulado e taxa.
- `SECRET_KEY` no `.env`, documentada no README. **Python 3.14 roda** — o aviso antigo de recriar o venv com 3.12 era de quando faltava wheel para alguma dependência e não vale mais; num clone novo, conferir antes de trocar de versão.
- Antes de citar arquivo, macro ou variável num prompt, conferir que existe onde o documento diz.
- **Backup**: o dump sai só por clique e o arquivo passa a ser responsabilidade do dono — o sistema não sabe se ele ainda existe. Se o `pg_dump` um dia pedir senha (hoje não pede: socket local, `trust`), o jeito é `-e PGPASSWORD=` no `docker exec`, e isso põe o valor na linha de comando do processo do host; está escrito na docstring de `_comando` e **precisa ser relatado** se for usado.
- **Só a Análise por prioridade lê `integra_ipca`**. A Análise por subcategoria continua somando tudo, e isso é decisão, não esquecimento: qualquer "correção por coerência" está errada. Tela nova que use a flag herda a obrigação do aviso na tela.
- O resumo das análises descarta períodos parciais; com agrupamento anual em janela de 12 meses ele simplesmente não aparece. Se incomodar, a alternativa discutida foi somar tudo e avisar quantos são parciais.

## 10. Lições aprendidas (para não repetir)

**Gráficos e JavaScript** (rodadas 9–11, 17, 24)
- Chart.js só na tela que desenha, pelo `{% block scripts %}`; contêiner com **altura fixa** e `maintainAspectRatio: false`, senão o canvas cresce a cada redimensionamento. Cores por `getComputedStyle` de variável CSS — nenhum hexadecimal no JS.
- O que a segunda tela com gráfico repetiria sai para um arquivo comum (`graficos.js`, rodada 24) antes de ser copiado, como helper de Python sai para `util.py`. O SHA da tela antiga prova que a extração não mexeu em pixel.
- **Rótulo de eixo arredondado tem de olhar o passo entre marcações, não o maior valor**: com marcações de 500 em 500, arredondar para milhar escreve "R$ 2 mil" duas vezes seguidas. Achado na Análise por subcategoria, corrigido no helper comum, sem efeito na Anual (marcações de 50 mil).
- **Suavização é decisão por tela, não padrão**: `tension: 0.4` ajuda em série contínua e mente em série com zeros — a curva passa por baixo do zero entre dois pontos. Onde o zero é resposta legítima, reta entre pontos.
- Valor chega ao JS **já arredondado a centavos**; `float` só na serialização final, num ponto único e nomeado.

**Ambiente e Postgres**
- pgAdmin recente rejeita e-mail `.local`. `teardown_appcontext` não é lugar para fechar pool. psycopg conta `%s` em comentário. `ESCAPE '\'` precisa de raw string.
- Filtrar por coluna derivada de view mata o índice; intervalo pela coluna base resolve — e o EXPLAIN na validação prova.
- `sorted()` puro ordena por ponto de código ("Água" depois de "Zoo"); chave NFD resolve sem `locale`. `en_US.utf8` no banco dá a mesma ordem.
- Mudança de schema em tabela vazia é troca de coluna com blocos idempotentes, nunca `DROP TABLE`; validar no banco com dados, re-executar, e num banco descartável do zero.
- Upsert: `ON CONFLICT ... DO UPDATE ... WHERE (...) IS DISTINCT FROM (...)` não reescreve linha igual e não a devolve no `RETURNING`; `RETURNING (xmax = 0)` separa inserido de atualizado. Contar no banco, não em Python: o banco compara depois de arredondar para o tipo da coluna. Identidade consumida em toda tentativa — o `id` pula e não importa.
- SIDRA (tabela 1737): a API devolve 13 casas no número-índice sem pedir `d/`; `d/` serve para reduzir, não ampliar. Os índices desde dez/1993 têm no máximo duas casas significativas; antes disso, moedas antigas e índice minúsculo — descartar pelo código do período antes de converter. Dez/1993 = 100 é a verificação de sanidade da série.
- Percentual tem duas unidades no banco: `tb_ipca.variacao_mensal` em pontos percentuais (como publicado) e `tb_configuracoes.valor` em fração. Documentar a diferença onde as duas se encontram; nunca "corrigir" o dado do IBGE.
- **`GROUPING SETS ((expr), ())` responde duas perguntas numa varredura só**: as linhas por mês mais uma linha de total com a chave nula. Foi o que permitiu à Análise por prioridade trazer o "ficou de fora" sem uma segunda consulta. Dois detalhes: o conjunto `()` devolve linha **mesmo sem nenhuma linha de entrada** (então "não há lançamento" não se testa pelo resultado estar vazio), e ordinal dentro de `GROUPING SETS` é arriscado — escreva a expressão.
- **`FILTER (WHERE ...)` na SOMA, e não no `WHERE`**, quando você precisa das linhas excluídas na mesma varredura. Com o filtro no `WHERE` elas somem e o "quanto ficou de fora" exigiria outra consulta. `SUM(...) FILTER` devolve NULL quando nada casa: `COALESCE(..., 0)`.
- `pg_dump` 16.15 (correção do CVE-2025-8714) embrulha o dump em `\restrict` / `\unrestrict`: o `-- PostgreSQL database dump complete` continua lá, mas **não é mais a última linha** do arquivo. Critério de aceite que exija isso literalmente falha por um motivo que não é defeito.
- Um `%` literal dentro de SQL que o psycopg vai parametrizar quebra o parser (`only '%s', '%b', '%t' are allowed`). `LIKE 'zz teste%'` vira `LIKE %s` com o parâmetro.

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
- **HTMX não baixa arquivo.** Resposta com `Content-Disposition` chegando por `hx-post` é engolida pelo swap e o download nunca começa; quem baixa é `<form method="post">` sem nenhum `hx-`, com o CSRF em campo escondido. E como a tela não muda quando o POST responde com anexo, ela precisa dizer isso em letra pequena — senão parece que nada aconteceu.
- **Herança de template é o que impede a segunda cópia de uma tela.** A Análise por prioridade não copiou nada: `main/_analise.html` virou o corpo e as duas telas preenchem quatro blocos. O mesmo vale para o serviço — o que separava as duas era o recorte, e ele virou um parâmetro (`Recorte`), não um segundo módulo.
- `url_for(request.endpoint)` na `action` de um formulário que submete para si mesmo evita um bloco por tela, e funciona igual nas duas.

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
- `git diff` não alcança arquivo novo (untracked) nem arquivo no `.gitignore`: restauração de uma edição temporária nesses arquivos se prova por SHA-256 antes e depois.
- Fonte externa se valida com a resposta salva em arquivo fora do repositório e cópias adulteradas, uma por regra de recusa, contra a função pura — sem rede, sem banco, e o arquivo é apagado no fim. A primeira carga real fica no banco e não é "dado de teste".
- Roteiro em um documento só (este). O `.md` do banco descreve o schema; quando ele ganhou um roteiro próprio, desatualizou em duas rodadas.
- Quando prompt e Histórico saem na mesma mensagem, a regra fica escrita **uma vez** e o outro aponta: "No ano" ficou "calculada na consulta" aqui e "na função pura" no prompt, e custou um ponto de interpretação. E o prompt afirmou um "teto de 130px" que era `max-width`: conferir o CSS antes de citar, como já valia para arquivos e macros.
- Dívida apontada por sintoma (imports suspeitos) estava em outra função: "confira e explique" rendeu mais do que "conserte X" teria rendido.
- Instrumento de captura com o olho: **fixar** o estado (`dataset.valores`) em vez de alternar por clique — o `sessionStorage` devolve a aba já aberta na segunda passada e o clique cego a fecha.
- **Status certo no test client não é faixa na tela**: o 409 do orçamento existiu oito rodadas sem nunca aparecer, porque o HTMX 2 descarta 4xx/5xx em silêncio. Erro que deve ser visto se valida no navegador, e a política de swap é declarada uma vez (`htmx-config`), nunca por script.
- Premissa errada no prompt ("reutilize o mecanismo que exibe o 409") custa uma rodada se o agente obedecer; custou uma pergunta porque ele mediu antes. "Pergunte antes de decidir" vale também contra o orquestrador.
- No Windows, o prompt oculto do Click lê do console (`msvcrt`), não do stdin: `echo senha | flask create-user` trava; injeta-se a entrada com `CliRunner`. E um launcher de segundo servidor não pode fazer `os.chdir`: o recarregador do Werkzeug reexecuta pelo caminho relativo.
- Deflação não precisa de série contínua — é uma conta por mês. O que a descontinuidade quebra é a leitura, e isso se resolve com granularidade escolhida pelo usuário, não com classificação dos dados.
- **Captura de página inteira não serve quando a rodada mexe na sidebar**: um item novo no menu muda o SHA de toda tela do sistema sem que o conteúdo tenha se mexido. Capture a coluna de conteúdo por elemento (`main.conteudo`). E quando a referência "antes" exigir o código anterior, `git stash push -u` / `git stash pop` resolve — conferindo os SHA-256 no fim **com o fim de linha normalizado**, porque o checkout converte LF em CRLF e todo arquivo parece ter mudado.
- **"Idêntico" pode ser um padrão, e não um valor único**: na rodada 26 o esperado era SHA igual em cinco estados (os que não ganharam conteúdo), altura crescida em exatamente 152 px em quatro, e números de tabela iguais em todos. Enunciar o padrão antes de medir é o que transforma a captura em prova.
- **Média e mediana juntas dizem mais que qualquer uma sozinha**: quando coincidem, o gasto é regular; quando se afastam, não existe "um mês típico". E média sobre período parcial mente em silêncio — nos 12 meses de "Essencial", setembro pela metade tirava R$ 300 da média, sem nada na tela explicando.
- **Erro do agente no instrumento não é erro na entrega, mas precisa ser dito**: nas rodadas 25 e 26 o número estava certo na tela e quem estava errada era a asserção do script de validação (uma regex gulosa, um `LIKE` com `%`). Conferir a falha antes de mexer no código.
- Pergunta de viabilidade ("dá para pôr um card de resumo?") rende mais respondida com as **decisões que mudam o número** do que com um "dá": parciais dentro ou fora, nominal ou real, uma tela ou as duas. As três foram decididas pelo dono em uma mensagem.
