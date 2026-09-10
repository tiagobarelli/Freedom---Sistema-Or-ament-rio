# Handoff: Freedom — Lançar despesa + Cadastros (Categorias)

Complementa `design_handoff_freedom_visao_anual/README.md` (leia-o primeiro: sidebar, barra superior, cartão padrão, tokens e tipografia são os mesmos e **não se repetem aqui**). Este documento cobre o que a Visão Anual não tinha: formulários, autocomplete, badges, tabela com ações, edição em linha, faixa de totais, paginação, filtro de inativos.

## Sobre o arquivo de design
`Freedom - Lançamentos e Cadastros.dc.html` é um protótipo de referência (abre no navegador; alterne as telas pela sidebar). Não é código de produção. A tarefa é reproduzir o visual na stack atual (Jinja + HTMX + CSS puro), **mantendo rotas, names, ids, macros e comportamento HTMX existentes**. Muda o CSS de `static/css/app.css` e, onde indicado, a estrutura do markup das macros.

## Fidelidade
Alta. Medidas, cores e raios abaixo são finais.

## Mapa classe atual → especificação
A maior parte do trabalho é reestilizar classes que já existem em `app.css`:

| Classe atual | Ver seção |
|---|---|
| `.entrada`, `.selecao`, `.area-texto`, `.entrada-moeda`, `.entrada--grande` | Controles de formulário |
| `.campo__rotulo`, `.campo__dica`, `.campo__apoio`, `.campo__erro` | Rótulos e apoio |
| `.grade-despesa`, `.campo--descricao`, `.form-despesa__acoes` | Layout do formulário |
| `.sugestoes*` | Autocomplete |
| `#classificacao`, `.classificacao-resumo*` | Classificação derivada |
| `.mais-opcoes*`, `.marcar` | Mais opções |
| `.btn`, `.btn--primario/--secundario/--discreto/--pequeno/--grande` | Botões |
| `.badge`, `.badge--essencial/--naoessencial/--ativo/--inativo` | Badges |
| `.tabela`, `.tabela-caixa`, `.tabela__principal/__suave/__acoes`, `.linha--inativa` | Tabelas |
| `.recentes-cabecalho`, `.total-mes*` | Faixa de totais |
| `.filtros`, `.filtros__rotulo` | Filtro "Mostrar inativos" |
| `.aviso-inline` | Confirmação após gravar |

---

## Controles de formulário
Todos os controles têm a mesma altura e raio; nada de bordas roxas ou sombras internas.

- **Rótulo** (`.campo__rotulo`): 12px/500 `#6E6E73`, `margin-bottom:6px`, `display:block`.
- **Input / select** (`.entrada`, `.selecao`): `height:36px; border:1px solid #D2D2D7; border-radius:8px; padding:0 10px; font-size:13px; color:#1D1D1F; background:#fff; width:100%; box-sizing:border-box; font-family:inherit`.
  - Placeholder `#AEAEB2`.
  - **Foco**: `outline:none; border-color:#30B0C7; box-shadow:0 0 0 3px rgba(48,176,199,.18)`.
  - **Erro** (`--erro`): `border-color:#FF3B30`; foco com `box-shadow:0 0 0 3px rgba(255,59,48,.16)`. Mensagem `.campo__erro` 12px `#D70015`, `margin-top:4px`.
  - Select: seta nativa do navegador é aceitável; se estilizar, chevron Lucide 14px `#6E6E73` a 10px da direita.
- **Textarea** (`.area-texto`): mesmo estilo; `padding:8px 10px; min-height:56px; resize:vertical`.
- **Valor** (`.entrada-moeda`): wrapper `position:relative`; prefixo "R$" absoluto à esquerda (`left:10px`, centrado verticalmente, 13px `#86868B`); input com `padding-left:32px; font-size:15px; font-weight:600; font-variant-numeric:tabular-nums`.
- **Data**: `<input type=date>` com o estilo padrão de `.entrada` (ícone nativo do navegador).
- **Checkbox** (`.marcar`): `<input type=checkbox>` 16×16 `accent-color:#30B0C7`, `gap:10px`, texto 13px; dica em linha abaixo 11px `#86868B`.
- **Apoio** (`.campo__dica`, `.campo__apoio`): 11px `#86868B`, `margin-top:4px`. `.campo__apoio--aviso`: `#B25E00`.
- Espaçamento entre campos: `gap:14px` (grid) / `margin-bottom:16px` (pilha).

