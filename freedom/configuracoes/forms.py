"""Formulários da tela de configurações.

O valor chega como texto e o que ele significa depende da chave: a rota
decide o formato (`form.formato`) antes de validar, porque a mesma caixa de
texto grava `0.04` a partir de `4` numa chave percentual e a partir de `0,04`
numa chave livre.
"""

from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from freedom.configuracoes.servico import NUMERO, PERCENTUAL
from freedom.util import ValorInvalido, converter_numero


class VigenciaForm(FlaskForm):
    """O que uma vigência tem além da chave. É o formulário da edição.

    Editar não muda a chave: trocar a chave de um registro é apagá-lo e lançar
    outro, e deixar isso no formulário só criaria uma forma silenciosa de
    mover histórico de um parâmetro para outro.
    """

    valor = StringField(
        "Valor",
        validators=[DataRequired(message="Informe o valor.")],
    )
    vigente_desde = DateField(
        "Vigente desde",
        default=date.today,
        validators=[DataRequired(message="Informe a data de vigência.")],
    )
    observacao = TextAreaField(
        "Observação", validators=[Optional(), Length(max=500)]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valor_decimal = None
        # A rota troca isto antes de validar; número puro é o padrão seguro.
        self.formato = NUMERO

    def validate_valor(self, field):
        """Texto -> Decimal. Erro vira mensagem de campo, nunca 500."""
        try:
            self.valor_decimal = converter_numero(
                field.data, percentual=self.formato == PERCENTUAL
            )
        except ValorInvalido as exc:
            raise ValidationError(str(exc)) from None


class ConfiguracaoForm(VigenciaForm):
    """Vigência nova: a única que escolhe a chave."""

    chave = StringField(
        "Chave",
        validators=[DataRequired(message="Informe a chave."), Length(max=60)],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Chaves oferecidas pelo combobox; texto livre continua valendo.
        self.sugestoes = []
