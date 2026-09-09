# Freedom — Rodada 15: Orçamento — schema e montagem do mês

## Contexto
Leia antes de começar: `docs/Freedom - Histórico e Estado do Projeto.md` (consolidado até a rodada 12; rodadas 13 e 14 ainda não estão nele — o estado abaixo prevalece), `docs/Freedom - Estrutura do Banco de Dados.md` (seção `tb_orcamentos`), `db/init/01_schema.sql`, `freedom/configuracoes/` inteiro (rotas, forms, serviço, templates — é o padrão de edição em linha, exclusão física e fragmentos HTMX que esta tela repete), `freedom/main/servico_mensal.py` (intervalo de mês, cubo, chave alfabética), `freedom/util.py` (`so_fragmento`, `converter_valor`, `MESES`), `templates/_macros.html` (`combobox`, `reais`, `barra_pct`), `templates/main/mensal.html` (seletor de mês) e `static/css/app.css`.

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres 16 em Docker (`freedom_postgres`), collation `en_US.utf8`. Há dado real: despesas e receitas de 2025 e 2026. Nenhuma linha que você não criou pode ser apagada. Login de teste: `zz_teste`, senha na variável `senha_teste` do `.env`. Validação em **navegador real, desktop**; o celular só não pode quebrar.

Estado relevante: `tb_orcamentos` existe desde a rodada 1, **vazia e nunca usada**, com `categoria_id`. Decidiu-se orçar por **subcategoria**, com um registro por mês que carrega a receita planejada e o encerramento. `so_fragmento` já está em `util.py` (rodada 13); a Visão Mensal tem seletor ano/mês por GET com recarga inteira; configurações têm edição em linha via HTMX com exclusão física.

## Stack
Flask 3 + psycopg 3 (SQL direto, parametrizado) + Flask-WTF + HTMX 2.0.4 local + CSS à mão (Glassmorphism claro). Já decidida, não proponha alternativas. Sem ORM, sem migrações, sem Chart.js.

## Entrega desta rodada — SOMENTE isto

### A. Schema (única mudança de DDL desde a rodada 7)

1. Em `db/init/01_schema.sql`, de forma **idempotente e segura para re-executar num banco com dados** (`ADD COLUMN IF NOT EXISTS`, `DROP COLUMN IF EXISTS`, `DO $$ ... IF NOT EXISTS (constraint) ... $$`; **nunca `DROP TABLE`**):
   - Nova tabela `tb_orcamento_meses`: `ano_mes DATE PRIMARY KEY` com CHECK dia 1; `receita_planejada NUMERIC(12,2) NOT NULL DEFAULT 0` CHECK `>= 0`; `criado_em TIMESTAMPTZ NOT NULL DEFAULT now()`; `encerrado_em TIMESTAMPTZ` (nulo = aberto); `observacoes TEXT`. Comentários em todas as colunas, no padrão do arquivo.
   - `tb_orcamentos` passa a ter `subcategoria_id INT NOT NULL REFERENCES tb_subcategorias ON DELETE RESTRICT` e `ano_mes DATE NOT NULL REFERENCES tb_orcamento_meses (ano_mes) ON DELETE RESTRICT`; `categoria_id` e a UNIQUE antiga saem; nova UNIQUE `(subcategoria_id, ano_mes)`; `valor_planejado` continua `>= 0`. Como a tabela está vazia, a troca é de coluna, sem migração de dados — mas o script tem que funcionar também num banco onde ela já esteja no formato novo.
   - Atualizar comentários, a seção de "decisões de desenho" no topo do arquivo e o diagrama/tabela em `docs/Freedom - Estrutura do Banco de Dados.md` (arquivo completo, coerente com o DDL — inclusive a linha "Realizado vs. orçado" da tabela de relatórios).
   - Regra de negócio **na aplicação, não no banco** (documentar no `.md` como as outras): mês encerrado não recebe UPDATE/INSERT/DELETE em suas linhas nem na receita; reabrir só é permitido se não existir `tb_orcamento_meses` com `ano_mes` posterior.

### B. Blueprint `orcamento` (prefixo `/orcamento`, item "Orçamento" no grupo Painel, abaixo de "Visão Mensal")

2. **Seletor** ano/mês por GET com recarga inteira, igual à Mensal, mas as opções de mês são apenas os que têm orçamento; padrão: o mês corrente se tiver orçamento, senão o orçamento mais recente, senão a tela vazia com o botão de criar. Um controle separado permite escolher **qual mês criar**: o corrente ou qualquer futuro que ainda não tenha orçamento (meses passados não são criáveis).

3. **Criar orçamento de <mês>** (POST, CSRF): grava `tb_orcamento_meses` e as linhas sugeridas em uma transação:
   - Se existir orçamento do **mês imediatamente anterior**, copia as subcategorias e os `valor_planejado` dele, e a `receita_planejada`.
   - Senão, uma linha por **subcategoria ativa com despesa nos 12 meses fechados anteriores** ao mês (para set/2026: set/2025 a ago/2026, por intervalo de `data`), com `valor_planejado` = soma dos 12 meses ÷ 12 (Decimal, duas casas, arredondamento `ROUND_HALF_UP`), e `receita_planejada` = média das receitas dos mesmos 12 meses.
   - Mês que já tem orçamento → erro de tela legível, nunca 500 (a PK garante; trate `UniqueViolation` como o projeto já faz).

