"""Serviço de autenticação: o único lugar que grava senha.

Dois caminhos trocam a senha de alguém — `flask set-password`, que é o
administrativo (quem esqueceu a senha não consegue entrar para trocá-la), e a
tela `/conta/senha`, que é o do dia a dia. Os dois passam por aqui, e por isso
o hash é gerado num lugar só: se um dia o algoritmo mudar, muda aqui, e não em
dois arquivos que precisariam concordar.
"""

from werkzeug.security import generate_password_hash

from freedom.db import executar


def trocar_senha(login, senha_nova):
    """Grava o hash da nova senha do usuário `login`. Scrypt, do
    `werkzeug.security`, o mesmo hash que o `create-user` escreve.

    **Não confere nada**, e é de propósito: quem chama já sabe de quem é a
    senha. O comando conferiu que o login existe antes de perguntar; a rota
    conferiu a senha atual de quem está logado. Pedir a senha atual aqui
    quebraria o comando, que existe justamente para quem não a tem.

    A senha em claro não sai desta função: o que vai ao banco é o hash, e o
    parâmetro morre com a chamada.
    """
    executar(
        "UPDATE tb_usuarios SET senha_hash = %s WHERE login = %s",
        (generate_password_hash(senha_nova), login),
    )
