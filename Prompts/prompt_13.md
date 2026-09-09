# Freedom — Rodada 14: limpeza de CSS dos painéis (sem mudança visual)

## Contexto
Leia antes de começar: `docs/Freedom - Histórico e Estado do Projeto.md` (seção 6 e a pendência "Dívida de CSS nomeada"), `static/css/app.css` (sumário, 5.13, 5.13.2, 5.14, 5.14.1, seção 7), `templates/main/index.html`, `templates/main/mensal.html`, `templates/main/_detalhe_categoria.html`.

Ambiente: Windows, PowerShell, venv em `venv/`, Postgres em Docker, dado real no banco (nada é escrito nesta rodada). Login de teste: `zz_teste`, senha na variável `senha_teste` do `.env`. Validação em **navegador real**.

Estado: a barra de seletores dos painéis usa `.filtro-ano` (nome herdado de quando só havia o ano) com o modificador `.filtro-ano--mensal`; as tabelas dos painéis usam `.tabela--categorias` (Anual), `.tabela--mes` (Mensal, quatro regras repetidas da 5.13.2) e `.tabela--detalhe` (detalhe expansível). Esta rodada paga essa dívida. **Nenhum pixel muda.**

## Stack
CSS à mão, Jinja. Sem pré-processador, sem ferramenta nova. Já decidida.

## Entrega desta rodada — SOMENTE isto

1. **Renomear** `.filtro-ano` → `.filtro-barra` e `.filtro-ano--mensal` → `.filtro-barra--mensal` (ou eliminar o modificador se as regras dele puderem virar padrão da barra sem alterar a Anual — decida pelo resultado visual e relate). Atualizar todos os pontos de uso nos templates.

2. **Unificar** `.tabela--categorias` e `.tabela--mes` numa única `.tabela--resumo`, com as regras comuns escritas uma vez (inclusive as de celular na seção 7). O que for específico de uma tela fica como modificador ou regra própria, com nome que diga o que é. `.tabela--detalhe` mantém o nome, mas passa a herdar de `.tabela--resumo` o que hoje repete; ficam nela só as regras que são dela (cinco colunas, recuo, celular).

3. **Sumário e numeração** do `app.css` atualizados para refletir o que sobrou. Não renumerar seções; a lacuna do 5.7 continua.

4. **Relatório de seletores sem uso**: liste seletores de classe de `app.css` que não aparecem em nenhum template nem JS (busca por nome). **Não remova** nenhum nesta rodada — só liste, para decidirmos.

## Regras
- Não altere HTML além de trocar nomes de classe. Não mexa em rotas, serviços, JS de comportamento, schema.
- Não altere valores de propriedade CSS: cores, espaçamentos, larguras, breakpoints, alturas. Se a unificação exigir mudar um valor para as telas ficarem iguais entre si, **pare e pergunte** — é sinal de que elas eram diferentes de propósito ou por descuido, e a decisão é nossa.
- Não toque em seções que não sejam 5.13, 5.14, 7 e o sumário, exceto pela remoção de seletores que só existiam para os nomes antigos.
- **Se algo estiver ambíguo, pergunte antes de decidir.**

## Validação real (execute e reporte)
Antes de qualquer alteração, capture os screenshots de referência em navegador real com login: Visão Anual (`/`) e Visão Mensal (`/mensal?ano=2026&mes=7`) com Comodidades expandida, cada uma em 1440px e 390px, mais 900px para a Mensal (matriz rolando). Fixe viewport, zoom e altura total da página. Salve os SHA-256.

Depois da alteração, repita com os mesmos parâmetros e reporte, por captura, se o SHA-256 é **idêntico**. Qualquer diferença: gere o diff visual (pixel a pixel), explique a causa e **não ajuste o CSS para "ficar parecido"** — reverta o trecho ou pergunte.

Mais:
1. `grep` confirmando que `.filtro-ano`, `.tabela--categorias` e `.tabela--mes` não existem mais em nenhum arquivo.
2. Consulta, receitas, configurações e lançar despesa continuam 200 (não devem ter sido tocadas; conferência de regressão).
3. Relate: linhas de CSS antes e depois, arquivos alterados, o relatório do item 4, resultado por captura e a lista de **pontos que precisou interpretar**.