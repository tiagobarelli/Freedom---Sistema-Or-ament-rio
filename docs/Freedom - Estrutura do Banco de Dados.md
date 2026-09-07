# Freedom — Estrutura do Banco de Dados

Sistema web pessoal de controle financeiro. Roda localmente; acesso de outros membros da casa via Tailscale (sem exposição de portas na nuvem). Banco de dados: **PostgreSQL 16**.

> **Status**: schema implementado em `db/init/01_schema.sql` (idempotente). Este documento reflete exatamente o que está no banco. Se o SQL mudar, atualizar aqui; se este documento mudar, atualizar o SQL.

## Decisões de projeto

- **Sem parcelamento nem faturas de cartão**: despesa no cartão entra com a data da compra, como qualquer outra.
- **Sem controle de saldo**: o sistema categoriza fluxos (entradas e saídas); não há saldo inicial nem transferências entre contas.
- **Nada derivado é armazenado**: categoria e essencialidade vêm da subcategoria via JOIN; o mês vem da data (`vw_despesas`). Isso evita dados inconsistentes quando algo é renomeado.
- **Usuários no próprio Postgres** (não em SQLite separado): a segurança está no hash da senha (scrypt via `werkzeug.security`), não no arquivo. Isso permite chave estrangeira entre lançamentos e usuários.
- **Toda tabela tem `id` como chave primária** (`GENERATED ALWAYS AS IDENTITY`). Nomes nunca são chave.
- **Registros não são apagados**: tabelas de referência têm coluna `ativo`, para sumir dos formulários sem quebrar o histórico. Todas as FKs são `ON DELETE RESTRICT`.
- **Configurações têm vigência**: mudar a TSR no futuro não altera relatórios do passado.

## Decisões de implementação (tomadas ao escrever o DDL)

1. **Toda FK é `NOT NULL`.** Subcategoria sem categoria seria órfã; despesa sem conta, pessoa ou usuário sumiria dos relatórios agrupados. Consequência: lançar despesa ou receita exige que as tabelas de referência já tenham pelo menos um registro cada, incluindo um usuário. Despesas compartilhadas da casa (aluguel, luz) são atribuídas a uma pessoa chamada **Casa**.
2. **`CHECK` de domínio em `tb_despesas.essencialidade` e `tb_contas.tipo`.** Sem o primeiro, o `COALESCE` da view poderia devolver texto arbitrário; o segundo existe porque `tipo` serve para agrupar relatórios e "outro" já é o escape. `tb_ativos.classe` fica **sem** CHECK de propósito (lista aberta).
3. **Regras de mês e sinal viraram `CHECK`.** `tb_ipca.mes` e `tb_orcamentos.ano_mes` exigem dia 1 (senão o JOIN por mês quebra em silêncio). `tb_orcamentos.valor_planejado` e `tb_patrimonio_snapshots.valor` aceitam zero, mas não negativo.
4. **Booleanos são `NOT NULL` além do `DEFAULT`.** Evita um terceiro estado entre ativo e inativo. Mesmo para `criado_em`.
5. **`atualizado_em` não tem `DEFAULT`.** Fica `NULL` até o primeiro `UPDATE`; assim o dado distingue registro nunca editado de editado.
6. **`vw_despesas` expõe só a essencialidade efetiva.** As duas origens (despesa e subcategoria) não são repetidas, para não induzir uso errado.

## Regras da aplicação (deliberadamente **não** impostas pelo banco)

- **Prioridade só se aplica a despesa não essencial.** O banco só garante a faixa 1–4. A interface exibe o campo apenas quando a essencialidade efetiva for "Não Essencial". Impor por trigger faria a reclassificação de uma subcategoria falhar ou zerar prioridades históricas.
- **Padronização de `tb_ativos.classe`**: dropdown alimentado pelos valores já usados.

## Convenções

- Nomes de tabelas e colunas em `snake_case`, minúsculas, sem acento.
- Valores monetários: `NUMERIC(12,2)` (`NUMERIC(14,2)` em patrimônio).
- Percentuais: em fração (4% = `0.04`).
- Datas: `DATE`. Carimbos de auditoria: `TIMESTAMPTZ`.
- `criado_em`: `NOT NULL DEFAULT now()`. `atualizado_em`: `NULL` até o primeiro `UPDATE`, preenchido pela trigger `fn_set_atualizado_em()`.
- Constraints nomeadas: `ck_` (CHECK), `uq_` (UNIQUE), `ix_` (índice), `tg_` (trigger), `fn_` (função), `vw_` (view).

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

Classificação das fontes de **receita** (categoria + subcategoria numa só tabela, pois o volume é pequeno).

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

