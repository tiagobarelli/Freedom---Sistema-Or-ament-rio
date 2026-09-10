# Freedom — Rodada 16: acompanhamento do orçamento (+ três limpezas de CSS)

## Contexto
Leia antes de começar: `docs/Freedom - Histórico e Estado do Projeto.md` (consolidado até a rodada 15 — seção 6 "Padrões" é obrigatória), `docs/Freedom - Estrutura do Banco de Dados.md` (`tb_orcamento_meses`, `tb_orcamentos`), `freedom/orcamento/` inteiro e `templates/orcamento/`, `freedom/main/servico_mensal.py` (cubo e realizado por subcategoria no mês), `freedom/util.py`, `templates/_macros.html` (`barra_pct`), `static/css/app.css` (5.13, 5.13.2, 5.15, seção 7 e o comentário sobre `letter-spacing` em `.tabela--detalhe`).

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres 16 em Docker. **Suba o servidor com `--debug`** e reinicie depois de mexer em Python ou template antes de qualquer validação (duas rodadas já perderam tempo com isso). Dado real: 1.770 despesas e 145 receitas (2025 e 2026), orçamento de **setembro/2026 aberto com 67 linhas** — não apague linhas do orçamento que não criou; edições de teste são revertidas pelo mesmo caminho. Login `zz_teste`, senha na variável `senha_teste` do `.env`. Validação em **navegador real, desktop**; celular só não pode quebrar.

Estado: `/orcamento` tem seletor ano/mês (só meses com orçamento), criação, edição em linha, receita planejada, encerrar/reabrir/excluir. A tabela de montagem tem Subcategoria · Planejado · Média 12m · Realizado anterior, agrupada por categoria com subtotais e rodapé de quatro linhas.

## Stack
Flask 3 + psycopg 3 (SQL direto, parametrizado) + Flask-WTF + HTMX 2.0.4 local + CSS à mão. Já decidida, não proponha alternativas. Sem ORM, **sem alteração de schema**, sem Chart.js (barras são `barra_pct`).

## Entrega desta rodada — SOMENTE isto

1. **Seletor de modo** na barra de filtros, GET com recarga inteira como os demais: **Montagem | Acompanhamento** (`modo=montagem|acompanhamento`). Padrão: Acompanhamento quando o mês tem alguma despesa lançada, Montagem quando não tem. Mês encerrado abre em Acompanhamento e a Montagem continua disponível, só leitura, como já é.

2. **Seletor de período**, visível só em Acompanhamento: **Mês | Acumulado no ano** (`periodo=mes|acumulado`, padrão `mes`).
   - **Mês**: planejado = linhas do mês; realizado = `vw_despesas` no intervalo de `data` do mês, por `subcategoria_id`.
   - **Acumulado**: considera os **meses do mesmo ano que têm orçamento, do primeiro até o mês selecionado** (setembro/2026 é o primeiro; janeiro a agosto não entram em nada). Planejado acumulado = soma das linhas desses meses; realizado acumulado = soma das despesas nos intervalos desses meses. Meses sem orçamento no meio da sequência não entram nem no planejado nem no realizado. Uma subcategoria que tem linha em alguns desses meses e não em outros soma o planejado que existe e o realizado de todos os meses considerados — a diferença mostra o efeito.

3. **Cards do acompanhamento** (substituem o cabeçalho numérico da montagem quando `modo=acompanhamento`): Receitas · Despesas · Poupança · Taxa de poupança, cada um com **realizado** em destaque e **planejado** na linha de apoio ("planejado R$ X"); o card Despesas traz também o % consumido, colorido pela regra do item 5. Receita realizada vem de `vw_receitas` no(s) mesmo(s) intervalo(s). No acumulado, todos os quatro são acumulados. Negativos em vermelho no `<span>`; "—" nunca vermelho.

4. **Tabela de acompanhamento**, agrupada por categoria como a montagem, com **subtotais por categoria** e rodapé: Subcategoria · Planejado · Realizado · Diferença (planejado − realizado; negativa = estouro) · **% consumido** (realizado ÷ planejado, uma casa, com `barra_pct` limitada visualmente a 100% e o número podendo passar de 100). Planejado zero: realizado zero → "—"; realizado > 0 → "—" no número, barra cheia, tratado como estouro. Mesmas regras nos subtotais e no rodapé. Sem colunas de edição (edição é da Montagem).

