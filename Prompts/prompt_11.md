# Freedom — Rodada 12: Visão Mensal (nova página do Painel)

## Contexto
Leia antes de começar: `docs/Freedom - Histórico e Estado do Projeto.md` (consolidado até a rodada 10; as rodadas 11 e 12 ainda não estão nele — o estado abaixo prevalece), `docs/Freedom - Estrutura do Banco de Dados.md`, `freedom/main/servico.py` e `freedom/main/routes.py` (Visão Anual: seletor de ano, `anos_com_lancamento`, `_totais_do_ano`, `_fracao`, `_tabela_categorias`), `templates/main/index.html`, `templates/_macros.html` (`barra_pct`, `reais`), `templates/layout_app.html` e `static/css/app.css` (5.13, componente `.barra`, `.tabela-caixa`, seção 7).

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres em Docker. Há dado real (725 despesas, 61 receitas, 2026): nenhuma linha que você não criou pode ser apagada. Login de teste: `zz_teste`, senha na variável `<VARIÁVEL>` do `.env`. Validação em **navegador real**.

Estado relevante: a Visão Anual (`/`) já tem seletor de ano por GET com recarga inteira, cards, gráficos e duas tabelas (mês a mês e por categoria, esta com `barra_pct`). A rodada 11 criou `MESES_CURTOS` em `util.py` e a variante de linha de apoio `<tr class="linha-apoio">` para tabelas cuja coluna principal é estreita.

## Stack
Flask 3 + psycopg 3 (SQL direto, parametrizado) + Flask-WTF + HTMX local + CSS à mão (Glassmorphism claro). Já decidida, não proponha alternativas. Sem ORM, sem alteração de schema, **sem Chart.js nesta página**.

## Entrega desta rodada — SOMENTE isto

1. **Nova rota `/mensal`** no blueprint `main`, item de menu **"Visão Mensal"** no grupo Painel, logo abaixo de "Visão Anual". Destaque do menu não pode acender "Visão Anual" junto (regra do caminho mais específico já existe). Leituras e composição em um módulo novo `freedom/main/servico_mensal.py`; a rota só orquestra. Reaproveite `anos_com_lancamento`, `_fracao` e o que mais de `main/servico.py` servir, promovendo (sem underscore) o que virar compartilhado entre os dois módulos — e relate.

2. **Seletores** no topo, na mesma barra de filtros da Visão Anual, todos GET com recarga inteira e submissão em `onchange`, como o seletor de ano já faz: **Ano** (anos com lançamento), **Mês** (sempre os 12, por extenso, de `util.MESES`) e **Ordem** ("Maior gasto" = `ordem=total`, padrão; "Nome" = `ordem=nome`). Padrão: mês corrente. `ano` ou `mes` ausente, inválido ou fora do previsto cai no mês corrente sem erro; `ordem` inválida cai em `total`. Subtítulo com o período, no estilo "fevereiro de 2026" (minúscula: está dentro de frase).

3. **Seis cards**, nesta ordem: Receitas · Despesas · Saldo · Taxa de Poupança · Essenciais · Não Essenciais. Mesmas regras da Visão Anual: essencialidade **efetiva** de `vw_despesas`; Saldo e Taxa negativos em vermelho no `<span>`; Taxa = saldo / receitas, uma casa, filtro `numero`; receitas zero → "—"; travessão nunca vermelho. Grade responsiva já existente dos cards (aqui podem ser 3 por linha no desktop, se a grade permitir sem nova regra; senão, use a de 4).

4. **Tabela "Despesas por categoria"**: Categoria · Total no mês · % do total (com `barra_pct`). **Só categorias com despesa no mês.** Ordem conforme `ordem` (total decrescente com nome como desempate, ou nome). Rodapé com total e 100,0%, sem barra.

5. **Tabela "Total por pessoa"**: Pessoa · Total no mês · % do total (com `barra_pct`). Só pessoas com despesa no mês, total decrescente, nome como desempate. Rodapé com total e 100,0%.

