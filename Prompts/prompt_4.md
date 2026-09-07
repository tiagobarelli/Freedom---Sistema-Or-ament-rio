# Freedom — Rodada 5: consulta de despesas com filtros + correção do separador decimal

## Contexto

Continuação direta da rodada 4, que entregou a tela de lançamento de despesas
(`/lancamentos/despesas`), a Home separada, a edição e a exclusão física de lançamento.
Ambiente Windows/PowerShell, venv em `venv/`, Postgres 16 em Docker.
Subir: `python -m flask --app freedom --debug run --port 5000`.

Antes de escrever código, leia:
- `freedom/lancamentos/` inteiro — rotas, forms e servico da rodada anterior.
- `templates/lancamentos/` — em especial `_linha_despesa.html`, `_total_oob.html` e o comentário
  no `_gravado.html` sobre swap out-of-band dentro de `<template>` em contexto de tabela.
- `templates/_macros.html` — `reais`, `badge_essencialidade`, `campos_despesa`, tabela e vazio.
- `docs/Freedom - Estrutura do Banco de Dados.md` e `db/init/01_schema.sql`, seção da
  `vw_despesas`.
- `static/css/app.css`, seção 5.9 e o bloco responsivo.

## Stack (já decidida, não proponha alternativas)

Flask + Jinja2 + Flask-WTF + Flask-Login + psycopg 3 com SQL direto e parametrizado + HTMX 2.0.4
local + CSS à mão. Sem ORM, sem migrações, sem novas dependências, sem extensão nova no Postgres.

## Entrega desta rodada — SOMENTE isto

### 1. Correção do separador decimal (dívida da rodada 4)

A regra atual trata todo `.` como milhar. No celular o teclado numérico costuma oferecer só o
ponto, então `1.5` grava quinze reais em silêncio — erro caro porque não dá sinal nenhum.
Regra nova, numa função única usada pelo lançamento e pela edição:

- Ignore espaços e um prefixo `R$`.
- Se `,` e `.` aparecerem juntos, o **separador mais à direita** é o decimal e os demais são
  milhar: `1.234,56` = 1234,56; `1,234.56` = 1234,56.
- Se aparecer **um único separador, uma única vez**: três dígitos depois dele = milhar
  (`1.234` = 1234,00; `1,234` = 1234,00); um ou dois dígitos depois = decimal (`1.5` = 1,50;
  `10,99` = 10,99); mais de três dígitos depois = erro de campo.
- Se o mesmo separador aparecer mais de uma vez, todos são milhar: `1.234.567` = 1234567,00.
- Separador solto no fim (`10.`, `10,`) continua sendo aceito como `10,00`.
- Resultado sempre `Decimal` com 2 casas; valor não numérico ou ≤ 0 vira erro de campo legível.

### 2. Tela de consulta — `GET /lancamentos/despesas/consulta`

Tela nova e independente. A lista de 15 recentes da tela de lançamento **não muda** e continua
onde está: são ritmos diferentes de uso, digitação rápida de um lado, leitura e conferência do
outro.

Na sidebar, o grupo **Lançamentos** passa a ter dois itens: "Lançar despesa" (a tela atual) e
"Consultar despesas" (esta).

**Uma única rota** serve a página inteira e o fragmento: se `request.headers.get("HX-Request")`
estiver presente, renderize só o bloco de resultados; senão, a página completa. Não duplique a
função de consulta.

### 3. Filtros — sempre por GET, na URL

Parâmetros: `mes` (`AAAAMM`, padrão o mês corrente), `pessoa_id`, `categoria_id`, `conta_id`,
`essencialidade`, `q` (texto na descrição), `ordem` (`data` padrão, ou `valor`), `pagina`.

- O mês tem setas para o anterior e o seguinte, além do seletor.
- Pessoa, categoria e conta listam **todas** as cadastradas, inclusive inativas (marcadas como
  tal): o histórico precisa continuar consultável depois que algo é desativado.
- Essencialidade filtra pela **coluna efetiva da `vw_despesas`**, nunca pela coluna crua da
  despesa.
- `q` usa `ILIKE '%' || %s || '%'` na descrição. Sem acento-insensível: **não** instale
  `unaccent` nem qualquer extensão.
- Um link "Limpar filtros" volta ao mês corrente sem os demais.

Toda mudança de filtro dispara `hx-get` com `hx-push-url="true"`, trocando apenas o bloco de
resultados. A busca por texto dispara com `changed delay:400ms`. Consequência exigida: colar a
URL com filtros numa aba nova reproduz a mesma tela, e o botão voltar do navegador desfaz o
último filtro.

O `WHERE` é montado como lista de condições e lista de parâmetros. Nenhum valor de request entra
em f-string de SQL, em hipótese alguma.

### 4. Bloco de resultados

Três partes, nesta ordem, todas refletindo o filtro inteiro (não a página visível):

**a) Faixa de totais** — total do período filtrado, quantidade de lançamentos, e a divisão
essencial × não essencial em valor e percentual.