## Tela 1 — Lançar despesa (`templates/lancamentos/despesas.html`)

### Barra superior
Padrão do handoff anterior. Esquerda: h1 "Lançar despesa" + subtítulo. **Direita: o total do mês** (`#total-mes`, hoje abaixo do formulário, sobe para a barra):
`display:flex; align-items:baseline; gap:8px; white-space:nowrap; font-size:12px; color:#6E6E73` → rótulo "Setembro de 2026" · valor 15px/700 `#1D1D1F` tabular · "26 lançamentos". Continua sendo o mesmo `hx-swap-oob`.

### Cartão do formulário
Cartão padrão com `padding:20px 20px 16px; display:flex; flex-direction:column; gap:16px`.

Grid de 12 colunas (`display:grid; grid-template-columns:repeat(12,minmax(0,1fr)); gap:14px`). Ocupação (`grid-column:span N`):

| Linha | Campo | span |
|---|---|---|
| 1 | Data | 3 |
| 1 | Valor | 3 |
| 1 | Descrição (autocomplete) | 6 |
| 2 | Subcategoria (select com `<optgroup>` por categoria) | 5 |
| 2 | Classificação (somente leitura, derivada) | 3 |
| 2 | Conta | 2 |
| 2 | Pessoa | 2 |

Abaixo de 900px: todos os campos `span 6`; abaixo de 600px: `span 12`.

Isto substitui a atual `.grade-despesa` (2 colunas) + `.campo--descricao` empilhados. As macros `campos_despesa` continuam as mesmas; muda só o wrapper e as classes de span.

### Classificação derivada (`#classificacao`)
Mesma altura de um input (36px), sem borda, `display:flex; align-items:center; gap:8px; font-size:13px`.
- Com subcategoria: nome da categoria 500 `#1D1D1F` (ellipsis) + badge de essencialidade (abaixo).
- Sem subcategoria: texto "Vem da subcategoria" em `#AEAEB2`.
É o alvo do `hx-get` de classificação; conteúdo continua vindo do servidor.

### Autocomplete (`.sugestoes`)
- Wrapper `position:relative`.
- **Painel** (`.sugestoes__painel`): `position:absolute; top:calc(100% + 4px); left:0; right:0; z-index:5; background:#fff; border-radius:10px; box-shadow:0 8px 24px rgba(0,0,0,.12), 0 0 0 1px rgba(0,0,0,.06); padding:6px`. Vazio = invisível (sem borda/altura).
- Cabeçalho dentro do painel (novo, opcional): 11px/600 uppercase `letter-spacing:.05em` `#86868B`, `padding:6px 10px 4px`, texto "Usadas antes · preenche classificação e conta".
- **Item** (`.sugestoes__item`): `display:flex; justify-content:space-between; gap:12px; padding:8px 10px; border-radius:7px; font-size:13px; cursor:pointer`. Descrição (`.sugestoes__descricao`) 500 `#1D1D1F`; apoio (`.sugestoes__apoio`) 12px `#6E6E73` `white-space:nowrap; overflow:hidden; text-overflow:ellipsis` (valor · subcategoria · usos).
- Hover e `--ativo` (teclado): `background:#F5F5F7`.
- Ao escolher: campo Valor mostra `.campo__apoio` "último: R$ 57,54" (comportamento já existe; estilo 11px `#86868B`).

