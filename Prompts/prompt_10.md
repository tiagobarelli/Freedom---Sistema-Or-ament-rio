# Freedom — Rodada 11: tabelas da Visão Anual (mês a mês e por categoria)

## Contexto
Leia antes de começar: `docs/Freedom - Histórico e Estado do Projeto.md` (agora existe em docs/, consolidado até a rodada 10 — seção 6 "Padrões" é obrigatória), `docs/Freedom - Estrutura do Banco de Dados.md`, `freedom/main/servico.py`, `freedom/main/routes.py`, `templates/main/index.html`, `templates/lancamentos/_resultados.html` (resumo por categoria com barra proporcional — o componente a reaproveitar), `templates/_macros.html` e `static/css/app.css` (seções 5.10 e 5.13).

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres em Docker. Há dado real (725 despesas, 61 receitas, 2026): nenhuma linha que você não criou pode ser apagada. Login de teste: `zz_teste`, senha na variável `<VARIÁVEL>` do `.env`. Validação em **navegador real**.

Estado da Visão Anual: seletor de ano por GET, 13 cards e 4 gráficos, tudo composto em `painel_do_ano` a partir das linhas mensais (despesas por essencialidade, receitas, não essenciais por prioridade) e do pico. Os gráficos usam o eixo de `meses_do_eixo` (jan..mês corrente no ano atual).

## Stack
Flask 3 + psycopg 3 (SQL direto, parametrizado) + Flask-WTF + HTMX local + Chart.js 4.5.1 local + CSS à mão (Glassmorphism claro). Já decidida, não proponha alternativas. Sem ORM, sem alteração de schema. Esta rodada **não usa Chart.js**: o mini-gráfico é CSS.

## Entrega desta rodada — SOMENTE isto

1. **Tabela "Mês a mês"**, num `.card` com título, abaixo dos gráficos. Colunas, nesta ordem: Mês · Receitas · Despesas · Essenciais · Não Essenciais · Saldo · Saldo Acumulado · Taxa de Poupança.
   - **Sempre 12 linhas**, janeiro a dezembro, com nome de mês por extenso vindo de `util.MESES` (inicial maiúscula: é rótulo). Mês sem lançamento mostra R$ 0,00 nas colunas de valor.
   - Saldo = receitas − despesas do mês. Saldo Acumulado = soma dos saldos de janeiro até o mês. Taxa de Poupança = saldo / receitas do mês, em % com uma casa (filtro `numero`); receita zero → "—".
   - No ano corrente, meses posteriores ao atual mostram "—" em Saldo Acumulado e Taxa de Poupança (zeros nas demais). Em ano anterior, todos os 12 meses são calculados.
   - **Linha de totais** (`<tfoot>`): soma de Receitas, Despesas, Essenciais, Não Essenciais e Saldo; Saldo Acumulado = saldo do ano; Taxa de Poupança = taxa anual. Os três últimos têm que ser **idênticos** aos cards Saldo Anual e Taxa de Poupança.
   - Saldo, Saldo Acumulado e Taxa negativos em vermelho; travessão nunca é vermelho.
   - Dados vêm das linhas mensais que `painel_do_ano` já tem — **nenhuma consulta nova** para esta tabela. Cálculo em `Decimal`, em Python, dentro de `main/servico.py`.

2. **Tabela "Despesas por categoria"**, num segundo `.card` abaixo da primeira. Colunas: Categoria · Total · % das despesas.
   - Uma consulta nova sobre `vw_despesas`, agrupada por categoria, no mesmo intervalo de `data` do ano, **só categorias com despesa no ano**, ordem por total decrescente e nome como desempate.
   - % das despesas = total da categoria / despesa anual, uma casa decimal, filtro `numero`. A célula mostra o número e uma **barra horizontal proporcional** ao percentual (largura em `style=` com ponto, como já se faz em `_resultados.html`).
   - Linha de totais com a soma (que deve bater com o card Despesa Anual) e 100,0%.
   - Ano sem despesa: em vez de tabela vazia, uma linha única "Nenhuma despesa em AAAA".

3. **Componente da barra proporcional**: se a barra do resumo por categoria em `_resultados.html` estiver como HTML/CSS inline ou duplicável, extraia para uma macro em `_macros.html` (nome sugerido `barra_pct`) e use-a nos dois lugares — consulta e Visão Anual — sem mudar a aparência da consulta. Se já for macro, só reutilize. Relate qual dos dois casos encontrou.

4. **Celular** (≤ 768px): na tabela mensal ficam visíveis apenas **Mês, Receitas, Despesas e Saldo**; Essenciais, Não Essenciais, Saldo Acumulado e Taxa vão para a linha de apoio, no padrão que as tabelas de consulta já usam. A linha de totais segue a mesma regra. A tabela de categorias cabe inteira; a barra encolhe com a célula. Sem rolagem horizontal em 390px.

5. **CSS**: subseção 5.13.2 (tabelas), seguindo o padrão do arquivo. Tabelas quase opacas dentro do `.card` de vidro, como as demais telas.

## Regras
- Não altere `01_schema.sql`; não crie tabela, view ou índice. Não filtre por `ano_mes`.
- Não mexa em cards, seletor de ano nem gráficos, além de reaproveitar o que `painel_do_ano` já calcula.
- Não use `float` em cálculo; não some em Jinja o que o Python já compôs; não repita no template a fórmula que existe no serviço.
- Não implemente: link de categoria para a consulta, ordenação por cabeçalho, subcategorias, comparação entre anos, exportação. Rodadas futuras.
- Não toque em `lancamentos/`, `configuracoes/` ou `cadastros/` fora do item 3.
- Mantenha os padrões do histórico (seção 6).
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. Login com `zz_teste` no **navegador**, abrir `/` no ano corrente: duas tabelas abaixo dos gráficos, 12 linhas na primeira, "—" de outubro a dezembro em Saldo Acumulado e Taxa.
2. Conferir e reportar: totais de Receitas, Despesas, Essenciais e Não Essenciais da linha de totais = cards correspondentes; Saldo Acumulado de setembro = Saldo Acumulado do total = card Saldo Anual; Taxa do total = card Taxa de Poupança; soma da coluna Total da segunda tabela = card Despesa Anual; soma dos percentuais entre 99,9 e 100,1.
3. Conferir uma linha mensal (março, por exemplo) contra a consulta de despesas e a página de receitas filtradas no mês.
4. Confirmar que o resumo por categoria da consulta continua igual antes e depois do item 3 (visual e valores).
5. Celular em 390px: 4 colunas visíveis na tabela mensal, linha de apoio com as outras quatro, barras da segunda tabela legíveis, `scrollWidth = clientWidth`.
6. Relate: arquivos criados/alterados, resultado de cada validação e a lista de **pontos que precisou interpretar**.