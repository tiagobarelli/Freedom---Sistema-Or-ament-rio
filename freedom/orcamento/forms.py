"""Formulários do orçamento.

Os três campos de dinheiro passam pelo mesmo `converter_valor` do lançamento:
vírgula é decimal, `R$` e espaços são ignorados, e o erro vira mensagem de
campo — nunca 500 e nunca um CHECK do banco estourando na cara de alguém.

A diferença para o lançamento é o zero: uma despesa de R$ 0,00 não existe, mas
uma linha de orçamento zerada existe, sim — é "esta subcategoria está no plano
e eu não pretendo gastar nada nela neste mês". Daí `_ValorPlanejado`, que
aceita zero e recusa negativo.
"""

from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField
from wtforms.validators import DataRequired, ValidationError

from freedom.util import ValorInvalido, converter_valor, parece_zero


class _ValorPlanejado(FlaskForm):
    """Base dos formulários que carregam um valor planejado.

    `converter_valor` recusa zero (regra do lançamento), então o zero é tratado
    antes de chamá-lo, por `parece_zero`. O resultado fica em `valor_decimal`,
    no padrão dos formulários de despesa e de configuração.

    `parece_zero` morava aqui, privada, e subiu para `util.py` na rodada 30 —
    a foto de patrimônio virou a segunda tela em que zero é entrada legítima,
    e helper duplicado, neste projeto, é contradição.
    """

    valor = StringField(
        "Valor",
        validators=[DataRequired(message="Informe o valor.")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valor_decimal = None

    def validate_valor(self, field):
        texto = (field.data or "").strip()
        try:
            # Zero é planejamento legítimo; o parser de lançamento o recusa.
            if parece_zero(texto):
                self.valor_decimal = Decimal("0.00")
                return
            self.valor_decimal = converter_valor(texto)
        except ValorInvalido as exc:
            raise ValidationError(str(exc)) from None


class LinhaForm(_ValorPlanejado):
    """Edição do planejado de uma linha que já existe."""


class ReceitaForm(_ValorPlanejado):
    """Edição da receita planejada do mês."""


class NovaLinhaForm(_ValorPlanejado):
    """Acréscimo de uma subcategoria que ainda não estava no mês."""

    subcategoria_id = IntegerField(
        "Subcategoria",
        validators=[DataRequired(message="Escolha a subcategoria.")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Preenchido pela rota: só o que está disponível no mês é aceito.
        self.disponiveis = []

    def validate_subcategoria_id(self, field):
        if field.data not in {s["id"] for s in self.disponiveis}:
            raise ValidationError(
                "Escolha uma subcategoria que ainda não esteja no mês.")
