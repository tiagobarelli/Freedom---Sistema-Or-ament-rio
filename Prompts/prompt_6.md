# Freedom — Rodada 7: receitas (lançamento e visualização numa página só)

## Contexto

Projeto Freedom, sistema pessoal de controle financeiro. Rodadas 0 a 6 concluídas:
banco, esqueleto Flask com login, cadastros das cinco entidades de referência,
e o ciclo completo de despesas (lançamento em série, consulta com filtros,
edição, exclusão física, autocomplete de descrição).

Antes de escrever qualquer código, leia:

- `docs/Freedom - Estrutura do Banco de Dados.md` — fonte da verdade do schema.
- `db/init/01_schema.sql` — em especial `tb_receitas`, `tb_ref_receitas` e `vw_despesas`.
- `freedom/lancamentos/` inteiro (`__init__.py`, `despesas.py`, `consulta.py`,
  `forms.py`, `servico.py`) — é o padrão que esta rodada deve seguir e reaproveitar.
- `templates/lancamentos/` inteiro e `templates/_macros.html`.
- `freedom/util.py`, `freedom/db.py`, `templates/layout_app.html`, `static/css/app.css`.

Ambiente: Windows, PowerShell, venv em `venv/`, Python 3.14, Postgres 16 em Docker
(`docker compose up -d`, container `freedom_postgres`). Subir a app com
`python -m flask --app freedom --debug run --port 5000`.

Dados reais no banco: 725 despesas, 24 categorias, 82 subcategorias, 3 contas,
5 pessoas, usuário `tiago` ativo. `tb_receitas` está vazia.

## Stack (já decidida, não proponha alternativas)

Flask 3 com application factory e Blueprints, psycopg 3 com SQL direto parametrizado
e `dict_row` (sem ORM, sem migrações), Flask-Login, Flask-WTF com CSRF, HTMX 2.0.4
local, CSS próprio Glassmorphism tema claro, Jinja2. Interface em português do Brasil.

## Entrega desta rodada — SOMENTE isto

### 1. View `vw_receitas` no schema

Acrescente ao `db/init/01_schema.sql`, na mesma seção de objetos auxiliares onde
está `vw_despesas`, uma view `vw_receitas` criada com `CREATE OR REPLACE VIEW`
(o arquivo continua idempotente e rodável sobre o banco existente).

Colunas: `id`, `data`, `ano_mes` (inteiro `AAAAMM`, derivado de `data`, mesma
expressão de `vw_despesas`), `descricao`, `valor`, `ref_receita_id`, `categoria`
e `subcategoria` (de `tb_ref_receitas`), `ref_receita_ativo` (o `ativo` da fonte,
para a tela marcar fonte desativada sem um JOIN extra), `pessoa_id`, `usuario_id`,
`anotacoes`, `criado_em`, `atualizado_em`. Sem JOIN de nome de pessoa ou usuário —
isso a aplicação faz quando precisa, como já faz nas despesas. `COMMENT ON VIEW`
no mesmo estilo dos demais objetos.

Toda leitura de receita passa a ser por `vw_receitas`; todo `INSERT`, `UPDATE` e
`DELETE` vai em `tb_receitas`.

Aplique o arquivo no banco existente e confirme que a view foi criada:

```powershell
docker compose exec -T postgres psql -U freedom -d freedom -f /docker-entrypoint-initdb.d/01_schema.sql
```

**Não edite nada em `docs/`** — relate as mudanças de schema no final; a
documentação é atualizada fora do agente.

### 2. Mover o parser de valor e o escape de LIKE para `freedom/util.py`

O parser de valor (`R$ 1.234,56` → `Decimal`) e `escapar_like` estão hoje em
`freedom/lancamentos/servico.py` e passam a servir duas telas. Mova os dois para
`freedom/util.py` sem mudar o comportamento, ajuste os imports em despesas e
consulta, e confirme que as telas de despesa continuam funcionando (item 8).

### 3. Página única `/lancamentos/receitas`

Uma só tela, em `freedom/lancamentos/receitas.py`, registrada no blueprint
`lancamentos` já existente. De cima para baixo:

**a) Formulário de lançamento**, em card, com os campos:
- `data` — padrão: hoje.
- `descricao` — texto obrigatório, sem autocomplete.
- `valor` — texto, passa pelo parser do `util.py`, grava `Decimal` positivo.
- `fonte` — select alimentado por `tb_ref_receitas` **ativas**, rotuladas como
  `Categoria › Subcategoria`, ordenadas por categoria e depois subcategoria.
  Opção em branco no topo, nunca pré-selecionada.
- `pessoa` — select de `tb_pessoas` ativas (quem recebeu).
- `anotacoes` — texto livre, opcional.

`usuario_id` vem de `current_user` e nunca é escolhido na tela.

**b) Filtros**, logo abaixo, no mesmo padrão da consulta de despesas: GET na URL
com `hx-push-url`, mesma rota devolvendo página inteira ou fragmento conforme
`HX-Request` (com a exceção de `HX-History-Restore-Request`), botão de limpar.
Filtros: mês (padrão: mês corrente), pessoa, fonte, e busca textual na descrição.

**c) Total do período e resumo por categoria de receita**, calculados por consulta
própria sobre o filtro inteiro — nunca somando em Python o que está na página.