**b) Resumo por categoria** — valor e percentual do total por categoria, do maior para o menor.
É a pergunta que se faz de verdade no fim do mês; use uma barra proporcional simples em CSS, sem
biblioteca de gráfico.

**c) Tabela** — data, descrição, categoria · subcategoria, pessoa, conta, valor e badge de
essencialidade efetiva com a prioridade junto quando houver. Ações por linha: Editar e Excluir.
Paginação clássica de **50 por página**, com "Anterior / Próxima" e "X–Y de Z".

Totais e resumo saem de consultas agregadas próprias sobre o filtro completo. **Nunca** some em
Python a partir das linhas da página. Filtro sem resultado usa a macro `vazio`.

### 5. Editar e excluir a partir da consulta

Reaproveite as rotas da rodada 4, sem duplicá-las.

- **Editar**: leve os filtros atuais adiante e, ao salvar, volte para a consulta com eles
  preservados. Use um parâmetro de retorno validado como caminho interno, na mesma regra do
  `?next=` do login — nada de aceitar URL absoluta.
- **Excluir**: como remover uma linha altera totais, resumo e paginação de uma vez, a exclusão
  disparada da consulta devolve o **bloco de resultados inteiro re-renderizado** com os filtros
  atuais. A exclusão disparada da tela de lançamento continua exatamente como está hoje.

### 6. CSS e celular

Tudo em `static/css/app.css`, nas seções existentes. Vidro só em sidebar, cabeçalho e cards de
moldura; a faixa de totais é card de moldura, tabela e filtros ficam quase opacos. Em 390px: os
filtros empilham (considere agrupá-los num `<details>` recolhido, com o mês sempre visível), o
resumo por categoria continua legível, e a tabela segue o padrão da rodada 4 — colunas
secundárias escondidas e realocadas na linha de apoio, sem rolagem horizontal.

## Regras

- Não crie nem altere tabelas, views, triggers ou índices. `01_schema.sql` não é tocado. Se achar
  que a consulta precisa de índice novo, **relate no final, não implemente**.
- Não altere arquivos em `docs/`.
- Leitura sempre em `vw_despesas`; nomes de pessoa e conta por JOIN.
- **Não implemente nesta rodada**: receitas, dashboard, gráficos, exportação CSV ou Excel,
  autocomplete de descrição, seleção múltipla de linhas, edição em lote, filtro por intervalo de
  datas livre (o filtro é mensal), cabeçalho de coluna clicável para ordenar.
- Sem novas dependências e sem framework JS.
- Nada de `DELETE` em tabela de referência, nem para teste. Movimento se exclui, referência se
  desativa — é a regra da rodada 4. Se precisar de usuário de teste, use um permanente e
  **desative** ao final. Verifique também se a pessoa `zz_teste` ficou órfã em `tb_pessoas`
  depois dos testes da rodada anterior; se ficou, desative, não apague.
- Erro de banco vira mensagem legível, nunca 500. Parâmetro de URL inválido (`mes=abc`,
  `pagina=-1`, `pessoa_id=999`) cai no padrão sem quebrar.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute, não presuma)

O banco está com zero despesas. Insira uma massa de teste de cerca de 60 despesas cobrindo três
meses, várias categorias, pessoas, contas, essencialidades e prioridades — e **apague as despesas
de teste ao final** (movimento pode ser apagado). Relate o resultado de cada item:

1. Tabela de casos do separador, conferindo o `Decimal` gravado para: `1.5`, `1,5`, `10,99`,
   `1.234`, `1,234`, `1.234,56`, `1,234.56`, `1.234.567`, `10.`, `1.2345`, `abc`, `0`.
2. Cada filtro isolado e depois três combinações, conferindo a contagem contra `psql`.
3. Totais e resumo por categoria batendo com `SUM` feito direto no `psql` sobre o mesmo filtro.
4. Filtro que devolve mais de 50 linhas: navegue entre páginas e confirme que os totais **não**
   mudam de uma página para outra.
5. Copie a URL com três filtros aplicados, abra em aba nova e confirme que a tela reproduz.
   Depois use o botão voltar e confirme que desfaz o último filtro.
6. Exclua um lançamento pela consulta e confirme que linha, totais, resumo e "X–Y de Z"
   atualizaram juntos e coerentes.
7. Edite um lançamento pela consulta e confirme que voltou para a mesma tela, com os mesmos
   filtros e na mesma página.
8. Passe parâmetros inválidos na URL (`mes=abc`, `pagina=0`, `pagina=9999`, `pessoa_id=99999`,
   `essencialidade=xyz`) e confirme que nenhum gera 500.
9. Teste em viewport de 390px: filtros, faixa de totais, resumo por categoria, tabela e
   paginação. Valide no navegador de verdade, não só por HTTP — foi o que pegou o bug do
   `afterbegin` na rodada passada.
10. Confirme que a tela de lançamento e as cinco telas de cadastro continuam intactas.

Ao final, entregue: arquivos criados e alterados, resultado de cada item acima, qualquer índice
que você julgue necessário (só a recomendação) e a seção **"Pontos que precisei interpretar"**.