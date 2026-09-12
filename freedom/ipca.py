"""Carga da série histórica do IPCA a partir da API do SIDRA (IBGE).

Três funções separadas de propósito, e a separação é o que torna a carga
exercitável e atômica:

- `buscar` é o **único** ponto com rede;
- `interpretar` é pura — nem rede nem banco —, então dá para exercitá-la com
  uma resposta salva em arquivo, inclusive adulterada de propósito;
- `gravar` é o único ponto com banco, e escreve tudo numa transação só.

Fonte: tabela 1737 do SIDRA, Brasil (`n1`), variáveis 2266 (número-índice, base
dezembro/1993 = 100) e 63 (variação mensal, em %), todos os períodos. A resposta
é um array JSON cujo primeiro elemento é o cabeçalho que nomeia as colunas; as
demais linhas trazem uma variável cada, então vêm duas por mês.
"""

import json
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal, InvalidOperation

import psycopg

from freedom.db import get_connection

URL_SIDRA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266,63/p/all"

# Sem nova tentativa automática: o comando é manual, e falhar rápido com
# mensagem clara é melhor do que um comando que parece travado.
TEMPO_LIMITE = 60

VARIAVEL_INDICE = "2266"
VARIAVEL_VARIACAO = "63"

# Antes de dezembro/1993 a série vem reconstruída em moedas extintas e o índice
# chega a 0,0000000076: não cabe em NUMERIC(14,6), não tem uso no Freedom e
# ainda faria o teste de "índice positivo" depender de arredondamento.
PRIMEIRO_MES = "199312"

_CODIGO_MES = re.compile(r"\d{4}(0[1-9]|1[0-2])")


class ErroIpca(Exception):
    """Falha na carga do IPCA, com mensagem pronta para mostrar ao dono."""


# --------------------------------------------------------------------------
# 1. Rede
# --------------------------------------------------------------------------

def buscar(url=URL_SIDRA, tempo_limite=TEMPO_LIMITE):
    """Baixa a série do SIDRA e devolve o JSON decodificado, como veio.

    Não interpreta nada: quem separa mês de variável é `interpretar`. Toda
    falha de rede vira `ErroIpca` com texto legível, porque o destino dela é a
    tela do comando, não um traceback.
    """
    requisicao = urllib.request.Request(url, headers={"User-Agent": "Freedom"})
    try:
        with urllib.request.urlopen(requisicao, timeout=tempo_limite) as resposta:
            corpo = resposta.read()
    except urllib.error.HTTPError as erro:
        raise ErroIpca(
            f"A API do SIDRA respondeu {erro.code} ({erro.reason}). "
            "Nada foi gravado."
        ) from erro
    except urllib.error.URLError as erro:
        raise ErroIpca(
            f"Não foi possível falar com a API do SIDRA: {erro.reason}. "
            "Confira a conexão e tente de novo."
        ) from erro
    except TimeoutError as erro:
        raise ErroIpca(
            f"A API do SIDRA não respondeu em {tempo_limite} segundos. "
            "Nada foi gravado."
        ) from erro
    except OSError as erro:
        raise ErroIpca(
            f"Falha de rede ao chamar a API do SIDRA: {erro}."
        ) from erro

    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroIpca(
            "A API do SIDRA devolveu algo que não é o JSON esperado."
        ) from erro


# --------------------------------------------------------------------------
# 2. Interpretação (pura)
# --------------------------------------------------------------------------

def _dobrar(texto):
    """Nome de coluna sem acento, em minúscula e com um espaço só.

    Mesma dobra NFD de `util.chave_alfabetica`, mas aqui o alvo é comparar
    rótulo do IBGE, e não ordenar lista: o que se compara é uma string, não a
    tupla de ordenação que aquela devolve.
    """
    dobrado = "".join(letra for letra in unicodedata.normalize("NFD", texto)
                      if not unicodedata.combining(letra))
    return " ".join(dobrado.lower().split())


def _coluna(cabecalho, rotulo):
    """Chave da coluna cujo nome no cabeçalho é `rotulo`.

    A posição das colunas não é documentada como estável; o cabeçalho é. Pedir
    a coluna pelo nome faz uma mudança de formato virar erro claro, em vez de
    número trocado.
    """
    for chave, nome in cabecalho.items():
        if isinstance(nome, str) and _dobrar(nome) == rotulo:
            return chave
    raise ErroIpca(
        f"O cabeçalho da resposta do SIDRA não tem a coluna '{rotulo}'. "
        "O formato da API mudou; nada foi gravado."
    )


