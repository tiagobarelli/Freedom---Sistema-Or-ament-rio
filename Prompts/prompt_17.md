# Freedom — Rodada 18: refatoração visual — lançamentos e cadastros

## Contexto
Leia antes de começar, nesta ordem:
1. `docs/Freedom - Histórico e Estado do Projeto.md` (consolidado até a rodada 16; a 17 entregou tokens, layout, macro `icone`, sidebar recolhível e a Visão Anual — o estado abaixo prevalece).
2. `design_handoff_freedom_visao_anual/README.md` (base: já implementado) e `design_handoff_freedom_lancamentos_cadastros/README.md` + protótipo `Freedom - Lançamentos e Cadastros.dc.html` — a referência desta rodada. Mesmas ressalvas da rodada 17: protótipo com estilos inline é referência de aparência, não markup; `support.js` não entra no repositório; nada de CDN/unpkg. **O handoff propõe mudanças funcionais; nenhuma delas entra** (ver "Decisões fechadas").
3. `templates/_macros.html`, `templates/lancamentos/*`, `templates/cadastros/*`, `freedom/lancamentos/despesas.py` e `servico.py` (o que `#total-mes` recebe hoje), `freedom/cadastros/servico.py`, `static/css/app.css` (seções 1, 1(b) aliases, 5.x de formulários, tabelas, badges, 5.9, 5.10, 5.11, 7).

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres em Docker, dado real. **Servidor com `--debug`**, reiniciado após mexer em código. Login `zz_teste`, senha na variável `senha_teste` do `.env`. Validação em **navegador real**, 1440px e 390px. Despesa de teste: crie e apague por id; nada real é apagado; edição real revertida pelo mesmo caminho e relatada.

## Stack (já decidida)
Flask 3 + psycopg 3 + Flask-WTF + HTMX 2.0.4 local + Chart.js local + CSS à mão com tokens em `:root` + JS vanilla mínimo. Ícones Lucide inline pela macro `icone`. Nenhuma requisição externa.

## Decisões fechadas (o handoff sugere; a decisão é esta)
- **Nenhuma rota, `name`, id de HTMX/JS, consulta ou regra muda.** Editar despesa continua na página `despesa_editar.html`; criar/editar cadastro continua nas páginas de formulário; sem busca client-side; sem paginação nos recentes.
- **Essencialidade**: `<select>` estilizado como `.selecao`. **Prioridade**: quatro `<input type="radio" name="prioridade">` com os mesmos valores 1–4, estilizados como os botões P1–P4 do handoff (selecionado escuro); continua escondida quando a essencialidade efetiva é Essencial (regra atual), sem `opacity`.
- **`#total-mes`** sobe para a barra superior como no handoff, continua sendo o alvo do swap OOB. Se hoje a resposta não traz a quantidade de lançamentos do mês, acrescente-a à mesma consulta que traz o total (uma coluna a mais, não uma consulta a mais) e relate.
- Rodapé dos recentes: "Total exibido" (das linhas na tela) e "Total do mês"; o do mês lê da **mesma origem** do `#total-mes`.
- Texto do badge: "Não essencial" com N maiúsculo, "· P3" quando houver prioridade. É rótulo de exibição; o valor gravado continua `Não Essencial` (mesmo padrão dos selects de CHECK).
- Switch "Mostrar inativos": `<label>` estilizada sobre o `<input type="checkbox" name="mostrar_inativos">` existente, visualmente escondido mas focável; o GET continua igual. Contagem "N ativas · M inativas" vem do servidor (uma consulta agregada, ou derivada da lista se ela já vier completa — relate).

## Entrega desta rodada — SOMENTE isto

1. **Tokens adicionais** do handoff na seção 1 (`--control-*`, `--focus-ring`, `--accent-soft*`, `--row-editing`, `--green-soft/-ink`, `--orange-soft/-ink`, `--red-soft/-ink`, `--shadow-popover`). Ícones novos na macro `icone`: `chevron-right`, `chevron-left`, `check`. `.card` genérico passa ao padding do design (18/20) — a Visão Anual não pode mudar (ela já está nesse padding; prove por SHA).

2. **Controles de formulário e botões** (macros `campo`, `campo_area`, classes `.entrada`, `.selecao`, `.area-texto`, `.entrada-moeda`, `.marcar`, rótulos, apoio, erro, `.btn` e variantes, `.badge` e variantes) conforme o handoff. Isso vale para **todas** as telas que usam as macros; `btn--grande` passa a 34px/13px.

3. **Lançar despesa** (`despesas.html` + parciais): barra superior com título, subtítulo e `#total-mes`; cartão do formulário com o grid de 12 colunas e os spans do handoff (900px → span 6, 600px → span 12); classificação derivada; autocomplete com o painel novo (o JS de autocomplete não muda — só classes e a estrutura mínima do painel, se precisar); "Mais opções" com chevron; ações com o texto de ajuda e o `htmx-indicator` no lugar dele; `#aviso-lancamento` como `.aviso-inline` com ícone `check`, sumindo em ~3,5 s por CSS/JS mínimo (se já some hoje, só o estilo). Recentes em cartão com a tabela do handoff, linha recém-gravada com `flashRow` (classe na linha devolvida pelo POST — flag no contexto do template, não decisão em Jinja), rodapé com os dois totais.

