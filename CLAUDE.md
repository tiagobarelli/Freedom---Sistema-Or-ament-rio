# CLAUDE.md

Orientações para o Claude Code (e qualquer agente) trabalhando neste repositório.

> **Idioma**: tudo em português do Brasil — interface, nomes de função, variáveis,
> comentários, mensagens de commit. Não traduza identificadores existentes nem
> introduza nomes em inglês. Comentários explicam **por que**, não o que.

---

## 1. O que é o Freedom

Sistema web pessoal de controle financeiro de uma família. Roda localmente em
Windows (Postgres em Docker, Flask no host); no futuro os demais membros da casa
acessam pela rede Tailscale. **Nada é exposto na internet.**

Registra despesas e receitas, classifica por categoria/subcategoria/pessoa/conta,
e mostra painéis anual e mensal, além de um orçamento por subcategoria. O objetivo
de longo prazo inclui deflação por IPCA, patrimônio e metas de independência
financeira — nada disso está implementado. A série do IPCA já está no banco
desde a rodada 21, mas ainda não há tela nem cálculo que a leia.

**Há dado real em produção** (mais de 1.800 despesas e 145 receitas, de 2025 e
2026). Ver a seção 8 antes de escrever qualquer coisa no banco.

## 2. Rodar

Pré-requisitos: Docker Desktop, Python 3.12 (o `venv/` já vem criado na máquina do
dono; Python 3.14 não tem wheel para tudo).

```powershell
docker compose up -d                     # Postgres 16 + pgAdmin
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m flask --app freedom --debug run --port 5000
```

**Sempre com `--debug`.** Sem ele o Jinja não recarrega template e o Python não
recarrega módulo — duas rodadas do projeto perderam a validação inteira por causa
disso, porque a captura "depois" comparava HTML velho com CSS novo. **Reinicie o
servidor depois de mexer em código, antes de validar.**

O schema em `db/init/01_schema.sql` roda sozinho na primeira criação do volume. É
idempotente; para reaplicar num banco com dados:

```powershell
docker compose exec -T postgres psql -U <usuario> -d <banco> -f /docker-entrypoint-initdb.d/01_schema.sql
```

Não existe seed de usuário em SQL (a senha precisa passar pelo hash da aplicação):

```powershell
flask create-user --login <login> --pessoa "<Nome>"
flask set-password --login <login>
```

A série do IPCA entra por comando, e por mais nada — não há tela:

```powershell
flask carregar-ipca
```

Roda depois do dia 10 de cada mês, quando o IBGE publica o índice do mês
anterior. Rodar de novo é inofensivo (upsert que nunca apaga linha).

### `.env` (não versionado)

O `.env` fica na raiz e **nunca** vai para o git. Chaves usadas:

