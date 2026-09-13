# Freedom — Estrutura do Banco de Dados

Sistema web pessoal de controle financeiro. Roda localmente; acesso de outros membros da casa via Tailscale (sem exposição de portas na nuvem). Banco de dados: **PostgreSQL 16**.

> **Status**: schema implementado em `db/init/01_schema.sql` (idempotente). Este documento reflete exatamente o que está no banco. Se o SQL mudar, atualizar aqui; se este documento mudar, atualizar o SQL.
>
> Histórico do DDL: criado na rodada 1 e inalterado até a rodada 6. São **três mudanças** desde então. A **rodada 7** acrescentou a view `vw_receitas`. A **rodada 15** criou `tb_orcamento_meses` e trocou `tb_orcamentos` de categoria para subcategoria (a tabela nunca recebera uma linha, então foi troca de coluna, sem migração de dados). A **rodada 20** criou `tb_resumos_anuais` e ampliou o `COMMENT` de `fn_set_atualizado_em()`, que agora serve três tabelas — nada mais foi tocado. Nenhuma tabela de movimento foi alterada em nenhuma das três.
>
> **Desde a rodada 20 o DDL não muda.** As rodadas 21 a 24 encheram e leram `tb_ipca` sem tocar em uma linha do schema: carga pelo comando (21), tela de leitura (22), botão de atualizar (23) e o primeiro uso do índice, na Análise por subcategoria (24). O que as rodadas 4 a 24 acrescentaram fora do DDL está em **Regras da aplicação** e em **Padrões de acesso**.

## Decisões de projeto

- **Sem parcelamento nem faturas de cartão**: despesa no cartão entra com a data da compra, como qualquer outra.
- **Sem controle de saldo**: o sistema categoriza fluxos (entradas e saídas); não há saldo inicial nem transferências entre contas.
- **Nada derivado é armazenado**: categoria e essencialidade vêm da subcategoria via JOIN; categoria e subcategoria de receita vêm da fonte via JOIN; o mês vem da data (`vw_despesas`, `vw_receitas`). Isso evita dados inconsistentes quando algo é renomeado.
- **Usuários no próprio Postgres** (não em SQLite separado): a segurança está no hash da senha (scrypt via `werkzeug.security`), não no arquivo. Isso permite chave estrangeira entre lançamentos e usuários.
- **Toda tabela tem `id` como chave primária** (`GENERATED ALWAYS AS IDENTITY`), **menos as duas em que o período é a chave**: `tb_orcamento_meses` (`ano_mes`, rodada 15) e `tb_resumos_anuais` (`ano`, rodada 20). Nos dois casos há no máximo uma linha por período, e um `id` sequencial ao lado exigiria um `UNIQUE` para dizer exatamente a mesma coisa. Nomes nunca são chave.
- **Registros de referência não são apagados**: tabelas de referência têm coluna `ativo`, para sumir dos formulários sem quebrar o histórico. Todas as FKs são `ON DELETE RESTRICT`.
- **Movimento se exclui, referência se desativa** (decisão da rodada 4): `tb_despesas` e `tb_receitas` não têm coluna de situação e admitem `DELETE` físico, porque um lançamento digitado errado é lixo, não histórico. Nenhuma tabela de referência pode ser apagada, nem em teste.
- **Configurações têm vigência**: mudar a TSR no futuro não altera relatórios do passado.
- **Configuração é corrigível** (decisão da rodada 8): `tb_configuracoes` admite `UPDATE` e `DELETE` físico pela interface. Uma vigência digitada errada é lixo, como um lançamento errado; como nada derivado é armazenado, apagá-la só muda o que os relatórios calculam dali em diante. A **chave** não muda na edição — trocar de chave é apagar e lançar de novo.
- **Resumo anual se exclui** (decisão da rodada 20): `tb_resumos_anuais` admite `UPDATE` e `DELETE` físico pela interface, pela mesma razão da configuração e da linha de orçamento — é entrada do usuário, não histórico gerado pelo sistema. O **ano** não muda na edição: trocar de ano é excluir e escrever outro. Sem `ativo` e sem autoria.
- **Orçamento é por subcategoria, e o mês tem tabela própria** (rodada 15): orçar por categoria pede um número que ninguém sabe dizer ("quanto vou gastar em Lazer?"); por subcategoria o número sai do histórico daquela linha e a categoria vira soma. O que é atributo do **mês** — receita planejada, encerramento, observação — mora em `tb_orcamento_meses`, e não repetido em cada linha; assim um mês recém-criado ou esvaziado continua existindo.
- **Mês de orçamento se encerra, não se congela por trigger** (rodada 15): `encerrado_em` nulo significa aberto. A recusa de alterar mês encerrado é da aplicação (ver Regras da aplicação).
- **Leitura pela view, escrita na tabela**, para os dois movimentos: `vw_despesas` e `vw_receitas` são o que a aplicação consulta; `INSERT`, `UPDATE` e `DELETE` vão sempre nas tabelas base.

## Decisões de implementação (tomadas ao escrever o DDL)

