"""Usuario da sessao (Flask-Login).

Nao ha ORM: o objeto e montado a partir de um dict vindo do psycopg.
"""

from flask_login import UserMixin

from freedom.db import query_one

# tb_usuarios guarda o acesso; o nome legivel vem de tb_pessoas.
_SELECT_USUARIO = """
    SELECT u.id,
           u.login,
           u.pessoa_id,
           u.senha_hash,
           p.nome AS pessoa_nome
      FROM tb_usuarios u
      JOIN tb_pessoas  p ON p.id = u.pessoa_id
     WHERE u.ativo = TRUE
       AND {condicao}
"""


class User(UserMixin):
    def __init__(self, id, login, pessoa_id, pessoa_nome, senha_hash=None):
        self.id = id
        self.login = login
        self.pessoa_id = pessoa_id
        self.pessoa_nome = pessoa_nome
        self.senha_hash = senha_hash

    def get_id(self):
        return str(self.id)

    @classmethod
    def _from_row(cls, row):
        if row is None:
            return None
        return cls(
            id=row["id"],
            login=row["login"],
            pessoa_id=row["pessoa_id"],
            pessoa_nome=row["pessoa_nome"],
            senha_hash=row.get("senha_hash"),
        )

    @classmethod
    def get_by_id(cls, user_id):
        """Carrega o usuario da sessao. Um usuario desativado deixa de existir
        para o Flask-Login, o que derruba a sessao no proximo request."""
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return None
        row = query_one(_SELECT_USUARIO.format(condicao="u.id = %s"), (user_id,))
        return cls._from_row(row)

    @classmethod
    def get_by_login(cls, login):
        row = query_one(_SELECT_USUARIO.format(condicao="u.login = %s"), (login,))
        return cls._from_row(row)