Quem pode entrar no sistema. Inicialmente só o usuário master.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `login` | `TEXT NOT NULL UNIQUE` | Nome de acesso. |
| `senha_hash` | `TEXT NOT NULL` | Hash da senha gerado pela aplicação com `werkzeug.security.generate_password_hash` (scrypt; formato `scrypt:N:r:p$salt$hash`). Criado pelo comando `flask create-user`. **Nunca** armazenar a senha em texto. |
| `pessoa_id` | `INT NOT NULL FK → tb_pessoas` | Liga o usuário ao membro da família correspondente. |
| `ativo` | `BOOLEAN NOT NULL DEFAULT TRUE` | Bloqueia o acesso sem apagar o registro (mantém a autoria dos lançamentos). |
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

Série histórica do IPCA, para deflacionar despesas e ver crescimento real. *(Carga prevista para o futuro.)*

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `mes` | `DATE NOT NULL UNIQUE` | Mês de referência, sempre dia 1 (ex.: `2026-08-01`). `CHECK (EXTRACT(DAY FROM mes) = 1)`. |
| `numero_indice` | `NUMERIC(14,6) NOT NULL` | Número-índice acumulado publicado pelo IBGE (dez/1993 = 100). Deflacionar = `valor × indice_base / indice_mes`. |
| `variacao_mensal` | `NUMERIC(6,4)` | Variação % do mês, apenas para consulta rápida (opcional; derivável do índice). |

### `tb_configuracoes`

Parâmetros do sistema com histórico de vigência.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `chave` | `TEXT NOT NULL` | Nome do parâmetro: `TSR`, `R`, `S` (outros no futuro). |
| `valor` | `NUMERIC(12,6) NOT NULL` | Valor do parâmetro. Percentuais em fração (4% = `0.04`). |
| `vigente_desde` | `DATE NOT NULL` | A partir de quando este valor vale. `UNIQUE (chave, vigente_desde)`. O valor vigente numa data é o registro com maior `vigente_desde ≤ data`. |
| `observacao` | `TEXT` | Motivo da alteração. |

Parâmetros iniciais:

| Chave | Significado |
|---|---|
| `TSR` | Taxa segura de retirada (anual). |
| `R` | Retorno real anual esperado da carteira. |
| `S` | Meta de taxa de poupança. |

---

## Tabelas de movimento

### `tb_despesas`

Tabela principal.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `BIGINT IDENTITY PK` | Identificador único. |
| `data` | `DATE NOT NULL` | Data da compra (também para cartão de crédito). Índice `ix_despesas_data`. |
| `descricao` | `TEXT NOT NULL` | O que foi comprado. |
| `valor` | `NUMERIC(12,2) NOT NULL` | Valor da despesa. `CHECK (valor > 0)`. |
| `subcategoria_id` | `INT NOT NULL FK → tb_subcategorias` | Classificação. Categoria e essencialidade padrão vêm daqui via JOIN. Índice `ix_despesas_subcategoria_id`. |
| `conta_id` | `INT NOT NULL FK → tb_contas` | Conta de onde o dinheiro saiu. |
| `pessoa_id` | `INT NOT NULL FK → tb_pessoas` | Para quem foi a despesa. Índice `ix_despesas_pessoa_id`. |
| `usuario_id` | `INT NOT NULL FK → tb_usuarios` | Quem fez o lançamento (autoria). |
| `essencialidade` | `TEXT` | **Nula por padrão.** Preencher só para sobrescrever a essencialidade da subcategoria nesta despesa específica. `CHECK` nos mesmos dois valores da subcategoria. Relatórios usam `COALESCE(despesa.essencialidade, subcategoria.essencialidade)`. |
| `prioridade` | `SMALLINT` | 1 a 4, apenas para despesas não essenciais (1 = mais importante). `CHECK (prioridade BETWEEN 1 AND 4)`. Nula quando essencial — regra da aplicação, não do banco. |
| `integra_ipca` | `BOOLEAN NOT NULL DEFAULT TRUE` | Se entra no agregado de despesas deflacionado. `FALSE` para gastos pontuais que distorceriam a série. |
| `observacoes` | `TEXT` | Anotação livre. |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Auditoria. |
| `atualizado_em` | `TIMESTAMPTZ` | Auditoria. `NULL` até o primeiro `UPDATE`; preenchido pela trigger `tg_despesas_atualizado_em`. |