1. **Toda FK é `NOT NULL`.** Subcategoria sem categoria seria órfã; despesa sem conta, pessoa ou usuário sumiria dos relatórios agrupados. Consequência: lançar despesa ou receita exige que as tabelas de referência já tenham pelo menos um registro cada, incluindo um usuário. Despesas compartilhadas da casa (aluguel, luz) são atribuídas a uma pessoa chamada **Casa**.
2. **`CHECK` de domínio em `tb_despesas.essencialidade` e `tb_contas.tipo`.** Sem o primeiro, o `COALESCE` da view poderia devolver texto arbitrário; o segundo existe porque `tipo` serve para agrupar relatórios e "outro" já é o escape. `tb_ativos.classe` fica **sem** CHECK de propósito (lista aberta), e `tb_configuracoes.chave` também (ver Regras da aplicação).
3. **Regras de mês e sinal viraram `CHECK`.** `tb_ipca.mes` e `tb_orcamentos.ano_mes` exigem dia 1 (senão o JOIN por mês quebra em silêncio). `tb_orcamentos.valor_planejado` e `tb_patrimonio_snapshots.valor` aceitam zero, mas não negativo.
4. **Booleanos são `NOT NULL` além do `DEFAULT`.** Evita um terceiro estado entre ativo e inativo. Mesmo para `criado_em`.
5. **`atualizado_em` não tem `DEFAULT`.** Fica `NULL` até o primeiro `UPDATE`; assim o dado distingue registro nunca editado de editado.
6. **`vw_despesas` expõe só a essencialidade efetiva.** As duas origens (despesa e subcategoria) não são repetidas, para não induzir uso errado.
7. **`vw_receitas` expõe `ref_receita_ativo`** (rodada 7). A tela precisa marcar "fonte inativa" na lista, e trazer o `ativo` junto evita um JOIN extra em toda leitura.

## Regras da aplicação (deliberadamente **não** impostas pelo banco)

- **Prioridade só se aplica a despesa não essencial.** O banco só garante a faixa 1–4. A interface exibe o campo apenas quando a essencialidade efetiva for "Não Essencial", e a rota grava `prioridade = NULL` quando a efetiva for "Essencial", mesmo que o POST traga valor. Impor por trigger faria a reclassificação de uma subcategoria falhar ou zerar prioridades históricas.
- **A interface nunca pré-seleciona subcategoria nem fonte de receita.** Os dois `<select>` têm opção em branco antes das demais, porque o navegador seleciona a primeira opção sozinho e a classificação exibida na tela passaria a discordar do que o servidor sabe.
- **Receita pré-seleciona a pessoa do usuário logado** (rodada 7). Diverge da despesa de propósito: em despesa se paga por outro com frequência, em receita quem recebe é quase sempre quem digita. Continua editável.
- **Autoria não muda na edição.** `usuario_id` vem sempre de `current_user` no lançamento e é preservado no `UPDATE`, em despesas e receitas.
- **Referência desativada continua editável.** Nas telas de edição e nos filtros, categorias, subcategorias, contas, pessoas e fontes de receita inativas aparecem marcadas como tal; sem isso, o histórico ficaria inconsultável e ineditável. Nenhum id inativo é gravado em lançamento novo — o POST recusa.
- **Regra de separador decimal (assimétrica, pt-BR).** A vírgula é sempre decimal: um ou dois dígitos depois dela são aceitos, três ou mais são erro (`10,999` é erro, não dez mil). O ponto sozinho segue heurística: seguido de exatamente três dígitos é milhar (`1.234` = 1234,00), de um ou dois dígitos é decimal (`1.5` = 1,50). Com os dois presentes, o separador mais à direita é o decimal (`1.234,56` e `1,234.56` = 1234,56). Prefixo `R$` e espaços ignorados; resultado sempre `Decimal` com 2 casas.
- **Catálogo de chaves de configuração vive na aplicação** (rodada 8), num dicionário em `freedom/configuracoes/servico.py` — não em coluna nem em tabela nova. Ele diz o rótulo, a descrição e o **formato** de cada chave conhecida (`TSR`, `R`, `S`: percentual). O banco guarda sempre o número final em `NUMERIC(12,6)`.
- **Entrada e exibição de configuração.** Chave de formato percentual: digita-se `4`, `4%` ou `4,5` e grava-se `0.04` / `0.045`; exibe-se `4,00%`. Chave livre (fora do catálogo): número puro — digita `0,03`, grava `0.030000`, exibe `0,03`. A tela avisa, enquanto se digita, quando a chave está fora do catálogo. A chave é normalizada para maiúsculas e sem espaços nas pontas antes de gravar.
- **Configuração não aceita valor negativo** (regra da aplicação; o banco não tem `CHECK`). Nenhum dos três parâmetros iniciais admite negativo e `-4` é quase sempre `4` com um dedo a mais. *Reabrir se o dashboard precisar de um `R` real negativo.*
- **Casas decimais em configuração**: percentual aceita até 4 casas digitadas (viram 6 ao dividir por 100, o limite de `NUMERIC(12,6)`); chave livre aceita 6. Acima disso, erro de campo — nunca arredondamento silencioso.
- **Vigência futura não é o valor de hoje.** A tela mostra a série inteira por chave, marca as vigências futuras como tais e destaca o valor vigente na data corrente.
- **Mês de orçamento encerrado não aceita alteração** (rodada 15). Com `tb_orcamento_meses.encerrado_em` preenchido, a aplicação recusa `INSERT`, `UPDATE` e `DELETE` nas linhas daquele mês, na receita planejada e na exclusão do próprio mês, sempre com mensagem legível — nunca 500. O banco não impede nada disso: uma trigger em `tb_orcamentos` consultando o mês a cada linha custaria caro e tornaria impossível corrigir um encerramento equivocado por SQL.
- **Reabrir mês só enquanto for o último** (rodada 15). Zerar `encerrado_em` é permitido apenas se não existir `tb_orcamento_meses` com `ano_mes` posterior: o mês seguinte é criado copiando o anterior, e reabrir um mês que já teve descendente faria o descendente derivar de números que mudaram depois.
- **Sugestão de orçamento vem do histórico, não é armazenada** (rodada 15). Ao criar um mês, se o mês imediatamente anterior tiver orçamento, copiam-se as linhas e a receita planejada dele; senão, sugere-se uma linha por subcategoria ativa com despesa nos **12 meses fechados anteriores**, com `valor_planejado` = soma dos 12 ÷ 12 (`ROUND_HALF_UP`, duas casas), e receita planejada pela mesma média. A divisão é sempre por 12, mesmo que só um mês tenha despesa: o orçamento é provisão, não média dos meses em que houve gasto. As colunas "Média 12m" e "Realizado no mês anterior" da tela são recalculadas a cada exibição e **nunca gravadas**.
- **Padronização de `tb_ativos.classe`**: dropdown alimentado pelos valores já usados.

