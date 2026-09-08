# Freedom — Histórico e Estado do Projeto

Documento de contexto para o projeto orquestrador. Resume o que foi decidido, o que existe e o que falta. Consolidado após a rodada 8 (07/09/2026).

## 1. O que é o Freedom

Sistema web pessoal de controle financeiro. Roda localmente em Windows via Docker; no futuro, outros membros da casa acessam pela rede Tailscale (nada exposto na nuvem). Um usuário master hoje; a esposa entra depois. Interface em português do Brasil.

Objetivo de longo prazo: além de registrar despesas e receitas, medir crescimento real das despesas (deflação por IPCA), orçamento mensal por categoria, evolução do patrimônio e metas de independência financeira (TSR, retorno real, taxa de poupança).

## 2. Modelo de trabalho

Três papéis:

- **Tiago** (dono do projeto): decide, cadastra dados pela interface, executa comandos, cola aqui as saídas do agente.
- **Orquestrador** (este projeto no Claude web): escreve os prompts de cada rodada, revisa as entregas do agente, responde às dúvidas técnicas que ele levanta, mantém a documentação alinhada.
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
- **Receitas são tela única** (rodada 7): formulário no topo, filtros e lista abaixo, na mesma página. O volume é baixo e ver o que entrou tem valor imediato; separar seria cerimônia. A assimetria com despesas é intencional.

## 4. Banco de dados

Fonte da verdade: `docs/Freedom - Estrutura do Banco de Dados.md` (está na base de conhecimento) e `db/init/01_schema.sql`. Regra: se um muda, o outro muda. **O DDL mudou uma única vez desde a rodada 1**: a view `vw_receitas`, na rodada 7. As rodadas 4 a 6 e a 8 não tocaram no schema.

Resumo do que importa para escrever prompts:

- PostgreSQL 16 em Docker (`docker-compose.yml`, serviço `postgres`, container `freedom_postgres`), pgAdmin em `localhost:5050`. Credenciais e `DATABASE_URL` no `.env`.
- 13 tabelas: `tb_categorias`, `tb_subcategorias`, `tb_ref_receitas`, `tb_pessoas`, `tb_usuarios`, `tb_contas`, `tb_ipca`, `tb_configuracoes`, `tb_despesas`, `tb_receitas`, `tb_orcamentos`, `tb_ativos`, `tb_patrimonio_snapshots`. Duas views: `vw_despesas` e `vw_receitas`.
- `vw_despesas`: despesa + subcategoria + categoria + **essencialidade efetiva** (`COALESCE(despesa, subcategoria)`) + `ano_mes` inteiro `AAAAMM`.
- `vw_receitas`: receita + categoria + subcategoria da fonte + `ref_receita_ativo` + `ano_mes`. Leitura sempre pelas views; escrita nas tabelas base.
- **`ano_mes` serve para exibir e agrupar, não para filtrar**: o filtro mensal usa `data >= início AND data < início do mês seguinte`, o que faz `ix_despesas_data` / `ix_receitas_data` serem usados. Índice de expressão sobre o mês foi avaliado e dispensado.
- Nada derivado é armazenado. Toda FK é `NOT NULL` e `ON DELETE RESTRICT`. Referência não é apagada: tem `ativo` (em `tb_contas`, `ativa`).
- CHECKs: essencialidade em `Essencial` / `Não Essencial` (subcategoria e despesa); `tb_contas.tipo` em `corrente, cartao, dinheiro, outro`; `prioridade` 1–4; `valor > 0` em despesas e receitas; dia 1 em `tb_ipca.mes` e `tb_orcamentos.ano_mes`; `>= 0` em orçamento e patrimônio. `tb_ativos.classe` e `tb_configuracoes.chave` sem CHECK, de propósito (listas abertas).
- `tb_configuracoes` tem `vigente_desde`; o valor vigente numa data é o registro com maior `vigente_desde ≤ data`, e todas as chaves de uma vez saem com `DISTINCT ON (chave)`.
- Trigger `fn_set_atualizado_em()` em despesas e receitas; `atualizado_em` fica NULL até o primeiro UPDATE.
- **Regras da aplicação, não do banco**: prioridade só quando a essencialidade efetiva é "Não Essencial" (grava NULL quando essencial); autoria nunca muda na edição; referência inativa continua visível na edição e nos filtros, marcada como tal, mas nunca é gravada em lançamento novo; receita pré-seleciona a pessoa do usuário logado; configuração não aceita negativo e tem limite de casas decimais; catálogo de chaves de configuração vive num dicionário Python, não no banco.