| Chave | Função |
|---|---|
| `DATABASE_URL` | String de conexão do psycopg. |
| `SECRET_KEY` | Assina o cookie de sessão e os tokens CSRF. |
| `DB_POOL_MIN` / `DB_POOL_MAX` | Tamanho do pool (padrão 1 e 5). |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_PORT` | Lidos pelo `docker-compose.yml`. |
| `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` / `PGADMIN_PORT` | idem. |
| `senha_teste` | Senha do usuário de teste, usada só pela validação em navegador. |

Num clone novo o `.env` precisa ser recriado. Gere a `SECRET_KEY` com
`python -c "import secrets; print(secrets.token_hex(32))"`.

**Nunca escreva o valor de nenhuma dessas chaves em código, prompt, commit,
relatório ou documento.** Referencie sempre pelo nome da variável.

## 3. Stack (fechada — não proponha alternativas)

| Camada | Escolha |
|---|---|
| Web | Flask 3, application factory (`create_app` em `freedom/__init__.py`), Blueprints |
| Banco | psycopg 3 + `psycopg_pool`, SQL direto parametrizado, `row_factory=dict_row`. **Sem ORM, sem migrações** |
| Auth | Flask-Login; hash com `werkzeug.security` (scrypt) |
| Formulários | Flask-WTF (CSRF em todo POST) |
| Interatividade | HTMX 2.0.4 (arquivo local) + JS vanilla pontual |
| Gráficos | Chart.js 4.5.1, UMD **local**, só na Visão Anual. Núcleo, sem plugins |
| CSS | Um arquivo escrito à mão (`static/css/app.css`), tokens em `:root`. **Sem Tailwind, sem React, sem biblioteca de ícones** |
| Ícones | Lucide (ISC), **SVG inline** pela macro `icone` em `templates/_macros.html` |
| Dinheiro | `Decimal` em todo cálculo; `float` só na serialização final para JSON de gráfico |
| Testes/validação | Playwright (`requirements-dev.txt`), navegador real |

**Nenhuma requisição a domínio externo, em nenhuma tela.** Sem CDN, sem unpkg, sem
fonte web. A única chamada externa do sistema inteiro é a da API do SIDRA em
`flask carregar-ipca` (`urllib.request` da stdlib, rodada 21): é comando, não
tela, e só acontece quando o dono o chama. A tipografia é a fonte do sistema. Isso é verificável e é verificado: a
validação de cada rodada confere que a aba Rede só tem `/static/...`.

## 4. Mapa do código

```
freedom/
  __init__.py      create_app: CSRF, pool, Flask-Login, blueprints, CLI,
                   filtros Jinja `moeda` e `numero`
  config.py        lê o .env; template_folder/static_folder apontam para a raiz
  db.py            ConnectionPool, dict_row, get_connection(), query_one(),
                   query_all(), executar()
  util.py          destino_interno(); ValorInvalido, converter_valor,
                   converter_numero(percentual=), formatar_valor,
                   formatar_numero, escapar_like; MESES; so_fragmento;
                   chave_alfabetica (NFD — nunca `locale`); fracao
  cli.py           flask create-user, flask set-password, flask carregar-ipca
  ipca.py          carga do IPCA: buscar (rede), interpretar (pura), gravar
                   (banco, uma transação só). tb_ipca só se alimenta daqui
  auth/            /login, /logout (POST com CSRF)
  main/            "/" Visão Anual, "/mensal" Visão Mensal,
                   "/mensal/categoria/<id>" fragmento
                   servico.py        Anual: painel_do_ano, _totais_do_ano
                                     (origem única dos totais), _tabela_mensal,
                                     _tabela_categorias, _graficos;
                                     helpers card, percentual;
                                     anos_com_lancamento e resumo_do_ano, que o
                                     cadastro de resumos importa daqui
                   servico_mensal.py Mensal: painel_do_mes e as três tabelas
  cadastros/       /cadastros — um módulo por entidade + servico.py
                   (alternar_ativo, traduzir_unique, contagem).
                   resumos_anuais.py é o de fora da série: chave é o ano, não
                   há `ativo`, e a segunda ação é Excluir
  lancamentos/     /lancamentos — despesas.py, consulta.py, receitas.py,
                   servico.py, servico_receitas.py, forms.py
  configuracoes/   /configuracoes — parâmetros com vigência (CATALOGO em Python)
  orcamento/       /orcamento — servico.py (montagem) e acompanhamento.py (leitura)
templates/         base.html, layout_app.html, _macros.html + uma pasta por blueprint
static/css/app.css seções numeradas 1–8 (ver seção 7 deste arquivo)
static/js/         htmx.min.js, chart.umd.js, visao_anual.js
db/init/01_schema.sql
docs/              Freedom - Estrutura do Banco de Dados.md   (fonte da verdade)
                   Freedom - Histórico e Estado do Projeto.md (decisões e lições)