4. **Editar despesa** (`despesa_editar.html`): mesmo cartão e grid; botões "Salvar alterações" / "Cancelar" no padrão.

5. **Consulta de despesas** e **Receitas**: derivam dos itens 2 e 3 — filtros com os controles novos, faixa de totais e resumo por categoria no cartão padrão (a `.faixa-totais` perde o `backdrop-filter`), tabela e paginação com o visual do handoff (botões de página como os `chevron-left/right` 28×28), badges novos. Receitas mantém a página única.

6. **Cinco cadastros** (listas e formulários): barra superior com botão primário "Nova …" com ícone `plus`; linha de filtros com contagem e switch; cartão com a lista (sem `thead` visível — cabeçalho vira `.so-leitor`), badge Ativo/Inativo, `.linha--inativa`, botões Editar / Desativar|Reativar com `min-width` fixo; vazio centralizado. Formulários de criar/editar no cartão com `.entrada` e `acoes_formulario`.

7. **Celular (< 768px) preservado** em todas as telas: linha de apoio dentro da célula de Descrição, ações como ícone com `aria-label`, formulários em coluna única, sem rolagem horizontal externa. O `min-width: 980px` da tabela de recentes do handoff vale só no desktop, dentro da `.tabela-caixa`.

8. **Playwright como dependência de desenvolvimento**: `requirements-dev.txt` com `playwright` (e só ele), instruções no README (`pip install -r requirements-dev.txt` e `playwright install chromium`), `venv/` já no `.gitignore`. A partir desta rodada a validação usa isso e não desinstala nada.

## Regras
- Só markup, CSS, macros e JS de apresentação. Backend só para a quantidade de lançamentos (item "Decisões") e a contagem de ativos/inativos, se faltarem.
- Não altere o JS de autocomplete além de nomes de classe. Não altere o comportamento de lançamento em série (foco, campos mantidos, swap OOB), da classificação reativa, dos filtros GET com `hx-push-url`, da paginação, do `?retorno=`.
- Sem CDN, sem unpkg, sem fonte web. Sem `localStorage` novo.
- A Visão Anual não muda (SHA idêntico em 1440 e 390). Mensal, Orçamento, configurações e login só não podem quebrar — ganham o visual definitivo na rodada 19; se o padding novo do `.card` os deixar feios, aceite e relate.
- Mantenha os padrões do histórico (seção 6).
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. **Lançar despesa** com login `zz_teste`: lançar três despesas em série por Enter (uma com autocomplete escolhido, uma com essencialidade sobrescrita para Não essencial e prioridade P2 pelos radios, uma com observações) → cada uma aparece no topo com `flashRow`, `#total-mes` na barra e o rodapé atualizam por OOB, os campos repetidos se mantêm, o foco volta. Conferir no banco os três registros (essencialidade, prioridade, observações) e **apagar os três por id**. Reportar os ids.
2. Trocar subcategoria para uma Essencial → radios de prioridade somem; voltar → reaparecem. Provocar erro de valor → `.campo__erro` sob o campo, borda vermelha.
3. Editar uma despesa real pela página, alterar a descrição, salvar, voltar de onde veio (consulta com filtro e `/mensal` com `?retorno=`), reverter pelo mesmo caminho. Reportar o id.
4. Consulta: filtro textual, filtro de essencialidade, página 2, totais e resumo por categoria → mesmos números de antes (leia do DOM antes e depois para um filtro fixo). Receitas: lançar uma, ver na lista, apagar por id.
5. Cadastros: os cinco listam; switch de inativos filtra e a URL muda; desativar e reativar uma pessoa de teste (crie "zz_teste_pessoa", desative, reative, deixe **inativa** e relate — referência não se apaga); editar um nome e reverter.
6. Lado a lado com o protótipo em 1440px para "Lançar despesa" e "Categorias": diferenças deliberadas (as decisões fechadas) e não deliberadas, com o que fez.
7. Celular 390px: lançar despesa (formulário em coluna, recentes com linha de apoio), consulta, um cadastro → `scrollWidth = clientWidth`, ações acessíveis.
8. Visão Anual: SHA idêntico em 1440 e 390. `/mensal`, `/orcamento`, `/configuracoes`, `/login`: 200, funcionais, console limpo. Rede: só `/static/...`.
9. Relate: arquivos criados/alterados, o que mudou no backend (se algo), tokens e ícones acrescentados, aliases da 1(b) que deixaram de ter uso (não remova ainda), resultado de cada validação e a lista de **pontos que precisou interpretar**.