5. **Cor do % consumido** (célula, barra e card Despesas): abaixo de 90% neutro; **de 90% a 100% âmbar**; **acima de 100% vermelho**. Âmbar é variável CSS nova na seção 1 (não existe cor de alerta hoje — confira; se existir, reuse). A regra vive em uma função Python que devolve a classe (`ok`/`alerta`/`estouro`), usada por célula, subtotal, rodapé e card; nada decidido em Jinja.

6. **Bloco "Fora do orçamento"**, abaixo da tabela: subcategorias **sem linha em nenhum dos meses considerados** que tiveram despesa no período, agrupadas por categoria, com Subcategoria · Realizado e um total. Esse realizado **entra** no rodapé da tabela principal e nos cards (o total realizado tem que ser o total do período, não só o orçado); o rodapé mostra em linha de apoio quanto dele é "fora do orçamento". Bloco ausente quando vazio.

7. **Conferência estrutural**: o total realizado do acompanhamento no modo Mês tem que ser **idêntico** ao card Despesas da Visão Mensal do mesmo mês — mesma view, mesmo intervalo. Se não bater, é bug.

8. **Limpeza 1**: remover de `app.css` os seletores sem uso listados na rodada 14 (`.campo__obrigatorio`, `.card__texto`, `.linha-flex`, `.pilha-p`, `.negrito`, `.mt-2`, `.mb-4`), conferindo por busca antes de cada remoção, e remover a classe morta `.tabela--expansivel` de `mensal.html`.

9. **Limpeza 2**: dar `.tabela--resumo--estreita` também à tabela por categoria da Visão Anual. **Esta muda pixel de propósito** (some a rolagem interna de ~30px entre 768 e 1030px); capture a Anual em 900px antes e depois e reporte que a diferença está restrita àquela tabela.

10. **Limpeza 3**: declarar o `letter-spacing` explicitamente em `.tabela--detalhe th` com o valor que hoje chega por herança, e trocar o comentário da rodada 14 por um que diga que é intencional. Capturas da Mensal em 1440 e 390 com Comodidades aberta: SHA idêntico.

## Regras
- Não altere schema. Não filtre por `ano_mes` das views; intervalos de `data`. Realizado sempre da view, nunca gravado.
- Não mexa na Montagem além de mover o cabeçalho numérico para depender do modo. Não implemente: gráfico do acompanhamento, comparação com o mês anterior, orçamento por pessoa, alerta por e-mail, link para a consulta, integração dos painéis com o orçamento. Rodadas futuras.
- Não toque em `lancamentos/`, `cadastros/`, `configuracoes/`; em `main/` só a classe da limpeza 2 e a remoção da limpeza 1.
- `Decimal` em tudo; composição em Python sobre conjuntos pequenos e completos; nada somado em Jinja; nada decidido em Jinja (cores, "—", estouro).
- Mantenha os padrões do histórico (seção 6).
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. `--debug` ligado. `/orcamento?ano=2026&mes=9` abre em Acompanhamento (setembro tem despesa). Reportar os quatro cards e conferir: Despesas realizado = card Despesas de `/mensal?ano=2026&mes=9`; Receitas realizado = card Receitas da Mensal; planejados = os da Montagem.
2. Reportar três linhas: uma abaixo de 90%, uma entre 90 e 100 (se não houver, uma sintética via função pura), uma acima de 100 — com a classe de cor aplicada em célula, barra e, se for a maior categoria, no subtotal. Uma linha com planejado zero e realizado > 0, se existir.
3. Bloco "Fora do orçamento": listar as subcategorias e o total; mostrar que rodapé − fora do orçamento = soma das linhas orçadas.
4. `periodo=acumulado` em setembro = idêntico a `periodo=mes` (é o primeiro mês). Para exercitar a soma de vários meses sem criar dado: função pura com dois meses sintéticos, um deles sem linha para uma subcategoria — reportar planejado, realizado e diferença dessa subcategoria.
5. Montagem continua funcionando: editar uma linha e voltar ao valor, alternar modo, mês encerrado abre em Acompanhamento (encerre e reabra setembro no fim; deixe aberto).
6. Limpeza 1: grep de cada seletor antes da remoção; console e telas sem regressão visual (capturas da Anual, Mensal e Orçamento antes/depois com SHA — a Anual em 900px é a única que pode diferir, pela limpeza 2, e só naquela tabela).
7. Limpeza 3: SHA idêntico nas duas capturas da Mensal com detalhe aberto.
8. Celular 390px em `/orcamento` nos dois modos: sem rolagem externa, tabela rolando por dentro, nada quebrado.
9. Relate: arquivos criados/alterados, resultado de cada validação, a variável de cor criada ou reusada, e a lista de **pontos que precisou interpretar**.