```

**Camadas**: a rota só orquestra (valida entrada, escolhe o template). Toda
consulta e toda composição de tela moram em `servico.py`. O template só formata.

## 5. Banco

Fonte da verdade: `docs/Freedom - Estrutura do Banco de Dados.md` e
`db/init/01_schema.sql`. **Se um muda, o outro muda.**

15 tabelas (`tb_categorias`, `tb_subcategorias`, `tb_ref_receitas`, `tb_pessoas`,
`tb_usuarios`, `tb_contas`, `tb_ipca`, `tb_configuracoes`, `tb_despesas`,
`tb_receitas`, `tb_orcamento_meses`, `tb_orcamentos`, `tb_resumos_anuais`,
`tb_ativos`, `tb_patrimonio_snapshots`) e duas views (`vw_despesas`,
`vw_receitas`).

Regras que se aplicam a todo código novo:

- **Leitura sempre pelas views; escrita nas tabelas base.** `vw_despesas` já
  resolve a essencialidade efetiva (`COALESCE(despesa, subcategoria)`).
- **`ano_mes` serve para exibir e agrupar, nunca para filtrar.** Todo filtro de
  período usa `data >= início AND data < início do período seguinte` — é o que
  faz os índices `ix_despesas_data` / `ix_receitas_data` serem usados. Filtrar por
  coluna derivada de view mata o índice (comprovado com EXPLAIN ANALYZE).
- **Nada derivado é armazenado.** Toda FK é `NOT NULL` e `ON DELETE RESTRICT`.
- Referência não se apaga: tem `ativo` (`ativa` em `tb_contas`).
- Chave primária é `id`, **menos onde o período é a chave**: `tb_orcamento_meses`
  (`ano_mes`) e `tb_resumos_anuais` (`ano`). Há no máximo uma linha por período,
  e um `id` ao lado exigiria um `UNIQUE` para dizer o mesmo.
- `NOT NULL` em `TEXT` aceita `''`. Quando o vazio não faz sentido, o `CHECK`
  vai junto: `texto ~ '[^[:space:]]'` (pelo menos um caractere visível) cobre
  vazio, espaços, tabulações e quebras de linha numa expressão só.
- `date_trunc(data) = ANY(...)` mata o índice; acumulado de vários meses é OR de
  intervalos com datas parametrizadas.
- Mudança de schema é feita com blocos idempotentes (`ADD/DROP COLUMN IF EXISTS`,
  `DO $$ IF NOT EXISTS (constraint)`), **nunca `DROP TABLE`**, e validada
  re-executando o script no banco com dados **e** num banco descartável do zero.

## 6. Regras de domínio (decididas, não reabrir)

- Cartão de crédito: **só data da compra**, sem parcelas nem faturas.
- **Sem controle de saldo**: o sistema categoriza fluxos; não há saldo inicial nem
  transferências.
- **Movimento se exclui, referência se desativa.** Lançamento errado é apagado de
  verdade (DELETE físico em `tb_despesas`); tabela de referência nunca.
  Configuração, linha de orçamento e **resumo anual** também se excluem (são
  entrada do usuário). Nenhum dos três tem `ativo`.
- Despesas compartilhadas da casa vão para uma pessoa chamada **Casa**.
- Consulta de despesas é tela separada da de lançamento. **Receitas são tela
  única.** A assimetria é intencional.
- **Ano/mês inválido na URL cai no período corrente**, sem erro e sem tela vazia.
- Prioridade (1–4) só existe quando a essencialidade efetiva é "Não Essencial" —
  isso é regra da aplicação, não do banco, e é limpa no servidor mesmo que o POST
  traga valor.
- Orçamento é por subcategoria, mês a mês, com uma receita planejada global.
  **Zero é planejado legítimo** ("está no plano, não pretendo gastar") — assimetria
  deliberada com lançamento, que exige `> 0`. Mês **encerrado** não recebe
  INSERT/UPDATE/DELETE; reabrir só se não existir mês orçado posterior.
- Nos painéis, só categorias e pessoas **com despesa no período** aparecem. Na
  tabela mensal da Anual os 12 meses aparecem sempre.
- **Resumo anual**: um texto livre por ano, sem tamanho máximo, sem formatação
  (quebras de linha preservadas, nada de Markdown). O ano é a chave — há no
  máximo um resumo por ano, e a edição não troca o ano. Só se oferece ano que a
  Visão Anual mostra e que ainda não tem resumo. Na Anual, **ano sem resumo não
  mostra card, aviso nem convite para escrever um**.

## 7. Convenções de código que o projeto exige

### Servidor

- **Nada é decidido em Jinja.** Cor, travessão, estado de estouro, classe CSS,
  plural, contador — tudo vem pronto do Python. O template escolhe o formato
  (macro `reais`, filtro `numero`) e emite o nome da classe que recebeu.
- **Agregados vêm de consulta própria**, nunca de soma em Python sobre a página.
  Exceção prevista e única: composição em `Decimal` sobre conjunto **pequeno e
  completo** cuja definição É "estas linhas" (ex.: `total_exibido` das 15 recentes).
- **Dois lugares que mostram o mesmo número leem da mesma origem.**
- Formatação: `moeda`; percentual pelo filtro `numero` (vírgula, uma casa); sem
  denominador → travessão (`fracao` devolve `None`); **negativo em vermelho no
  `<span>`**, travessão nunca vermelho.
- Valor monetário entra com vírgula (`converter_valor`). `UniqueViolation` vira
  erro de campo legível. Transação por request; rollback em erro.
- Ordenação alfabética pt-BR em Python com `chave_alfabetica` (NFD), nunca `locale`.
- Busca textual escapa `%` e `_` (`ESCAPE '\'` em **raw string**), sem `unaccent`.
- `destino_interno` em todo redirect que aceita `?next=` / `?retorno=`.
- **Helper duplicado é contradição**: promova para `util.py` na hora e aponte
  todos os módulos para lá.

