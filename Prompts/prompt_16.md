# Freedom — Rodada 17: refatoração visual — tokens, layout e Visão Anual

## Contexto
Leia antes de começar, nesta ordem:
1. `docs/Freedom - Histórico e Estado do Projeto.md` (consolidado até a rodada 16; seções 3 "Visual em transição", 5 e 6 são obrigatórias).
2. `design_handoff_freedom_visao_anual/README.md` e o protótipo `Freedom - Visão Anual v2.dc.html` — a referência visual. **Atenção**: o README foi escrito por uma ferramenta de design e erra sobre a stack. Onde ele disser Java, CDN, unpkg, `localStorage` como única persistência ou "sem celular", vale o que está abaixo, não o README. `support.js` é o runtime da ferramenta (React) e **não entra no repositório**. O protótipo usa estilos inline e tags `<x-dc>`/`<sc-if>`/`{{ }}`: é referência de aparência e de configuração dos gráficos (função `build()`), não markup para copiar.
3. `templates/base.html`, `templates/layout_app.html`, `templates/_macros.html`, `templates/main/index.html`, `static/css/app.css` (seção 1 inteira e 5.13), `static/js/visao_anual.js`, `freedom/main/servico.py` (`card`, `fracao`, `painel_do_ano`, `_graficos`), `freedom/orcamento/servico.py` (`_fracao`).

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres 16 em Docker, dado real (nada é escrito nesta rodada). **Servidor com `--debug`**, reiniciado após mexer em código. Login `zz_teste`, senha na variável `senha_teste` do `.env`. Validação em **navegador real**, desktop 1440px e celular 390px.

## Stack (já decidida, não proponha alternativas)
Flask 3 + psycopg 3 + Flask-WTF + HTMX 2.0.4 local + **Chart.js 4.5.1 local** (já em `static/js/chart.umd.js` — **não** trocar por CDN nem por 4.4.1) + CSS à mão com variáveis em `:root` + JS vanilla. **Sem React, sem Tailwind, sem biblioteca de ícones carregada de fora**: os ícones Lucide entram como SVG inline copiado do protótipo. Nenhuma requisição a domínio externo em nenhuma tela.

## Entrega desta rodada — SOMENTE isto

1. **Tokens**. Reescreva a seção 1 do `app.css` com as variáveis do README (`--bg`, `--surface`, `--ink-*`, `--line*`, `--fill`, `--grid`, `--sidebar*`, `--accent*`, `--green`, `--red`, `--orange`, raios, sombra, `--font`). **Mantenha os nomes antigos de variáveis existindo como aliases** para os tokens novos (ex.: a antiga cor primária → `var(--accent)`, `--cor-erro` → `var(--red)`, `--cor-aviso` mantida, `--grafico-*` remapeados: receita verde, despesa vermelho, essenciais `--accent`, não essenciais `--orange`, total `--ink-5`, P1–P4 nos quatro tons de teal). Assim as telas ainda não refeitas continuam funcionando com a paleta nova até as rodadas 18–19. Tipografia: fonte do sistema, tamanhos 11/12/13/14/15/17 e `font-variant-numeric: tabular-nums` em todo número. O Glassmorphism (blur, transparência em cartão) sai do cartão e da sidebar; permanece **só** o `backdrop-filter` da barra superior, como no protótipo.

2. **Macro `icone(nome)`** em `_macros.html` com os SVGs Lucide do protótipo (`calendar-range`, `calendar-days`, `pie-chart`, `circle-plus`, `search`, `trending-up`, `tags`, `tag`, `landmark`, `users`, `banknote`, `settings`, `log-out`, `chevron-down`, `plus`), 16×16, `stroke-width` 1.75 (2.25 no `plus` do botão), `currentColor`, `aria-hidden="true"`. Licença ISC registrada no README do projeto, na seção de dependências de front-end.

3. **Layout** (`layout_app.html` + CSS): sidebar 232px escura, sticky, com marca, três seções **recolhíveis** (Painel, Lançamentos, Cadastros — Configurações continua no fim de Cadastros), rodapé com avatar (inicial do nome da pessoa do usuário logado), nome, login e **logout que continua sendo POST com CSRF** (um `<form>` com botão-ícone `log-out`, `title="Sair"`; o protótipo tem `<a href="#">`, ignore). Barra superior sticky com título e subtítulo da tela à esquerda (blocos Jinja que cada tela preenche) e ações à direita. Cartão padrão (`.card`) branco, raio 14px, sombra do README, sem borda sólida. Estados de hover/ativo do menu conforme o README; ativo continua decidido pelo caminho mais específico.
   - Recolher/expandir: JS vanilla no `layout_app.html` (bloco pequeno, no padrão do menu atual), `aria-expanded` no botão, chevron girando, estado salvo em `localStorage` (`freedom.sidebar.painel|lancamentos|cadastros`), inicial Painel e Lançamentos abertos, Cadastros fechado. Sem `localStorage` disponível, tudo aberto e sem erro.
   - **Celular (< 768px) preservado**: a sidebar continua virando barra superior como hoje; as seções recolhíveis não se aplicam ali (tudo visível, como hoje). Nada do protótipo manda abaixo de 768px.