### Mais opções (`.mais-opcoes`)
- `summary` (`.mais-opcoes__resumo`): `display:inline-flex; align-items:center; gap:6px; font-size:13px; font-weight:500; color:#30B0C7; cursor:pointer; list-style:none` (esconder o marcador nativo). Chevron Lucide `chevron-right` 12px `stroke-width:2.5`; `rotate(90deg)` quando `open`, `transition:transform .2s`.
- Corpo (`.mais-opcoes__corpo`): mesmo grid de 12 colunas, `padding-top:2px`:
  - **Essencialidade** (span 4): controle segmentado no lugar do `<select>` atual — container `display:flex; background:#E5E5EA; border-radius:8px; padding:2px; height:36px`; dois botões `flex:1; border:0; border-radius:6px; font-size:13px; font-weight:500`; selecionado `background:#fff; color:#1D1D1F; box-shadow:0 1px 2px rgba(0,0,0,.1)`; não selecionado `background:transparent; color:#6E6E73`. Dica abaixo: "Sobrescreve a subcategoria só nesta despesa." **Implementação**: manter o `<select name="essencialidade">` (o backend e o `hx-get` dependem dele) — ou visualmente escondido e sincronizado por JS com os botões, ou estilizado como select comum se preferir zero JS.
  - **Prioridade** (span 4): 4 botões P1–P4 `flex:1; height:36px; border:1px solid #D2D2D7; border-radius:8px; font-size:13px; font-weight:600; background:#fff`; selecionado `background:#1D1D1F; color:#fff; border-color:#1D1D1F`. Legenda 11px `#86868B` "P1 mais importante · P4 menos". Quando Essencial, o bloco fica `opacity:.4`. Mesma regra do select: manter o input real (`name="prioridade"`) por trás.
  - **Série histórica** (span 4): rótulo + checkbox `.marcar` "Integra o agregado deflacionado pelo IPCA" com dica.
  - **Observações** (span 12): textarea 2 linhas.

### Ações (`.form-despesa__acoes`)
`display:flex; align-items:center; justify-content:space-between; gap:16px; border-top:1px solid #F0F0F2; padding-top:14px; flex-wrap:wrap`.
- Esquerda: botão primário grande (`.btn--primario.btn--grande`: `height:34px; padding:0 16px; border-radius:8px; font-size:13px; font-weight:600`, ícone `plus` 14px) + texto 12px `#86868B` "Enter lança e mantém data, conta e pessoa para a próxima." (o `htmx-indicator` "gravando…" fica no lugar deste texto enquanto envia).
- Direita: `#aviso-lancamento` / `.aviso-inline` — 12px/500 `#1D7F3B` com ícone `check` 14px `stroke-width:2.5`: "Lançado: Varejão Serve Bem · R$ 57,54". Sem caixa, sem fundo. Somem após ~3,5s (`transition:opacity .3s`).

### Lançamentos recentes
Cartão padrão `overflow:hidden`.
- Cabeçalho (`.recentes-cabecalho`): `display:flex; justify-content:space-between; align-items:center; padding:14px 20px; border-bottom:1px solid #F0F0F2`. Título 14px/600; à direita, 12px `#6E6E73` "Clique em Editar para alterar na própria linha" (ver nota em Edição em linha).
- `.tabela-caixa`: `overflow-x:auto`; sem borda própria (a borda é o cartão).
- Tabela: `width:100%; min-width:980px; border-collapse:collapse; font-size:13px; white-space:nowrap`.
  - `thead tr` `#FAFAFC`; `th` 11px/600 `#6E6E73` **sem uppercase**, `padding:9px 12px` (20px nas pontas), `border-bottom:1px solid #F0F0F2`. Valor alinhado à direita. Coluna de ações `width:120px`, sem título.
  - `td` `padding:10px 12px; border-bottom:1px solid #F0F0F2`; hover da linha `#FAFAFC`.
  - Data `#6E6E73` tabular · Descrição (`.tabela__principal`) 600 · Classificação/Pessoa/Conta (`.tabela__suave`) `#6E6E73` (Pessoa e Conta em `#1D1D1F` no protótipo — use `#1D1D1F` para ambos e `#6E6E73` só para Classificação) · Valor 600 tabular à direita.
  - Ações (`.tabela__acoes`): `text-align:right`; wrapper `display:inline-flex; gap:4px`.