Estado dos dados: **725 despesas reais**, 1 receita real, 24 categorias, 82 subcategorias, 3 contas, 5 pessoas, 8 fontes de receita, `tb_configuracoes` vazia (os valores reais de TSR, R e S ainda serão cadastrados). Usuário `tiago` ativo, `zz_consulta` desativado, `zz_teste` criado na rodada 8 para o agente validar em navegador. **Há dado real em produção: nenhuma rodada pode apagar linha que não tenha criado, e a faxina de teste é sempre por id.**

## 5. Stack da aplicação (fechada, não reabrir)

| Camada | Escolha |
|---|---|
| Web | Flask 3, application factory (`create_app` em `freedom/__init__.py`), Blueprints |
| Banco | psycopg 3 + `psycopg_pool`, SQL direto parametrizado, `row_factory=dict_row`. **Sem ORM, sem migrações** |
| Auth | Flask-Login; hash com `werkzeug.security` (scrypt) |
| Formulários | Flask-WTF (CSRF em todo POST) |
| Interatividade | HTMX 2.0.4, arquivo local em `static/js/`, mais JS próprio pontual (menu, limpar filtros, autocomplete) |
| Gráficos (futuro) | Chart.js, arquivo local em `static/` |
| CSS | Escrito à mão, variáveis CSS, Glassmorphism tema claro. Sem Tailwind, sem bibliotecas de ícones |
| Ambiente | Windows, PowerShell, venv em `venv/`, Python 3.14 |

## 6. Estrutura atual do código

```
freedom/
  __init__.py      create_app: CSRF, pool, Flask-Login, blueprints, CLI, filtro Jinja `moeda`
                   (agora vindo de util.py)
  config.py        lê .env; template_folder/static_folder apontam para a raiz
  db.py            ConnectionPool, dict_row, get_connection(), executar()
  util.py          destino_interno(); parser e formatação de número: ValorInvalido, converter_valor,
                   converter_numero(percentual=), formatar_valor, formatar_numero, escapar_like
  cli.py           flask create-user, flask set-password
  auth/            forms.py, models.py, routes.py (/login, /logout)
  main/            routes.py (/ "Início" — lugar reservado ao dashboard)
  cadastros/       um módulo por entidade + servico.py (alternar_ativo, UniqueViolation → mensagem)
  lancamentos/     __init__.py (blueprint, prefixo /lancamentos)
                   despesas.py  lançar, editar, excluir, classificação reativa, sugestões
                   consulta.py  consulta de despesas (mesma rota serve página e fragmento)
                   receitas.py  página única de receitas: rotas, filtros, escritas
                   servico_receitas.py  leituras sobre vw_receitas
                   forms.py     inclui ReceitaForm
                   servico.py   consultas e agregados de despesa, sugestões; helpers compartilhados
                                id_valido, pagina_pedida, so_fragmento (promovidos na rodada 8)
  configuracoes/   __init__.py (blueprint, prefixo /configuracoes)
                   rotas.py, forms.py
                   servico.py   CATALOGO de chaves, valor_vigente(), valores vigentes de todas
templates/
  base.html, layout_app.html (3 grupos de menu: Painel, Lançamentos, Cadastros;
                              "Configurações" no fim de Cadastros)
  _macros.html     campo, campo_area, badge, ações, `reais`, `badge_essencialidade`,
                   `campos_despesa` (com url_sugestoes), `campos_receita`, `combobox`
                   (escrita na rodada 8: <input list> + <datalist>)
  auth/, main/, cadastros/
  lancamentos/     despesas.html, despesa_editar.html, consulta.html, receitas.html,
                   receita_editar.html, _linha_despesa.html, _linha_consulta.html,
                   _linha_receita.html, _resultados.html, _receitas_resultados.html,
                   _formulario_oob.html, _receita_formulario.html, _gravado.html,
                   _receita_gravada.html, _receita_erro.html, _total_oob.html,
                   _classificacao.html, _classificacao_macro.html, _sugestoes.html
  configuracoes/   configuracoes.html, _formulario.html, _formato.html, _lista.html,
                   _linha.html, _linha_edicao.html, _gravada.html, _erro.html
static/
  css/app.css      seções 1–8 + 5.9 (lançamento), 5.10 (consulta), 5.11 (autocomplete),
                   5.12 (configurações)
  js/htmx.min.js
db/init/01_schema.sql
docs/
run.py, requirements.txt, .gitignore, README.md, .env, .flaskenv
```