## Padrões de acesso (rodadas 5 a 8)

- **Filtro mensal usa intervalo de datas, não o `ano_mes` derivado.** A consulta filtra `data >= primeiro dia do mês AND data < primeiro dia do mês seguinte`, com as bordas calculadas na aplicação. Filtrar pelo `ano_mes` da view força `Seq Scan`, porque a coluna é derivada; com o intervalo, o índice de `data` é usado. Vale para despesas (`ix_despesas_data`) e para receitas (`ix_receitas_data`, confirmado por `EXPLAIN` na rodada 7: `Bitmap Index Scan` com `Index Cond` sobre o intervalo). `ano_mes` continua servindo para exibir e agrupar, não para filtrar.
- **Um índice de expressão sobre `(ano * 100 + mês)` foi avaliado e dispensado** — o intervalo de datas resolve com o índice que já existe. Só reconsiderar se algum relatório futuro precisar filtrar diretamente pelo `ano_mes`.
- **Totais e agregados vêm de consultas próprias sobre o filtro completo**, nunca de soma em Python sobre a página exibida.
- **Busca textual**: `ILIKE '%' || %s || '%'` sobre `descricao`, com os curingas `%` e `_` escapados na aplicação (`ESCAPE '\'`, em string Python *raw*). Sem `unaccent` e sem qualquer extensão do Postgres — a busca é sensível a acento por escolha. Vale para despesas e receitas.
- **Sugestão de descrição** (só despesas): agrupa por `lower(descricao)`, ordena por número de usos e desempata pela mais recente, e traz `subcategoria_id`, `conta_id`, `pessoa_id` e o último valor do lançamento mais recente daquela descrição — tudo em **uma** consulta. Receitas não têm autocomplete (decisão da rodada 7: poucas fontes, o select resolve).
- **Valor vigente de configuração** (rodada 8): o valor de uma chave numa data é o registro com maior `vigente_desde <= data`. Para todas as chaves de uma vez, `DISTINCT ON (chave) ... ORDER BY chave, vigente_desde DESC` — uma consulta só. As duas funções (`valor_vigente` de uma chave e a de todas) vivem em `freedom/configuracoes/servico.py` e são o que o dashboard deve usar.

- **Upsert do IPCA** (rodada 21): `INSERT ... ON CONFLICT (mes) DO UPDATE ... WHERE tb_ipca.numero_indice IS DISTINCT FROM EXCLUDED.numero_indice OR ...` — o `WHERE` é o que faz o mês já igual não ser tocado. As contagens saem do próprio comando: `RETURNING mes, (xmax = 0) AS nasceu` separa a linha que nasceu da que foi atualizada, e um `array_agg` diz **quais** meses entraram (a faixa da tela precisa nomear o mês novo). Uma transação só, 393 linhas, `unnest` de três arrays — não há laço de `INSERT` linha a linha.
- **Deflação por lançamento, soma depois** (rodada 24): `SUM(v.valor * base / COALESCE(i.numero_indice, base))` sobre `vw_despesas LEFT JOIN tb_ipca i ON i.mes = date_trunc('month', v.data)::date`. A ordem importa: deflacionar a **soma do trimestre** por um índice só daria outro número, e o agrupamento por trimestre e ano é o que a tela oferece. O `COALESCE` no denominador resolve o mês posterior à base (fator 1). O arredondamento a centavos acontece **só no ponto exibido**; as somas em SQL ficam com a precisão do `NUMERIC`.
- **Série de uma subcategoria** (rodada 24): **uma** consulta por requisição devolve, por mês, soma nominal, soma corrigida e `COUNT(*)`. Meses sem lançamento simplesmente não voltam — quem os transforma em **zero** é a composição em Python, porque zero é resposta ("não gastei") e buraco não é. O filtro continua sendo `data >= ... AND data < ...`; `date_trunc('month', data)` aparece só no `GROUP BY` e no `JOIN` com o IPCA, nunca no `WHERE`.

