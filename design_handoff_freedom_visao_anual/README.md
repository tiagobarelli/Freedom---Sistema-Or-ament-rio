# Handoff: Freedom — Visão Anual (refatoração visual)

## Visão geral
Refatoração completa do visual da tela inicial ("Visão Anual") do sistema orçamentário **Freedom**. Direção aprovada: estilo Apple/macOS — sóbrio, fonte do sistema, cinzas neutros, um único acento (teal), verde/vermelho reservados para receita/despesa/saldo negativo. Substitui o tema roxo atual.

## Sobre os arquivos de design
`Freedom - Visão Anual v2.dc.html` é uma **referência de design em HTML** (protótipo), não código de produção. A tarefa é **recriar esse visual na stack do projeto: HTML + CSS + Java (templates server-side), sem React**. Reaproveite as classes/ids/rotas existentes em `templates/` e `static/`; o que muda é o CSS e a estrutura de markup, não a lógica.

Os dados exibidos são os do print original (ano 2026, 9 meses lançados). Todos os valores vêm do backend; nada deve ficar hardcoded.

## Fidelidade
**Alta (hi-fi).** Cores, tipografia, espaçamentos, raios e sombras abaixo são finais. Reproduza pixel-perfect.

## Stack alvo
- CSS puro, com variáveis em `:root` (tokens abaixo) em um único arquivo, ex. `static/css/freedom.css`.
- Gráficos: **Chart.js 4.4.x** via CDN (`https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js`).
- Ícones: **Lucide** (ISC, open source). Duas formas válidas:
  - inline SVG copiado do protótipo (zero dependência), ou
  - `<script src="https://unpkg.com/lucide@latest"></script>` + `<i data-lucide="calendar-range"></i>` + `lucide.createIcons()`.
- JS vanilla apenas para: toggle das seções da sidebar (persistir estado em `localStorage`), inicialização dos gráficos.

## Layout geral
- `body`: `margin:0; background:#F5F5F7; font-family:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Helvetica,sans-serif; color:#1D1D1F; -webkit-font-smoothing:antialiased`.
- Wrapper `display:flex; min-height:100vh`.
- **Sidebar** 232px fixa (`position:sticky; top:0; height:100vh`), fundo `#1D1D1F`.
- **Main** `flex:1; min-width:0`, com barra superior sticky e conteúdo em `padding:24px 28px 40px; display:flex; flex-direction:column; gap:18px`.

## Sidebar (`#1D1D1F`)
Padding `24px 12px 16px`, `display:flex; flex-direction:column; gap:1px`.

**Marca**: linha com quadrado 26×26, `border-radius:7px`, `background:#30B0C7` + texto "Freedom" 15px/600 branco, `letter-spacing:-.01em`. Padding-bottom 24px.

**Cabeçalho de seção (botão recolhível)**: `<button>` full-width, sem borda/fundo, texto 11px/600 uppercase `letter-spacing:.06em`, cor `#8E8E93`, padding `6px 10px`, `border-radius:6px`; hover cor `#C7C7CC`. Chevron Lucide `chevron-down` 12px à direita; `transform:rotate(0)` aberto / `rotate(-90deg)` fechado, `transition:transform .2s`. Seções após a primeira têm `margin-top:14px`.

Estado inicial: **Painel aberto, Lançamentos aberto, Cadastros fechado**. Persistir em `localStorage` (`freedom.sidebar.<secao>`).

**Item de menu** (`<a>`): `display:flex; align-items:center; gap:10px; padding:7px 10px; border-radius:7px; font-size:13px; color:#C7C7CC`. Hover: `background:rgba(255,255,255,.06); color:#fff`. Ativo: `font-weight:500; color:#fff; background:rgba(255,255,255,.12)`. Ícone 16×16, `stroke-width:1.75`, cor `#8E8E93` (branco no ativo).

Ícones Lucide por item:
- Painel: Visão Anual `calendar-range` · Visão Mensal `calendar-days` · Orçamento `pie-chart`
- Lançamentos: Lançar despesa `circle-plus` · Consultar despesas `search` · Receitas `trending-up`
- Cadastros: Categorias `tags` · Subcategorias `tag` · Contas `landmark` · Pessoas `users` · Fontes de receita `banknote` · Configurações `settings`

**Rodapé usuário**: `margin-top:auto; padding:14px 10px 0; border-top:1px solid rgba(255,255,255,.1)`. Avatar 28px círculo `#30B0C7` com inicial 12px/600 branca; nome 13px/500 branco; login 11px `#8E8E93`; ícone `log-out` 16px `#8E8E93` (hover branco) com `title="Sair"`.

