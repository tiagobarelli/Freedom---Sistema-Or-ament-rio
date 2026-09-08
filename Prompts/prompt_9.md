# Freedom — Rodada 10: gráficos da Visão Anual (Chart.js)

## Contexto
Leia antes de começar: `docs/Freedom - Estrutura do Banco de Dados.md`, `docs/Freedom - Histórico e Estado do Projeto.md` (o arquivo agora existe em docs/; onde ele disser que `/` é "lugar reservado ao dashboard", ignore — a rodada 9 já entregou a Visão Anual), `freedom/main/servico.py`, `freedom/main/routes.py`, `templates/main/index.html`, `static/css/app.css` (seção 5.13) e `freedom/util.py`.

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres em Docker. Há dado real no banco: nenhuma linha que você não criou pode ser apagada; faxina de teste sempre por id. Login de teste: usuário `tiago`, senha na variável `senha_teste` do `.env`. **Esta rodada exige validação em navegador real** (canvas e redimensionamento não se medem por HTTP).

Estado atual da Visão Anual: seletor de ano por GET (`/?ano=`), 13 cards compostos em `main/servico.py` a partir de duas consultas agregadas por mês (despesas: total, essencial, não essencial; receitas: total) mais a consulta do pico. O divisor de meses (jan até o mês corrente no ano atual; 12 nos anteriores) já está calculado lá.

## Stack
Flask 3 + psycopg 3 (SQL direto, parametrizado) + Flask-WTF + HTMX local + CSS à mão (Glassmorphism claro) + **Chart.js 4, arquivo local**. Já decidida, não proponha alternativas. Sem CDN, sem bundler, sem ORM, sem alteração de schema.

## Entrega desta rodada — SOMENTE isto

1. **Chart.js local**: baixe o build UMD da versão 4.x estável mais recente para `static/js/chart.umd.js`, registre a versão exata no `README.md` (seção de dependências de front-end, ao lado do HTMX) e carregue-o apenas na Visão Anual, não em `layout_app.html`.

2. **Dados para os gráficos, no servidor.** Em `main/servico.py`, uma função monta a estrutura dos quatro gráficos a partir das mesmas linhas mensais que já alimentam os cards (não repita as consultas), mais **uma** consulta nova: despesas não essenciais (essencialidade efetiva de `vw_despesas`) agrupadas por mês e `prioridade`, no mesmo intervalo de `data` do ano. O eixo X de todos os gráficos são os meses do divisor (jan..mês corrente no ano atual; jan..dez nos anteriores), rótulos abreviados em português vindos de `util.MESES` (ou tupla irmã), meses sem lançamento valem 0. O saldo acumulado é calculado em Python com `Decimal`; a conversão para número JSON acontece uma única vez, na serialização. A rota passa a estrutura ao template, que a embute em `<script type="application/json" id="dados-graficos">` via `tojson`. Nenhum número financeiro é calculado em JavaScript.

3. **Quatro gráficos**, abaixo da grade de cards, nesta ordem, cada um num `.card` com título:
   - **Receitas × Despesas** — barras agrupadas por mês, duas séries.
   - **Despesas Essenciais × Não Essenciais** — linhas: Essenciais, Não Essenciais, Total (valor do mês, não acumulado). Total em traço mais grosso ou tracejado para se distinguir.
   - **Poupança acumulada** — linha do saldo acumulado (receitas − despesas, somado mês a mês desde janeiro) com área preenchida e linha do zero visível; trecho negativo deve ficar visualmente evidente pelo eixo, sem truques de cor por ponto.
   - **Não essenciais por prioridade** — barras empilhadas por mês, uma série por prioridade (1 a 4), rótulos "P1 – mais importante" … "P4 – menos importante"; série "Sem prioridade" só quando houver despesa não essencial com `prioridade` NULL no ano.

4. **JavaScript próprio** em `static/js/visao_anual.js` (sem inline no template além do JSON): lê o JSON, lê as cores das variáveis CSS com `getComputedStyle` (não repita hex no JS), formata eixos e tooltips em pt-BR com `Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'})`, cria os quatro gráficos com `maintainAspectRatio: false`. Cada canvas fica dentro de um contêiner com altura fixa em CSS (~320px desktop, ~260px celular) para o Chart.js não crescer sem limite. Ano sem lançamento: gráficos renderizam com zeros, sem erro no console.

5. **Layout**: grade de gráficos em 2 colunas acima de 1100px, 1 coluna abaixo; nova subseção em 5.13 seguindo o padrão. Vidro só na moldura (`.card`); a área do gráfico quase opaca, como tabelas e formulários.

6. **Limpeza pendente**: as telas de consulta de despesas e de receitas imprimem percentual com `'%.1f'|format` (ponto). Troque pelo mesmo caminho que a Visão Anual usa (`formatar_numero`, vírgula), sem mudar mais nada nessas telas. Relate os arquivos tocados.

## Regras
- Não altere `01_schema.sql`; não crie tabela, view ou índice. Não filtre por `ano_mes`.
- Não mexa nos 13 cards nem no seletor de ano, além de reaproveitar as linhas mensais que já existem.
- Não use CDN, não use `float` em cálculo (só na serialização final), não calcule soma, média ou acumulado em JS, não use plugin de Chart.js além do núcleo.
- Não implemente: filtro por categoria, comparação entre anos, clique no gráfico levando à consulta, gráfico por categoria, deflação por IPCA, exportação de imagem. Rodadas futuras.
- Não toque em `lancamentos/`, `configuracoes/` ou `cadastros/` fora do item 6.
- Mantenha os padrões de código listados no histórico.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. Login com `zz_teste` no **navegador**, abrir `/` no ano corrente: 4 gráficos abaixo dos cards, eixo X de janeiro ao mês corrente, console sem erro.
2. Conferir números: soma das barras de despesa do gráfico 1 = card Despesa Anual; último ponto do gráfico 3 = card Saldo Anual; soma da pilha do gráfico 4 no ano = card Despesas Não Essenciais (se houver "Sem prioridade", ela entra na soma). Reporte os três valores.
3. Tooltip em pt-BR (`R$ 1.234,56`) nos quatro gráficos.
4. `/?ano=2019` (sem dado): gráficos com zeros, eixo X com 12 meses, sem erro.
5. Celular ≤ 768px no navegador: 1 coluna, sem rolagem horizontal, gráficos legíveis; redimensionar a janela do desktop para o celular e voltar não deixa canvas com tamanho errado.
6. Consulta e receitas mostram percentual com vírgula depois do item 6, e continuam 200.
7. Relate: versão do Chart.js, arquivos criados/alterados, resultado de cada validação e a lista de **pontos que precisou interpretar**.