### HTMX

- Filtros são GET na URL com `hx-push-url`; a mesma rota devolve página ou
  fragmento conforme `HX-Request`, com exceção para `HX-History-Restore-Request`.
  **Exceção deliberada**: seletores de painel e de orçamento recarregam a página
  inteira.
- **`<template>` em resposta out-of-band que comece com `<tr>`.** Misturar `<tr>`
  e `<div>` soltos põe o parser em contexto de tabela e expulsa os `<div>`.
- **Swap OOB que não seja `outerHTML`/`true` insere o CONTEÚDO do elemento
  marcado, não o elemento.** Para inserir uma `<tr>` com
  `hx-swap-oob="beforeend:#alvo"`, embrulhe-a num `<tbody>` que carregue o
  atributo — senão chegam `<td>` soltos, que o parser descarta.
- **Alvo de troca OOB que às vezes não aparece continua no DOM, com `hidden`.**
  Elemento que some não pode ser trocado (é a razão do `#bloco-prioridade` e,
  desde a rodada 20, do `#botao-novo-resumo`). Cuidado com o par disso no CSS:
  `display` de folha de autor vence o `[hidden]` do navegador — já resolvido
  para `.btn`.
- Uma ação que muda duas regiões da tela devolve as duas de uma vez: o alvo
  principal e o resto fora de banda. Excluir um resumo anual troca a lista
  **e** o botão da barra superior, porque os dois dependem do mesmo fato.
- Estado de UI que sobrevive ao re-render vai em `<input type="hidden">`; filtro
  fora do formulário vai por `hx-include`.
- `hx-vals` para renomear parâmetro; `hx-params="none"` cancela. O gatilho
  `changed` **ignora preenchimento por JavaScript** (`fill` não dispara `keyup`) —
  isso vale inclusive para escrever teste.
- `HX-Retarget` quando o alvo natural do disparador não é onde a resposta cai.
- Rota só de fragmento: sem `HX-Request` → redirect para a página-mãe com os
  mesmos parâmetros, **antes** de qualquer 404. Regra de estado recusada → **409**.

### CSS (`static/css/app.css`, ~4.370 linhas, seções numeradas)

```
1 Variáveis   2 Reset   3 Fundo   4 Layout   5 Componentes   6 Login
7 Responsivo (< 768px)   8 Utilitários
```

- A seção 1 tem **duas camadas**: (a) tokens do design system (`--bg`, `--ink-*`,
  `--accent`, `--control-h`, `--green-ink`…) e (b) **apelidos do tema roxo antigo**
  (`--cor-destaque`, `--linha`, `--vidro*`…) apontando para eles. Os apelidos
  existem só até as telas antigas serem refeitas. **Nada de novo deve usar um
  apelido.**