## Convenções

- Nomes de tabelas e colunas em `snake_case`, minúsculas, sem acento.
- Valores monetários: `NUMERIC(12,2)` (`NUMERIC(14,2)` em patrimônio).
- Percentuais: em fração (4% = `0.04`) — **com uma exceção documentada**: `tb_ipca.variacao_mensal` guarda **pontos percentuais**, como o IBGE publica (`0.3800` é 0,38 %). As duas convenções convivem porque a do IPCA é dado de terceiro, copiado como veio; a fração é a do que o sistema mesmo grava.
- Datas: `DATE`. Carimbos de auditoria: `TIMESTAMPTZ`.
- `criado_em`: `NOT NULL DEFAULT now()`. `atualizado_em`: `NULL` até o primeiro `UPDATE`, preenchido pela trigger `fn_set_atualizado_em()`.
- Constraints nomeadas: `ck_` (CHECK), `uq_` (UNIQUE), `ix_` (índice), `tg_` (trigger), `fn_` (função), `vw_` (view), `fk_` (chave estrangeira). O prefixo `fk_` entrou na rodada 15 e vale para FK nova: as anteriores usam o nome automático do Postgres, e renomeá-las não traria nada. Nomear importa quando o script precisa perguntar "esta constraint já existe?" antes de criá-la.

---

## Tabelas de referência

### `tb_categorias`

Categorias de **despesa** (nível superior). Reutilizada pelo orçamento.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `nome` | `TEXT NOT NULL UNIQUE` | Nome da categoria (ex.: Moradia, Alimentação, Transporte). |
| `ativo` | `BOOLEAN NOT NULL DEFAULT TRUE` | Se `FALSE`, não aparece nos formulários, mas o histórico permanece. |

### `tb_subcategorias`

Subcategorias de **despesa**. É a única coisa que o usuário escolhe ao lançar uma despesa; categoria e essencialidade vêm daqui.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `categoria_id` | `INT NOT NULL FK → tb_categorias` | Categoria à qual a subcategoria pertence. |
| `nome` | `TEXT NOT NULL` | Nome da subcategoria (ex.: Aluguel, Supermercado, Combustível). `UNIQUE (categoria_id, nome)`. |
| `essencialidade` | `TEXT NOT NULL` | `Essencial` ou `Não Essencial` (`CHECK`). Valor padrão herdado por toda despesa desta subcategoria. |
| `ativo` | `BOOLEAN NOT NULL DEFAULT TRUE` | Oculta dos formulários sem apagar. |

### `tb_ref_receitas`

Classificação das fontes de **receita** (categoria + subcategoria numa só tabela, pois o volume é pequeno). É a única classificação que o usuário escolhe ao lançar uma receita.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `categoria` | `TEXT NOT NULL` | Categoria da receita (ex.: Salário, Investimentos, Extras). |
| `subcategoria` | `TEXT NOT NULL` | Subcategoria (ex.: Salário líquido, Dividendos, Venda de item). `UNIQUE (categoria, subcategoria)`. |
| `observacao` | `TEXT` | Anotação livre sobre a fonte. |
| `ativo` | `BOOLEAN NOT NULL DEFAULT TRUE` | Oculta dos formulários sem apagar. |

### `tb_pessoas`

Membros da família. **Pessoa ≠ usuário**: toda pessoa pode ter despesas atribuídas a ela, mas nem toda pessoa acessa o sistema. Deve existir uma pessoa **Casa** para despesas compartilhadas.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `nome` | `TEXT NOT NULL UNIQUE` | Nome do membro da família. |
| `ativo` | `BOOLEAN NOT NULL DEFAULT TRUE` | Oculta dos formulários sem apagar. |

### `tb_usuarios`

Quem pode entrar no sistema.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `login` | `TEXT NOT NULL UNIQUE` | Nome de acesso. |
| `senha_hash` | `TEXT NOT NULL` | Hash da senha gerado pela aplicação com `werkzeug.security.generate_password_hash` (scrypt; formato `scrypt:N:r:p$salt$hash`). Criado pelo comando `flask create-user`. **Nunca** armazenar a senha em texto. |
| `pessoa_id` | `INT NOT NULL FK → tb_pessoas` | Liga o usuário ao membro da família correspondente. |
| `ativo` | `BOOLEAN NOT NULL DEFAULT TRUE` | Bloqueia o acesso sem apagar o registro (mantém a autoria dos lançamentos). Usuário de teste é **desativado**, nunca apagado. |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Quando a conta foi criada. |

### `tb_contas`

