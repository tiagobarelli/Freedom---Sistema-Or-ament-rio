# Freedom — Rodada 9: Visão Anual (dashboard em cards)

## Contexto
Leia antes de começar: `docs/Freedom - Histórico e Estado do Projeto.md`, `docs/Freedom - Estrutura do Banco de Dados.md`, `freedom/main/routes.py`, `freedom/lancamentos/servico.py` (padrão das consultas agregadas sobre `vw_despesas`), `freedom/lancamentos/servico_receitas.py`, `freedom/configuracoes/servico.py`, `templates/layout_app.html`, `templates/main/`, `templates/_macros.html` e `static/css/app.css`.

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres em Docker já de pé. Há dado real no banco (despesas e receitas de 2026): nenhuma linha que você não criou pode ser apagada; faxina de teste sempre por id.

A rota `/` hoje é a página "Início", reservada ao dashboard. Esta rodada a transforma na **Visão Anual**.

## Stack
Flask 3 + psycopg 3 (SQL direto, parametrizado, `dict_row`) + Flask-WTF + HTMX local + CSS à mão (Glassmorphism claro). Já decidida, não proponha alternativas. Sem ORM, sem migrações, sem Chart.js nesta rodada.

## Entrega desta rodada — SOMENTE isto

1. **Renomear** o item de menu "Início" para "Visão Anual" (grupo Painel), título da página idem. Rota continua `/`, blueprint `main` continua com esse nome.

2. **Seletor de ano** no topo da página: `<select>` com os anos que têm pelo menos uma despesa ou uma receita (união das duas, ordem decrescente), submetido por GET (`/?ano=2026`) com recarga da página inteira — sem HTMX aqui. Padrão: ano corrente. `ano` ausente, não numérico ou fora da lista cai no ano corrente sem erro. O select submete ao mudar (`onchange`), sem botão.

3. **Treze cards**, nesta ordem e com estes rótulos:
   - Receita Anual
   - Despesa Anual
   - Saldo Anual (receita − despesa; negativo em vermelho)
   - Taxa de Poupança (saldo / receita, em %; "—" quando a receita do ano é zero)
   - Despesas Essenciais (total)
   - Despesas Não Essenciais (total)
   - Despesa Média / Mês
   - Melhor Mês (Saldo) — nome do mês e o saldo
   - Mês de Maior Gasto — nome do mês e o total
   - Pico de Despesa — maior lançamento individual: valor, descrição e data
   - % Essencial (sobre a despesa anual)
   - % Não Essencial
   - Meses no Azul — quantidade de meses com receita > despesa, no formato "N de M"

   Definições:
   - Essencialidade é a **efetiva** de `vw_despesas` (coluna já resolvida na view).
   - **Despesa Média / Mês**: divisor = meses transcorridos (janeiro até o mês corrente, inclusive) quando o ano selecionado é o corrente; 12 quando é ano anterior; "—" para ano futuro sem dado. O "M" de "Meses no Azul" usa o mesmo divisor.
   - Ano sem nenhum lançamento: cards de valor mostram R$ 0,00, cards de mês e pico mostram "—". Nunca 500.
   - Nomes de mês em português vêm de uma tupla/dicionário Python, não de `locale`.

4. **Consultas**: uma consulta agregada por mês sobre `vw_despesas` (total, essencial, não essencial) e uma sobre `vw_receitas` (total), ambas filtrando por intervalo de `data` (`>= 1º de janeiro AND < 1º de janeiro do ano seguinte`), nunca por `ano_mes`. Mais uma consulta para o pico. Os cards são compostos em Python a partir dessas linhas (no máximo 12 por consulta). Coloque as leituras num `freedom/main/servico.py`; a rota só orquestra. Use `Decimal`, nunca `float`, em valor de dinheiro.

5. **Layout**: grade de cards responsiva — 1 coluna abaixo de 768px, 2 entre 768 e ~1100px, 4 acima. Rótulo pequeno em cima, valor grande embaixo, linha de apoio quando houver (nome do mês, descrição do pico). Reaproveite o componente `.card` e o filtro `moeda` / macro `reais` existentes; nova seção CSS numerada (5.13) seguindo o padrão do arquivo. Vidro só na moldura, conforme o padrão da app.

6. **Limpeza pendente**: remover de `app.css` os componentes `.modal` e `.card--sem-padding`, que não têm uso. Confirme com busca nos templates antes de remover.

## Regras
- Não altere `01_schema.sql` nem crie tabela, view ou índice. Não use `ano_mes` como filtro.
- Não implemente gráficos, filtros por categoria, comparação entre anos, detalhamento mensal em tabela nem link dos cards para a consulta. Tudo isso é de rodadas futuras.
- Não use ORM, não use `locale`, não use `float` em dinheiro, não some em Python o que o SQL pode agregar (a composição dos 13 cards a partir das 12 linhas mensais é a exceção prevista).
- Não toque em `lancamentos/`, `configuracoes/` ou `cadastros/`, exceto se precisar promover um helper compartilhado — nesse caso, promova para `util.py` sem underscore e relate.
- Mantenha os padrões do projeto listados em "Padrões já estabelecidos no código" do histórico.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
1. Suba a aplicação, faça login com `zz_teste` no **navegador** e abra `/`: confira os 13 cards com o ano corrente.
2. Confira dois valores contra a consulta de despesas e a página de receitas (Despesa Anual e Receita Anual do mesmo ano devem bater com os totais filtrados por ano lá; se a consulta só filtra por mês, some os meses no SQL via pgAdmin ou `psql`).
3. Abra `/?ano=2019` (ou outro ano sem dado), `/?ano=abc` e `/?ano=` — nenhum 500, comportamento conforme item 2 e 3.
4. Verifique Taxa de Poupança e Meses no Azul manualmente para um mês, a partir dos números do banco.
5. Viewport de celular (≤ 768px): 1 coluna, sem rolagem horizontal, menu vira barra superior como nas outras telas.
6. `grep`/busca confirmando que `.modal` e `.card--sem-padding` não eram referenciados antes da remoção.
7. Relate: arquivos criados/alterados, resultado de cada validação acima, e a lista de **pontos que precisou interpretar**.