O que mudou em cada versão do Freedom, da mais nova para a mais antiga. Este
arquivo é a fonte do número de versão que aparece no rodapé do menu: a versão
é o primeiro título daqui, e o sistema o lê quando sobe.

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
