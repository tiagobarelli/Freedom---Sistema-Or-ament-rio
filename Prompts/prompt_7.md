# Freedom — Rodada 8: configurações (parâmetros com vigência) + limpezas pendentes

## Contexto

Projeto Freedom, sistema pessoal de controle financeiro. Rodadas 0 a 7 concluídas:
banco, esqueleto Flask com login, cadastros das cinco entidades de referência,
ciclo completo de despesas (lançamento em série, consulta com filtros, edição,
exclusão, autocomplete) e a página única de receitas com `vw_receitas`.

Antes de escrever qualquer código, leia:

- `docs/Freedom - Estrutura do Banco de Dados.md` — fonte da verdade do schema.
  Atenção a `tb_configuracoes` e ao conceito de vigência.
- `db/init/01_schema.sql` — `tb_configuracoes` e a view `vw_receitas` da rodada 7.
- `freedom/lancamentos/` inteiro, com destaque para `receitas.py` e
  `servico_receitas.py` — a tela desta rodada segue a mesma forma (uma página só,
  formulário no topo, lista embaixo, HTMX sem recarregar).
- `freedom/cadastros/servico.py` — tradução de `UniqueViolation` em mensagem de campo.
- `freedom/util.py`, `freedom/db.py`, `templates/_macros.html` (em especial as
  macros `campo`, `campo_area`, `combobox`, `tabela`), `templates/layout_app.html`,
  `static/css/app.css`.

Ambiente: Windows, PowerShell, venv em `venv/`, Python 3.14, Postgres 16 em Docker
(`docker compose up -d`, container `freedom_postgres`). Subir a app com
`python -m flask --app freedom --debug run --port 5000`.

Dados reais no banco: 725 despesas, 24 categorias, 82 subcategorias, 3 contas,
5 pessoas, 8 fontes de receita, usuário `tiago` ativo. `tb_receitas` e
`tb_configuracoes` estão vazias.

## Stack (já decidida, não proponha alternativas)

Flask 3 com application factory e Blueprints, psycopg 3 com SQL direto parametrizado
e `dict_row` (sem ORM, sem migrações), Flask-Login, Flask-WTF com CSRF, HTMX 2.0.4
local, CSS próprio Glassmorphism tema claro, Jinja2. Interface em português do Brasil.

**Esta rodada não muda o schema.** `tb_configuracoes` já existe e basta.

## Entrega desta rodada — SOMENTE isto

### 1. Blueprint `configuracoes`

Novo pacote `freedom/configuracoes/` (`__init__.py` com o blueprint, prefixo
`/configuracoes`, mais `rotas.py`, `forms.py` e `servico.py`), registrado no
factory. No `layout_app.html`, item "Configurações" no fim do grupo **Cadastros**
— não crie grupo novo de menu para um item só.

### 2. Página única `/configuracoes`

De cima para baixo:

**a) Formulário de novo valor**, em card, com os campos:
- `chave` — combobox: sugere as chaves já existentes no banco e as chaves
  conhecidas do catálogo (item 3), mas **aceita texto livre** para parâmetros
  futuros. Normalize para maiúsculas e sem espaços nas pontas antes de gravar.
- `valor` — texto. Como interpretar depende da chave (item 3).
- `vigente_desde` — data, padrão hoje.
- `observacao` — texto livre, opcional (motivo da alteração).

**b) Lista agrupada por chave**, uma seção por chave existente, ordenadas
alfabeticamente. Cada seção traz: a chave, o rótulo amigável quando houver, o
**valor vigente hoje** em destaque (com a data desde quando vale) e, abaixo, a
tabela do histórico daquela chave — `vigente_desde` decrescente, valor, observação,
ações de editar e excluir. Vigências futuras aparecem marcadas como tal e não
contam como valor vigente hoje.

Estado vazio explícito quando `tb_configuracoes` não tem nenhum registro, com uma
frase curta explicando o que são TSR, R e S.

### 3. Catálogo de chaves conhecidas, na aplicação

Um dicionário em `configuracoes/servico.py` — não no banco, não em coluna nova —
com as chaves conhecidas, cada uma com rótulo, descrição de uma linha e formato:

- `TSR` — "Taxa segura de retirada (anual)", percentual.
- `R` — "Retorno real anual esperado da carteira", percentual.
- `S` — "Meta de taxa de poupança", percentual.

Regra de entrada e exibição:

- Chave do catálogo marcada como percentual: o usuário digita `4`, `4%` ou `4,5`
  e grava-se `0.04` / `0.045`; a exibição mostra `4,00%`. Reaproveite o parser de
  valor de `util.py` para aceitar vírgula e ponto, mas o `R$` não se aplica aqui —
  se o parser atual atrapalhar, escreva uma função irmã em `util.py`, não distorça
  a existente.
- Chave livre (fora do catálogo): tratada como **número puro** — digita `0,04`,
  grava `0.04`, exibe `0,04`. A tela deve dizer isso ao usuário no momento em que
  ele digita uma chave que não está no catálogo, para não haver ambiguidade.

Sem coluna nova no banco: o formato é conhecimento da aplicação, e o banco guarda
sempre o número final em `NUMERIC(12,6)`.

### 4. Helper `valor_vigente`

Em `configuracoes/servico.py`, uma função que devolve o valor de uma chave vigente
numa data (`vigente_desde <= data`, maior `vigente_desde`), e outra que devolve os
valores vigentes de **todas** as chaves numa data em uma só consulta
(`DISTINCT ON (chave)`). O dashboard vai usá-las na próxima rodada. Não construa
nada de dashboard agora — só deixe as funções prontas e usadas pela própria tela.

### 5. Editar e excluir uma vigência