- Tema: fundo `#F5F5F7`, cartão branco raio 14, sidebar escura, acento teal
  `#30B0C7`. **Verde e vermelho são reservados** a receita, despesa e valor
  negativo — não servem de decoração. O único `backdrop-filter` do sistema é o da
  barra superior.
- `font-variant-numeric: tabular-nums` é global (no `body`).
- Utilitário nasce **global**, na seção 8. Classe utilitária criada dentro de um
  seletor de tela não funciona fora dela e o erro é silencioso.
- `1fr` tem mínimo `min-content`: em grade com canvas ou tabela larga, use
  `minmax(0, 1fr)`.
- **Texto de cartão ocupa a largura do cartão.** Nada de `max-width` em `ch`
  para "encurtar a linha de leitura": num monitor largo isso quebra o parágrafo
  no meio do cartão e estica a altura à toa. Quem decide o comprimento da linha
  é a largura da tela, como no resto do painel. (Tentado e desfeito no card de
  resumo anual, rodada 20.)
- Texto livre do usuário: `white-space: pre-wrap` preserva as quebras sem
  interpretar formatação, e `overflow-wrap: anywhere` impede que uma URL sem
  espaço alargue a página no celular. Os dois andam juntos.
- `.so-leitor` é absoluto: dentro de contêiner que rola precisa de ancestral
  `position: relative`, senão ele estica a página inteira.
- `display` de folha de autor vence o `[hidden]` do navegador (regra de user
  agent). Todo componente com `display:` próprio precisa de
  `.componente[hidden] { display: none }` — feito para `.btn` na rodada 20,
  quando um botão passou a sumir da barra superior.
- `white-space: nowrap` herdado estica tabela no celular — sempre desfaça na
  seção 7.
- Chart.js: contêiner com **altura fixa** e `maintainAspectRatio: false`; eixo sem
  centavos, tooltip com centavos; **cores lidas de variáveis CSS por
  `getComputedStyle`** — nenhum hexadecimal no JS.

### Ocultar valores — o olho (rodada 19)

O dono às vezes abre o sistema com alguém olhando a tela. O botão olho da Visão
Anual apaga **todo número da tela**. A proteção é **visual**: os números
continuam no HTML e no JSON dos gráficos, e isso é aceitável.

**Como marcar.** Nada de servidor: nenhuma rota, nenhum cookie, nenhuma sessão
Flask, nenhum Python. Só quatro classes, globais, na seção **5.16** do CSS:

| Marca | Onde vai | O que faz oculto |
|---|---|---|
| `.sensivel` | no elemento **mais interno**, o que embrulha o valor | vira bloco cinza da largura do texto |
| `.sensivel-bloco` | na caixa toda | a caixa inteira vira o bloco, com o que houver dentro |
| `.sensivel-barra` | no trilho (ou na célula que contém a barra) | o sulco fica, a fatia colorida some |
| `.sensivel-area` | na área do gráfico | a área vira bloco neutro e o conteúdo fica invisível |

- Marcar não pode mudar a tela com os valores à mostra: `.sensivel` sozinha não
  declara nada. Mas **um `<span>` a mais no meio de uma frase muda o
  arredondamento das letras seguintes** — o diff de pixels da rodada 19 pegou
  isso na linha de apoio da tabela mês a mês em 390px. Por isso valor no meio de
  texto se esconde pela caixa em volta (`.sensivel-bloco`), nunca por um `<span>`
  no meio da frase.
- Os seletores começam em `:root[data-valores=...]`: sem o `:root` o peso perde
  para regra de tela (duas classes mais um elemento) e o texto continua pintado.
- `display: none` no canvas está **proibido**: o Chart.js mede o pai a cada
  redimensionamento. Use `visibility`, que também tira o canvas do ponteiro e
  mata o tooltip.
- `user-select: none` é o que impede o Ctrl+A de revelar — sem ele o realce da
  seleção pinta o texto por cima do bloco.