**d) Lista** das receitas do filtro: data, descrição, categoria › subcategoria,
pessoa, valor, e ações de editar e excluir. Ordenada por data decrescente e
`criado_em` decrescente. Paginação de 50, igual à consulta de despesas. Estado
vazio explícito quando o filtro não retorna nada.

### 4. Lançamento em série

O POST grava por HTMX sem recarregar a página e devolve, num único response:
- o formulário limpo em `descricao`, `valor` e `anotacoes`, mantendo data, fonte
  e pessoa, com o foco de volta na descrição;
- confirmação curta de gravação, no padrão do `_gravado.html` das despesas;
- o bloco de resultados (lista + total + resumo) **recalculado com os filtros
  vigentes**, por swap out-of-band.

Recalcular o bloco inteiro é intencional: se a receita gravada for de um mês fora
do filtro, ela não deve aparecer na lista, e o total tem que continuar batendo com
o filtro. Para isso o formulário carrega os filtros vigentes em campos ocultos.

Lembre-se: swap out-of-band em contexto de tabela vai dentro de `<template>`.

### 5. Edição

Página separada `/lancamentos/receitas/<id>/editar`, no padrão da edição de despesa:
todos os campos editáveis menos a autoria, que nunca muda. Se a fonte gravada
estiver desativada, ela continua aparecendo no select marcada como desativada,
mas nenhuma fonte desativada pode ser escolhida em lançamento novo. Ao salvar,
volta para a página de receitas preservando os filtros de origem, via
`util.destino_interno`.

### 6. Exclusão física

Movimento se exclui: `DELETE` de verdade em `tb_receitas`, com `hx-confirm`,
removendo a linha e atualizando total e resumo por swap out-of-band.

### 7. Menu e CSS

No grupo "Lançamentos" do `layout_app.html`, acrescente "Receitas" apontando para
a nova página. O destaque do item ativo continua vencendo pelo caminho mais
específico. Reaproveite as seções de CSS já existentes (5.9 lançamento, 5.10
consulta); só escreva CSS novo se algo realmente não tiver equivalente, e nesse
caso numa seção 5.12 identificada.

### 8. Erros e validação

`valor` inválido, data ausente, descrição vazia ou fonte não escolhida viram erro
de campo legível no formulário, nunca 500. Transação por request, rollback em erro.

## Regras

- Não crie tabelas, colunas, índices ou triggers. A única mudança de schema
  permitida nesta rodada é a view `vw_receitas`.
- Sem ORM, sem migrações, sem bibliotecas novas. Se achar que precisa de alguma
  dependência, pare e pergunte.
- Não implemente dashboard, taxa de poupança, comparação receita × despesa,
  configurações, orçamento ou exportação — são rodadas futuras.
- Não implemente autocomplete de descrição em receitas.
- Não altere o comportamento das telas de despesas. As únicas mudanças permitidas
  lá são o import do parser movido para `util.py` e o item de menu.
- Reaproveite macros (`campo`, `tabela`, `reais`, ações) e helpers em vez de
  duplicar código. Se uma macro de despesa quase serve, prefira parametrizá-la a
  copiá-la — mas não a distorça: se ficar cheia de `if`, faça uma macro própria e
  explique a escolha.
- Nomes de rota, arquivos e templates seguem o padrão de `lancamentos/`.
- Não crie massa de dados fictícia além do teste do item de validação.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute, não descreva)

Antes de começar, confirme que existe pelo menos uma linha em `tb_ref_receitas`.
Se não existir, pare e avise — o cadastro é feito pela interface pelo dono do
projeto, não por seed.

Com a aplicação rodando e logado como `tiago`, no navegador:

1. Lance três receitas plausíveis em série (uma delas com data de outro mês) e
   confirme: página não recarrega, campos certos limpos, foco na descrição, lista
   e total corretos, e a de outro mês **não** aparecendo no filtro do mês corrente.
2. Troque o filtro para o mês da terceira receita e confirme que ela aparece e o
   total muda.
3. Use a busca textual, inclusive com um `%` na caixa de busca, e confirme que não
   quebra nem retorna tudo.
4. Edite uma receita, mude fonte e valor, salve e confirme que volta para a lista
   com os filtros preservados e a linha atualizada.
5. Provoque erros: valor `abc`, descrição vazia, fonte em branco. Confirme mensagem
   de campo, sem 500 e sem perder o que já estava digitado.
6. Exclua as três receitas de teste e confirme que a lista, o total e o resumo
   voltam ao estado vazio. `tb_receitas` deve terminar a rodada vazia.
7. Abra as telas de despesa (lançamento e consulta), lance e exclua uma despesa de
   teste, e confirme que a mudança do parser não quebrou nada.
8. Teste a página de receitas em viewport de celular (≈390px): sidebar como barra
   superior, sem rolagem horizontal na tabela, formulário utilizável.
9. Rode `EXPLAIN` no SQL da lista filtrada por mês e informe se o `ix_receitas_data`
   está sendo usado. Se não estiver, relate — não crie índice por conta própria.

No relatório final, informe: arquivos criados e alterados, o SQL da view como ficou,
o resultado de cada item acima, e a lista dos **pontos que precisou interpretar**,
com o que decidiu e por quê.