**Decisão de projeto desta rodada, registre-a no relatório**: `tb_configuracoes`
admite `UPDATE` e `DELETE` físico pela interface. Uma vigência digitada errada é
lixo, não histórico — mesma regra dos lançamentos. Nada derivado é armazenado, então
apagar uma vigência apenas muda o que os relatórios calculam dali em diante.

- Editar: valor, data de vigência e observação. A chave **não** muda na edição
  (trocar a chave é apagar e lançar de novo). Pode ser em linha (HTMX trocando só
  a `<tr>`) ou em página separada — escolha e justifique.
- Excluir: `DELETE` real com `hx-confirm`, atualizando a seção da chave. Se a
  última vigência de uma chave for apagada, a chave some da tela; isso é esperado.
- Violação de `uq_configuracoes_chave_vigencia` vira mensagem de campo legível
  ("já existe um valor para esta chave nesta data"), nunca 500.

### 6. Gravação sem recarregar

O POST grava por HTMX e devolve, num único response, o formulário limpo (mantendo
a chave escolhida, para lançar vigências em sequência), a confirmação curta e a
lista recalculada, no padrão de `_receita_gravada.html` / resultados por swap
out-of-band. Lembre-se de que `<template>` só é necessário quando a resposta
**começa** com `<tr>`.

### 7. Limpezas pendentes (fora da tela nova, mas parte desta rodada)

1. **Helpers privados compartilhados**: `_id_valido`, `_pagina_pedida` e
   `_so_fragmento` hoje moram em `consulta.py` com underscore e são importados de
   fora. Promova-os a `freedom/lancamentos/servico.py` sem underscore e ajuste
   todos os usos. Se algum servir também às configurações, o lugar é `util.py`.
2. **`formatar_valor`** continua em `lancamentos/servico.py` enquanto o parser foi
   para `util.py`. Mova-o para `util.py` junto e ajuste o registro do filtro
   Jinja `moeda` no factory.
3. **Bug do `query_string`**: em `consulta.py`, `v not in (None, "", 1)` descarta
   qualquer filtro cujo valor seja `1`, o que hoje só não quebra porque não existe
   pessoa, conta ou categoria de id 1. Corrija para excluir apenas a página 1,
   comparando pelo nome do parâmetro. Confirme com um teste que um filtro de id 1
   sobrevive na URL.
4. **`<details class="filtros-extras">` no desktop**: acima de 768px o `<summary>`
   é `display:none` e o `<details>` fechado esconde o corpo, deixando os filtros
   extras inacessíveis quando nenhum está aplicado. Corrija nas **duas** telas
   (consulta de despesas e receitas), preferindo CSS a JS — no desktop os filtros
   extras simplesmente ficam visíveis; no celular o `<details>` continua como está.

## Regras

- Não crie tabelas, colunas, índices, views ou triggers. Nenhuma mudança de schema.
- Sem ORM, sem migrações, sem bibliotecas novas. Precisando de dependência, pare e pergunte.
- Não implemente dashboard, taxa de poupança, orçamento, patrimônio ou IPCA.
- Não mexa em nada de despesas e receitas além dos quatro itens do bloco 7.
- Reaproveite macros e helpers em vez de duplicar. Macro própria só quando
  parametrizar a existente a encheria de `if` — foi o critério certo na rodada 7.
- Não invente valores de TSR, R e S como se fossem do dono do projeto: os valores
  reais são cadastrados por ele pela interface. Os valores desta rodada são de
  teste e são apagados no fim (item de validação).
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute, não descreva)

**Faça login no navegador de verdade.** Se houver credencial de teste disponível
no `.env`, use-a. Se não houver nenhuma forma de autenticar num navegador real,
**pare e avise antes de recorrer ao test client** — a validação da rodada 7 ficou
frouxa no layout justamente por isso.

1. Cadastre `TSR` = `4`, `R` = `5%`, `S` = `30` com vigência de hoje e confirme no
   banco que gravaram `0.040000`, `0.050000` e `0.300000`.
2. Cadastre uma segunda vigência de `TSR` com data futura e confirme que o valor
   vigente hoje **não** mudou e que a futura aparece marcada.
3. Cadastre uma vigência anterior de `TSR` e confirme que o vigente hoje continua
   sendo o registro certo.
4. Repita chave e data e confirme a mensagem de campo, sem 500 e sem perder o digitado.
5. Cadastre uma chave livre (ex.: `INFLACAO_ALVO`) com `0,03`, confirme que grava
   `0.030000`, exibe como número puro e que a tela avisou que a chave é livre.
6. Edite uma vigência (valor e data) e exclua outra; confirme a atualização da seção
   e que a exclusão da última vigência de uma chave faz a chave sumir.
7. Provoque erros: valor `abc`, chave vazia, data vazia, id inexistente na edição e
   na exclusão. Nada de 500.
8. Teste em viewport de celular real (≈390px): sem rolagem horizontal, seções e
   histórico legíveis, formulário utilizável.
9. Depois das correções do bloco 7: lance e exclua uma despesa e uma receita de
   teste, use os filtros das duas telas (inclusive com um filtro de id 1, se existir
   referência com esse id — se não existir, teste a função `query_string`
   diretamente), confirme que os filtros extras aparecem no desktop e que o
   `<details>` continua funcionando no celular.
10. Apague todos os registros de teste: `tb_configuracoes`, `tb_receitas` e as
    despesas de teste devem terminar a rodada como começaram.

No relatório final, informe: arquivos criados e alterados, como ficou o catálogo de
chaves, onde a edição foi feita (linha ou página) e por quê, o resultado de cada
item acima, e a lista dos **pontos que precisou interpretar**, com o que decidiu
e por quê.