6. **Matriz "Pessoa × Categoria"**: linhas = as mesmas categorias da tabela 4, **na mesma ordem**; colunas = as mesmas pessoas da tabela 5, **na mesma ordem**, mais uma coluna **Total** à direita; rodapé com o total de cada pessoa e o total geral. Célula sem despesa mostra R$ 0,00 em cor secundária (atenuada), para os valores reais saltarem. **Exceção deliberada ao padrão da app**: esta tabela tem rolagem horizontal **interna** (na `.tabela-caixa`) em qualquer largura em que não caiba, com a **primeira coluna fixa** (`position: sticky; left: 0`) para a categoria não sumir ao rolar. A página em si continua sem rolagem horizontal.

7. **Consultas** (todas por intervalo de `data`: primeiro dia do mês até o primeiro dia do mês seguinte, nunca `ano_mes`):
   - despesas do mês: total, essencial, não essencial (cards);
   - receitas do mês: total (cards);
   - despesas agrupadas por **(categoria, pessoa)** sobre `vw_despesas` — **uma só consulta** de onde saem as tabelas 4, 5 e 6, compostas em Python com `Decimal` (o conjunto é pequeno e completo, mesma exceção da Visão Anual). O total da matriz tem que ser idêntico ao card Despesas; se não bater, é bug, não arredondamento.

8. **Mês sem despesa**: cards com R$ 0,00 e "—" onde couber; no lugar das três tabelas, uma linha única "Nenhuma despesa em <mês> de <ano>". Mês sem receita mas com despesa: cards normais, Taxa "—".

9. **Celular** (≤ 768px): cards em 1 coluna; tabelas 4 e 5 cabem inteiras (3 colunas) sem esconder nada; matriz com a rolagem interna do item 6; seletores empilhados. `scrollWidth = clientWidth` na página.

10. **CSS**: subseção 5.14 (Visão Mensal) com só o que a Anual não cobre — reaproveite `.card`, `.barra`, `.tabela-caixa`, a barra de filtros e a grade de cards. A regra de primeira coluna fixa é um modificador da `.tabela-caixa` (ex.: `.tabela-caixa--fixa-primeira`), reutilizável.

## Regras
- Não altere `01_schema.sql`; não crie tabela, view ou índice. Não filtre por `ano_mes`.
- Não mexa na Visão Anual além de promover helpers compartilhados.
- Não use `float` em cálculo; não some em Jinja o que o Python compôs; não repita no template fórmula que existe no serviço; nada de Chart.js nem `{% block scripts %}` nesta página.
- Não implemente: gráfico, receitas por fonte, comparação com o mês anterior, link para a consulta filtrada, orçamento/meta, navegação por setas entre meses. Rodadas futuras.
- Não toque em `lancamentos/`, `configuracoes/` ou `cadastros/`.
- Mantenha os padrões do histórico (seção 6) e as convenções da rodada 11 descritas no contexto.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. Login com `zz_teste` no **navegador**, abrir `/mensal`: mês corrente pré-selecionado, item "Visão Mensal" destacado sozinho, console sem erro.
2. `/mensal?ano=2026&mes=2`: reportar os seis cards e conferir Despesas, Essenciais e Não Essenciais contra a consulta de despesas filtrada em fevereiro/2026, e Receitas contra a página de receitas no mesmo mês.
3. Reportar: soma da tabela 4 = soma da tabela 5 = total geral da matriz = card Despesas; total de cada pessoa no rodapé da matriz = coluna Total da tabela 5; coluna Total da matriz = Total no mês da tabela 4, linha a linha.
4. `ordem=nome`: tabela 4 e linhas da matriz em ordem alfabética idêntica; tabela 5 inalterada. Voltar a `ordem=total` e conferir o desempate por nome em duas categorias de mesmo total, se houver.
5. `?mes=13`, `?mes=abc`, `?ano=1999`, `?ordem=x`: 200 e comportamento do item 2.
6. Um mês sem despesa (dezembro/2026, se ainda estiver vazio): cards zerados, Taxa "—", linha "Nenhuma despesa em dezembro de 2026".
7. Celular em 390px: cards em 1 coluna, tabelas 4 e 5 sem rolagem, matriz com rolagem interna e primeira coluna fixa ao rolar, página com `scrollWidth = clientWidth`. Também em 900px (tablet): a matriz rola internamente se não couber.
8. Relate: arquivos criados/alterados, helpers promovidos, resultado de cada validação e a lista de **pontos que precisou interpretar**.