4. **Visão Anual** (`main/index.html`, `servico.py`, `visao_anual.js`, CSS 5.13):
   - Barra superior: título "Visão Anual", subtítulo "O ano inteiro num relance", **seletor de ano segmentado** (continua GET `?ano=` com recarga inteira; pode ser links ou `<input type="radio">` estilizados — decida e relate) e botão primário "Lançar despesa" com ícone `plus`.
   - **4 KPIs** em cartão: Receita anual (barra verde cheia), Despesa anual (trilho com preenchimento vermelho na proporção despesa ÷ receita — fração vinda do servidor, "—" sem receita), Saldo anual (valor em `--accent`; apoio "N de M meses no azul"), Taxa de poupança (apoio "Média mensal R$ X" = despesa média/mês). Os quatro saem dos cards que já existem em `painel_do_ano`; acrescente ao modelo só a fração despesa/receita.
   - **9 indicadores secundários** num único cartão, na ordem do README, com a nota complementar (mês, "9 meses", descrição e data do pico) vinda do servidor. `card()` ganha o que precisar para carregar rótulo, valor, nota e classe; nada decidido em Jinja.
   - **4 gráficos** com as opções da função `build()` do protótipo (legenda embaixo com ponto, tooltip escuro em BRL, eixos, `borderRadius`, `tension`, `fill`, empilhamento), mas **cores lidas das variáveis CSS por `getComputedStyle`** como hoje — nenhum hex no JS. Séries continuam vindo do JSON do servidor; JS só desenha.
   - **Tabela mês a mês** e **tabela por categoria** com o visual do README. A barra por categoria continua proporcional ao **total** (o protótipo usa o máximo; não seguir — o rodapé de 100% precisa fechar). Contador "N categorias" no cabeçalho do cartão vem do servidor.
   - **Celular**: a tabela mês a mês mantém a variante `<tr class="linha-apoio">` (Mês · Receitas · Despesas · Saldo visíveis) — **não** adote o `min-width: 960px` com rolagem do protótipo; grades de cards 1/2/4 como hoje.

5. **Favicon**: `static/favicon.svg` recolorido para `#30B0C7` (continua sendo a única cópia do hex fora do CSS; registre no comentário do arquivo).

6. **Limpeza**: promover `fracao` de `main/servico.py` para `util.py`, remover `orcamento/servico.py._fracao` e apontar os dois módulos para `util`. Relatar.

## Regras
- Não altere rotas, serviços de leitura, consultas ou schema; só markup, CSS, JS de apresentação e o mínimo no modelo dos cards (item 4).
- Nenhum recurso externo: sem CDN, sem unpkg, sem fonte web. A fonte é a do sistema.
- Não refaça as outras telas (lançamentos, cadastros, configurações, Mensal, Orçamento): elas só precisam continuar **funcionando e legíveis** com os aliases de variáveis. Se um alias não bastar para uma tela não quebrar (ex.: texto invisível por contraste), corrija o mínimo e relate — o visual definitivo delas é das rodadas 18 e 19.
- Não remova os padrões de celular existentes em nenhuma tela.
- Mantenha os padrões do histórico (seção 6): nada decidido em Jinja, `Decimal`, `barra_pct`, `fracao` → "—", negativo em vermelho no `<span>`.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. **Antes de mexer**, leia do DOM da Visão Anual (ano 2026) os 13 valores dos cards, os 8 totais do rodapé mês a mês e o total da tabela por categoria; guarde. Depois da refatoração, os mesmos números têm que ser **idênticos** (são só apresentação). Reporte a lista.
2. Captura da Visão Anual em 1440px ao lado de uma captura do protótipo aberto no navegador na mesma largura. Reporte as diferenças **deliberadas** (logout como formulário, barra ao total, seletor de ano, dados reais) e qualquer diferença **não** deliberada, com o que fez a respeito.
3. Sidebar: recolher Cadastros, recarregar → continua recolhido; abrir → persiste; teclado (Tab até o botão, Enter) funciona; `aria-expanded` acompanha. Item ativo correto em `/`, `/mensal`, `/orcamento`, consulta e uma tela de cadastro.
4. Gráficos: as quatro cores lidas de `getComputedStyle` (reporte os valores), tooltip em BRL, legenda embaixo, sem erro no console; **aba Rede sem nenhuma requisição externa** (ou log do servidor mostrando só `/static/...`).
5. Celular 390px: `/` com sidebar virando barra, cards em 1 coluna, tabela mês a mês com linha de apoio, `scrollWidth = clientWidth`. Também 900px.
6. Regressão funcional das outras telas com o tema novo: login, lançar uma despesa por HTMX e apagá-la por id, consulta com filtro, receitas, uma edição em linha em configurações (revertida), `/mensal` com detalhe expandido, `/orcamento` nos dois modos. Todas 200, console limpo, nada ilegível (reporte o que ficou visualmente feio mas funcional — é insumo das rodadas 18–19).
7. Item 6: `/orcamento` acompanhamento e Anual continuam com os mesmos percentuais após a promoção de `fracao`.
8. Relate: arquivos criados/alterados, mecanismo do seletor de ano, lista de aliases de variáveis criados, resultado de cada validação e a lista de **pontos que precisou interpretar**.