- Continuam visíveis: barra superior, rótulos, títulos de cartão, cabeçalhos de
  tabela, nomes de mês e de categoria, e "Total".

**Onde mora o estado.** Em `data-valores` (`ocultos` | `visiveis`) no `<html>`,
escrito por um script inline no bloco `cabeca` de `templates/layout_app.html` —
o único dono. O CSS lê dali e o `aria-pressed` do botão sai da mesma função:
os dois nunca divergem. O estado pertence à **aba**, não à tela nem ao usuário.
**O servidor sempre manda a página oculta**: sem JavaScript ela fica oculta
(falha fechada) e não há um quadro sequer com valor à mostra.

**As regras, todas verificadas em navegador:**

- **(a)** aba nova, ou entrar de novo depois de sair → oculto;
- **(b)** o olho alterna;
- **(c)** com valores à mostra, continuam à mostra ao trocar de ano, ir a outra
  tela e voltar (link ou Voltar do navegador) e recarregar com F5;
- **(d)** sair da aba (outra aba, janela minimizada, trocar de app no celular) →
  ao voltar, oculto, sem recarregar;
- **(e)** fechar a aba → oculto na próxima vez, **inclusive** se o navegador
  restaurar a aba ou duplicá-la copiando o `sessionStorage`.

**Como (c), (d) e (e) convivem:** um **bastão** no `sessionStorage`, entregue no
`pagehide` de quem sai e **consumido na leitura** por quem entra — enquanto a
página vive não há nada guardado, então aba duplicada copia um armazém vazio. O
bastão leva a hora e só vale por **300 ms**, e esse prazo tem um único trabalho:
fechar a aba e navegar são a mesma sequência de eventos, e o prazo é o que
impede uma aba **reaberta** de herdar o bastão do fechamento. Navegação real
chega com 2–4 ms (13 ms com a CPU 4× freada, 101 ms com 20×); reabrir aba à mão
leva muito mais.

> **Armadilha:** `visibilitychange` com `hidden` dispara também quando a
> **própria aba navega** — trocar de ano, clicar no menu, F5 — e não só quando o
> usuário sai dela. Tratar todo `hidden` como "saiu da aba" transforma (c) em
> (d). O que separa os dois é a **ordem**, não o relógio: **quando a aba navega,
> o `pagehide` vem sempre antes do `hidden`** (medido em F5, troca de ano, link,
> Voltar e ida para o bfcache). `hidden` depois do `pagehide` deste documento é
> navegação; `hidden` sozinho é saída de aba. Validação que não prova os dois
> lados não prova nada.

> **Segunda armadilha, a que só aparece no navegador de verdade:** Voltar pode
> devolver o documento **inteiro** do cache de ida e volta (bfcache), vivo, sem
> carregar nada — e o `pageshow` de quem volta dispara **antes** do `pagehide` de
> quem sai (medido: 1 ms antes), então ali o bastão ainda nem foi entregue. Quem
> volta do cache é o mesmo documento e volta como estava; a única coisa que pode
> ter tirado dele o direito de ver é o usuário ter saído da aba enquanto ele
> dormia, e isso a outra tela anota na marca `freedom.valores.saiu` no momento em
> que a saída acontece — já gravada quando o `pageshow` lê. A marca morre quando
> a aba reconquista o direito. O Playwright **desliga o bfcache** (página com
> depurador atado não entra no cache), então essa falha não aparece em teste
> automatizado comum: foi preciso soltar o CDP e mandar Alt+Seta esquerda pela
> janela do Windows.

A detecção de saída de aba roda em **toda tela autenticada** — sem isso (d)
falha quando o usuário sai estando em "Lançar despesa". Mas **o olho e as
marcações existem só na Visão Anual, por decisão do dono**: as outras telas não
o ganham, nem a de cadastro de resumos anuais, onde o texto é escrito. O
mecanismo continua pronto para outra tela aderir (basta marcar os elementos e
repetir o botão) — só não é para fazer isso sem ele pedir.

