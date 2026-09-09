# Freedom — Rodada 13: detalhamento por categoria na Visão Mensal (+ três limpezas)

## Contexto
Leia antes de começar: `docs/Freedom - Histórico e Estado do Projeto.md` (consolidado até a rodada 12 — seção 6 "Padrões" é obrigatória), `docs/Freedom - Estrutura do Banco de Dados.md`, `freedom/main/servico_mensal.py`, `freedom/main/routes.py`, `templates/main/mensal.html`, `freedom/lancamentos/consulta.py` e `freedom/lancamentos/despesas.py` (como a consulta chama a edição ciente da origem e como a edição volta para onde veio), `freedom/lancamentos/servico.py` (`so_fragmento`, `id_valido`), `freedom/util.py`, `templates/lancamentos/_linha_consulta.html` (linha de apoio dentro da célula) e `static/css/app.css` (5.13.2, 5.14, `.tabela-caixa`, seção 7).

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres em Docker. Há dado real (725 despesas, 61 receitas, 2026): nenhuma linha que você não criou pode ser apagada; se editar uma despesa real na validação, restaure o valor original pelo mesmo caminho e relate o id. Login de teste: `zz_teste`, senha na variável `senha_teste` do `.env`. Validação em **navegador real**.

Estado relevante: a Visão Mensal (`/mensal?ano=&mes=&ordem=`) tem seis cards e três tabelas compostas de uma consulta agrupada por (categoria, pessoa). A tabela "Despesas por categoria" lista só categorias com despesa no mês, na ordem escolhida.

## Stack
Flask 3 + psycopg 3 (SQL direto, parametrizado) + Flask-WTF + HTMX 2.0.4 local + CSS à mão (Glassmorphism claro). Já decidida, não proponha alternativas. Sem ORM, sem alteração de schema, sem Chart.js.

## Entrega desta rodada — SOMENTE isto

1. **Linha expansível** na tabela "Despesas por categoria" da Visão Mensal. Cada linha de categoria é clicável (linha inteira, cursor de ponteiro, indicador de seta que gira quando aberta, `aria-expanded`, acessível por teclado com Enter/Espaço). O primeiro clique faz um GET HTMX a `/mensal/categoria/<id>?ano=&mes=` e insere a resposta logo abaixo (`hx-swap="afterend"`, alvo a própria linha). O segundo clique **remove** a linha de detalhe sem nova requisição (pode ser um `hx-on` ou um JS mínimo no padrão do menu; escolha e relate). Várias categorias podem estar abertas ao mesmo tempo. Mudar ano/mês/ordem recarrega a página e fecha tudo — comportamento aceito.

2. **Rota de fragmento** `main.detalhe_categoria` (`/mensal/categoria/<int:categoria_id>`), GET, só orquestra; leitura em `servico_mensal.py`. Sem cabeçalho `HX-Request`, redireciona para `/mensal` com os mesmos `ano`, `mes` e `ordem` (não existe versão de página inteira). `ano`/`mes` inválidos seguem a regra da tela (caem no mês corrente). Categoria inexistente → 404. Consulta sobre `vw_despesas` no intervalo de `data` do mês, filtrando `categoria_id`, ordenada por subcategoria (nome, chave alfabética pt-BR já existente), depois `data`, depois `id`.

3. **Conteúdo do detalhe**: uma `<tr class="linha-detalhe">` com `colspan` total, contendo uma tabela interna **agrupada por subcategoria**: para cada subcategoria, uma linha de subtotal (nome, quantidade de lançamentos, valor) seguida das linhas dos lançamentos com Data (dd/mm) · Descrição · Pessoa · Valor · ação **Editar**. Rodapé da tabela interna com o total da categoria — que tem que ser idêntico ao "Total no mês" da linha que foi expandida. Categoria sem lançamento no período (URL montada à mão) → linha "Nenhum lançamento".

4. **Editar**: o link leva a `lancamentos.despesa_editar` da mesma forma que a consulta faz (origem/retorno pelo mecanismo que já existe e é validado por `destino_interno`), com retorno para `/mensal?ano=&mes=&ordem=` do período em exibição. Ao voltar, a página recarrega com cards e tabelas atualizados; a categoria não precisa vir reaberta. Se o mecanismo atual de origem não aceitar querystring completa, adapte-o em `despesas.py` com a menor mudança possível e relate.