Padrões já estabelecidos no código (o agente deve mantê-los):

- Subir: `python -m flask --app freedom --debug run --port 5000` ou `flask run` com `.flaskenv`.
- Cadastros: lista + criar + editar + ativar/desativar (HTMX troca só a `<tr>`); filtro "mostrar inativos"; sem excluir.
- Lançamento em série: grava por HTMX sem recarregar, limpa os campos que mudam a cada lançamento, mantém os que se repetem, devolve o foco ao primeiro campo variável e atualiza lista e agregados por swap out-of-band.
- **Swap out-of-band em contexto de tabela vai dentro de `<template>`** — e a regra vale quando a resposta **começa** com `<tr>`. Resposta que começa com `<form>` não precisa.
- Estado de UI que precisa sobreviver ao re-render (o `open` do `<details>`) vai em `<input type="hidden">`; filtros que vivem fora do formulário vão por `hx-include`, não por campo oculto.
- Filtros são GET na URL, com `hx-push-url`; a mesma rota devolve página inteira ou fragmento conforme `HX-Request`, com exceção explícita para `HX-History-Restore-Request`.
- Quando gravar ou excluir pode reordenar a lista ou mudar a paginação, devolver o bloco de resultados inteiro em vez da linha isolada — se necessário, redirecionando o swap com `HX-Retarget`.
- Agregados vêm de consulta própria sobre o filtro inteiro, nunca de soma em Python sobre a página.
- Busca textual escapa `%` e `_` (`ESCAPE '\'` em string *raw*), sem `unaccent`.
- `UniqueViolation` vira erro de campo legível, pendurado no campo que a pessoa vai corrigir, nunca 500. Transação por request, rollback em erro.
- Mensagem de login única para login inexistente / inativo / senha errada. Redirecionamento sempre por `destino_interno`. Logout via POST com CSRF.
- Selects com valores de CHECK exibem rótulo amigável, mas gravam o valor exato. Subcategoria e fonte de receita têm opção em branco e nunca vêm pré-selecionadas.
- Conhecimento que a tela precisa (catálogo de formatos, por exemplo) fica no servidor e chega por fragmento HTMX, sem cópia em JavaScript.
- Destaque do item de menu vence pelo caminho mais específico (`/despesas` × `/despesas/consulta`).
- Responsivo: abaixo de 768px a sidebar vira barra superior; nas tabelas, colunas secundárias são escondidas e realocadas numa linha de apoio, sem rolagem horizontal.
- Validação de entrega inclui **navegador real**, não só requisições HTTP.

## 7. Rodadas concluídas