Marcado na Anual desde a rodada 20: o **texto do card de resumo do ano**
(`.resumo-ano__texto`, com `.sensivel`). Explicar os números é falar deles.
Título do card e link "Editar" continuam visíveis.

### Celular (< 768px) — preservar sempre

- A sidebar vira barra superior com botão de menu; as seções recolhíveis do menu
  não se aplicam ali (tudo visível).
- Grades de cards 1/2/4 colunas (quebras em 768 e 1100); gráficos 1/2.
- Coluna principal larga (descrição) → texto de apoio **dentro da célula**;
  coluna principal estreita (mês) → `<tr class="linha-apoio">` com `colspan`.
- Rolagem interna (`.tabela-caixa`) é aceitável e é o padrão; **rolagem horizontal
  da página não é**.
- Ações viram ícone com `aria-label` só onde o padrão já existe (detalhe da
  Mensal); nas demais tabelas os botões empilham com texto.
- Botão da barra superior cresce por `flex: 1 1 auto`, e não por `width: 100%`:
  onde há um botão só o resultado é o mesmo, e onde há dois (Anual: "Lançar
  despesa" mais o olho, que é `.btn--icone` com `flex: none`) eles dividem a
  linha em vez de empilhar.

## 8. Trabalhando com dado real

O banco de desenvolvimento **é** o banco de produção do dono. Portanto:

- **Nenhuma rodada apaga linha que não criou.** Faxina de teste sempre por id
  (ou pela chave, onde a chave não é `id`: o ano, em `tb_resumos_anuais`), e a
  chave é relatada. Onde a linha é texto do dono, confira o prefixo `zz teste`
  **antes** de apagar.
- **O dono escreve enquanto você trabalha.** Ele lança despesa, e desde a
  rodada 20 também escreve resumo anual. Antes de criar, confira que o ano (ou
  o registro) ainda está livre; se não estiver, não toque e relate.
- Edição de registro real feita para validar é **revertida pelo mesmo caminho** e
  relatada. Repare que editar carimba `atualizado_em` (trigger
  `fn_set_atualizado_em`) e isso não volta atrás — quando incomodar, crie e apague
  a própria despesa de teste.
- Referência de teste (pessoa, categoria) **não se apaga**: cria, exercita e deixa
  **inativa**, relatando qual é.
- Prefixo `zz_teste` / `zz teste` para o que for criado por validação.

## 9. Como validar uma entrega

O projeto não tem suíte de testes automatizados. A validação é feita em
**navegador real, logado**, com o servidor em `--debug`, e o resultado é relatado
passo a passo. Instale as dependências de desenvolvimento:

```powershell
pip install -r requirements-dev.txt
playwright install chromium
```

O que se espera de uma validação:

- **Números conferidos lidos do DOM**, comparados com a outra tela ou com SQL —
  não com o que o código "deveria" produzir.
- **Refatoração sem mudança visual se prova por SHA-256 de captura**, com a
  referência capturada **duas vezes** para provar que o instrumento é
  determinístico (viewport e `device_scale_factor` fixos, espera pelos gráficos,
  expansão por `element.click()`). Se o SHA mudar, faça o diff de pixels antes de
  culpar o CSS: **o dono pode ter lançado uma despesa — ou escrito um resumo
  anual — enquanto você trabalhava**, e aí a diferença é dado, não regressão.
  Compare também as dimensões: mesma largura e altura crescida no tamanho exato
  de um bloco novo é a assinatura de "apareceu conteúdo", não de layout mexido.
- **A referência da Visão Anual tem quatro estados por largura**, não um: cada
  ano relevante × olho fechado e aberto. Capturar só o estado aberto esconde
  metade da tela desde a rodada 19.
- Console limpo e **aba Rede só com `/static/...`**.
- Celular conferido em 390px (e 900px quando houver grade intermediária):
  `scrollWidth === clientWidth`.
- Ramo sem dado real exercitado por função pura.
- O relatório termina com a lista de **"pontos que precisei interpretar"**.

Dois detalhes de instrumento:

- O botão de sair da sidebar é o **primeiro** `button[type=submit]` do DOM. Um
  seletor genérico faz logout no meio do teste — escopo sempre em
  `.conteudo__corpo` ou no id do formulário.
- **O Playwright mente sobre duas coisas do navegador**, e as duas foram
  necessárias na rodada 19: página com depurador atado nunca vai para segundo
  plano (`document.visibilityState` fica em `visible` mesmo com outra aba na
  frente, outra janela por cima, `window.open`, `Browser.setWindowBounds`
  minimizando ou `Page.setWebLifecycleState`) e nunca entra no **bfcache**. Para
  exercitar troca de aba e Voltar-do-cache: suba o Chrome à mão com
  `--remote-debugging-port`, prepare a tela pelo CDP, **solte o CDP**, mexa na
  janela pelo Windows (`ShowWindow` para minimizar, `SendKeys` `%{LEFT}` para
  voltar) e só então reate o CDP para ler o que a própria página gravou.
  Adicionar um `<span>` no meio de um texto muda o **subpixel** das letras
  seguintes: se o SHA mudar sem o layout mudar, é isso — esconda pela caixa em
  volta em vez de embrulhar o valor.

## 10. Estado e roteiro

Consolidado em `docs/Freedom - Histórico e Estado do Projeto.md` (rodadas,
decisões, lições aprendidas). Resumo:

- **Pronto**: login; cadastros; lançamento de despesas em série; consulta com
  filtros; receitas em página única; configurações com vigência; Visão Anual (13
  cards, 4 gráficos, 2 tabelas); Visão Mensal com detalhe por categoria; orçamento
  (montagem + acompanhamento). Refatoração visual: rodada 17 (tokens, layout,
  Visão Anual) e rodada 18 (lançamentos e cadastros) concluídas. Rodada 19:
  botão olho da Visão Anual, que esconde todo número da tela (ver "Ocultar
  valores" na seção 7). Rodada 20: **resumo anual** — `tb_resumos_anuais`,
  cadastro em `/cadastros/resumos-anuais` e card na Visão Anual. Rodada 21:
  **carga do IPCA** — `freedom/ipca.py` e `flask carregar-ipca` enchem
  `tb_ipca` com a série do SIDRA/IBGE desde dez/1993 (só a carga; nada lê a
  tabela ainda).
- **Pendente**: a refatoração visual das telas que faltam — Visão Mensal,
  Orçamento, configurações e login ainda rodam sobre os apelidos da seção 1(b)
  do CSS. **Citada pelo nome, e não por número de rodada**: o número já mudou
  duas vezes, e cada mudança deixou comentário mentindo pelo código.
- **Depois**: metas de independência (TSR/S/R já estão em `tb_configuracoes`, nada
  os lê); patrimônio; **uso** do IPCA — a série já está carregada, faltam tela e
  gráficos deflacionados; deploy com gunicorn no docker-compose + Tailscale +
  segundo usuário.

Referência visual: `design_handoff_freedom_visao_anual/` e
`design_handoff_freedom_lancamentos_cadastros/`. **Cuidado**: os README desses
handoffs foram escritos por uma ferramenta de design e erram sobre a stack (falam
em Java, CDN, unpkg, biblioteca de ícones, "sem celular"). Onde divergirem deste
arquivo, **este arquivo vale**. Os `support.js` são runtime da ferramenta e não
fazem parte da aplicação.

## 11. O que não fazer

- Não instale framework de CSS ou de front-end. Não troque Chart.js/HTMX por CDN.
- Não introduza ORM nem ferramenta de migração.
- Não use `float` para dinheiro.
- Não decida cor, texto ou estado dentro do template.
- Não some linhas em Python quando existe consulta agregada.
- Não apague dado que você não criou.
- Não leve o olho da Visão Anual para outra tela sem o dono pedir: o mecanismo
  é reutilizável, a decisão de onde usá-lo não é sua.
- Não escreva valor de senha, chave ou token em lugar nenhum.
- Não faça commit nem push sem o dono pedir.