5. **Celular** (≤ 768px): na tabela interna ficam visíveis Data · Descrição · Valor; Pessoa vai para a linha de apoio dentro da célula de Descrição (a coluna principal aqui é larga — variante da consulta, não a `<tr class="linha-apoio">`). O botão Editar vira ícone ou fica no fim da linha de apoio; sem rolagem horizontal na página. A tabela interna herda o visual quase opaco e fica visivelmente recuada/aninhada em relação à tabela externa.

6. **Limpeza 1 — `so_fragmento`**: promova de `lancamentos/servico.py` para `util.py` (sem underscore, se houver), atualize os pontos de uso e remova o `import request` de `lancamentos/servico.py` se ele só servia a isso. Esta é a terceira tela que precisa dele.

7. **Limpeza 2 — favicon**: acabe com o 404 em toda tela. Um `static/favicon.svg` simples (letra F ou um círculo na cor primária, sem marca de terceiros) referenciado em `base.html`. Nada mais.

8. **Limpeza 3 — collation do desempate na Visão Anual**: rode `SHOW lc_collate;` (e `SELECT datcollate FROM pg_database WHERE datname = current_database();`). Se o desempate por nome em `_tabela_categorias` da Anual (`ORDER BY` no SQL) puder pôr "Água e esgoto" depois de "Zoo", alinhe com a Mensal: ordene em Python com a mesma chave alfabética (promovida para `util.py`), sem mudar o SQL. Se a collation já for pt-BR/unicode e o resultado for igual, só relate e não mude nada.

## Regras
- Não altere `01_schema.sql`; não crie tabela, view ou índice. Não filtre por `ano_mes`.
- Não implemente: detalhe na Visão Anual, detalhe por pessoa ou na matriz, exclusão a partir do detalhe, paginação do detalhe, edição em linha. Rodadas futuras.
- Não renomeie `.filtro-ano` nem unifique `.tabela--categorias`/`.tabela--mes`: é dívida conhecida, fica para a rodada que reabrir o CSS da Anual.
- Não toque em `configuracoes/` ou `cadastros/`; em `lancamentos/` só o necessário para os itens 4 e 6.
- Mantenha os padrões do histórico (seção 6), inclusive `<template>` em resposta OOB que comece com `<tr>` (aqui não há OOB, mas confira se a inserção `afterend` de um `<tr>` funciona no Edge com a resposta começando por `<tr>`; se o HTMX descartar a linha, envolva em `<template>` ou use `<tbody>` e relate).
- Cálculo em `Decimal`; nada somado em Jinja.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. Login `zz_teste` no **navegador**, `/mensal?ano=2026&mes=7`: expandir "Comodidades" — grupos por subcategoria, soma dos subtotais = rodapé = R$ 12.440,93 da linha. Reportar os subtotais.
2. Abrir uma segunda categoria com a primeira aberta; fechar a primeira; reabrir. Repetir por teclado (Tab até a linha, Enter). Console sem erro.
3. Clicar em Editar num lançamento de julho, alterar a descrição, salvar: volta para `/mensal?ano=2026&mes=7&ordem=total`, a descrição alterada aparece ao reexpandir. Restaurar a descrição original pelo mesmo caminho. Reportar o id.
4. Abrir `/mensal/categoria/<id>?ano=2026&mes=7` direto na barra de endereço → redirect para `/mensal` com os parâmetros. `/mensal/categoria/999999` via HTMX → 404 sem 500. Categoria válida num mês em que ela não tem despesa → "Nenhum lançamento".
5. Celular em 390px: expandir uma categoria — três colunas visíveis, pessoa na linha de apoio, editar acessível, `scrollWidth = clientWidth`.
6. Favicon carregando em `/`, `/mensal`, `/login` (sem 404 no console).
7. Consulta, receitas e configurações continuam 200 depois da promoção de `so_fragmento`; voltar do histórico do navegador continua devolvendo página inteira.
8. Resultado do item 8 (collation e o que mudou, se mudou), com a ordem das categorias da Anual antes e depois em `ordem` por total com empate sintético, se necessário.
9. Relate: arquivos criados/alterados, mecanismo escolhido para fechar a linha, resultado de cada validação e a lista de **pontos que precisou interpretar**.