def _rotulo(codigo):
    """'202608' -> '2026-08', para as mensagens de erro."""
    return f"{codigo[:4]}-{codigo[4:]}"


def _codigos_entre(inicio, fim):
    """Todos os códigos AAAAMM de `inicio` a `fim`, mês a mês, inclusive."""
    ano, mes = int(inicio[:4]), int(inicio[4:])
    ultimo = (int(fim[:4]), int(fim[4:]))
    while (ano, mes) <= ultimo:
        yield f"{ano:04d}{mes:02d}"
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _para_decimal(texto):
    """Texto do SIDRA -> Decimal, ou None quando não é número.

    `Decimal(texto)` direto, sem passar por float: o índice vem com treze casas
    e float não guarda todas. `util.converter_numero` não serve aqui — ela lê a
    vírgula que gente digita, e o IBGE publica com ponto.

    Devolve None para os marcadores de "não publicado" ('...', '-', 'X', vazio)
    e também para 'NaN' e 'Infinity', que o Decimal aceitaria como número.
    """
    if not isinstance(texto, str):
        return None
    try:
        valor = Decimal(texto.strip())
    except InvalidOperation:
        return None
    return valor if valor.is_finite() else None


def interpretar(bruto):
    """JSON do SIDRA -> lista de `(mes, numero_indice, variacao_mensal)`.

    `mes` é o primeiro dia do mês; `numero_indice` é o publicado, sem
    arredondar; `variacao_mensal` é Decimal em pontos percentuais (0.38 é
    0,38 %, negativo em mês de deflação) ou None quando o IBGE não publica
    número.

    Recusa a série inteira — e aí nada é gravado — quando dezembro/1993 falta
    ou não vale exatamente 100, quando há buraco entre o primeiro e o último
    mês, quando algum índice não é positivo e quando um mês vem repetido. Meia
    série é pior que série nenhuma: o número-índice só serve encadeado.
    """
    if not isinstance(bruto, list) or len(bruto) < 2:
        raise ErroIpca(
            "A resposta do SIDRA não é a lista esperada (cabeçalho e linhas)."
        )

    cabecalho, *linhas = bruto
    if not isinstance(cabecalho, dict):
        raise ErroIpca(
            "O primeiro elemento da resposta do SIDRA não é o cabeçalho."
        )

    chave_mes = _coluna(cabecalho, "mes (codigo)")
    chave_variavel = _coluna(cabecalho, "variavel (codigo)")
    chave_valor = _coluna(cabecalho, "valor")

    indices, variacoes = {}, {}
    for numero, linha in enumerate(linhas, start=2):
        if not isinstance(linha, dict):
            raise ErroIpca(
                f"A linha {numero} da resposta do SIDRA não é um objeto."
            )

        codigo = linha.get(chave_mes)
        if not isinstance(codigo, str) or not _CODIGO_MES.fullmatch(codigo.strip()):
            raise ErroIpca(
                f"Código de mês inesperado na linha {numero} do SIDRA: {codigo!r}."
            )
        codigo = codigo.strip()

        # O descarte é pelo código, antes de converter valor nenhum: o índice
        # de antes de dez/1993 não precisa nem ser lido.
        if codigo < PRIMEIRO_MES:
            continue

        variavel = linha.get(chave_variavel)
        texto = linha.get(chave_valor)

        if variavel == VARIAVEL_INDICE:
            if codigo in indices:
                raise ErroIpca(
                    f"O mês {_rotulo(codigo)} veio mais de uma vez na série do "
                    "número-índice."
                )
            valor = _para_decimal(texto)
            if valor is None:
                raise ErroIpca(
                    f"O número-índice de {_rotulo(codigo)} não é um número: "
                    f"{texto!r}."
                )
            indices[codigo] = valor
        elif variavel == VARIAVEL_VARIACAO:
            if codigo in variacoes:
                raise ErroIpca(
                    f"O mês {_rotulo(codigo)} veio mais de uma vez na série da "
                    "variação mensal."
                )
            # Variação sem número é NULL, e não erro: a coluna é opcional e o
            # índice, que é o que importa, continua vindo.
            variacoes[codigo] = _para_decimal(texto)

    if not indices:
        raise ErroIpca(
            "A resposta do SIDRA não trouxe nenhum mês a partir de dezembro "
            "de 1993."
        )

    if PRIMEIRO_MES not in indices:
        raise ErroIpca(
            "A série não traz dezembro de 1993, que é a base do número-índice."
        )
    if indices[PRIMEIRO_MES] != 100:
        raise ErroIpca(
            f"O índice de dezembro de 1993 deveria ser exatamente 100 e veio "
            f"{indices[PRIMEIRO_MES]:f}. A base da série mudou — confira no SIDRA "
            "antes de gravar."
        )

    codigos = sorted(indices)
    esperados = list(_codigos_entre(codigos[0], codigos[-1]))
    faltando = [codigo for codigo in esperados if codigo not in indices]
    if faltando:
        mostra = ", ".join(_rotulo(codigo) for codigo in faltando[:5])
        resto = "" if len(faltando) <= 5 else f" (e mais {len(faltando) - 5})"
        raise ErroIpca(
            f"A série do SIDRA tem buraco entre {_rotulo(codigos[0])} e "
            f"{_rotulo(codigos[-1])}: falta {mostra}{resto}."
        )

    nao_positivos = [codigo for codigo in esperados if indices[codigo] <= 0]
    if nao_positivos:
        mostra = ", ".join(
            f"{_rotulo(codigo)} = {indices[codigo]:f}"
            for codigo in nao_positivos[:5]
        )
        raise ErroIpca(
            f"Número-índice não positivo na série do SIDRA: {mostra}. "
            "Deflacionar por ele daria divisão por zero ou sinal trocado."
        )

    return [
        (date(int(codigo[:4]), int(codigo[4:]), 1),
         indices[codigo],
         variacoes.get(codigo))
        for codigo in esperados
    ]