De onde o dinheiro sai. Serve apenas para classificar a saída — não há saldo.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `nome` | `TEXT NOT NULL UNIQUE` | Nome da conta (ex.: Conta corrente Banco X, Cartão Y, Dinheiro). |
| `tipo` | `TEXT NOT NULL` | `corrente`, `cartao`, `dinheiro`, `outro` (`CHECK`). Permite agrupar relatórios por tipo. |
| `observacao` | `TEXT` | Anotação livre. |
| `ativa` | `BOOLEAN NOT NULL DEFAULT TRUE` | Conta encerrada some dos formulários, histórico permanece. |

### `tb_ipca`

Série histórica do IPCA, para deflacionar despesas e ver crescimento real.

**Como é alimentada.** Por **dois gatilhos, os dois manuais e os dois passando pela mesma função** (`ipca.carregar`): o comando `flask carregar-ipca` (rodada 21) e o botão "Atualizar do IBGE" da tela do IPCA (rodada 23). Não há `INSERT` manual e não há agendamento — nem cron, nem thread, nem tarefa do Windows. O comando lê a **tabela 1737 do SIDRA/IBGE** (Brasil, variáveis **2266** — número-índice, base dezembro/1993 = 100 — e **63** — variação mensal, em %), em `https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266,63/p/all`, e grava de **dezembro/1993 em diante**: antes disso a série vem reconstruída em moedas extintas, com índice na casa de 0,0000000076, que não caberia em `NUMERIC(14,6)` e não tem uso no Freedom.

A gravação é um `INSERT ... ON CONFLICT (mes) DO UPDATE` com `WHERE ... IS DISTINCT FROM ...`, numa transação só: o mês que já está igual não é tocado, **nenhuma linha é apagada** e qualquer erro no meio desfaz tudo — não existe carga parcial, porque meia série não serve (o número-índice só vale encadeado). A série inteira é recusada, sem gravar nada, se dezembro/1993 faltar ou não valer exatamente 100, se houver mês faltando entre o primeiro e o último, se algum índice não for positivo ou se algum mês vier duplicado.

**Quando rodar.** Depois do dia 10 de cada mês, quando o IBGE publica o índice do mês anterior. Rodar de novo é inofensivo — o resultado é "0 inseridos, 0 atualizados". A tela do IPCA diz sozinha quando está na hora: a partir do **dia 12** ela espera o mês anterior (antes disso, o retrasado) e mostra "O IBGE já deve ter publicado <mês>" enquanto o último mês carregado for mais velho que isso.

**Quem lê.** A tela `/cadastros/ipca` (rodada 22), que mostra a série em matriz ano × mês, e a **Análise por subcategoria** (rodada 24), primeiro uso do índice para deflacionar. A **base da correção é o último mês carregado** — `SELECT mes, numero_indice FROM tb_ipca ORDER BY mes DESC LIMIT 1` —, e mês posterior a ela usa fator 1: corrigir para um mês que o IBGE ainda não publicou seria inventar inflação.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `mes` | `DATE NOT NULL UNIQUE` | Mês de referência, sempre dia 1 (ex.: `2026-08-01`). `CHECK (EXTRACT(DAY FROM mes) = 1)`. |
| `numero_indice` | `NUMERIC(14,6) NOT NULL` | Número-índice acumulado publicado pelo IBGE (dez/1993 = 100), **gravado como publicado, sem arredondar e sem recalcular**: o índice não é reconstruído encadeando variações. A API devolve 13 casas decimais, mas de dez/1993 em diante só 2 são significativas, então as 6 da coluna guardam o valor exato. Deflacionar = `valor × indice_base / indice_mes`. |
| `variacao_mensal` | `NUMERIC(6,4)` | Variação do mês **em pontos percentuais, como o IBGE publica**: `0.3800` é 0,38 %, e mês de deflação vem negativo. **Diferente de `tb_configuracoes.valor`, que guarda fração** (`0.04` é 4 %) — as duas colunas são percentuais e as duas convenções convivem no banco. `NULL` quando o IBGE não publica número para o mês (marcadores `...`, `-`, `X`); a coluna é opcional e derivável do índice, e existe para consulta rápida. |

### `tb_configuracoes`

Parâmetros do sistema com histórico de vigência. Tela em `/configuracoes` desde a rodada 8; admite `UPDATE` e `DELETE` físico (ver Decisões de projeto).

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `chave` | `TEXT NOT NULL` | Nome do parâmetro. **Lista aberta, sem `CHECK`**: as chaves conhecidas estão no catálogo da aplicação, e qualquer chave nova pode ser cadastrada pela interface sem mexer no código. Gravada em maiúsculas, sem espaços nas pontas. |
| `valor` | `NUMERIC(12,6) NOT NULL` | Valor do parâmetro, sempre já convertido. Percentuais em fração (4% = `0.04`). Sem `CHECK` de sinal; a aplicação recusa negativo. |
| `vigente_desde` | `DATE NOT NULL` | A partir de quando este valor vale. `UNIQUE (chave, vigente_desde)`. O valor vigente numa data é o registro com maior `vigente_desde ≤ data`. Datas futuras são permitidas e ficam agendadas. |
| `observacao` | `TEXT` | Motivo da alteração. |

Chaves do catálogo da aplicação (todas de formato percentual):

| Chave | Significado |
|---|---|
| `TSR` | Taxa segura de retirada (anual). |
| `R` | Retorno real anual esperado da carteira. |
| `S` | Meta de taxa de poupança. |

