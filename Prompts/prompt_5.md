# Freedom — Rodada 6: autocomplete de descrição + correção da vírgula + filtro por intervalo de datas

## Contexto

Continuação das rodadas 4 e 5, que entregaram o lançamento de despesas, a edição, a exclusão
física e a tela de consulta com filtros, totais e resumo por categoria.
Ambiente Windows/PowerShell, venv em `venv/`, Postgres 16 em Docker.
Subir: `python -m flask --app freedom --debug run --port 5000`.

**O banco tem dados reais**: 725 despesas lançadas pelo dono do sistema, além das tabelas de
referência preenchidas. Valide sobre esses dados. Não crie massa fictícia e não apague nada que
não tenha sido você a criar.

Antes de escrever código, leia:
- `freedom/lancamentos/` inteiro — `despesas.py`, `consulta.py`, `forms.py`, `servico.py`.
- `freedom/util.py` — o parser de valor e o `destino_interno`.
- `templates/lancamentos/` — em especial `_formulario_oob.html`, `_classificacao.html`,
  `_classificacao_macro.html` e o comentário do `_gravado.html` sobre swap out-of-band dentro de
  `<template>` em contexto de tabela.
- `templates/_macros.html` — `campos_despesa` e as demais macros.
- `static/css/app.css`, seções 5.9 e 5.10 e o bloco responsivo.

## Stack (já decidida, não proponha alternativas)

Flask + Jinja2 + Flask-WTF + Flask-Login + psycopg 3 com SQL direto e parametrizado + HTMX 2.0.4
local + CSS à mão. Sem ORM, sem migrações, sem novas dependências, sem extensão no Postgres, sem
biblioteca de autocomplete.

## Entrega desta rodada — SOMENTE isto

### 1. Correção da regra de separador decimal

A regra atual é simétrica entre `.` e `,`, e isso está errado para pt-BR: `1,234` virou 1234,00 e,
pelo mesmo caminho, `10,999` grava dez mil novecentos e noventa e nove reais sem aviso. Em
português a vírgula é sempre decimal. Regra nova, na mesma função de `util.py`:

- **Vírgula presente e ponto ausente**: a vírgula é decimal. Um ou dois dígitos depois dela = ok
  (`10,99` = 10,99; `1,5` = 1,50); vírgula solta no fim = `,00` (`10,` = 10,00); **três ou mais
  dígitos depois dela = erro de campo** (`1,234` e `10,999` passam a ser erro). Mais de uma
  vírgula = erro.
- **Ponto presente e vírgula ausente**: heurística atual, mantida. Ponto único seguido de
  exatamente três dígitos = milhar (`1.234` = 1234,00); seguido de um ou dois dígitos = decimal
  (`1.5` = 1,50); seguido de quatro ou mais = erro; ponto solto no fim = `,00`; ponto repetido =
  todos milhar (`1.234.567` = 1234567,00).
- **Os dois presentes**: o separador mais à direita é o decimal, os demais são milhar
  (`1.234,56` = 1234,56; `1,234.56` = 1234,56). Se houver mais de dois dígitos depois do decimal,
  é erro.
- Prefixo `R$` e espaços continuam ignorados; resultado sempre `Decimal` com 2 casas; não
  numérico ou ≤ 0 continua sendo erro de campo legível.

Ajuste a suíte da rodada 5 aos novos esperados; não deixe teste antigo passando por acidente.

### 2. Filtro de mês por intervalo de datas

Na consulta, nada muda para quem usa: mesmo seletor de mês, mesmas setas, mesmo parâmetro
`mes=AAAAMM` na URL. Muda só o SQL: em vez de filtrar pelo `ano_mes` derivado da view, filtre por
`data >= %s AND data < %s`, com o primeiro dia do mês e o primeiro dia do mês seguinte calculados
em Python. Isso faz o `ix_despesas_data`, que já existe, ser usado, e dispensa o índice de
expressão que você recomendou. Vale para a tabela, para os totais e para o resumo por categoria —
os três precisam usar o mesmo filtro.

Não crie índice. Não altere `01_schema.sql`.

### 3. Autocomplete de descrição — rota

`GET /lancamentos/despesas/sugestoes?q=` devolve um fragmento HTML com no máximo **seis**
sugestões. Dispara a partir de **dois caracteres**, com `keyup changed delay:250ms`. Busca por
trecho em qualquer posição: `ILIKE '%' || %s || '%'`. Sem `unaccent`, sem extensão.

Agrupe por `lower(descricao)` e exiba a grafia da ocorrência mais recente. Ordene por **número de
usos (desc)** e, no empate, pela **mais recente (desc)**. Descrição usada uma vez só continua
aparecendo, atrás das demais.

Cada sugestão carrega, tirados do **lançamento mais recente com aquela descrição**:
`subcategoria_id`, `conta_id`, `pessoa_id` e o último valor. Resolva numa consulta só (agregação
mais `DISTINCT ON` ou função de janela) — não faça uma consulta por sugestão. Toda ela
parametrizada.

Cada item da lista mostra a descrição e, em texto discreto, o último valor e a subcategoria.

### 4. Autocomplete — comportamento na tela

