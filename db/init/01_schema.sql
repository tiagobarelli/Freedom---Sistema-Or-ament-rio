-- =============================================================================
-- Freedom - Sistema Orcamentario
-- 01_schema.sql - DDL completo (PostgreSQL 16)
--
-- Fonte da verdade: "Database - instrucoes.md"
-- Script idempotente: pode ser reaplicado sem erro em banco ja inicializado.
-- Nao contem dados de exemplo.
-- =============================================================================
--
-- DECISOES DE IMPLEMENTACAO
--
-- O documento de especificacao e a fonte da verdade, mas e silencioso em alguns
-- pontos onde o DDL precisa decidir. O que segue e o registro dessas escolhas e
-- do porque delas, para que este arquivo se explique sozinho no futuro.
--
-- 1. TODA COLUNA DE FK E "NOT NULL".
--    O .md escreve apenas "INT FK -> tb_x", sem dizer se aceita nulo. Optou-se
--    por exigir preenchimento em todas: subcategoria sem categoria seria orfa,
--    e despesa sem conta, pessoa ou usuario perderia a classificacao e a
--    autoria que justificam a existencia dessas colunas. Consequencia pratica:
--    lancar despesa ou receita exige que as tabelas de referencia ja tenham
--    pelo menos um registro cada, incluindo um usuario.
--
-- 2. "CHECK" DE DOMINIO EM tb_despesas.essencialidade E EM tb_contas.tipo.
--    O .md so pede CHECK explicitamente em tb_subcategorias.essencialidade,
--    em valor > 0 e em prioridade 1..4. Foram acrescentados dois:
--      - tb_despesas.essencialidade: sem ele, o COALESCE de vw_despesas poderia
--        devolver texto arbitrario e contaminar todo relatorio que agrupa por
--        essencial / nao essencial.
--      - tb_contas.tipo: o documento lista os quatro valores como fechados
--        (corrente, cartao, dinheiro, outro), e "outro" ja e o escape.
--    tb_ativos.classe ficou SEM CHECK de proposito: ali o .md usa "ex.:",
--    sinalizando lista aberta que deve crescer sem exigir migracao.
--
-- 3. REGRAS IMPLICITAS DE MES E DE SINAL VIRARAM "CHECK".
--    O .md diz "sempre dia 1" para tb_ipca.mes e tb_orcamentos.ano_mes sem
--    pedir constraint; um dia diferente de 1 quebraria silenciosamente o JOIN
--    por mes. Do mesmo modo, tb_orcamentos.valor_planejado e
--    tb_patrimonio_snapshots.valor aceitam zero mas nao valor negativo.
--
-- 4. AS COLUNAS "BOOLEAN" SAO "NOT NULL" ALEM DE TEREM DEFAULT.
--    O .md escreve so "BOOLEAN DEFAULT TRUE" em ativo / ativa / integra_ipca.
--    O DEFAULT nao impede um INSERT que passe NULL explicitamente, o que criaria
--    um terceiro estado sem significado entre ativo e inativo. Mesmo motivo para
--    criado_em ser NOT NULL.
--
-- 5. "atualizado_em" NAO TEM DEFAULT.
--    As convencoes do .md falam em "default now() e trigger", mas a descricao da
--    coluna diz "atualizado por trigger". Fica NULL ate o primeiro UPDATE: assim
--    o proprio dado distingue registro nunca editado de registro editado, o que
--    um default now() apagaria.
--
-- 6. "vw_despesas" EXPOE APENAS A ESSENCIALIDADE EFETIVA.
--    A coluna essencialidade da view ja e o COALESCE(despesa, subcategoria),
--    que e o valor que os relatorios devem usar. As duas origens separadas nao
--    sao repetidas para nao induzir uso errado; auditar de onde veio o valor
--    exige consultar tb_despesas e tb_subcategorias diretamente.
--
-- -----------------------------------------------------------------------------
-- REGRAS DA APLICACAO (deliberadamente NAO impostas pelo banco)
--
-- PRIORIDADE SO SE APLICA A DESPESA NAO ESSENCIAL.
--    tb_despesas.prioridade tem CHECK de faixa (1..4), mas nada no banco impede
--    que uma despesa de essencialidade efetiva "Essencial" tenha prioridade
--    preenchida. Isso e intencional: a regra vive na interface, que so exibe o
--    campo prioridade quando a essencialidade efetiva for "Nao Essencial".
--    Impor no banco exigiria uma trigger cruzando a despesa com a essencialidade
--    da subcategoria, e o efeito colateral seria pior que o problema: renomear
--    ou reclassificar a essencialidade de uma subcategoria passaria a falhar,
--    ou a zerar prioridades historicas em silencio, alterando o passado.
-- =============================================================================