---

## Tabelas de movimento

### `tb_despesas`

Tabela principal. **Movimento**: admite `DELETE` físico pela interface (ver Decisões de projeto). Leitura pela `vw_despesas`.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `BIGINT IDENTITY PK` | Identificador único. |
| `data` | `DATE NOT NULL` | Data da compra (também para cartão de crédito). Índice `ix_despesas_data`, usado pelo filtro mensal por intervalo. |
| `descricao` | `TEXT NOT NULL` | O que foi comprado. Fonte das sugestões do autocomplete. |
| `valor` | `NUMERIC(12,2) NOT NULL` | Valor da despesa. `CHECK (valor > 0)`. |
| `subcategoria_id` | `INT NOT NULL FK → tb_subcategorias` | Classificação. Categoria e essencialidade padrão vêm daqui via JOIN. Índice `ix_despesas_subcategoria_id`. |
| `conta_id` | `INT NOT NULL FK → tb_contas` | Conta de onde o dinheiro saiu. |
| `pessoa_id` | `INT NOT NULL FK → tb_pessoas` | Para quem foi a despesa. Índice `ix_despesas_pessoa_id`. |
| `usuario_id` | `INT NOT NULL FK → tb_usuarios` | Quem fez o lançamento (autoria). Vem de `current_user` e não muda na edição. |
| `essencialidade` | `TEXT` | **Nula por padrão.** Preencher só para sobrescrever a essencialidade da subcategoria nesta despesa específica. `CHECK` nos mesmos dois valores da subcategoria. Relatórios usam `COALESCE(despesa.essencialidade, subcategoria.essencialidade)`. |
| `prioridade` | `SMALLINT` | 1 a 4, apenas para despesas não essenciais (1 = mais importante). `CHECK (prioridade BETWEEN 1 AND 4)`. Nula quando essencial — regra da aplicação, não do banco. |
| `integra_ipca` | `BOOLEAN NOT NULL DEFAULT TRUE` | Se entra no agregado de despesas deflacionado. `FALSE` para gastos pontuais que distorceriam a série. **Nada lê esta coluna até hoje** (estado da rodada 24): ela está reservada para uma tela futura de despesas mensais somadas só das marcadas, e a Análise por subcategoria **não** a consulta — decisão do dono, para a série de uma subcategoria ser a subcategoria inteira. |
| `observacoes` | `TEXT` | Anotação livre. |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Auditoria. Ordena a lista de lançamentos recentes. |
| `atualizado_em` | `TIMESTAMPTZ` | Auditoria. `NULL` até o primeiro `UPDATE`; preenchido pela trigger `tg_despesas_atualizado_em`. |

### `tb_receitas`

**Movimento**, mesma regra de exclusão de `tb_despesas`. Tela única em `/lancamentos/receitas` desde a rodada 7 (lançamento, filtros, edição e exclusão na mesma página). Leitura pela `vw_receitas`.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `BIGINT IDENTITY PK` | Identificador único. |
| `data` | `DATE NOT NULL` | Data do recebimento. Índice `ix_receitas_data`, usado pelo filtro mensal por intervalo. |
| `descricao` | `TEXT NOT NULL` | Descrição da receita. Sem autocomplete, por decisão da rodada 7. |
| `valor` | `NUMERIC(12,2) NOT NULL` | Valor recebido. `CHECK (valor > 0)`. |
| `ref_receita_id` | `INT NOT NULL FK → tb_ref_receitas` | Classificação (categoria e subcategoria vêm daqui via JOIN). |
| `pessoa_id` | `INT NOT NULL FK → tb_pessoas` | Quem recebeu. Pré-preenchida com a pessoa do usuário logado. |
| `usuario_id` | `INT NOT NULL FK → tb_usuarios` | Quem fez o lançamento. Não muda na edição. |
| `anotacoes` | `TEXT` | Anotação livre. |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Auditoria. Desempata a ordenação da lista. |
| `atualizado_em` | `TIMESTAMPTZ` | Auditoria. `NULL` até o primeiro `UPDATE`; preenchido pela trigger `tg_receitas_atualizado_em`. |

---

## Tabelas de planejamento e patrimônio

### `tb_orcamento_meses`

Cabeçalho de cada mês orçado, criado na rodada 15. É a tabela **pai** das linhas de `tb_orcamentos`: guarda o que é atributo do mês, não da linha, e faz um mês sem nenhuma linha continuar existindo.

| Coluna | Tipo | Função |
|---|---|---|
| `ano_mes` | `DATE PK` | Mês orçado, sempre dia 1. `CHECK (EXTRACT(DAY FROM ano_mes) = 1)`. Sendo chave primária, há no máximo um orçamento por mês. |
| `receita_planejada` | `NUMERIC(12,2) NOT NULL DEFAULT 0` | Receita esperada no mês. `CHECK (>= 0)`. A poupança planejada é ela menos a soma das linhas. |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Quando o mês foi aberto. |
| `encerrado_em` | `TIMESTAMPTZ` | Quando foi encerrado. `NULL` = aberto. Mês encerrado não aceita alteração — **regra da aplicação**, não do banco. |
| `observacoes` | `TEXT` | Anotação livre sobre o mês (as premissas do planejamento, por exemplo). |

