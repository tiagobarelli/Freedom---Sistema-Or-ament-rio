"""Formulário de despesa.

O valor chega como texto (pt-BR aceita vírgula) e é convertido por
`converter_valor`; o Decimal validado fica em `form.valor_decimal`.
"""

from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    HiddenField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from freedom.lancamentos.servico import (
    ESSENCIAL,
    NAO_ESSENCIAL,
    ValorInvalido,
    converter_valor,
)

# Vazio = herdar da subcategoria (grava NULL). Os outros dois são as strings
# exatas do CHECK ck_despesas_essencialidade.
ESSENCIALIDADES = [
    ("", "Herdar da subcategoria"),
    (ESSENCIAL, ESSENCIAL),
    (NAO_ESSENCIAL, NAO_ESSENCIAL),
]

PRIORIDADES = [
    ("", "Sem prioridade"),
    ("1", "1 — mais importante"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4 — menos importante"),
]


class DespesaForm(FlaskForm):
    data = DateField(
        "Data",
        default=date.today,
        validators=[DataRequired(message="Informe a data.")],
    )
    descricao = StringField(
        "Descrição",
        validators=[DataRequired(message="Informe a descrição."), Length(max=200)],
    )
    valor = StringField(
        "Valor",
        validators=[DataRequired(message="Informe o valor.")],
    )
    subcategoria_id = SelectField(
        "Subcategoria",
        coerce=int,
        validators=[DataRequired(message="Escolha a subcategoria.")],
    )
    conta_id = SelectField(
        "Conta",
        coerce=int,
        validators=[DataRequired(message="Escolha a conta.")],
    )
    pessoa_id = SelectField(
        "Pessoa",
        coerce=int,
        validators=[DataRequired(message="Escolha a pessoa.")],
    )

    # --- bloco "Mais opções" ---
    essencialidade = SelectField(
        "Essencialidade",
        choices=ESSENCIALIDADES,
        validators=[Optional()],
    )
    integra_ipca = BooleanField("Integra o agregado do IPCA", default=True)
    observacoes = TextAreaField("Observações", validators=[Optional(),
                                                           Length(max=1000)])

    # --- fora do bloco: depende da essencialidade efetiva ---
    prioridade = SelectField(
        "Prioridade",
        choices=PRIORIDADES,
        validators=[Optional()],
    )

    # Guarda se o <details> estava aberto, para o re-render por HTMX não
    # fechar o bloco que a pessoa tinha aberto. Sincronizado por 3 linhas de JS.
    mais_opcoes = HiddenField(default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valor_decimal = None
        self.grupos = []

    def validate_valor(self, field):
        """Texto -> Decimal. Erro vira mensagem de campo, nunca 500."""
        try:
            self.valor_decimal = converter_valor(field.data)
        except ValorInvalido as exc:
            raise ValidationError(str(exc)) from None

    def prioridade_int(self):
        return int(self.prioridade.data) if self.prioridade.data else None

    def essencialidade_ou_none(self):
        """String vazia do select vira NULL: é o 'herdar da subcategoria'."""
        return self.essencialidade.data or None

    def carregar_opcoes(self, grupos_subcategoria, contas, pessoas):
        """Preenche os selects.

        Optgroup no WTForms 3 é um dict {rótulo: [(valor, texto), ...]}; como
        dict preserva a ordem de inserção, a ordenação por categoria vinda do
        SELECT é mantida. Nome de categoria é UNIQUE, então não há colisão.
        """
        grupos = list(grupos_subcategoria)
        # O template monta o <select> a mao (precisa de uma opcao em branco
        # antes dos optgroups), entao guarda os grupos; as choices continuam
        # aqui porque sao elas que validam o valor recebido.
        self.grupos = grupos
        self.subcategoria_id.choices = {rotulo: itens for rotulo, itens in grupos}
        self.conta_id.choices = [(c["id"], c["nome"]) for c in contas]
        self.pessoa_id.choices = [(p["id"], p["nome"]) for p in pessoas]

    @property
    def mais_opcoes_aberto(self):
        """Abre o bloco também quando há erro num campo de dentro dele."""
        if self.mais_opcoes.data == "1":
            return True
        return bool(self.essencialidade.errors or self.observacoes.errors)
