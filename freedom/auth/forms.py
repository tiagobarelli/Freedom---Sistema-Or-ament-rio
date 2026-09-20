"""Formularios de autenticacao. CSRF vem do Flask-WTF."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length


class LoginForm(FlaskForm):
    login = StringField(
        "Login",
        validators=[DataRequired(message="Informe o login."), Length(max=255)],
    )
    senha = PasswordField(
        "Senha",
        validators=[DataRequired(message="Informe a senha.")],
    )
    entrar = SubmitField("Entrar")


class TrocaSenhaForm(FlaskForm):
    """Os três campos da tela /conta/senha.

    O mínimo de 8 caracteres é a única exigência sobre a nova senha: nada de
    medidor de força, símbolo obrigatório ou lista de senhas comuns. O sistema
    não está na internet e tem dois usuários.

    Quem confere a senha ATUAL é a rota, e não um validador daqui: para isso
    é preciso o hash do usuário logado, que é coisa de request, não de
    formulário.
    """

    senha_atual = PasswordField(
        "Senha atual",
        validators=[DataRequired(message="Informe a senha atual.")],
    )
    senha_nova = PasswordField(
        "Nova senha",
        validators=[
            DataRequired(message="Informe a nova senha."),
            Length(
                min=8,
                message="A nova senha precisa ter pelo menos 8 caracteres.",
            ),
        ],
    )
    senha_confirmacao = PasswordField(
        "Repita a nova senha",
        validators=[
            DataRequired(message="Repita a nova senha."),
            EqualTo(
                "senha_nova",
                message="A confirmação não confere com a nova senha.",
            ),
        ],
    )