4. **Tela do mês aberto**: cabeçalho com o período ("setembro de 2026", minúscula), estado (Aberto), **receita planejada** editável em linha; tabela agrupada por **categoria** (subtotal por categoria; ordem por nome com a chave alfabética já existente — promova-a para `util.py` agora que uma terceira tela precisa), linhas por subcategoria com as colunas: Subcategoria · **Planejado** (editável em linha) · Média 12m · Realizado no mês anterior · ação Excluir. Média 12m e Realizado anterior são **referência calculada ao vivo** de `vw_despesas`, nunca gravadas. Rodapé: total planejado, receita planejada, **poupança planejada** (receita − total) e **taxa de poupança planejada** (%, "—" se receita zero, vermelho se negativa, no `<span>`).
   - Edição em linha e exclusão de linha via HTMX, no padrão de configurações (fragmentos, `<template>` onde a resposta começar com `<tr>`, `HX-Retarget` quando o subtotal/rodapé precisar atualizar — o rodapé e o subtotal da categoria **sempre** mudam com a edição, então devolva o bloco necessário).
   - **Adicionar linha**: `combobox` das subcategorias **ativas ainda não presentes** no mês, com valor inicial; grava e insere na categoria correta.
   - Valor aceita vírgula (`converter_valor`), recusa negativo com mensagem no campo.

5. **Encerrar mês** (POST): grava `encerrado_em`; a tela passa a só leitura (sem inputs, sem botões de excluir/adicionar), estado "Encerrado em dd/mm/aaaa", e exibe o botão **Criar orçamento de <mês seguinte>** (que usa a regra de cópia do item 3). **Reabrir** (POST) disponível só se não existir mês posterior; caso contrário o botão não aparece e a rota devolve erro legível se chamada à mão.

6. **Excluir mês** aberto (POST, com confirmação simples via `hx-confirm` ou página de confirmação — escolha e relate): apaga linhas e o registro do mês. Mês encerrado não se exclui.

7. **Celular**: sem layout dedicado. A tabela rola por dentro da `.tabela-caixa` (exceção já usada na matriz); a página não pode ter rolagem horizontal externa nem quebrar. Não gaste em mais nada.

8. **CSS**: seção 5.15 (Orçamento), reaproveitando `.card`, `.filtro-barra`, `.tabela--resumo`, `.tabela-caixa`, a barra de filtros e o visual de edição em linha das configurações. Novo só o que não existe.

## Regras
- Schema muda **só** pelo `01_schema.sql` + `.md` do banco, juntos. Nada de `ALTER` avulso fora do arquivo. Toda FK `NOT NULL`.
- Não filtre por `ano_mes` de `vw_despesas`/`vw_receitas`; intervalo de `data`. Média sempre ÷ 12, mesmo que a subcategoria tenha despesa em só um dos meses (é provisão).
- Não implemente: acompanhamento realizado × planejado do mês corrente, "fora do orçamento", acumulado no ano, integração com Visão Mensal/Anual, orçamento por pessoa, cópia entre anos, histórico de alterações. Rodada 16 em diante.
- Não toque em `lancamentos/`, `cadastros/`, `main/` além da promoção da chave alfabética, nem nas telas de configurações (só leia o padrão).
- Cálculo em `Decimal`; nada somado em Jinja; agregados por consulta ou por composição em Python sobre conjunto pequeno e completo (as linhas do mês).
- Mantenha os padrões do histórico (seção 6) e as convenções das rodadas 13–14 descritas no contexto.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. **Schema**: rode o `01_schema.sql` no banco atual (que tem dados) → sem erro, `tb_orcamentos` no formato novo, despesas/receitas intactas (conte antes e depois). Rode **de novo** → sem erro, sem mudança. Crie um banco descartável (`CREATE DATABASE freedom_teste`), rode o script nele do zero → sem erro; depois `DROP DATABASE freedom_teste`. Reporte `\d tb_orcamentos` e `\d tb_orcamento_meses`.
2. Login `zz_teste` no **navegador**: `/orcamento` vazio → criar **setembro/2026**. Reportar quantas linhas foram sugeridas e conferir três delas (uma recorrente, uma esporádica, uma que só teve despesa em 2025) contra SQL direto: soma dos 12 meses ÷ 12. Conferir a receita planejada da mesma forma.
3. Editar o planejado de uma linha (com vírgula), ver subtotal da categoria e rodapé atualizarem sem recarregar; tentar negativo → erro no campo; excluir uma linha → subtotal e rodapé atualizam; adicionar uma subcategoria que não estava → aparece na categoria certa e sai do combobox.
4. Editar a receita planejada → taxa de poupança planejada muda; zerar → "—".
5. Encerrar setembro → só leitura, inputs sumiram, `POST` direto de edição numa linha → recusado com mensagem, sem 500. Botão "Criar orçamento de outubro" → criar → linhas e receita idênticas às de setembro. Tentar reabrir setembro → botão ausente e rota recusa. Excluir outubro (aberto) → some; reabrir setembro → volta a editável.
6. Deixe **setembro/2026 aberto, com as linhas sugeridas**, para o Tiago revisar; **não deixe outubro**. Reporte o estado final (`SELECT count(*)` nas duas tabelas).
7. Celular 390px: página sem rolagem horizontal externa, tabela rolando por dentro, nada quebrado. Só isso.
8. Regressão: `/`, `/mensal`, consulta, receitas, configurações → 200; a promoção da chave alfabética não mudou a ordem na Mensal (conferir `ordem=nome` em um mês).
9. Relate: arquivos criados/alterados, o `.md` do banco atualizado, mecanismo de confirmação escolhido para excluir mês, resultado de cada validação e a lista de **pontos que precisou interpretar**.