## Barra superior (sticky)
`padding:14px 28px; background:rgba(255,255,255,.75); backdrop-filter:blur(20px); border-bottom:1px solid #E0E0E5; z-index:2`.
- Esquerda: `<h1>` "Visão Anual" 17px/600 `letter-spacing:-.01em` + subtítulo "O ano inteiro num relance" 13px `#6E6E73`, gap 16px.
- Direita (gap 10px):
  - **Seletor de ano** segmentado: container `background:#E5E5EA; border-radius:7px; padding:2px`; itens 12px/500 `padding:4px 12px; border-radius:5px; color:#6E6E73`; selecionado `background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.1); color:#1D1D1F`. (Substitui o `<select>` atual; pode continuar sendo um `<select>` estilizado se preferir.)
  - **Botão primário** "Lançar despesa": `height:30px; padding:0 14px; border-radius:7px; background:#30B0C7; color:#fff; font-size:13px; font-weight:500`, ícone `plus` 14px `stroke-width:2.25` à esquerda (gap 6px). Hover `#2A9DB2`.

## Cartão padrão
`background:#fff; border-radius:14px; box-shadow:0 1px 3px rgba(0,0,0,.06), 0 0 0 1px rgba(0,0,0,.03)`. Sem bordas sólidas.

## 1. KPIs principais (4 cartões)
Grid `grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:14px`. Padding interno `18px 20px`.
- Rótulo 12px/500 `#6E6E73`.
- Valor `font-size:clamp(20px,1.6vw,28px); font-weight:700; letter-spacing:-.03em; margin-top:8px; font-variant-numeric:tabular-nums; white-space:nowrap`.
- Linha de apoio `margin-top:8px`:
  - Receita anual: barra 3px `border-radius:2px; background:#34C759`.
  - Despesa anual: trilho 3px `#E5E5EA` com preenchimento `#FF3B30` na proporção despesa/receita (72% no exemplo).
  - Saldo anual: valor em `#30B0C7`; texto 12px `#6E6E73` "5 de 9 meses no azul".
  - Taxa de poupança: texto 12px `#6E6E73` "Média mensal R$ 45.049,70".

## 2. Indicadores secundários (9 itens em um cartão)
Cartão com `padding:6px 20px`, grid `repeat(auto-fit,minmax(260px,1fr)); gap:0 32px; font-size:13px`.
Cada item: `display:flex; justify-content:space-between; padding:11px 0; border-bottom:1px solid #F0F0F2` (última linha sem borda). Rótulo `#6E6E73`; valor 600 tabular. Nota complementar `#86868B` peso 400 (ex.: "· Janeiro", "· 9 meses"). "Pico de despesa": nota em linha secundária `display:block; font-size:11px` ("Provisão (TEMP) · 05/09").
Ordem: Despesas essenciais · Despesas não essenciais · Pico de despesa · % essencial · % não essencial · Despesa média/mês · Melhor mês (saldo) · Mês de maior gasto · Meses no azul.

## 3. Gráficos (4 cartões)
Grid `repeat(auto-fit,minmax(340px,1fr)); gap:14px`. Padding `18px 20px`. Título 14px/600. Área do canvas `position:relative; height:230px; margin-top:14px`.

Chart.js defaults: `font.family` = fonte do sistema, `font.size:11`, `color:'#86868B'`. Opções comuns: `responsive:true, maintainAspectRatio:false, interaction:{mode:'index',intersect:false}`; legenda embaixo com `usePointStyle:true, pointStyle:'circle', boxWidth:6, boxHeight:6, padding:18`; tooltip `backgroundColor:'#1D1D1F', padding:10, cornerRadius:8`, label formatado em BRL; eixo X sem grid nem borda; eixo Y `beginAtZero`, grid `#EEEEF0`, sem borda, `maxTicksLimit:5`, ticks "R$ 140 mil".

1. **Receitas × Despesas** — bar. Receitas `#34C759`, Despesas `#FF3B30`, `borderRadius:6, borderSkipped:false, barPercentage:.75, categoryPercentage:.62`.
2. **Essenciais × Não essenciais** — line. Essenciais `#30B0C7`, Não essenciais `#FF9500`, Total `#8E8E93` tracejado `[4,4]` sem pontos, `borderWidth:1.5`. Linhas: `borderWidth:2, tension:.4, pointRadius:3, pointBackgroundColor:'#fff', pointBorderWidth:2`.
3. **Poupança acumulada** — line com `fill:true`, cor `#30B0C7`, área `rgba(48,176,199,.12)`, sem legenda.
4. **Não essenciais por prioridade** — bar stacked (x e y). P1 `#0E7C8A`, P2 `#30B0C7`, P3 `#8ED7E3`, P4 `#D3F0F5`, `borderRadius:0`.