### `tb_receitas`

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `BIGINT IDENTITY PK` | Identificador único. |
| `data` | `DATE NOT NULL` | Data do recebimento. Índice `ix_receitas_data`. |
| `descricao` | `TEXT NOT NULL` | Descrição da receita. |
| `valor` | `NUMERIC(12,2) NOT NULL` | Valor recebido. `CHECK (valor > 0)`. |
| `ref_receita_id` | `INT NOT NULL FK → tb_ref_receitas` | Classificação (categoria e subcategoria vêm daqui via JOIN). |
| `pessoa_id` | `INT NOT NULL FK → tb_pessoas` | Quem recebeu. |
| `usuario_id` | `INT NOT NULL FK → tb_usuarios` | Quem fez o lançamento. |
| `anotacoes` | `TEXT` | Anotação livre. |
| `criado_em` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Auditoria. |
| `atualizado_em` | `TIMESTAMPTZ` | Auditoria. `NULL` até o primeiro `UPDATE`; preenchido pela trigger `tg_receitas_atualizado_em`. |

---

## Tabelas de planejamento e patrimônio

### `tb_orcamentos`

Orçamento mensal por categoria de despesa.

| Coluna | Tipo | Função |
|---|---|---|
| `id` | `INT IDENTITY PK` | Identificador único. |
| `categoria_id` | `INT NOT NULL FK → tb_categorias` | Categoria orçada. |
| `ano_mes` | `DATE NOT NULL` | Mês de referência, dia 1. `CHECK (EXTRACT(DAY FROM ano_mes) = 1)`. `UNIQUE (categoria_id, ano_mes)`. |
| `valor_planejado` | `NUMERIC(12,2) NOT NULL` | Teto planejado para o mês. `CHECK (>= 0)` — zero é permitido. Realizado vs. planejado sai comparando com `vw_despesas`. |

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

## Objetos auxiliares

### `fn_set_atualizado_em()`

Função `plpgsql` usada pelas triggers `BEFORE UPDATE` de `tb_despesas` e `tb_receitas`. Carimba `NEW.atualizado_em := now()`.

### `vw_despesas`

View que a aplicação e os relatórios devem consultar em vez de `tb_despesas` diretamente. Nada aqui é armazenado.

| Coluna | Origem | Função |
|---|---|---|
| `id`, `data`, `descricao`, `valor`, `prioridade`, `integra_ipca`, `observacoes`, `criado_em`, `atualizado_em` | `tb_despesas` | Colunas da despesa, sem alteração. |
| `ano_mes` | derivada de `data` | Mês de competência no formato `AAAAMM` (inteiro, ex.: `202609`). |
| `subcategoria_id`, `subcategoria` | `tb_subcategorias` | Id e nome da subcategoria. |
| `categoria_id`, `categoria` | `tb_categorias` via subcategoria | Id e nome da categoria. |
| `essencialidade` | `COALESCE(despesa, subcategoria)` | Essencialidade **efetiva**. É esta que os relatórios usam. |
| `conta_id`, `pessoa_id`, `usuario_id` | `tb_despesas` | FKs, sem JOIN de nome (fazer na aplicação quando necessário). |

---

## Relacionamentos

```
tb_categorias 1──n tb_subcategorias 1──n tb_despesas
tb_categorias 1──n tb_orcamentos
tb_ref_receitas 1──n tb_receitas
tb_contas 1──n tb_despesas
tb_pessoas 1──n tb_despesas
tb_pessoas 1──n tb_receitas
tb_pessoas 1──n tb_usuarios
tb_usuarios 1──n tb_despesas
tb_usuarios 1──n tb_receitas
tb_ativos 1──n tb_patrimonio_snapshots
tb_ipca (sem FK; cruza com vw_despesas.ano_mes)
tb_configuracoes (sem FK; consultada por chave e data)
```

## Indicadores derivados (não armazenados)

| Indicador | Cálculo |
|---|---|
| Taxa de poupança do mês | `(receitas − despesas) / receitas` |
| Patrimônio total | soma de `tb_patrimonio_snapshots` na última data disponível |
| Número de independência | `despesas anuais / TSR` |
| Despesa deflacionada | `valor × indice_base / indice_do_mes`, só para `integra_ipca = TRUE` |
| Realizado vs. orçado | soma de `vw_despesas` por categoria e mês comparada a `tb_orcamentos` |

## Roteiro

1. ~~DDL em `db/init/01_schema.sql`~~ — feito.
2. ~~Criar o usuário master via `flask create-user`~~ — feito.
3. Aplicação web: cadastro de categorias, subcategorias, contas, pessoas e fontes de receita pela interface; lançamento de despesas e receitas.
4. Futuro: carga do IPCA (API SIDRA/IBGE, `INSERT ... ON CONFLICT (mes) DO UPDATE`), orçamento, patrimônio e indicadores.