| Rodada | Entrega | Estado |
|---|---|---|
| 0 | Docker (Postgres + pgAdmin), `.env` | ✅ |
| 1 | `01_schema.sql` idempotente, view, trigger, comentários | ✅ |
| 2 | Esqueleto Flask, pool, login, `create-user` | ✅ |
| 3 | CSS Glassmorphism, layout com sidebar, cadastros das 5 entidades, `set-password` | ✅ |
| 4 | Lançamento de despesas (série, classificação reativa, edição, exclusão física), Home separada, blueprint `lancamentos`, `executar` promovido a `db.py` | ✅ |
| 5 | Consulta de despesas: filtros por GET, totais, resumo por categoria, paginação 50, editar/excluir cientes da origem, `util.destino_interno` | ✅ |
| 6 | Regra de vírgula corrigida, filtro mensal por intervalo de datas (Index Scan), autocomplete de descrição com preenchimento de subcategoria/conta/pessoa | ✅ |
| 7 | Receitas em página única (lançamento em série, filtros, total, resumo por categoria, edição, exclusão), view `vw_receitas`, parser de valor promovido a `util.py` | ✅ |
| 8 | Configurações com vigência (chave livre + catálogo na aplicação, percentual digitado como 4 → 0.04, edição em linha, exclusão física), promoção dos helpers compartilhados, `formatar_valor` para `util.py`, correção do `query_string` e do `<details>` no desktop | ✅ |

## 8. Roteiro (ordem sugerida)

1. **Dashboard** (`/`): totais do mês, por categoria, essencial × não essencial, taxa de poupança (receitas × despesas do mesmo intervalo), número de independência com a TSR vigente. O resumo por categoria da consulta de despesas e o de receitas são os primeiros cartões prontos; `configuracoes/servico.py` já entrega os parâmetros vigentes.
2. **Orçamento** mensal por categoria e realizado × planejado.
3. **Patrimônio**: ativos e snapshots; número de independência com dado real.
4. **IPCA**: script de carga (API SIDRA/IBGE, `INSERT ... ON CONFLICT (mes) DO UPDATE`) e gráficos deflacionados.
5. **Deploy**: serviço `app` no `docker-compose` com gunicorn; acesso via Tailscale; segundo usuário.

Backlog consciente (adiado, não esquecido): exportação CSV/Excel, duplicar lançamento, edição em lote, filtro por intervalo livre de datas, ordenação por cabeçalho de coluna, sugestão que preencha valor, aprendizado de descrição por usuário, autocomplete de descrição em receitas.

## 9. Pendências e lembretes

- **Rodadas 4 a 8 não foram commitadas** — o working tree acumula as cinco.
- Existe **dado real** no banco (725 despesas, 1 receita). Toda faxina de teste é por id; nenhuma rodada apaga o que não criou.
- Usuários: `tiago` ativo, `zz_consulta` desativado, `zz_teste` criado na rodada 8 para validação em navegador (credencial no `.env`). Usuário de teste se desativa, nunca se apaga.
- `so_fragmento` mora em `lancamentos/servico.py` e por isso o módulo agora importa `flask.request`. Se uma terceira tela precisar dele, o lugar certo passa a ser `util.py`.
- A correção do `<details>` no desktop usa `::details-content { content-visibility: visible }`, que exige Chromium 131+ ou Firefox 139+. Em navegador mais antigo a regra é ignorada e os filtros extras voltam a ficar inacessíveis quando fechados. Se isso aparecer no celular de alguém da casa, trocar por uma abordagem sem `::details-content`.
- Configuração recusa valor negativo por regra da aplicação. Se o dashboard precisar de um `R` real negativo (cenário pessimista), é uma linha em `converter_numero` — decisão a reabrir, não bug.
- Autocomplete: com `hx-trigger ... changed`, escolher uma sugestão e redigitar exatamente o mesmo trecho não reabre a lista, porque o HTMX compara com o último valor que ele viu digitado. Digitação normal não esbarra nisso.
- O JS do autocomplete ficou em ~75 linhas. Se crescer de novo, avaliar extrair para `static/js/`.
- `SECRET_KEY` está no `.env`, documentada no README.
- Python 3.14 é recente; se um pacote não tiver wheel, recriar o venv com 3.12 em vez de compilar.
- Componentes CSS `modal` e `.card--sem-padding` continuam sem uso (a confirmação de exclusão usa `hx-confirm`).
- Documentar em `docs/` qualquer decisão nova de schema — e conferir o que este documento afirma sobre o código antes de citá-lo num prompt (ver lições).

## 10. Lições aprendidas (para não repetir)