## 4. Tabela "Mês a mês"
Cartão `overflow:hidden`; título 14px/600 em `padding:16px 20px; border-bottom:1px solid #F0F0F2`; wrapper `overflow-x:auto`.
Tabela `width:100%; min-width:960px; border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums; white-space:nowrap`.
- `thead tr` fundo `#FAFAFC`; `th` 11px/600 `#6E6E73`, `padding:9px 12px` (20px nas extremidades), `border-bottom:1px solid #F0F0F2`; numéricas alinhadas à direita.
- `td` `padding:10px 12px; border-bottom:1px solid #F0F0F2`; hover da linha `#FAFAFC`. Mês 500. Saldo 600; **negativo em `#FF3B30`**. Taxa negativa também `#FF3B30`. Meses sem lançamento: texto `#AEAEB2`, acumulado e taxa "—".
- Linha Total: fundo `#FAFAFC`, `padding:12px`, 600; "Total" e Saldo 700; Saldo total em `#30B0C7`.
Colunas: Mês · Receitas · Despesas · Essenciais · Não essenciais · Saldo · Acumulado · Poupança.

## 5. Despesas por categoria
Cartão; cabeçalho `padding:16px 20px; border-bottom:1px solid #F0F0F2` com título 14px/600 e contador "21 categorias" 12px `#6E6E73` à direita. Corpo `padding:4px 20px 8px`.
Linha: grid `260px 1fr 130px 56px; gap:16px; align-items:center; padding:9px 0; border-bottom:1px solid #F0F0F2; font-size:13px`.
- Nome 500, `white-space:nowrap; overflow:hidden; text-overflow:ellipsis`.
- Barra: trilho 6px `#F0F0F2` `border-radius:3px`; preenchimento `#30B0C7`, largura = pct / pct_máximo.
- Total à direita 500 tabular; % à direita `#6E6E73`.
- Linha Total: 700, `padding:12px 0 8px`, "R$ 405.447,29" e "100%".

## Interações
- Toggle das seções da sidebar (click no cabeçalho): mostra/oculta lista, gira chevron, salva em `localStorage`.
- Hover em itens de menu, linhas da tabela, botões (valores acima). Transições 150–200ms `ease`.
- Seletor de ano recarrega a página com `?ano=`.
- Responsivo: grids `auto-fit`; tabela rola horizontalmente abaixo de ~1200px.

## Tokens (CSS variables sugeridas)
```css
:root{
  --bg:#F5F5F7; --surface:#fff; --surface-alt:#FAFAFC;
  --ink:#1D1D1F; --ink-2:#3A3A3C; --ink-3:#6E6E73; --ink-4:#86868B; --ink-5:#8E8E93; --ink-disabled:#AEAEB2;
  --line:#E0E0E5; --line-soft:#F0F0F2; --fill:#E5E5EA; --grid:#EEEEF0;
  --sidebar:#1D1D1F; --sidebar-text:#C7C7CC;
  --accent:#30B0C7; --accent-hover:#2A9DB2; --accent-2:#0E7C8A; --accent-3:#8ED7E3; --accent-4:#D3F0F5;
  --green:#34C759; --red:#FF3B30; --orange:#FF9500;
  --radius-card:14px; --radius-control:7px; --radius-chip:5px;
  --shadow-card:0 1px 3px rgba(0,0,0,.06),0 0 0 1px rgba(0,0,0,.03);
  --font:-apple-system,BlinkMacSystemFont,'SF Pro Text','Helvetica Neue',Helvetica,sans-serif;
}
```
Tipografia: 11 (rótulos uppercase, ths), 12 (notas), 13 (corpo), 14 (títulos de cartão), 15 (marca), 17 (h1), 20–28 (KPI). Pesos 400/500/600/700. Números sempre `font-variant-numeric:tabular-nums`.
Espaçamento: 1, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32.

## Assets
- Ícones: Lucide (https://lucide.dev), licença ISC.
- Sem imagens.

## Arquivos
- `Freedom - Visão Anual v2.dc.html` — protótipo aprovado (referência visual e configs Chart.js em `build()`).
- `Freedom - Visão Anual.dc.html` — exploração inicial com 3 direções (1a/1b/1c); 1c foi a escolhida.