### `tb_orcamentos`

Uma linha por **subcategoria** orçada num mês. Até a rodada 14 era por categoria e nunca recebeu uma linha; a rodada 15 trocou a coluna, sem migração de dados.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `subcategoria_id` | `INT NOT NULL FK → tb_subcategorias` (`fk_orcamentos_subcategoria`) | Subcategoria orçada. O total da categoria é a soma das subcategorias dela — não se orça categoria diretamente. |
| `ano_mes` | `DATE NOT NULL FK → tb_orcamento_meses (ano_mes)` (`fk_orcamentos_mes`) | Mês de referência, dia 1, que **tem de existir** em `tb_orcamento_meses`. `CHECK (EXTRACT(DAY FROM ano_mes) = 1)` mantido, redundante com a FK mas barato. `UNIQUE (subcategoria_id, ano_mes)`. |
| `valor_planejado` | `NUMERIC(12,2) NOT NULL` | Teto planejado da subcategoria no mês. `CHECK (>= 0)` — zero é permitido. Realizado vs. planejado sai comparando com `vw_despesas` por intervalo de `data`. |

### `tb_ativos`

Onde o patrimônio está aplicado. Base para as metas de independência financeira.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `nome` | `TEXT NOT NULL UNIQUE` | Nome do ativo (ex.: Tesouro IPCA+ 2035, Fundo X, Poupança). |
| `classe` | `TEXT NOT NULL` | Classe (ex.: `renda_fixa`, `acoes`, `fiis`, `caixa`, `imovel`). Lista aberta, sem `CHECK`. Para gráficos de alocação. |
| `observacao` | `TEXT` | Anotação livre. |
| `ativo` | `BOOLEAN NOT NULL DEFAULT TRUE` | Posição encerrada some dos formulários; snapshots permanecem. |

### `tb_patrimonio_snapshots`

Foto mensal do valor de cada ativo, lançada manualmente (o sistema não controla saldo).

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `data` | `DATE NOT NULL` | Data da foto (sugestão: último dia do mês). Sem restrição de dia. |
| `ativo_id` | `INT NOT NULL FK → tb_ativos` | Ativo avaliado. `UNIQUE (data, ativo_id)`. |
| `valor` | `NUMERIC(14,2) NOT NULL` | Valor de mercado na data. `CHECK (>= 0)`. |
| `observacao` | `TEXT` | Anotação livre. |

---

## Anotações do usuário

### `tb_resumos_anuais`

Um resumo em texto livre por ano, escrito pelo dono para lembrar no futuro o porquê dos números daquele ano. Criada na rodada 20. Não é referência (ninguém aponta para ela) nem movimento (não entra em conta nenhuma): é anotação, e por isso tem seção própria. Tela em `/cadastros/resumos-anuais`; admite `UPDATE` e `DELETE` físico (ver Decisões de projeto).

| Coluna | Tipo | Função |
|---|---|---|
| `ano` | `INT PK` | Ano do resumo. Sendo chave primária, há no máximo um resumo por ano. `CHECK (ano BETWEEN 2000 AND 2100)` — sem ele, um dedo a mais gravaria `20026` em silêncio. **Sem FK**: o ano não é tabela; quem restringe a lista ao que faz sentido é a interface, que só oferece anos com lançamento. |
| `texto` | `TEXT NOT NULL` | O resumo, **sem tamanho máximo**. `CHECK (texto ~ '[^[:space:]]')`: exige pelo menos um caractere visível, o que recusa vazio, só espaços, só tabulações e só quebras de linha de uma vez — `NOT NULL` sozinho aceitaria `''`. Quebras de linha são preservadas; nada é interpretado como Markdown. |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Auditoria. |
| `atualizado_em` | `TIMESTAMPTZ` | Auditoria; `NULL` até o primeiro `UPDATE`, preenchido pela trigger `tg_resumos_anuais_atualizado_em`. A lista mostra este carimbo, ou `criado_em` quando o resumo nunca foi editado. |

---

## Objetos auxiliares

### `fn_set_atualizado_em()`

Função `plpgsql` usada pelas triggers `BEFORE UPDATE` de `tb_despesas`, `tb_receitas` e `tb_resumos_anuais`. Carimba `NEW.atualizado_em := now()`.

### `vw_despesas`

View que a aplicação e os relatórios devem consultar em vez de `tb_despesas` diretamente. Nada aqui é armazenado. Escrita (`INSERT`, `UPDATE`, `DELETE`) vai sempre em `tb_despesas`.

| Coluna | Origem | Função |
|---|---|---|
| `id`, `data`, `descricao`, `valor`, `prioridade`, `integra_ipca`, `observacoes`, `criado_em`, `atualizado_em` | `tb_despesas` | Colunas da despesa, sem alteração. |
| `ano_mes` | derivada de `data` | Mês de competência no formato `AAAAMM` (inteiro, ex.: `202609`). Para exibir e agrupar; **não** para filtrar (ver Padrões de acesso). |
| `subcategoria_id`, `subcategoria` | `tb_subcategorias` | Id e nome da subcategoria. |
| `categoria_id`, `categoria` | `tb_categorias` via subcategoria | Id e nome da categoria. |
| `essencialidade` | `COALESCE(despesa, subcategoria)` | Essencialidade **efetiva**. É esta que os relatórios e os filtros usam. |
| `conta_id`, `pessoa_id`, `usuario_id` | `tb_despesas` | FKs, sem JOIN de nome (fazer na aplicação quando necessário). |

