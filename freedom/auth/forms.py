"""Formularios de autenticacao. CSRF vem do Flask-WTF."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length


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
