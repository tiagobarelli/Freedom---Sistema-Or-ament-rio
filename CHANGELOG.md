O que mudou em cada versão do Freedom, da mais nova para a mais antiga. Este
arquivo é a fonte do número de versão que aparece no rodapé do menu: a versão
é o primeiro título daqui, e o sistema o lê quando sobe.

## 1.1 — 26/09/2026

- **Alocação da carteira**, a primeira tela do módulo de investimentos, no
  fim do grupo Painel. Dois modos:
  - **Plano**: o alvo de cada classe sobre o total e, dentro dela, o de cada
    subclasse, com a data em que o plano passa a valer. Criar um plano copia
    o que valia na data escolhida. A grade só salva se as classes somarem
    100% e as subclasses de cada classe também — senão diz qual bloco não
    fechou, e nada é gravado. Cada subclasse diz se recebe aporte.
  - **Balanceamento**: a última foto de patrimônio contra o plano vigente —
    alvo, atual, desvio, quanto falta ou sobra e, com a tolerância cadastrada
    em Parâmetros, o que está fora do alvo, em âmbar. Digitando um aporte (e o
    caixa de cada classe), a tela sugere como reparti-lo, do mesmo jeito que
    a planilha. Nada disso é gravado.
- **Classes e Subclasses** em Cadastros, perto de Ativos.
- **Composição do ativo**: no cadastro de cada ativo, quanto dele vai para
  cada subclasse — um ETF é 100% de uma; a previdência pode se repartir entre
  classes. A soma precisa dar 100%, ou fica tudo vazio para um ativo sem
  classificação. A lista de ativos mostra a composição no lugar da classe.
- **Parâmetros**: chave nova, **TOL** (tolerância da alocação), em
  porcentagem do próprio alvo — 20% num alvo de 5% aceita de 4% a 6%.
- **Patrimônio**: a alocação por classe passa a usar as classes novas, pela
  composição de cada ativo; o que não tem composição aparece como "Não
  classificado".

> **Ao atualizar:** o campo de texto "Classe" dos ativos deixou de existir.
> O único ativo cadastrado tinha "Investimentos" ali, e esse texto não foi
> guardado. Ele aparece como "Não classificado" até receber uma composição.

## 1.0.3 — 25/09/2026

- **Observação à vista na lista.** Despesa que tem observação ganha um "i" ao
  lado da descrição, em Lançar despesa, em Consultar despesas e no detalhe
  por categoria da Visão Mensal. Passar o mouse sobre ele mostra o texto; no
  celular, basta tocar. Clicar deixa o texto aberto até clicar fora ou
  apertar Esc.
- O mesmo vale para as **anotações das receitas**, na tela de Receitas.
- Despesa e receita sem observação continuam exatamente como eram.

## 1.0.2 — 21/09/2026

- **O Freedom não desloga mais sozinho.** O servidor hospeda outros sistemas, e
  o cookie de sessão do Freedom tinha o mesmo nome do de outro deles — cada um
  apagava o do outro, e bastava ter os dois abertos no mesmo navegador para
  cair a cada poucos segundos. Agora o cookie do Freedom tem nome próprio, e os
  dois convivem.
- **Sessão que acaba no meio da digitação agora leva à tela de login**, em vez
  de fazer o cartão "Faça login para continuar." aparecer dentro do formulário
  de despesa. Depois de entrar, você volta para a tela em que estava.
- Sair do sistema passou a ser só pelo botão Sair; abrir o endereço de saída na
  barra do navegador não encerra mais nada.

> **Ao atualizar, todo mundo precisa entrar uma vez.** O cookie antigo tem
> outro nome e deixa de valer — é esperado, e acontece uma vez só.

## 1.0.1 — 20/09/2026

- **Ícone de app e nome próprio.** Instalado como aplicativo, o Freedom passa
  a aparecer com o ícone da corrente e o nome "Freedom", e abre sem a barra do
  navegador — no iPhone, no Android e no Windows.
- No iPhone isso não existia: sem o ícone declarado, o Safari usava uma foto
  da tela. Agora a página diz qual é o ícone.
- Nada mais mudou: nenhuma tela, nenhum número, nenhum comportamento.

## 1.0 — 20/09/2026

- O sistema passa a rodar **no servidor**, dentro do mesmo `docker compose`
  que já subia o banco: agora são três serviços — banco, app e pgAdmin. O
  acesso é pela rede de casa, como sempre foi.
- O **backup** passou a ser gerado pelo cliente do PostgreSQL da própria
  máquina que serve o sistema, em vez de por dentro do container do banco.
  Para quem usa a tela nada muda: o botão continua entregando o mesmo
  arquivo. O que muda é que ele funciona igual no servidor e aqui.
- As mensagens de login, logout e "faça login para continuar" ganharam os
  acentos que faltavam.
- Com o sistema em produção, esta é a **versão 1.0**.

## 0.24 — 20/09/2026

- Troca de senha pela própria interface, em **Alterar senha** (o nome do
  usuário, no rodapé do menu): pede a senha atual, exige oito caracteres na
  nova e confirma a digitação. Trocar a senha não derruba nenhuma sessão.
- Esta página, o **histórico de versões**, com o número da versão no rodapé
  do menu levando a ela.
- Por dentro: a gravação de senha da tela e a do comando `flask set-password`
  passaram a ser a mesma função, e o número de versão passou a ter uma fonte
  só — este arquivo.