SET client_encoding = 'UTF8';

-- =============================================================================
-- 1. FUNCAO GENERICA DE AUDITORIA
-- =============================================================================

CREATE OR REPLACE FUNCTION fn_set_atualizado_em()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.atualizado_em := now();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION fn_set_atualizado_em() IS
    'Trigger generica BEFORE UPDATE: carimba atualizado_em com now(). Usada em tb_despesas e tb_receitas.';


-- =============================================================================
-- 2. TABELAS DE REFERENCIA
-- =============================================================================

-- ----------------------------------------------------------------- categorias
CREATE TABLE IF NOT EXISTS tb_categorias (
    id      INT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome    TEXT    NOT NULL UNIQUE,
    ativo   BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE  tb_categorias        IS 'Categorias de despesa (nivel superior). Reutilizada pelo orcamento.';
COMMENT ON COLUMN tb_categorias.id     IS 'Identificador unico.';
COMMENT ON COLUMN tb_categorias.nome   IS 'Nome da categoria (ex.: Moradia, Alimentacao, Transporte).';
COMMENT ON COLUMN tb_categorias.ativo  IS 'Se FALSE, nao aparece nos formularios, mas o historico permanece.';

-- -------------------------------------------------------------- subcategorias
CREATE TABLE IF NOT EXISTS tb_subcategorias (
    id              INT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria_id    INT     NOT NULL
                            REFERENCES tb_categorias (id) ON DELETE RESTRICT,
    nome            TEXT    NOT NULL,
    essencialidade  TEXT    NOT NULL
                            CONSTRAINT ck_subcategorias_essencialidade
                            CHECK (essencialidade IN ('Essencial', 'Não Essencial')),
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_subcategorias_categoria_nome UNIQUE (categoria_id, nome)
);

COMMENT ON TABLE  tb_subcategorias                IS 'Subcategorias de despesa. E a unica coisa que o usuario escolhe ao lancar uma despesa; categoria e essencialidade vem daqui.';
COMMENT ON COLUMN tb_subcategorias.id             IS 'Identificador unico.';
COMMENT ON COLUMN tb_subcategorias.categoria_id   IS 'Categoria a qual a subcategoria pertence.';
COMMENT ON COLUMN tb_subcategorias.nome           IS 'Nome da subcategoria (ex.: Aluguel, Supermercado, Combustivel). UNIQUE (categoria_id, nome).';
COMMENT ON COLUMN tb_subcategorias.essencialidade IS 'Essencial ou Nao Essencial. Valor padrao herdado por toda despesa desta subcategoria.';
COMMENT ON COLUMN tb_subcategorias.ativo          IS 'Oculta dos formularios sem apagar.';

-- --------------------------------------------------------- referencia receita
CREATE TABLE IF NOT EXISTS tb_ref_receitas (
    id            INT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria     TEXT    NOT NULL,
    subcategoria  TEXT    NOT NULL,
    observacao    TEXT,
    ativo         BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_ref_receitas_categoria_subcategoria UNIQUE (categoria, subcategoria)
);

COMMENT ON TABLE  tb_ref_receitas              IS 'Classificacao das fontes de receita (categoria + subcategoria numa so tabela, pois o volume e pequeno).';
COMMENT ON COLUMN tb_ref_receitas.id           IS 'Identificador unico.';
COMMENT ON COLUMN tb_ref_receitas.categoria    IS 'Categoria da receita (ex.: Salario, Investimentos, Extras).';
COMMENT ON COLUMN tb_ref_receitas.subcategoria IS 'Subcategoria (ex.: Salario liquido, Dividendos, Venda de item). UNIQUE (categoria, subcategoria).';
COMMENT ON COLUMN tb_ref_receitas.observacao   IS 'Anotacao livre sobre a fonte.';
COMMENT ON COLUMN tb_ref_receitas.ativo        IS 'Oculta dos formularios sem apagar.';

-- -------------------------------------------------------------------- pessoas
CREATE TABLE IF NOT EXISTS tb_pessoas (
    id     INT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome   TEXT    NOT NULL UNIQUE,
    ativo  BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE  tb_pessoas       IS 'Membros da familia. Pessoa nao e o mesmo que usuario: toda pessoa pode ter despesas atribuidas a ela, mas nem toda pessoa acessa o sistema.';
COMMENT ON COLUMN tb_pessoas.id    IS 'Identificador unico.';
COMMENT ON COLUMN tb_pessoas.nome  IS 'Nome do membro da familia.';
COMMENT ON COLUMN tb_pessoas.ativo IS 'Oculta dos formularios sem apagar.';

-- ------------------------------------------------------------------- usuarios
CREATE TABLE IF NOT EXISTS tb_usuarios (
    id          INT         GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login       TEXT        NOT NULL UNIQUE,
    senha_hash  TEXT        NOT NULL,
    pessoa_id   INT         NOT NULL
                            REFERENCES tb_pessoas (id) ON DELETE RESTRICT,
    ativo       BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  tb_usuarios            IS 'Quem pode entrar no sistema. Inicialmente so o usuario master.';
COMMENT ON COLUMN tb_usuarios.id         IS 'Identificador unico.';
COMMENT ON COLUMN tb_usuarios.login      IS 'Nome de acesso.';
COMMENT ON COLUMN tb_usuarios.senha_hash IS 'Hash da senha (bcrypt ou argon2). NUNCA armazenar a senha em texto.';
COMMENT ON COLUMN tb_usuarios.pessoa_id  IS 'Liga o usuario ao membro da familia correspondente.';
COMMENT ON COLUMN tb_usuarios.ativo      IS 'Bloqueia o acesso sem apagar o registro (mantem a autoria dos lancamentos).';
COMMENT ON COLUMN tb_usuarios.criado_em  IS 'Quando a conta foi criada.';

-- --------------------------------------------------------------------- contas
CREATE TABLE IF NOT EXISTS tb_contas (
    id          INT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome        TEXT    NOT NULL UNIQUE,
    tipo        TEXT    NOT NULL
                        CONSTRAINT ck_contas_tipo
                        CHECK (tipo IN ('corrente', 'cartao', 'dinheiro', 'outro')),
    observacao  TEXT,
    ativa       BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE  tb_contas            IS 'De onde o dinheiro sai. Serve apenas para classificar a saida - nao ha saldo.';
COMMENT ON COLUMN tb_contas.id         IS 'Identificador unico.';
COMMENT ON COLUMN tb_contas.nome       IS 'Nome da conta (ex.: Conta corrente Banco X, Cartao Y, Dinheiro).';
COMMENT ON COLUMN tb_contas.tipo       IS 'corrente, cartao, dinheiro, outro. Permite agrupar relatorios por tipo.';
COMMENT ON COLUMN tb_contas.observacao IS 'Anotacao livre.';
COMMENT ON COLUMN tb_contas.ativa      IS 'Conta encerrada some dos formularios, historico permanece.';

-- ----------------------------------------------------------------------- ipca
CREATE TABLE IF NOT EXISTS tb_ipca (
    id               INT           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mes              DATE          NOT NULL UNIQUE
                                   CONSTRAINT ck_ipca_mes_dia_1
                                   CHECK (EXTRACT(DAY FROM mes) = 1),
    numero_indice    NUMERIC(14,6) NOT NULL,
    variacao_mensal  NUMERIC(6,4)
);

COMMENT ON TABLE  tb_ipca                 IS 'Serie historica do IPCA, para deflacionar despesas e ver crescimento real.';
COMMENT ON COLUMN tb_ipca.id              IS 'Identificador unico.';
COMMENT ON COLUMN tb_ipca.mes             IS 'Mes de referencia, sempre dia 1 (ex.: 2026-08-01).';
COMMENT ON COLUMN tb_ipca.numero_indice   IS 'Numero-indice acumulado publicado pelo IBGE (dez/1993 = 100). Deflacionar = valor * indice_base / indice_mes.';
COMMENT ON COLUMN tb_ipca.variacao_mensal IS 'Variacao percentual do mes, apenas para consulta rapida (opcional; derivavel do indice).';

-- -------------------------------------------------------------- configuracoes
CREATE TABLE IF NOT EXISTS tb_configuracoes (
    id             INT           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave          TEXT          NOT NULL,
    valor          NUMERIC(12,6) NOT NULL,
    vigente_desde  DATE          NOT NULL,
    observacao     TEXT,
    CONSTRAINT uq_configuracoes_chave_vigencia UNIQUE (chave, vigente_desde)
);

COMMENT ON TABLE  tb_configuracoes               IS 'Parametros do sistema com historico de vigencia. Mudar a TSR no futuro nao altera relatorios do passado.';
COMMENT ON COLUMN tb_configuracoes.id            IS 'Identificador unico.';
COMMENT ON COLUMN tb_configuracoes.chave         IS 'Nome do parametro: TSR (taxa segura de retirada anual), R (retorno real anual esperado da carteira), S (meta de taxa de poupanca). Outros no futuro.';
COMMENT ON COLUMN tb_configuracoes.valor         IS 'Valor do parametro. Percentuais em fracao (4 por cento = 0.04).';
COMMENT ON COLUMN tb_configuracoes.vigente_desde IS 'A partir de quando este valor vale. UNIQUE (chave, vigente_desde). O valor vigente numa data e o registro com maior vigente_desde menor ou igual a data.';
COMMENT ON COLUMN tb_configuracoes.observacao    IS 'Motivo da alteracao.';


-- =============================================================================
-- 3. TABELAS DE MOVIMENTO
-- =============================================================================

-- ------------------------------------------------------------------- despesas
CREATE TABLE IF NOT EXISTS tb_despesas (
    id               BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data             DATE          NOT NULL,
    descricao        TEXT          NOT NULL,
    valor            NUMERIC(12,2) NOT NULL
                                   CONSTRAINT ck_despesas_valor_positivo
                                   CHECK (valor > 0),
    subcategoria_id  INT           NOT NULL
                                   REFERENCES tb_subcategorias (id) ON DELETE RESTRICT,
    conta_id         INT           NOT NULL
                                   REFERENCES tb_contas (id) ON DELETE RESTRICT,
    pessoa_id        INT           NOT NULL
                                   REFERENCES tb_pessoas (id) ON DELETE RESTRICT,
    usuario_id       INT           NOT NULL
                                   REFERENCES tb_usuarios (id) ON DELETE RESTRICT,
    essencialidade   TEXT          CONSTRAINT ck_despesas_essencialidade
                                   CHECK (essencialidade IN ('Essencial', 'Não Essencial')),
    prioridade       SMALLINT      CONSTRAINT ck_despesas_prioridade
                                   CHECK (prioridade BETWEEN 1 AND 4),
    integra_ipca     BOOLEAN       NOT NULL DEFAULT TRUE,
    observacoes      TEXT,
    criado_em        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    atualizado_em    TIMESTAMPTZ
);

COMMENT ON TABLE  tb_despesas                 IS 'Tabela principal de lancamentos de saida. Despesa no cartao entra com a data da compra, como qualquer outra.';
COMMENT ON COLUMN tb_despesas.id              IS 'Identificador unico.';
COMMENT ON COLUMN tb_despesas.data            IS 'Data da compra (tambem para cartao de credito).';
COMMENT ON COLUMN tb_despesas.descricao       IS 'O que foi comprado.';
COMMENT ON COLUMN tb_despesas.valor           IS 'Valor da despesa. CHECK (valor > 0).';
COMMENT ON COLUMN tb_despesas.subcategoria_id IS 'Classificacao. Categoria e essencialidade padrao vem daqui via JOIN.';
COMMENT ON COLUMN tb_despesas.conta_id        IS 'Conta de onde o dinheiro saiu.';
COMMENT ON COLUMN tb_despesas.pessoa_id       IS 'Para quem foi a despesa.';
COMMENT ON COLUMN tb_despesas.usuario_id      IS 'Quem fez o lancamento (autoria).';
COMMENT ON COLUMN tb_despesas.essencialidade  IS 'Nula por padrao. Preencher so para sobrescrever a essencialidade da subcategoria nesta despesa especifica. Relatorios usam COALESCE(despesa.essencialidade, subcategoria.essencialidade).';
COMMENT ON COLUMN tb_despesas.prioridade      IS '1 a 4, apenas para despesas nao essenciais (1 = mais importante). Nula quando essencial.';
COMMENT ON COLUMN tb_despesas.integra_ipca    IS 'Se entra no agregado de despesas deflacionado. FALSE para gastos pontuais que distorceriam a serie.';
COMMENT ON COLUMN tb_despesas.observacoes     IS 'Anotacao livre.';
COMMENT ON COLUMN tb_despesas.criado_em       IS 'Auditoria.';
COMMENT ON COLUMN tb_despesas.atualizado_em   IS 'Auditoria; atualizado por trigger.';

CREATE INDEX IF NOT EXISTS ix_despesas_data            ON tb_despesas (data);
CREATE INDEX IF NOT EXISTS ix_despesas_subcategoria_id ON tb_despesas (subcategoria_id);
CREATE INDEX IF NOT EXISTS ix_despesas_pessoa_id       ON tb_despesas (pessoa_id);

DROP TRIGGER IF EXISTS tg_despesas_atualizado_em ON tb_despesas;
CREATE TRIGGER tg_despesas_atualizado_em
    BEFORE UPDATE ON tb_despesas
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_atualizado_em();

-- ------------------------------------------------------------------- receitas
CREATE TABLE IF NOT EXISTS tb_receitas (
    id              BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data            DATE          NOT NULL,
    descricao       TEXT          NOT NULL,
    valor           NUMERIC(12,2) NOT NULL
                                  CONSTRAINT ck_receitas_valor_positivo
                                  CHECK (valor > 0),
    ref_receita_id  INT           NOT NULL
                                  REFERENCES tb_ref_receitas (id) ON DELETE RESTRICT,
    pessoa_id       INT           NOT NULL
                                  REFERENCES tb_pessoas (id) ON DELETE RESTRICT,
    usuario_id      INT           NOT NULL
                                  REFERENCES tb_usuarios (id) ON DELETE RESTRICT,
    anotacoes       TEXT,
    criado_em       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    atualizado_em   TIMESTAMPTZ
);

COMMENT ON TABLE  tb_receitas                IS 'Lancamentos de entrada.';
COMMENT ON COLUMN tb_receitas.id             IS 'Identificador unico.';
COMMENT ON COLUMN tb_receitas.data           IS 'Data do recebimento.';
COMMENT ON COLUMN tb_receitas.descricao      IS 'Descricao da receita.';
COMMENT ON COLUMN tb_receitas.valor          IS 'Valor recebido. CHECK (valor > 0).';
COMMENT ON COLUMN tb_receitas.ref_receita_id IS 'Classificacao (categoria e subcategoria vem daqui via JOIN).';
COMMENT ON COLUMN tb_receitas.pessoa_id      IS 'Quem recebeu.';
COMMENT ON COLUMN tb_receitas.usuario_id     IS 'Quem fez o lancamento.';
COMMENT ON COLUMN tb_receitas.anotacoes      IS 'Anotacao livre.';
COMMENT ON COLUMN tb_receitas.criado_em      IS 'Auditoria.';
COMMENT ON COLUMN tb_receitas.atualizado_em  IS 'Auditoria; atualizado por trigger.';

CREATE INDEX IF NOT EXISTS ix_receitas_data ON tb_receitas (data);

DROP TRIGGER IF EXISTS tg_receitas_atualizado_em ON tb_receitas;
CREATE TRIGGER tg_receitas_atualizado_em
    BEFORE UPDATE ON tb_receitas
    FOR EACH ROW
    EXECUTE FUNCTION fn_set_atualizado_em();


-- =============================================================================
-- 4. TABELAS DE PLANEJAMENTO E PATRIMONIO
-- =============================================================================

-- ----------------------------------------------------------------- orcamentos
CREATE TABLE IF NOT EXISTS tb_orcamentos (
    id               INT           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    categoria_id     INT           NOT NULL
                                   REFERENCES tb_categorias (id) ON DELETE RESTRICT,
    ano_mes          DATE          NOT NULL
                                   CONSTRAINT ck_orcamentos_ano_mes_dia_1
                                   CHECK (EXTRACT(DAY FROM ano_mes) = 1),
    valor_planejado  NUMERIC(12,2) NOT NULL
                                   CONSTRAINT ck_orcamentos_valor_planejado
                                   CHECK (valor_planejado >= 0),
    CONSTRAINT uq_orcamentos_categoria_ano_mes UNIQUE (categoria_id, ano_mes)
);

COMMENT ON TABLE  tb_orcamentos                 IS 'Orcamento mensal por categoria de despesa.';
COMMENT ON COLUMN tb_orcamentos.id              IS 'Identificador unico.';
COMMENT ON COLUMN tb_orcamentos.categoria_id    IS 'Categoria orcada.';
COMMENT ON COLUMN tb_orcamentos.ano_mes         IS 'Mes de referencia, dia 1. UNIQUE (categoria_id, ano_mes).';
COMMENT ON COLUMN tb_orcamentos.valor_planejado IS 'Teto planejado para o mes. Realizado vs. planejado sai comparando com tb_despesas.';

-- --------------------------------------------------------------------- ativos
CREATE TABLE IF NOT EXISTS tb_ativos (
    id          INT     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome        TEXT    NOT NULL UNIQUE,
    classe      TEXT    NOT NULL,
    observacao  TEXT,
    ativo       BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE  tb_ativos            IS 'Onde o patrimonio esta aplicado. Base para as metas de independencia financeira.';
COMMENT ON COLUMN tb_ativos.id         IS 'Identificador unico.';
COMMENT ON COLUMN tb_ativos.nome       IS 'Nome do ativo (ex.: Tesouro IPCA+ 2035, Fundo X, Poupanca).';
COMMENT ON COLUMN tb_ativos.classe     IS 'Classe (ex.: renda_fixa, acoes, fiis, caixa, imovel). Para graficos de alocacao.';
COMMENT ON COLUMN tb_ativos.observacao IS 'Anotacao livre.';
COMMENT ON COLUMN tb_ativos.ativo      IS 'Posicao encerrada some dos formularios; snapshots permanecem.';

-- ------------------------------------------------------- patrimonio snapshots
CREATE TABLE IF NOT EXISTS tb_patrimonio_snapshots (
    id          INT           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    data        DATE          NOT NULL,
    ativo_id    INT           NOT NULL
                              REFERENCES tb_ativos (id) ON DELETE RESTRICT,
    valor       NUMERIC(14,2) NOT NULL
                              CONSTRAINT ck_patrimonio_snapshots_valor
                              CHECK (valor >= 0),
    observacao  TEXT,
    CONSTRAINT uq_patrimonio_snapshots_data_ativo UNIQUE (data, ativo_id)
);

COMMENT ON TABLE  tb_patrimonio_snapshots            IS 'Foto mensal do valor de cada ativo, lancada manualmente (o sistema nao controla saldo).';
COMMENT ON COLUMN tb_patrimonio_snapshots.id         IS 'Identificador unico.';
COMMENT ON COLUMN tb_patrimonio_snapshots.data       IS 'Data da foto (sugestao: ultimo dia do mes).';
COMMENT ON COLUMN tb_patrimonio_snapshots.ativo_id   IS 'Ativo avaliado. UNIQUE (data, ativo_id).';
COMMENT ON COLUMN tb_patrimonio_snapshots.valor      IS 'Valor de mercado na data.';
COMMENT ON COLUMN tb_patrimonio_snapshots.observacao IS 'Anotacao livre.';


-- =============================================================================
-- 5. VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW vw_despesas AS
SELECT
    d.id,
    d.data,
    (EXTRACT(YEAR FROM d.data) * 100 + EXTRACT(MONTH FROM d.data))::INT AS ano_mes,
    d.descricao,
    d.valor,
    d.subcategoria_id,
    s.nome                                       AS subcategoria,
    s.categoria_id,
    c.nome                                       AS categoria,
    COALESCE(d.essencialidade, s.essencialidade) AS essencialidade,
    d.prioridade,
    d.conta_id,
    d.pessoa_id,
    d.usuario_id,
    d.integra_ipca,
    d.observacoes,
    d.criado_em,
    d.atualizado_em
FROM tb_despesas d
JOIN tb_subcategorias s ON s.id = d.subcategoria_id
JOIN tb_categorias    c ON c.id = s.categoria_id;

COMMENT ON VIEW vw_despesas IS
    'Despesas ja com JOIN de subcategoria e categoria, essencialidade efetiva (COALESCE da despesa com a da subcategoria) e ano_mes no formato AAAAMM. Nada aqui e armazenado.';

COMMENT ON COLUMN vw_despesas.ano_mes        IS 'Mes de competencia derivado de data, no formato AAAAMM (ex.: 202609).';
COMMENT ON COLUMN vw_despesas.subcategoria   IS 'Nome da subcategoria (tb_subcategorias.nome).';
COMMENT ON COLUMN vw_despesas.categoria      IS 'Nome da categoria (tb_categorias.nome), obtido via subcategoria.';
COMMENT ON COLUMN vw_despesas.essencialidade IS 'Essencialidade efetiva: COALESCE(despesa.essencialidade, subcategoria.essencialidade).';

CREATE OR REPLACE VIEW vw_receitas AS
SELECT
    r.id,
    r.data,
    (EXTRACT(YEAR FROM r.data) * 100 + EXTRACT(MONTH FROM r.data))::INT AS ano_mes,
    r.descricao,
    r.valor,
    r.ref_receita_id,
    rr.categoria,
    rr.subcategoria,
    rr.ativo AS ref_receita_ativo,
    r.pessoa_id,
    r.usuario_id,
    r.anotacoes,
    r.criado_em,
    r.atualizado_em
FROM tb_receitas     r
JOIN tb_ref_receitas rr ON rr.id = r.ref_receita_id;

COMMENT ON VIEW vw_receitas IS
    'Receitas ja com JOIN da fonte (tb_ref_receitas), trazendo categoria, subcategoria e a situacao da fonte, mais ano_mes no formato AAAAMM. Nada aqui e armazenado.';

COMMENT ON COLUMN vw_receitas.ano_mes           IS 'Mes de competencia derivado de data, no formato AAAAMM (ex.: 202609).';
COMMENT ON COLUMN vw_receitas.categoria         IS 'Categoria da fonte (tb_ref_receitas.categoria).';
COMMENT ON COLUMN vw_receitas.subcategoria      IS 'Subcategoria da fonte (tb_ref_receitas.subcategoria).';
COMMENT ON COLUMN vw_receitas.ref_receita_ativo IS 'Situacao da fonte (tb_ref_receitas.ativo). Exposta aqui para a tela marcar fonte desativada sem um JOIN extra.';
