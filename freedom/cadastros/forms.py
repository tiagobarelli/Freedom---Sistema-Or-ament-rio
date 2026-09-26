"""Formulários das telas de cadastro.

Os valores dos selects são exatamente os do CHECK no banco; o rótulo amigável
fica só na interface.
"""

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

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


def _ano_ou_none(valor):
    """Coerce do select de ano: opção em branco vira None, não erro.

    Mesmo motivo dos selects de receita: `coerce=int` estoura em "" e sobra
    uma mensagem em inglês. Devolvendo None, quem reclama é o DataRequired,
    com o texto que a tela deve mostrar.
    """
    if valor in (None, "", "None"):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


class ResumoAnualForm(_Base):
    """Resumo de um ano. O ano é a chave; o texto não tem tamanho máximo.

    `validate_choice=False` porque a checagem de qual ano é aceitável é feita
    abaixo, contra os anos carregados, para a mensagem sair em português — e
    porque ela é regra da aplicação: o ano tem de ter lançamento e ainda não
    ter resumo. Na edição, a lista carregada é só o ano do próprio registro.
    """

    ano = SelectField(
        "Ano",
        coerce=_ano_ou_none,
        validate_choice=False,
        validators=[DataRequired(message="Escolha o ano.")],
    )
    texto = TextAreaField(
        "Resumo",
        validators=[DataRequired(message="Escreva o resumo.")],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.anos = []

    def carregar_anos(self, anos):
        """Os anos que o formulário aceita. O template monta o <select>."""
        self.anos = list(anos)
        self.ano.choices = [(a, str(a)) for a in self.anos]

    def validate_ano(self, field):
        if field.data not in self.anos:
            raise ValidationError(
                "Escolha um ano com lançamento que ainda não tenha resumo."
            )

    def validate_texto(self, field):
        """Apara as pontas e normaliza a quebra de linha para \\n.

        O navegador manda CRLF em textarea (regra do HTML), e o banco guardaria
        os dois bytes. Normalizar aqui é o que faz o texto lido de volta ser o
        mesmo que se digitou, e o CHECK do banco recusar o que sobrar de vazio
        nunca ser alcançado - o erro sai como campo, antes.
        """
        texto = (field.data or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not texto:
            raise ValidationError("Escreva o resumo.")
        field.data = texto


class AtivoForm(_Base):
    """Um ativo de patrimônio (tb_ativos), da rodada 30.

    Até a rodada 36 tinha um campo `classe`, texto livre. Na 37 a classe
    passou a sair da COMPOSIÇÃO, que é uma grade de percentuais por
    subclasse no mesmo formulário: ela não cabe num campo WTForms de valor
    único, e quem a lê é `alocacao/composicao.py`. Aqui ficam só os dois
    campos que são do ativo mesmo.

    As pontas são aparadas na validação, como nos cadastros vizinhos, e o
    resto do texto vai para o banco como foi digitado — caixa inclusive.
    """

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=120)],
    )
    observacao = TextAreaField(
        "Observação",
        validators=[Optional(), Length(max=500)],
    )

    def validate_nome(self, field):
        texto = (field.data or "").strip()
        if not texto:
            raise ValidationError("Informe o nome.")
        field.data = texto


class ClasseAlocacaoForm(_Base):
    """Uma classe de alocação (tb_alocacao_classes), da rodada 37."""

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=120)],
    )

    def validate_nome(self, field):
        """Aparar aqui, e não só na rota, é o que faz "  " virar erro de
        campo antes de chegar ao CHECK de caractere visível do banco."""
        texto = (field.data or "").strip()
        if not texto:
            raise ValidationError("Informe o nome.")
        field.data = texto


class SubclasseAlocacaoForm(_Base):
    """Uma subclasse de alocação (tb_alocacao_subclasses), da rodada 37.

    A classe é `<select>`, e não texto livre: é cadastro fechado, como a
    categoria da subcategoria.
    """

    classe_id = SelectField(
        "Classe",
        coerce=int,
        validators=[DataRequired(message="Escolha a classe.")],
    )
    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=120)],
    )

    def validate_nome(self, field):
        texto = (field.data or "").strip()
        if not texto:
            raise ValidationError("Informe o nome.")
        field.data = texto


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