Lista própria renderizada pelo HTMX, ancorada abaixo do campo. **Não** use `<datalist>`: ele só
carrega texto e não traz os ids que o item 5 precisa.

Ao escolher uma sugestão (clique ou Enter):
- preenche a **descrição**;
- seleciona **subcategoria**, **conta** e **pessoa**;
- **não** preenche o valor — mostra ao lado do campo valor um texto de apoio "último: R$ 87,40",
  que some assim que o usuário digitar um valor ou alterar a descrição manualmente;
- **dispara a classificação** (`htmx.trigger` no select de subcategoria), para que categoria,
  essencialidade efetiva e o campo prioridade sejam recalculados — sem isso o resumo fica
  mentindo;
- fecha a lista e deixa o foco no valor, que é o próximo campo a preencher.

Se a subcategoria, a conta ou a pessoa do lançamento antigo estiver desativada e por isso não
existir no select, deixe aquele campo como está e mostre um aviso discreto de que a classificação
anterior não está mais disponível. Não reative nada, não grave id inativo.

Teclado e acessibilidade: setas para cima e para baixo navegam, Enter escolhe o item destacado,
Esc fecha, Tab fecha, clique fora fecha. Use `role="combobox"` / `role="listbox"` /
`role="option"`, com `aria-expanded` e `aria-activedescendant`. Enter com a lista fechada continua
submetendo o formulário; Enter com a lista aberta escolhe e **não** submete.

O autocomplete vale **só na tela de lançamento**, não na edição — editar é corrigir um registro
específico, não repetir um anterior. Como o formulário vem da macro `campos_despesa`, controle
isso por parâmetro da macro, sem duplicar marcação.

No celular (390px): a lista ocupa a largura do campo, tem itens altos o suficiente para o polegar
e não fica escondida atrás do teclado virtual.

O JavaScript é próprio, na ordem de grandeza de 30 a 40 linhas, no mesmo estilo do menu mobile e
do "limpar filtros". Sem framework, sem `localStorage`.

## Regras

- Não crie nem altere tabelas, views, triggers ou índices. `01_schema.sql` não é tocado.
- Não altere arquivos em `docs/`. Não faça `git commit`; o working tree é conferido fora daqui.
- Leitura sempre em `vw_despesas`; `INSERT`/`UPDATE`/`DELETE` em `tb_despesas`.
- Nenhum valor de request em f-string de SQL.
- **Não implemente nesta rodada**: receitas, dashboard, gráficos, exportação, duplicar lançamento,
  edição em lote, sugestão de valor preenchido automaticamente, aprendizado de "descrição favorita"
  por usuário.
- Nada de `DELETE` em tabela de referência, nem para teste — movimento se exclui, referência se
  desativa. Lançamento de teste que você criar, você apaga ao final; despesa real do dono, jamais.
- Erro de banco vira mensagem legível, nunca 500. `q` vazio, com um caractere, com `%`, `_` ou
  aspas não pode quebrar nem virar busca aberta.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute, não presuma)

Sobre os dados reais que já estão no banco. Relate o resultado de cada item:

1. Tabela do parser com pelo menos: `10,99`, `1,5`, `10,`, `1,234`, `10,999`, `1,2,3`, `1.5`,
   `1.234`, `1.2345`, `1.234.567`, `1.234,56`, `1,234.56`, `1.234,567`, `R$ 1.234,56`, `abc`, `0`.
   Marque quais mudaram de comportamento em relação à rodada 5.
2. `EXPLAIN ANALYZE` da consulta mensal antes e depois do item 2, mostrando se o
   `ix_despesas_data` passou a ser usado; e confirmação de que os números da tela (total, divisão
   essencial × não essencial, resumo por categoria, contagem) continuam idênticos aos da rodada 5
   para o mesmo mês.
3. Autocomplete sobre descrições reais: digite trechos de três descrições que se repetem no banco
   e confirme ordem por frequência, desempate por data e limite de seis.
4. Escolha uma sugestão e confirme que subcategoria, conta e pessoa foram preenchidas, que o valor
   **não** foi, que o texto de apoio apareceu e que a classificação recalculou (inclusive o campo
   prioridade aparecendo ou sumindo conforme o caso).
5. Force o caso da referência desativada: desative temporariamente uma subcategoria que aparece em
   sugestão, confirme o aviso discreto e que nada de inativo foi gravado, e **reative** ao final.
6. Teclado: setas, Enter escolhendo, Esc, Tab, clique fora. E Enter com a lista fechada
   submetendo normalmente.
7. Lance duas despesas seguidas usando o autocomplete e confirme que o lançamento em série da
   rodada 4 continua intacto — campos mantidos, foco, swap out-of-band, total atualizado.
8. `q` com `%`, `_`, aspas simples e string vazia; nenhum 500, nenhuma busca retornando o banco
   inteiro.
9. Viewport de 390px, no navegador de verdade: lista de sugestões visível com o teclado aberto,
   itens clicáveis, sem rolagem horizontal.
10. Regressão: tela de consulta (filtros, paginação, editar, excluir) e as cinco telas de cadastro.

Ao final, entregue: arquivos criados e alterados, resultado de cada item acima e a seção
**"Pontos que precisei interpretar"**.