### `vw_receitas`

Criada na rodada 7 — **única mudança de DDL desde a rodada 1**. Mesma regra: leitura por aqui, escrita em `tb_receitas`. `CREATE OR REPLACE VIEW`, `JOIN` simples com `tb_ref_receitas` (a FK é `NOT NULL`, então nenhum `LEFT JOIN` é necessário).

| Coluna | Origem | Função |
|---|---|---|
| `id`, `data`, `descricao`, `valor`, `ref_receita_id`, `pessoa_id`, `usuario_id`, `anotacoes`, `criado_em`, `atualizado_em` | `tb_receitas` | Colunas da receita, sem alteração. |
| `ano_mes` | derivada de `data` | Mês de competência `AAAAMM` (inteiro), mesma expressão de `vw_despesas`. Exibir e agrupar; **não** filtrar. |
| `categoria`, `subcategoria` | `tb_ref_receitas` | Classificação da fonte. |
| `ref_receita_ativo` | `tb_ref_receitas.ativo` | Se a fonte está ativa. A lista usa para marcar "fonte inativa" sem JOIN adicional. |

Definição:

```sql
CREATE OR REPLACE VIEW vw_receitas AS
SELECT r.id, r.data,
       (EXTRACT(YEAR FROM r.data) * 100 + EXTRACT(MONTH FROM r.data))::INT AS ano_mes,
       r.descricao, r.valor, r.ref_receita_id,
       rr.categoria, rr.subcategoria, rr.ativo AS ref_receita_ativo,
       r.pessoa_id, r.usuario_id, r.anotacoes, r.criado_em, r.atualizado_em
FROM tb_receitas     r
JOIN tb_ref_receitas rr ON rr.id = r.ref_receita_id;
```

---

## Relacionamentos

```
tb_categorias 1──n tb_subcategorias 1──n tb_despesas
tb_subcategorias 1──n tb_orcamentos
tb_orcamento_meses 1──n tb_orcamentos  (por ano_mes)
tb_ref_receitas 1──n tb_receitas
tb_contas 1──n tb_despesas
tb_pessoas 1──n tb_despesas
tb_pessoas 1──n tb_receitas
tb_pessoas 1──n tb_usuarios
tb_usuarios 1──n tb_despesas
tb_usuarios 1──n tb_receitas
tb_ativos 1──n tb_patrimonio_snapshots
tb_ipca (sem FK; cruza com vw_despesas pelo MES DA DATA,
         date_trunc('month', data) = tb_ipca.mes - nao pelo ano_mes)
tb_configuracoes (sem FK; consultada por chave e data)
tb_resumos_anuais (sem FK; consultada pelo ano, que e a chave)
```

## Indicadores derivados (não armazenados)

| Indicador | Cálculo |
|---|---|
| Taxa de poupança do mês | `(receitas − despesas) / receitas`, agregando `vw_receitas` e `vw_despesas` pelo mesmo intervalo de datas |
| Patrimônio total | soma de `tb_patrimonio_snapshots` na última data disponível |
| Número de independência | `despesas anuais / TSR`, com a TSR vigente na data de referência |
| Despesa deflacionada | `valor × indice_base / indice_do_mes`, por lançamento, somada depois; `indice_base` é o do último mês carregado em `tb_ipca`. Implementado na Análise por subcategoria (rodada 24), que **não filtra por `integra_ipca`** |
| Série de uma subcategoria | soma nominal, soma corrigida e `COUNT(*)` por mês, agrupadas depois em mês, trimestre, ano ou janela de 12 meses; mês sem lançamento é zero. Nada disso é gravado |
| Realizado vs. orçado | soma de `vw_despesas` por **subcategoria** no intervalo de `data` do mês, comparada a `tb_orcamentos` do mesmo `ano_mes`; a categoria é a soma das subcategorias dela |
| Poupança planejada do mês | `tb_orcamento_meses.receita_planejada` − soma de `tb_orcamentos.valor_planejado` do mês; a taxa é a poupança sobre a receita planejada |
| Total do período e divisão essencial × não essencial | agregados sobre `vw_despesas` no intervalo de datas filtrado (implementado na consulta de despesas) |
| Total de receitas do período por categoria | agregados sobre `vw_receitas` no intervalo filtrado (implementado na tela de receitas) |

## O roteiro não mora aqui

O que está feito e o que falta vive em `docs/Freedom - Histórico e Estado do Projeto.md`, seções 7 e 8. Este documento descreve **o banco**: duas listas de roteiro derivariam uma da outra e uma delas envelheceria — foi o que aconteceu com a que ficava aqui, que ainda dava como futuros o acompanhamento do orçamento (rodada 16) e a carga do IPCA (rodada 21).