def casas_decimais(registros):
    """Casas decimais com que a API devolveu o número-índice.

    `Decimal` guarda os zeros à direita do texto original, então o expoente
    conta o que veio na resposta, e não as casas significativas. É por isso que
    dá para relatar a precisão da API sem carregar o texto bruto até aqui.
    """
    return max(max(0, -indice.as_tuple().exponent) for _, indice, _ in registros)


# --------------------------------------------------------------------------
# 3. Banco
# --------------------------------------------------------------------------

# Um comando só, e por isso uma transação só: ou a série inteira entra, ou nada
# entra. O WHERE do DO UPDATE é o que faz o mês já igual não ser tocado, e as
# contagens saem do próprio banco — `xmax = 0` é verdadeiro na linha que nasceu
# neste comando e falso na que foi atualizada. DELETE não existe aqui: mês
# publicado não some do IBGE.
SQL_CARGA = """
    WITH entrada AS (
        SELECT *
          FROM unnest(%s::date[], %s::numeric[], %s::numeric[])
            AS t(mes, numero_indice, variacao_mensal)
    ),
    gravado AS (
        INSERT INTO tb_ipca (mes, numero_indice, variacao_mensal)
        SELECT mes, numero_indice, variacao_mensal FROM entrada
        ON CONFLICT (mes) DO UPDATE
           SET numero_indice   = EXCLUDED.numero_indice,
               variacao_mensal = EXCLUDED.variacao_mensal
         WHERE tb_ipca.numero_indice   IS DISTINCT FROM EXCLUDED.numero_indice
            OR tb_ipca.variacao_mensal IS DISTINCT FROM EXCLUDED.variacao_mensal
        RETURNING (xmax = 0) AS nasceu
    )
    SELECT count(*) FILTER (WHERE nasceu)            AS inseridos,
           count(*) FILTER (WHERE NOT nasceu)        AS atualizados,
           (SELECT count(*) FROM entrada) - count(*) AS iguais
      FROM gravado
"""


def gravar(registros):
    """Grava a lista de `interpretar` numa transação só.

    Devolve o dicionário com `inseridos`, `atualizados` e `iguais`. Qualquer
    erro no meio desfaz tudo: não existe carga parcial, e a tabela nunca perde
    linha — o pior caso é ficar como estava.
    """
    if not registros:
        raise ErroIpca("Não há nada a gravar: a série veio vazia.")

    meses = [mes for mes, _, _ in registros]
    indices = [indice for _, indice, _ in registros]
    variacoes = [variacao for _, _, variacao in registros]

    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_CARGA, (meses, indices, variacoes))
            contagens = cur.fetchone()
    except psycopg.Error as erro:
        raise ErroIpca(
            f"O banco recusou a carga e nada foi gravado: {str(erro).strip()}"
        ) from erro

    return contagens
