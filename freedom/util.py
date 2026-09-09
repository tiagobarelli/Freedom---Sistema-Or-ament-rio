"""Utilidades pequenas compartilhadas entre blueprints.

Além do destino seguro de redirecionamento, mora aqui o que despesas, receitas
e o painel usam em comum: os nomes dos meses, o parser de valor monetário, o
escape de curingas do LIKE, a ordenação alfabética em português e a leitura do
cabeçalho do HTMX. Todos nasceram em
`lancamentos/servico.py`, quando só havia uma tela de lançamento; passaram a
servir mais de uma e subiram para cá.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from flask import request

# Nomes de mês em português vindos do Python, e não de `locale`: locale depende
# do que está instalado no sistema operacional, e a mesma aplicação mudaria de
# idioma conforme a máquina em que roda.
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def destino_interno(valor):
    """Devolve `valor` se for um caminho interno seguro, senão None.

    Usado pelo `?next=` do login e pelo `?retorno=` da edição de lançamento:
    aceitar URL absoluta aqui transformaria os dois em open redirect.
    """
    if not valor:
        return None
    partes = urlparse(valor)
    if partes.scheme or partes.netloc:
        return None
    # "//outro.site" é protocol-relative: o urlparse acima já pega, mas a
    # checagem explícita deixa a intenção clara.
    if not valor.startswith("/") or valor.startswith("//"):
        return None
    return valor


# --------------------------------------------------------------------------
# Valor monetário
# --------------------------------------------------------------------------

class ValorInvalido(Exception):
    """Texto digitado que não vira um valor monetário aceitável."""


# Agrupamento de milhar bem formado: 1-3 dígitos e depois grupos de 3.
# Só existe para o ponto: vírgula repetida é erro, não milhar.
_AGRUPAMENTO = {
    ".": re.compile(r"\d{1,3}(\.\d{3})+"),
}


def _partir(bruto):
    """Decide o que em `bruto` é milhar e o que é decimal.

    Devolve (parte_inteira, casas_decimais) já sem separadores.

    A regra NÃO é simétrica entre `,` e `.`, porque em português a vírgula é
    sempre decimal e o ponto é ambíguo:

      - vírgula sem ponto: a vírgula é o decimal, ponto final. 10,99 = 10,99;
        1,5 = 1,50; 10, = 10,00; e 1,234 ou 10,999 são ERRO — quem escreve
        assim quase sempre errou a digitação, e gravar dez mil no lugar de dez
        é caro demais para adivinhar;
      - ponto sem vírgula: aí sim há heurística, porque o teclado numérico do
        celular costuma oferecer só o ponto. Ponto único com 3 dígitos depois é
        milhar (1.234 = 1234,00); com 1 ou 2 é decimal (1.5 = 1,50); com 4 ou
        mais é erro; ponto repetido é tudo milhar (1.234.567);
      - os dois presentes: o mais à direita é o decimal e o outro é milhar
        (1.234,56 e 1,234.56 dão os dois 1234,56).

    Quem passar de 2 casas decimais cai no teste de tamanho em converter_valor.
    """
    tem_virgula, tem_ponto = "," in bruto, "." in bruto

    if tem_virgula and tem_ponto:
        decimal_sep = "," if bruto.rfind(",") > bruto.rfind(".") else "."
        milhar_sep = "." if decimal_sep == "," else ","
        if bruto.count(decimal_sep) > 1:
            raise ValorInvalido(
                "Valor inválido: há mais de um separador decimal."
            )
        inteiro, _, decimais = bruto.rpartition(decimal_sep)
        return inteiro.replace(milhar_sep, ""), decimais

    if tem_virgula:
        # Vírgula é decimal, sempre. Nada de heurística de milhar aqui.
        if bruto.count(",") > 1:
            raise ValorInvalido("Valor inválido. Use apenas uma vírgula.")
        inteiro, _, decimais = bruto.partition(",")
        return inteiro, decimais

    if not tem_ponto:
        return bruto, ""

    if bruto.count(".") > 1:
        # Repetido: só pode ser milhar, e o agrupamento tem que fechar.
        if not _AGRUPAMENTO["."].fullmatch(bruto):
            raise ValorInvalido("Valor inválido. Escreva como 1.234.567,89.")
        return bruto.replace(".", ""), ""

    inteiro, _, depois = bruto.partition(".")
    if len(depois) == 3:
        return inteiro + depois, ""      # 1.234 -> milhar
    if len(depois) <= 2:
        return inteiro, depois           # 1.5 / 10. -> decimal
    raise ValorInvalido("Use no máximo 2 casas decimais.")


def converter_valor(texto):
    """Converte o texto digitado em Decimal com 2 casas.

    Única função de conversão do sistema: lançamento e edição, de despesa e de
    receita, passam por aqui. Levanta ValorInvalido com mensagem pronta para
    virar erro de campo — nunca deixa estourar o CHECK (valor > 0) do banco.
    """
    if texto is None:
        raise ValorInvalido("Informe o valor.")

    bruto = str(texto).strip()
    for lixo in ("R$", " ", "\xa0", " "):  # inclui espaços finos de colagem
        bruto = bruto.replace(lixo, "")
    if not bruto:
        raise ValorInvalido("Informe o valor.")

    if not re.fullmatch(r"-?[\d.,]+", bruto):
        raise ValorInvalido("Valor inválido. Use apenas números, como 1234,56.")

    negativo = bruto.startswith("-")
    bruto = bruto.lstrip("-")
    if not bruto:
        raise ValorInvalido("Informe o valor.")

    inteiro, decimais = _partir(bruto)

    inteiro = inteiro or "0"
    if not inteiro.isdigit() or (decimais and not decimais.isdigit()):
        raise ValorInvalido("Valor inválido. Use apenas números, como 1234,56.")
    # Vale para todos os ramos de _partir: dinheiro não é arredondado em
    # silêncio, quem digitou 3 casas vê o erro.
    if len(decimais) > 2:
        raise ValorInvalido("Use no máximo 2 casas decimais.")

    try:
        valor = Decimal(f"{inteiro}.{decimais or '0'}")
    except InvalidOperation:
        raise ValorInvalido("Valor inválido.") from None

    if negativo:
        valor = -valor
    if valor <= 0:
        raise ValorInvalido("O valor deve ser maior que zero.")
    if valor >= Decimal("10000000000"):
        raise ValorInvalido("Valor alto demais.")

    return valor.quantize(Decimal("0.01"))


def converter_numero(texto, percentual=False, casas=6):
    """Texto -> Decimal para os parâmetros de configuração.

    Irmã de `converter_valor`, não uma variante dela: aqui não há R$, o valor
    pode ter até seis casas (é o que `tb_configuracoes.valor` guarda) e existe
    o sufixo `%`. Distorcer a de dinheiro com dois modos deixaria a função de
    dinheiro pior para caber um caso que não é dinheiro.

    A leitura dos separadores é a mesma (`_partir`), então `4,5`, `4.5` e
    `1.234,5` são lidos igual nas duas.

    Com `percentual=True`, o que se digita é uma porcentagem e o que se grava
    é a fração: `4`, `4%` e `4,00` viram todos `0.04`. Sem ele, o número entra
    como está: `0,04` vira `0.04`.
    """
    if texto is None:
        raise ValorInvalido("Informe o valor.")

    bruto = str(texto).strip()
    for lixo in (" ", "\xa0"):  # espaco nao-quebravel de colagem
        bruto = bruto.replace(lixo, "")
    bruto = bruto.rstrip("%")
    if not bruto:
        raise ValorInvalido("Informe o valor.")

    if not re.fullmatch(r"-?[\d.,]+", bruto):
        raise ValorInvalido("Valor inválido. Use apenas números, como 4,5.")
    if bruto.startswith("-"):
        # Nenhum dos parâmetros conhecidos admite valor negativo, e "-4" é
        # quase sempre um "4" com um dedo a mais.
        raise ValorInvalido("O valor não pode ser negativo.")

    inteiro, decimais = _partir(bruto)
    inteiro = inteiro or "0"
    if not inteiro.isdigit() or (decimais and not decimais.isdigit()):
        raise ValorInvalido("Valor inválido. Use apenas números, como 4,5.")

    # Ao dividir por 100 o percentual ganha duas casas: quem digita 4 casas
    # num percentual já chega no limite de seis da coluna.
    maximo = casas - 2 if percentual else casas
    if len(decimais) > maximo:
        raise ValorInvalido(f"Use no máximo {maximo} casas decimais.")

    try:
        valor = Decimal(f"{inteiro}.{decimais or '0'}")
    except InvalidOperation:
        raise ValorInvalido("Valor inválido.") from None

    if percentual:
        valor = valor / 100

    # NUMERIC(12,6): seis casas decimais e seis dígitos antes da vírgula.
    if valor >= Decimal("1000000"):
        raise ValorInvalido("Valor alto demais.")

    return valor.quantize(Decimal(1).scaleb(-casas))


def formatar_numero(valor, casas=2):
    """Decimal -> texto pt-BR com `casas` decimais e ponto de milhar."""
    if valor is None:
        return ""
    inteiro, _, decimais = f"{Decimal(valor):,.{casas}f}".partition(".")
    inteiro = inteiro.replace(",", ".")
    return f"{inteiro},{decimais}" if decimais else inteiro


def formatar_valor(valor):
    """Decimal -> '1.234,56' (sem o prefixo R$, que fica no template).

    Registrada no factory como o filtro Jinja `moeda`. Fica ao lado do parser:
    os dois são o mesmo assunto visto dos dois lados.
    """
    return formatar_numero(valor, 2)


# --------------------------------------------------------------------------
# Ordenação alfabética
# --------------------------------------------------------------------------

def chave_alfabetica(nome):
    """Nome dobrado (sem acento, em minúscula) para ordenar como em pt-BR.

    O `sorted` do Python compara ponto de código, e aí 'Água e esgoto' cairia
    depois de 'Vestuário', porque 'Á' vale mais que qualquer letra ASCII —
    ninguém procura a primeira categoria da lista no fim dela. Decompor em NFD
    e descartar as marcas combinantes põe cada nome onde se espera.

    `locale.strxfrm` faria o mesmo, mas locale no Windows não é confiável: é a
    mesma razão pela qual os nomes dos meses são uma tupla aqui em cima.
    O nome original entra como segunda chave para 'Saude' e 'Saúde', se um dia
    existirem, não trocarem de lugar entre uma leitura e outra.

    Nasceu privada em `main/servico_mensal.py` (rodada 12) e subiu para cá na
    rodada 15, quando o orçamento virou a terceira tela a precisar dela.
    """
    dobrado = "".join(letra for letra in unicodedata.normalize("NFD", nome)
                      if not unicodedata.combining(letra))
    return dobrado.lower(), nome


# --------------------------------------------------------------------------
# Busca textual
# --------------------------------------------------------------------------

def escapar_like(texto):
    """Neutraliza os curingas do ILIKE dentro do que a pessoa digitou.

    Sem isso, buscar por `%` casa com tudo e a busca por texto vira uma
    listagem aberta; `_` casaria com qualquer caractere. A barra invertida
    vem primeiro, senão escaparíamos as barras que acabamos de inserir.
    """
    return (texto.replace("\\", "\\\\")
                 .replace("%", "\\%")
                 .replace("_", "\\_"))


# --------------------------------------------------------------------------
# HTMX
# --------------------------------------------------------------------------

def so_fragmento():
    """True quando o HTMX quer apenas um fragmento, e não a página inteira.

    Morava em `lancamentos/servico.py`, que era o único lugar com telas
    filtradas; subiu para cá quando o detalhe da Visão Mensal virou a terceira
    a precisar dela — e um blueprint importar helper de outro seria pior que
    a duplicata.

    A exceção é a restauração de histórico: quando o cache do HTMX não tem a
    tela, ele refaz o GET com HX-History-Restore-Request e espera a página
    inteira de volta. Devolver o fragmento ali quebraria o botão voltar.
    """
    return bool(
        request.headers.get("HX-Request")
        and not request.headers.get("HX-History-Restore-Request")
    )
