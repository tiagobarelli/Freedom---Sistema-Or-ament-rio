"""Formulários das telas de cadastro.

Os valores dos selects são exatamente os do CHECK no banco; o rótulo amigável
fica só na interface.
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

# Valores exatos do CHECK ck_subcategorias_essencialidade / ck_despesas_*.
ESSENCIALIDADES = [
    ("Essencial", "Essencial"),
    ("Não Essencial", "Não Essencial"),
]

# Valores exatos do CHECK ck_contas_tipo, com rótulo legível na tela.
TIPOS_CONTA = [
    ("corrente", "Conta corrente"),
    ("cartao", "Cartão"),
    ("dinheiro", "Dinheiro"),
    ("outro", "Outro"),
]

TIPOS_CONTA_ROTULO = dict(TIPOS_CONTA)


class _Base(FlaskForm):
    salvar = SubmitField("Salvar")


class CategoriaForm(_Base):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=120)],
    )


class PessoaForm(_Base):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=120)],
    )


class SubcategoriaForm(_Base):
    categoria_id = SelectField(
        "Categoria",
        coerce=int,
        validators=[DataRequired(message="Escolha a categoria.")],
    )
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=120)],
    )
    essencialidade = SelectField(
        "Essencialidade",
        choices=ESSENCIALIDADES,
        validators=[DataRequired(message="Escolha a essencialidade.")],
    )


class ContaForm(_Base):
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=120)],
    )
    tipo = SelectField(
        "Tipo",
        choices=TIPOS_CONTA,
        validators=[DataRequired(message="Escolha o tipo.")],
    )
    observacao = TextAreaField(
        "Observação",
        validators=[Optional(), Length(max=500)],
    )


class RefReceitaForm(_Base):
    categoria = StringField(
        "Categoria",
        validators=[DataRequired(message="Informe a categoria."), Length(max=120)],
    )
    subcategoria = StringField(
        "Subcategoria",
        validators=[DataRequired(message="Informe a subcategoria."),
                    Length(max=120)],
    )
    observacao = TextAreaField(
        "Observação",
        validators=[Optional(), Length(max=500)],
    )