**Ambiente e Postgres**
- pgAdmin recente rejeita e-mail com domínio `.local`; usar `.com`.
- `teardown_appcontext` roda a cada request — não é lugar para fechar pool; usar `atexit`.
- psycopg conta `%s` dentro de comentário SQL como placeholder; `%s IS NULL` precisa de cast.
- `ESCAPE '\'` em string Python não-raw vira `ESCAPE ''` e quebra o SQL.
- Filtrar por coluna derivada de view mata o índice; filtrar pela coluna base com intervalo resolve sem criar índice novo.

**Flask e Jinja**
- `flask run` só encontra o app com `app.py`/`wsgi.py`, `--app` ou `FLASK_APP` (por isso o `.flaskenv`).
- Comentário `{# #}` dentro de uma expressão Jinja quebra o arquivo inteiro — e como o login importa `_macros.html`, derrubou a tela de login junto.
- `{% include %}` dentro de macro enxerga o contexto do template, não os argumentos da macro; nesses casos, macro chamando macro.
- Helper com underscore importado de outro módulo é contradição: se vai ser compartilhado, promover e tirar o underscore na mesma rodada.

**HTMX**
- Swap out-of-band depois de um `<tr>` só sobrevive dentro de `<template>` — mas a regra é sobre a resposta *começar* com `<tr>`; começando com `<form>`, não é necessário.
- Filtro que vive fora do formulário vai por `hx-include`, não por campo oculto: o oculto envelhece assim que o filtro muda, e sincronizá-lo exigiria JS. Isso obriga a dar nomes distintos aos parâmetros de filtro e aos campos do formulário, senão eles se atropelam no corpo do POST.
- Quando o que foi gravado pode reordenar a lista ou mudar de página, devolver o bloco inteiro e usar `HX-Retarget` em vez de trocar só a linha.
- O HTMX envia o campo com o `name` dele; para outro nome de parâmetro, `hx-vals` — e `hx-params="none"` junto cancela a requisição.
- `changed` compara com o último valor digitado; preenchimento por JS não conta como mudança.
- `HX-History-Restore-Request` vem junto com `HX-Request` e espera a página inteira; devolver fragmento quebra o botão voltar.
- Destaque de menu por prefixo de caminho acende dois itens quando uma rota é prefixo da outra.

**CSS**
- `flex-basis` fixo vira altura quando o container passa a `column` no responsivo.
- `<details>` fechado esconde o conteúdo mesmo com o `<summary>` em `display:none` — foi assim que os filtros extras ficaram inacessíveis no desktop por duas rodadas sem ninguém notar.
- `nowrap` herdado numa coluna de data estica a tabela inteira no celular quando outra coluna tem texto longo.

**Processo**
- Suíte só de HTTP passa com bug de parser de tabela de pé; **validar no navegador real** pegou os piores bugs até agora (o OOB expulso da tabela, o vão branco no celular, os filtros extras inacessíveis).
- Sem credencial de teste, o agente cai no test client e a validação de layout perde valor. Manter um usuário de teste ativo com senha no `.env` durante a rodada.
- Prompts que funcionaram: escopo fechado ("SOMENTE isto"), lista de regras negativas, pedido explícito de validação executada e de relatório de interpretações, e sempre "se algo estiver ambíguo, pergunte antes de decidir".
- Deixar o agente propor opções quando há ambiguidade e decidir aqui com justificativa produz melhor resultado do que antecipar tudo no prompt.
- Regra escrita simétrica quando o domínio é assimétrico gera erro silencioso: a primeira versão do parser tratava `.` e `,` igual, e `10,999` virava dez mil sem aviso. Ao escrever regra de formato, escrever também o que deve **falhar**.
- Documentação que afirma coisas sobre o código precisa ser conferida: a estrutura listava as macros `combobox` e `tabela` como existentes, e o agente descobriu na rodada 8 que nenhuma das duas existia. Citar arquivo ou macro num prompt sem conferir custa uma rodada de retrabalho.
- Rodada boa mistura entrega nova com duas ou três limpezas pendentes já identificadas; a dívida não sobrevive a três rodadas assim.