- **Linha recém-gravada** (afterbegin do HTMX): `animation:flashRow 1.2s ease-out` com `@keyframes flashRow{from{background:#E6F6F9}to{background:#fff}}`. Adicionar a classe na linha retornada por `_linha_despesa.html` quando vier do POST.
- **Rodapé** (novo): `display:flex; justify-content:space-between; align-items:center; padding:12px 20px; background:#FAFAFC; border-top:1px solid #F0F0F2; font-size:12px; color:#6E6E73`.
  - Esquerda: "Total da página **R$ x**" · "Total do mês **R$ y**" (negrito `#1D1D1F` tabular, `gap:16px`).
  - Direita: "1–8 de 26" + dois botões 28×28 `border:1px solid #D2D2D7; border-radius:6px; background:#fff` com `chevron-left`/`chevron-right` 14px; desabilitado `opacity:.4`. Hoje a tela mostra as 15 mais recentes sem paginação; se paginar não fizer parte do escopo, mantenha só os totais.

### Botões de ação em linha
- **Editar** (`.btn--discreto.btn--pequeno`): `height:28px; padding:0 10px; border:0; border-radius:6px; background:none; color:#30B0C7; font-size:12px; font-weight:500`. Hover `background:#E6F6F9`.
- **Excluir / Desativar** (`.btn--secundario.btn--pequeno`): mesmas medidas, `color:#6E6E73`, sem borda. Hover: Excluir `background:#FFF1F0; color:#D70015`; Desativar `background:#F0F0F2; color:#1D1D1F`. Texto "Reativar" quando inativo.
- **Salvar** (em linha): `height:28px; padding:0 10px; border-radius:6px; background:#30B0C7; color:#fff; font-size:12px; font-weight:600`. **Cancelar**: `border:1px solid #D2D2D7; background:#fff; color:#1D1D1F; font-weight:500`.

### Edição em linha (proposta)
O protótipo edita a despesa **na própria linha** (Data, Descrição, Pessoa, Conta e Valor viram controles de 30px; Classificação e badge ficam como texto). Linha em edição: `background:#F7FCFD`; inputs com `border-color:#30B0C7`, `height:30px; border-radius:6px; font-size:12–13px`.
Hoje "Editar" abre `despesa_editar.html`. **Duas opções válidas** — escolha uma e diga qual:
1. Manter a página `despesa_editar.html` (menor esforço): aplicar a ela o mesmo cartão/grid do formulário acima e os botões "Salvar alterações" / "Cancelar" (`acoes_formulario`).
2. Edição em linha via HTMX: `hx-get` troca a `<tr>` por uma versão editável (novo parcial `_linha_despesa_edicao.html`), `hx-post` devolve a linha normal. Só Data/Descrição/Pessoa/Conta/Valor; subcategoria e "Mais opções" continuam na página completa.

## Tela 2 — Categorias (`templates/cadastros/categorias_lista.html`)
Mesmo padrão serve para Subcategorias, Contas, Pessoas e Fontes de receita.

### Barra superior
h1 "Categorias" + subtítulo; à direita o `.btn--primario` "Nova categoria" (30px, ícone `plus`), padrão do handoff anterior (`acoes_pagina`).

### Conteúdo
`padding:24px 28px 40px; max-width:960px; display:flex; flex-direction:column; gap:14px`.

**Linha de filtros** (`.filtros`, sem cartão): `display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap`.
- Esquerda: busca (novo, opcional) — `.entrada` com ícone `search` 14px `#86868B` absoluto a 10px e `padding-left:30px`, `max-width:360px`, placeholder "Buscar categoria". Filtragem client-side simples, ou omitir.
- Direita: contagem 12px `#6E6E73` "24 ativas · 2 inativas" + **switch** "Mostrar inativos": trilho 34×20 `border-radius:10px` (`#D2D2D7` off / `#30B0C7` on), bolinha 16px branca `box-shadow:0 1px 3px rgba(0,0,0,.25)`, `left:2px` → `16px`, `transition .15s`; rótulo 13px. Continua sendo o `<input type=checkbox name=mostrar_inativos>` de `filtro_inativos` (visualmente escondido, `<label>` estilizado como switch) enviando o `GET` como hoje.

