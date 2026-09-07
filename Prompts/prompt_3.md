# Freedom — Rodada 4: lançamento de despesas + Home separada

## Contexto

Projeto pessoal de controle financeiro. Flask + PostgreSQL 16 rodando em Docker, ambiente
Windows/PowerShell, venv em `venv/`. As rodadas 0 a 3 entregaram: schema completo, esqueleto
Flask com pool psycopg 3, login, CSS Glassmorphism com sidebar e as cinco telas de cadastro
(categorias, subcategorias, contas, pessoas, fontes de receita).

Antes de escrever qualquer código, leia:
- `docs/Freedom - Estrutura do Banco de Dados.md` — fonte da verdade do schema.
- `db/init/01_schema.sql` — `tb_despesas`, `vw_despesas`, trigger `tg_despesas_atualizado_em`.
- `freedom/cadastros/` inteiro, com atenção a `servico.py` (helpers `executar`, `alternar_ativo`,
  tradução de UniqueViolation) e a um módulo de entidade completo, para copiar o padrão.
- `templates/_macros.html`, `templates/layout_app.html`, `templates/main/index.html`.
- `static/css/app.css` — 8 seções comentadas; todo CSS novo entra nelas, nada de `<style>` no template.

Subir para testar: `python -m flask --app freedom --debug run --port 5000`.

## Stack (já decidida, não proponha alternativas)

Flask + Jinja2 + Flask-WTF (CSRF) + Flask-Login + psycopg 3 com SQL direto e parametrizado +
HTMX 2.0.4 local + CSS escrito à mão. Sem ORM, sem migrações, sem novas dependências, sem
bibliotecas de máscara, de ícones ou de componentes.

## Entrega desta rodada — SOMENTE isto

### 1. Home separada do lançamento

A rota `/` (`main.index`) continua sendo a Home e passa a ser o lugar reservado ao futuro
dashboard: mantenha o card de boas-vindas, atualize o texto (os cadastros já existem, o
lançamento de despesas já existe, o painel de indicadores vem depois) e inclua um botão de
atalho "Lançar despesa". Não coloque números nem gráficos: o dashboard é rodada futura.

Na sidebar, `navegacao` passa a ter três grupos, nesta ordem: **Painel** (Início),
**Lançamentos** (Despesas) e **Cadastros** (os cinco itens atuais, sem alteração).

### 2. Blueprint de lançamentos

Novo pacote `freedom/lancamentos/` com blueprint `lancamentos`, prefixo de URL `/lancamentos`,
seguindo a organização de `cadastros`: `__init__.py` (blueprint), `despesas.py` (rotas),
`forms.py`, `servico.py` (consultas e helpers desta área). Registre em `create_app`.

Refatoração pequena e obrigatória, para não duplicar código: mova a função `executar` de
`freedom/cadastros/servico.py` para `freedom/db.py` e ajuste os imports existentes. As telas de
cadastro devem continuar funcionando exatamente como hoje; nada mais nelas muda.

### 3. Tela de lançamento — `GET /lancamentos/despesas`

Uma página só, com o formulário no topo e a lista de lançamentos recentes abaixo.

**Guarda de pré-requisitos**: lançar despesa exige pelo menos uma subcategoria ativa (de
categoria ativa), uma conta ativa e uma pessoa ativa. Se faltar alguma, não renderize o
formulário: use a macro `vazio` dizendo exatamente o que falta e com link para o cadastro
correspondente.

**Campos visíveis por padrão**, nesta ordem:
- **Data** — `type="date"`, padrão hoje. Data futura é permitida, sem aviso.
- **Descrição** — texto obrigatório, `strip` antes de gravar, recusa string vazia.
- **Valor** — campo de texto com `inputmode="decimal"`, renderizado maior que os demais (é o
  campo que mais recebe atenção). Aceita `1234,56`, `1.234,56` e `1234.56`; converte para
  `Decimal` com 2 casas. Valor não numérico ou menor ou igual a zero vira erro de campo legível,
  nunca 500 nem estouro do CHECK do banco.
