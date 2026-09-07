Contexto: projeto "Freedom". A rodada anterior entregou esqueleto Flask,
pool psycopg 3, login e `flask create-user`. Leia `docs/Freedom -
Estrutura do Banco de Dados.md` (fonte da verdade do banco, não alterar
o schema) e o código existente antes de começar. Mesma stack, mesmas
regras: SQL direto parametrizado, Flask-WTF, HTMX local, venv em
`venv/`, Windows/PowerShell. Interface em português do Brasil.

Entrega desta rodada:

A) LAYOUT E CSS BASE (Glassmorphism, tema claro apenas)
- `static/css/app.css` escrito à mão, organizado em: variáveis CSS
  (cores, raios, sombras, espaçamentos, blur), reset mínimo, layout,
  componentes (card, botão, input, select, tabela, badge, flash, modal),
  utilitários.
- Direção visual: fundo da página com degradê suave em tons frios
  claros (azul-lavanda muito claro para branco), com duas ou três formas
  circulares grandes e desfocadas ao fundo para o vidro ter o que
  desfocar. Superfícies "vidro": fundo branco com alfa ~0.55-0.7,
  `backdrop-filter: blur(16px)` (com `-webkit-`), borda 1px branca
  semitransparente, raio 16-20px, sombra difusa e leve. Cor de destaque
  única (um azul-violeta) para botões primários, links e item ativo da
  sidebar. Tipografia: `system-ui` stack; hierarquia clara entre título
  de página, título de card e texto.
- REGRA DE LEGIBILIDADE: vidro só em sidebar, cabeçalho e cards de
  moldura. Tabelas de dados, formulários e áreas de leitura têm fundo
  branco quase opaco (alfa >= 0.92) e texto com contraste AA. Nada de
  texto sobre degradê.
- Layout: sidebar fixa à esquerda (~240px) com logo "Freedom" no topo,
  grupos de navegação com rótulo pequeno em caixa alta (por enquanto:
  "Cadastros" com Categorias, Subcategorias, Contas, Pessoas, Fontes de
  receita), e no rodapé o nome do usuário logado com botão Sair. Área de
  conteúdo à direita com cabeçalho de página (título + ação primária).
- Responsivo: abaixo de 768px a sidebar vira barra superior com botão
  que abre/fecha o menu; tabelas rolam horizontalmente. Isso importa
  porque o sistema será usado no celular via Tailscale.
- Sem Tailwind, sem bibliotecas CSS ou de ícones. Se precisar de ícone,
  SVG inline simples.
- `base.html` passa a ter esse layout; a rota `/` vira uma página
  "Início" vazia com um card de boas-vindas (o dashboard vem depois).

B) TELAS DE CADASTRO — blueprint `cadastros`, um módulo por entidade:
   tb_categorias, tb_subcategorias, tb_contas, tb_pessoas, tb_ref_receitas
- Para cada uma: lista, criar, editar, ativar/desativar. NÃO existe
  excluir — o schema usa `ativo`/`ativa` e FKs RESTRICT.
- Lista: tabela com as colunas relevantes, badge Ativo/Inativo, filtro
  "mostrar inativos" (padrão oculto), botões Editar e Ativar/Desativar.
  Ativar/Desativar via HTMX (POST) trocando só a linha, sem recarregar.
  Subcategorias: mostrar a categoria e a essencialidade; filtro por
  categoria. Contas: mostrar tipo.
- Formulários (criar/editar) em página própria, com Flask-WTF:
  - subcategoria: select de categoria (só ativas, exceto a já vinculada
    na edição), select de essencialidade com os dois valores exatos do
    CHECK ("Essencial", "Não Essencial").
  - conta: select de tipo com os quatro valores do CHECK
    (corrente, cartao, dinheiro, outro), exibidos com rótulo amigável.
  - Violação de UNIQUE (psycopg `UniqueViolation`) deve virar erro de
    campo legível ("Já existe uma categoria com esse nome"), nunca
    página 500. Transação por request; rollback em erro.
- Mensagens flash para sucesso, estilizadas como componente.
- Ordenação padrão: nome (categoria + nome para subcategorias).

C) CLI: `flask set-password --login X` pedindo a nova senha sem eco,
   com confirmação, atualizando `senha_hash`. Falha claro se o login
   não existir.

Regras:
- Não crie tabelas/colunas/views. Não use ORM. Não implemente despesas,
  receitas, configurações, relatórios ou dashboard — isso é outra rodada.
- Reaproveite: macros Jinja para campos de formulário e para a tabela,
  um helper Python genérico para "ativar/desativar" e para traduzir
  `UniqueViolation` em mensagem, em vez de repetir cinco vezes.
- Se algo estiver ambíguo, pergunte antes de decidir.
- Ao final, valide de verdade: crie, edite, desative e reative um
  registro de cada entidade pelo navegador (ou por requests com sessão
  autenticada), provoque uma duplicidade de nome e confirme a mensagem
  amigável, teste a lista no viewport de 390px de largura. Rode
  `flask set-password` e faça login com a senha nova. Reporte o
  resultado e os pontos que precisou interpretar.