**Lista** (cartão padrão, `overflow:hidden`). Pode continuar `<table class="tabela">`; medidas:
- Linha: `min-height:46px; padding:0 20px; border-bottom:1px solid #F0F0F2; font-size:13px`; colunas Nome (`1fr`) · Situação (`110px`) · Ações (`170px`, à direita). Sem `thead` visível (o cabeçalho "Nome / Situação" de `cabecalho_tabela` pode virar `.so-leitor`). Hover `#FAFAFC`.
- Nome (`.tabela__principal`) 500. `.linha--inativa`: nome `#86868B`.
- Badge Ativo/Inativo (abaixo).
- Ações: Editar / Desativar|Reativar (botões acima; Desativar com `min-width:72px` para não pular ao trocar o texto).
- **Nova categoria** (proposta): em vez de ir para `categorias_form.html`, uma faixa no topo do cartão `background:#E6F6F9; border-bottom:1px solid #C9EBF1; padding:12px 20px; display:flex; gap:10px` com input (`height:34px; border-color:#30B0C7`) + Salvar (32px, primário) + Cancelar. **Edição em linha**: a linha vira `background:#F7FCFD` com o input no lugar do nome e Salvar/Cancelar no lugar das ações. Enter salva, Esc cancela. Ao gravar, linha pisca (`flashRow`). Se preferir manter `categorias_form.html` como página, aplicar a ela cartão + `.entrada` + `acoes_formulario` no padrão acima.
- Vazio (`m.vazio`): `padding:28px 20px; text-align:center; font-size:13px; color:#86868B`.

## Badges (`.badge`)
`display:inline-flex; align-items:center; gap:6px; padding:3px 9px; border-radius:999px; font-size:12px; font-weight:500; white-space:nowrap`. Ponto à esquerda 6×6 `border-radius:50%; background:currentColor`.

| Variante | Fundo | Texto |
|---|---|---|
| `--essencial` "Essencial" | `#E4F7EA` | `#1D7F3B` |
| `--naoessencial` "Não essencial · P3" | `#FFF3E0` | `#B25E00` |
| `--ativo` "Ativo" | `#E4F7EA` | `#1D7F3B` |
| `--inativo` "Inativo" | `#F0F0F2` | `#6E6E73` |

Texto do badge de não essencial: "Não essencial" (só o N maiúsculo), prioridade após " · ".

## Tokens adicionais
Acrescentar aos `:root` do handoff anterior:
```css
--control-h:36px; --control-h-sm:30px; --btn-h-sm:28px;
--control-border:#D2D2D7; --control-radius:8px; --control-radius-sm:6px;
--focus-ring:0 0 0 3px rgba(48,176,199,.18);
--accent-soft:#E6F6F9; --accent-soft-line:#C9EBF1; --row-editing:#F7FCFD;
--green-soft:#E4F7EA; --green-ink:#1D7F3B;
--orange-soft:#FFF3E0; --orange-ink:#B25E00;
--red-soft:#FFF1F0; --red-ink:#D70015;
--shadow-popover:0 8px 24px rgba(0,0,0,.12),0 0 0 1px rgba(0,0,0,.06);
```

## Ícones novos (Lucide, inline como os demais em `_macros.html`)
`chevron-right` (Mais opções), `chevron-left`/`chevron-right` (paginação), `check` (aviso de gravado), `search` (busca; já existe), `plus` (já existe).

## O que NÃO muda
Rotas, `name`s dos campos, ids usados pelo HTMX/JS (`#form-despesa`, `#sugestoes-painel`, `#classificacao`, `#lista-despesas`, `#total-mes`, `#aviso-lancamento`, `#mais-opcoes`), o JS de autocomplete em `despesas.html`, e a lógica Java/Python do backend.

## Arquivos
- `Freedom - Lançamentos e Cadastros.dc.html` + `support.js` — protótipo (abrir no navegador; alternar telas pela sidebar; testar autocomplete, Enter para lançar, Editar em linha, switch de inativos, Nova categoria).
- `../design_handoff_freedom_visao_anual/README.md` — base (sidebar, barra, cartão, tokens).