- **Subcategoria** — `<select>` com `<optgroup>` por categoria, ordenado por categoria e depois
  por subcategoria. Só subcategorias ativas de categorias ativas.
- **Conta** — só contas ativas.
- **Pessoa** — só pessoas ativas.

**Bloco "Mais opções"**, recolhido por padrão (use `<details>`, sem JavaScript):
- **Essencialidade** — select com "Herdar da subcategoria" (valor vazio, padrão), "Essencial" e
  "Não Essencial". Grava `NULL` quando herdada; os outros dois gravam a string exata do CHECK.
- **Integra IPCA** — checkbox marcado por padrão.
- **Observações** — textarea.

**Prioridade** não fica dentro do bloco recolhido: ela vive num contêiner de id fixo logo abaixo
da subcategoria e só existe quando a essencialidade **efetiva** for "Não Essencial".

**Pré-preenchimento ao abrir a página**: data = hoje; conta e pessoa = as do último lançamento
feito pelo usuário logado (uma consulta por `usuario_id` ordenada por `criado_em DESC LIMIT 1`).
Sem lançamento anterior, pessoa = a pessoa do próprio usuário, conta em branco.

### 4. Classificação reativa via HTMX

Rota `GET /lancamentos/despesas/classificacao?subcategoria_id=&essencialidade=&prioridade=`
que devolve um fragmento e é disparada por `hx-get` no `change` da subcategoria **e** no `change`
do select de essencialidade. O fragmento contém:
- uma linha de resumo em texto discreto: categoria da subcategoria escolhida e a essencialidade
  efetiva (a do override se houver, senão a da subcategoria);
- o campo **Prioridade** (select 1 a 4, 1 = mais importante, vazio permitido) somente quando a
  efetiva for "Não Essencial", preservando a prioridade já escolhida se ainda fizer sentido.

No servidor, na hora de gravar: se a essencialidade efetiva for "Essencial", grave
`prioridade = NULL` mesmo que o POST traga valor. Essa regra é da aplicação, não do banco —
está explicada no cabeçalho do `01_schema.sql`.

### 5. Gravação em série — `POST /lancamentos/despesas`

Enviado por HTMX, sem recarregar a página. `usuario_id` vem sempre de `current_user.id`; nunca
do formulário. Em sucesso, a resposta traz:
- a nova `<tr>` inserida no topo da lista de recentes (`hx-swap="afterbegin"` no `tbody`);
- o formulário re-renderizado por swap out-of-band, **limpo em descrição, valor, observações e
  prioridade, mantendo data, conta, pessoa e o estado do bloco recolhido**, com o foco de volta
  na descrição;
- o total do mês (item 6) atualizado, também out-of-band;
- uma confirmação curta e discreta na própria página ("Despesa lançada"), não `flash` de sessão,
  já que não há recarga.

Em erro de validação, devolva o formulário com os erros nos campos e sem tocar na lista.
Responda sempre 200 para o HTMX processar o fragmento.

### 6. Lista de lançamentos recentes

Abaixo do formulário, as **15 despesas mais recentes por `criado_em DESC`** (de todos os
usuários, é um sistema doméstico), consultando `vw_despesas` e completando nomes de conta e
pessoa por JOIN na aplicação — nunca `tb_despesas` direto.

Colunas: data, descrição, categoria · subcategoria, pessoa, conta, valor formatado em reais, e um
badge de essencialidade efetiva (com a prioridade junto quando houver). Acima da tabela, um único
número: **total lançado no mês corrente**, rotulado com o nome do mês. Sem filtros, sem paginação,
sem ordenação clicável — é outra rodada.

Ações por linha: **Editar** (link) e **Excluir**.

### 7. Edição — `GET/POST /lancamentos/despesas/<id>/editar`

Página própria (não inline), reaproveitando a mesma macro de formulário, com os valores atuais
carregados e a mesma reatividade da prioridade. Salvar volta para a tela de lançamento com
`flash` de sucesso. `usuario_id` **não** muda na edição: a autoria original é preservada.
Id inexistente devolve 404.

### 8. Exclusão física — `POST /lancamentos/despesas/<id>/excluir`

Decisão de projeto tomada nesta rodada: **movimento se exclui, referência se desativa**. O
princípio "nada é apagado" vale para as tabelas de referência, que têm `ativo`; um lançamento
digitado errado é lixo, não histórico, e `tb_despesas` não tem coluna de situação. Portanto:
`DELETE` físico, com CSRF, confirmação antes (`hx-confirm`), removendo apenas a `<tr>` da lista e
atualizando o total do mês out-of-band. Só `tb_despesas`; nenhuma outra tabela ganha exclusão.

### 9. CSS

Tudo dentro de `static/css/app.css`, nas seções existentes e no mesmo estilo de comentário.
Vidro continua restrito a sidebar, cabeçalho e cards de moldura: o formulário e a tabela desta
tela são quase opacos. No celular (teste em 390px de largura) os campos ocupam a largura toda, o
valor usa teclado numérico, a tabela de recentes não força rolagem horizontal (empilhe ou esconda
o que for secundário) e os botões são clicáveis com o polegar.

## Regras

- Não crie nem altere tabelas, views, triggers ou índices. `db/init/01_schema.sql` não é tocado
  nesta rodada. Se você achar que precisa de mudança no schema, **pare e pergunte**.
- Não altere arquivos em `docs/`. A documentação é atualizada fora daqui.
- Relatórios e listagens leem `vw_despesas`; `INSERT`, `UPDATE` e `DELETE` vão em `tb_despesas`.
- SQL direto com psycopg 3, sempre parametrizado. Sem ORM, sem query builder, sem f-string com
  valor do request dentro de SQL.
- **Não implemente nesta rodada**: receitas, listagem com filtros por mês/pessoa/categoria,
  autocomplete de descrição, cadastro inline de subcategoria ou conta a partir do formulário,
  duplicar lançamento, importação, dashboard, gráficos. Estão no backlog.
- Sem novas dependências no `requirements.txt`. Sem `localStorage` nem framework JS; se precisar
  de script, poucas linhas próprias, como já é feito no menu mobile.
- Reutilize as macros de `_macros.html` e crie novas lá se houver repetição; não copie marcação
  entre a tela de lançamento e a de edição.
- Erros de banco viram mensagem legível no campo ou no formulário, nunca página 500.
- Interface toda em português do Brasil, incluindo formatação de data e de valor.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute, não presuma)

Suba a aplicação e faça de verdade, relatando o resultado de cada item:
1. Lance três despesas seguidas sem recarregar a página; confirme que data, conta e pessoa
   permaneceram, que descrição e valor limparam e que o foco voltou para a descrição.
2. Escolha uma subcategoria "Não Essencial" e confirme que o campo prioridade aparece; escolha uma
   "Essencial" e confirme que ele some.
3. Grave uma despesa de subcategoria essencial forçando prioridade preenchida (por exemplo,
   trocando a subcategoria depois de escolher a prioridade) e confirme no banco, com
   `docker compose exec -T postgres psql -U freedom -d freedom -c "..."`, que `prioridade` gravou
   `NULL`.
4. Use o override de essencialidade e confirme pela `vw_despesas` que a essencialidade efetiva
   mudou só naquela despesa.
5. Provoque erros: valor `0`, valor `abc`, descrição vazia, subcategoria não escolhida. Nenhum
   pode gerar 500.
6. Edite uma despesa e confirme, no banco, que `atualizado_em` deixou de ser `NULL` e que
   `usuario_id` não mudou.
7. Exclua uma despesa e confirme que a linha sumiu, o total do mês recalculou e o registro não
   está mais na tabela.
8. Teste a tela em viewport de 390px: formulário, bloco "Mais opções", lista e botões.
9. Confirme que as cinco telas de cadastro continuam funcionando depois da mudança em
   `servico.py`/`db.py`.

Ao final, entregue: lista dos arquivos criados e alterados, o resultado de cada item acima e uma
seção **"Pontos que precisei interpretar"** com cada decisão que você tomou sozinho e o porquê.