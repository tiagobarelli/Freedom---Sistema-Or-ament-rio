"""Carga da série histórica do IPCA a partir da API do SIDRA (IBGE).

Três funções separadas de propósito, e a separação é o que torna a carga
exercitável e atômica:

- `buscar` é o **único** ponto com rede;
- `interpretar` é pura — nem rede nem banco —, então dá para exercitá-la com
  uma resposta salva em arquivo, inclusive adulterada de propósito;
- `gravar` é o único ponto com banco, e escreve tudo numa transação só.

`carregar` encadeia as três e é o caminho de verdade: `flask carregar-ipca` e
o botão "Atualizar do IBGE" chamam essa mesma função, mudando só a espera. O
que cada um mostra sai de funções puras sobre o resultado dela — `texto_da_faixa`
e `texto_do_erro` para a tela, o `click.echo` do comando para o terminal.

Fonte: tabela 1737 do SIDRA, Brasil (`n1`), variáveis 2266 (número-índice, base
dezembro/1993 = 100) e 63 (variação mensal, em %), todos os períodos. A resposta
é um array JSON cujo primeiro elemento é o cabeçalho que nomeia as colunas; as
demais linhas trazem uma variável cada, então vêm duas por mês.
"""

import json
import re
import urllib.error
import urllib.request
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import psycopg

from freedom.db import get_connection, query_all, query_one
from freedom.util import (MESES, dobrar, formatar_numero,
                          intervalo_de_meses, nome_do_periodo,
                          somar_meses)

URL_SIDRA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266,63/p/all"

# Sem nova tentativa automática nem no comando nem no botão: falhar rápido
# com mensagem clara é melhor do que um comando que parece travado.
#
# São dois limites porque são duas esperas diferentes. No terminal quem espera
# é o dono, que vê o cursor parado e sabe o que pediu. Na tela quem espera é o
# gunicorn do deploy, que corta a requisição em 30 s: 20 s deixam margem para
# interpretar e gravar antes disso, e o erro sai como faixa em vez de 502 do
# servidor web.
TEMPO_LIMITE = 60
TEMPO_LIMITE_WEB = 20

VARIAVEL_INDICE = "2266"
VARIAVEL_VARIACAO = "63"

# Antes de dezembro/1993 a série vem reconstruída em moedas extintas e o índice
# chega a 0,0000000076: não cabe em NUMERIC(14,6), não tem uso no Freedom e
# ainda faria o teste de "índice positivo" depender de arredondamento.
PRIMEIRO_MES = "199312"

_CODIGO_MES = re.compile(r"\d{4}(0[1-9]|1[0-2])")


# Etapas da carga. A etapa não muda a mensagem — muda quem é o culpado, e é
# isso que decide o status HTTP da rota (502 quando o IBGE falhou, 503 quando
# o banco falhou) e a primeira metade do texto da faixa.
ETAPA_IBGE = "ibge"      # a rede, ou a API fora do ar
ETAPA_DADOS = "dados"    # o IBGE respondeu, mas a série não serve
ETAPA_BANCO = "banco"    # a série serve, o banco recusou


class ErroIpca(Exception):
    """Falha na carga do IPCA, com mensagem pronta para mostrar ao dono."""

    def __init__(self, mensagem, etapa=ETAPA_IBGE, motivo=None):
        super().__init__(mensagem)
        self.etapa = etapa
        # A mensagem é a frase inteira, escrita para o terminal ("A API do
        # SIDRA respondeu 503... Nada foi gravado."); o motivo é só a causa,
        # para a faixa da tela não repetir o que a frase dela já diz. Sem
        # motivo próprio, a faixa usa a mensagem.
        self.motivo = motivo


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
            "Nada foi gravado.",
            motivo=f"a API respondeu {erro.code} ({erro.reason})",
        ) from erro
    except urllib.error.URLError as erro:
        raise ErroIpca(
            f"Não foi possível falar com a API do SIDRA: {erro.reason}. "
            "Confira a conexão e tente de novo.",
            motivo=str(erro.reason),
        ) from erro
    except TimeoutError as erro:
        raise ErroIpca(
            f"A API do SIDRA não respondeu em {tempo_limite} segundos. "
            "Nada foi gravado.",
            motivo=f"não respondeu em {tempo_limite} segundos",
        ) from erro
    except OSError as erro:
        raise ErroIpca(
            f"Falha de rede ao chamar a API do SIDRA: {erro}.",
            motivo=str(erro),
        ) from erro

    try:
        return json.loads(corpo.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroIpca(
            "A API do SIDRA devolveu algo que não é o JSON esperado.",
            motivo="a resposta não é o JSON esperado",
        ) from erro


# --------------------------------------------------------------------------
# 2. Interpretação (pura)
# --------------------------------------------------------------------------

def _dobrar(texto):
    """Nome de coluna dobrado e com um espaço só, para casar com o rótulo.

    A dobra NFD é a de `util.dobrar`, a mesma que ordena nome de categoria:
    era reescrita aqui até a rodada 22. O que é próprio deste uso é colapsar o
    espaço em branco — o que se compara é rótulo do IBGE, não nome digitado.
    """
    return " ".join(dobrar(texto).split())


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
    , ETAPA_DADOS)


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
        , ETAPA_DADOS)

    cabecalho, *linhas = bruto
    if not isinstance(cabecalho, dict):
        raise ErroIpca(
            "O primeiro elemento da resposta do SIDRA não é o cabeçalho."
        , ETAPA_DADOS)

    chave_mes = _coluna(cabecalho, "mes (codigo)")
    chave_variavel = _coluna(cabecalho, "variavel (codigo)")
    chave_valor = _coluna(cabecalho, "valor")

    indices, variacoes = {}, {}
    for numero, linha in enumerate(linhas, start=2):
        if not isinstance(linha, dict):
            raise ErroIpca(
                f"A linha {numero} da resposta do SIDRA não é um objeto."
            , ETAPA_DADOS)

        codigo = linha.get(chave_mes)
        if not isinstance(codigo, str) or not _CODIGO_MES.fullmatch(codigo.strip()):
            raise ErroIpca(
                f"Código de mês inesperado na linha {numero} do SIDRA: {codigo!r}."
            , ETAPA_DADOS)
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
                , ETAPA_DADOS)
            valor = _para_decimal(texto)
            if valor is None:
                raise ErroIpca(
                    f"O número-índice de {_rotulo(codigo)} não é um número: "
                    f"{texto!r}."
                , ETAPA_DADOS)
            indices[codigo] = valor
        elif variavel == VARIAVEL_VARIACAO:
            if codigo in variacoes:
                raise ErroIpca(
                    f"O mês {_rotulo(codigo)} veio mais de uma vez na série da "
                    "variação mensal."
                , ETAPA_DADOS)
            # Variação sem número é NULL, e não erro: a coluna é opcional e o
            # índice, que é o que importa, continua vindo.
            variacoes[codigo] = _para_decimal(texto)

    if not indices:
        raise ErroIpca(
            "A resposta do SIDRA não trouxe nenhum mês a partir de dezembro "
            "de 1993."
        , ETAPA_DADOS)

    if PRIMEIRO_MES not in indices:
        raise ErroIpca(
            "A série não traz dezembro de 1993, que é a base do número-índice."
        , ETAPA_DADOS)
    if indices[PRIMEIRO_MES] != 100:
        raise ErroIpca(
            f"O índice de dezembro de 1993 deveria ser exatamente 100 e veio "
            f"{indices[PRIMEIRO_MES]:f}. A base da série mudou — confira no SIDRA "
            "antes de gravar."
        , ETAPA_DADOS)

    codigos = sorted(indices)
    esperados = list(_codigos_entre(codigos[0], codigos[-1]))
    faltando = [codigo for codigo in esperados if codigo not in indices]
    if faltando:
        mostra = ", ".join(_rotulo(codigo) for codigo in faltando[:5])
        resto = "" if len(faltando) <= 5 else f" (e mais {len(faltando) - 5})"
        raise ErroIpca(
            f"A série do SIDRA tem buraco entre {_rotulo(codigos[0])} e "
            f"{_rotulo(codigos[-1])}: falta {mostra}{resto}."
        , ETAPA_DADOS)

    nao_positivos = [codigo for codigo in esperados if indices[codigo] <= 0]
    if nao_positivos:
        mostra = ", ".join(
            f"{_rotulo(codigo)} = {indices[codigo]:f}"
            for codigo in nao_positivos[:5]
        )
        raise ErroIpca(
            f"Número-índice não positivo na série do SIDRA: {mostra}. "
            "Deflacionar por ele daria divisão por zero ou sinal trocado."
        , ETAPA_DADOS)

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
        RETURNING mes, (xmax = 0) AS nasceu
    )
    SELECT count(*) FILTER (WHERE nasceu)            AS inseridos,
           count(*) FILTER (WHERE NOT nasceu)        AS atualizados,
           (SELECT count(*) FROM entrada) - count(*) AS iguais,
           array_agg(mes ORDER BY mes) FILTER (WHERE nasceu) AS meses_inseridos
      FROM gravado
"""


def gravar(registros):
    """Grava a lista de `interpretar` numa transação só.

    Devolve o dicionário com `inseridos`, `atualizados`, `iguais` e
    `meses_inseridos` — a lista, e não só a contagem, porque a faixa da tela
    diz *qual* mês entrou. Quem sabe disso é o banco: `xmax = 0` separa a
    linha que nasceu da que foi atualizada, e o `array_agg` a nomeia.

    Qualquer erro no meio desfaz tudo: não existe carga parcial, e a tabela
    nunca perde linha — o pior caso é ficar como estava.
    """
    if not registros:
        raise ErroIpca("Não há nada a gravar: a série veio vazia.", ETAPA_DADOS)

    meses = [mes for mes, _, _ in registros]
    indices = [indice for _, indice, _ in registros]
    variacoes = [variacao for _, _, variacao in registros]

    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(SQL_CARGA, (meses, indices, variacoes))
            contagens = cur.fetchone()
    except psycopg.Error as erro:
        raise ErroIpca(
            f"O banco recusou a carga e nada foi gravado: {str(erro).strip()}",
            ETAPA_BANCO,
            motivo=str(erro).strip(),
        ) from erro

    # array_agg sem nenhuma linha devolve NULL, e não lista vazia.
    contagens["meses_inseridos"] = contagens["meses_inseridos"] or []
    return contagens


# --------------------------------------------------------------------------
# 4. Leitura (tela /cadastros/ipca)
# --------------------------------------------------------------------------

VARIACAO = "variacao"
INDICE = "indice"
MODOS = (VARIACAO, INDICE)

# Travessão: a célula existe, o número não. Mesma convenção da Visão Anual.
SEM_VALOR = "\u2014"

CENTAVO = Decimal("0.01")


def modo_valido(texto):
    """Modo pedido na URL, ou variação. Texto fora da lista não é erro.

    Mesma regra de todo seletor do projeto: ano inválido na Anual, mês
    inválido na Mensal e modo inválido aqui caem no padrão em silêncio.
    """
    return texto if texto in MODOS else VARIACAO


def serie():
    """A série inteira, do mês mais antigo ao mais novo.

    Sem filtro de período: a tela mostra tudo o que está carregado, e são 393
    linhas de três colunas — uma consulta só custa menos que paginar.
    """
    return query_all(
        "SELECT mes, numero_indice, variacao_mensal FROM tb_ipca ORDER BY mes"
    )


def base_de_correcao():
    """O último mês carregado e o índice dele, ou None com a tabela vazia.

    É a base da deflação ("a preços de agosto de 2026"): corrigir para um mês
    que o IBGE ainda não publicou seria inventar inflação. Uma linha, e não a
    série inteira, porque quem chama só quer o topo.
    """
    return query_one(
        "SELECT mes, numero_indice FROM tb_ipca ORDER BY mes DESC LIMIT 1")


def _celula(valor):
    """Decimal ou None -> texto pronto, mais o aviso de negativo.

    None é mês sem dado (1993 antes de dezembro, mês do ano corrente que o
    IBGE ainda não publicou) ou variação que o IBGE não publicou. Nos três
    casos: travessão — e travessão nunca sai vermelho.
    """
    if valor is None:
        return {"texto": SEM_VALOR, "negativo": False}
    return {"texto": formatar_numero(valor, 2), "negativo": valor < 0}


def _no_ano(indices, ano):
    """Acumulado do ano em pontos percentuais, ou None.

    Índice do último mês carregado do ano sobre o índice de dezembro do ano
    anterior. É a conta do IBGE, e é a única que serve: somar as variações
    mensais ignora que elas se compõem, e erraria mais quanto maior a
    inflação do ano.

    None em 1993, que é a base da série e não tem dezembro anterior.
    """
    base = indices.get((ano - 1, 12))
    if base is None:
        return None
    meses = [mes for (a, mes) in indices if a == ano]
    if not meses:
        return None
    ultimo = indices[(ano, max(meses))]
    return ((ultimo / base - 1) * 100).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def matriz(linhas, modo=VARIACAO):
    """Série do banco -> matriz ano × mês pronta para a tela.

    Pura: nem rede nem banco, então dá para exercitá-la com a série em memória
    e com a lista vazia. Devolve texto e estado prontos — o template escolhe
    só o lugar de cada coisa.

    Uma linha por ano, do mais recente ao mais antigo, com as doze colunas de
    mês e a coluna "No ano". "No ano" é a MESMA conta nos dois modos: trocar
    de modo troca o que a célula do mês mostra, não o acumulado.

    Nada daqui é gravado: a matriz nasce a cada requisição.
    """
    indices, variacoes = {}, {}
    for linha in linhas:
        mes = linha["mes"]
        indices[(mes.year, mes.month)] = linha["numero_indice"]
        variacoes[(mes.year, mes.month)] = linha["variacao_mensal"]

    if not indices:
        return {"modo": modo, "linhas": [], "nota": None, "subtitulo": None,
                "ultimo": None, "vazia": True}

    chaves = sorted(indices)
    primeiro, ultimo = chaves[0], chaves[-1]
    valores = variacoes if modo == VARIACAO else indices

    linhas_matriz = [
        {
            "ano": ano,
            "celulas": [_celula(valores.get((ano, mes))) for mes in range(1, 13)],
            "no_ano": _celula(_no_ano(indices, ano)),
        }
        for ano in range(ultimo[0], primeiro[0] - 1, -1)
    ]

    # O ano corrente só tem os meses já publicados, e o acumulado dele não é o
    # do ano fechado. A nota diz isso embaixo da tabela, em vez de um asterisco
    # na célula: quem lê a coluna inteira precisa da ressalva uma vez só.
    nota = (None if ultimo[1] == 12
            else f"{ultimo[0]}: acumulado até {MESES[ultimo[1] - 1]}")

    return {
        "modo": modo,
        "linhas": linhas_matriz,
        "nota": nota,
        "subtitulo": (f"Série do IBGE · {nome_do_periodo(*primeiro)} "
                      f"a {nome_do_periodo(*ultimo)}"),
        # O último mês sai em `date` porque quem o usa é a dica, que compara
        # com o mês esperado — comparar texto de tela seria comparar rótulo.
        "ultimo": date(ultimo[0], ultimo[1], 1),
        "vazia": False,
    }


# --------------------------------------------------------------------------
# 5. Carga completa: a mesma para o comando e para o botão
# --------------------------------------------------------------------------

def carregar(tempo_limite=TEMPO_LIMITE):
    """Encadeia buscar -> interpretar -> gravar e devolve o que aconteceu.

    Existe para que `flask carregar-ipca` e o botão "Atualizar do IBGE" sejam
    literalmente o mesmo caminho: se um trouxer o mês novo, o outro traria
    igual. O que muda entre eles é só a espera (o comando dá 60 s, a tela 20 s)
    e o formato do relato — texto no terminal, faixa na tela —, e os dois saem
    deste mesmo dicionário.

    Levanta `ErroIpca` com a etapa preenchida; nada é gravado pela metade.
    """
    registros = interpretar(buscar(tempo_limite=tempo_limite))
    contagens = gravar(registros)

    ultimo_mes, ultimo_indice, ultima_variacao = registros[-1]
    return {
        "primeiro": registros[0][0],
        "ultimo": ultimo_mes,
        "meses": len(registros),
        "casas": casas_decimais(registros),
        "inseridos": contagens["inseridos"],
        "atualizados": contagens["atualizados"],
        "iguais": contagens["iguais"],
        "meses_inseridos": contagens["meses_inseridos"],
        "meses_nulos": [mes for mes, _, variacao in registros if variacao is None],
        "indice_ultimo": ultimo_indice,
        "variacao_ultimo": ultima_variacao,
    }


def texto_das_nulas(meses_nulos):
    """"Variação nula em 2 mês(es): 1994-02, 1994-03." ou None.

    Mês sem variação publicada é legítimo (a coluna é opcional), mas é o tipo
    de buraco que se descobre tarde, quando um gráfico some. Acima de doze
    meses vira só a contagem, que é quando a lista deixaria de caber — na tela
    e na linha do terminal.
    """
    if not meses_nulos:
        return None
    lista = ("" if len(meses_nulos) > 12
             else ": " + ", ".join(f"{mes:%Y-%m}" for mes in meses_nulos))
    return f"Variação nula em {len(meses_nulos)} mês(es){lista}."


def texto_da_faixa(resultado):
    """Resultado de `carregar` -> a frase que a faixa da tela mostra.

    Pura, e é ela que decide tudo o que a faixa diz: o Jinja recebe a frase
    pronta. Três começos possíveis (nada novo, um mês, vários) e dois
    acréscimos (revisão do IBGE, variação nula), na ordem em que interessam a
    quem clicou.
    """
    inseridos = resultado["meses_inseridos"]

    if not inseridos:
        frase = ("Nenhum mês novo — a série já vai até "
                 f"{nome_do_periodo(resultado['ultimo'])}.")
    elif len(inseridos) == 1:
        variacao = resultado["variacao_ultimo"]
        fim = ("variação não publicada" if variacao is None
               else f"variação {formatar_numero(variacao, 2)} %")
        frase = (f"{nome_do_periodo(inseridos[0]).capitalize()} carregado: "
                 f"índice {formatar_numero(resultado['indice_ultimo'], 2)}, {fim}.")
    else:
        frase = (f"{len(inseridos)} meses carregados "
                 f"({intervalo_de_meses(inseridos[0], inseridos[-1])}).")

    partes = [frase]
    if resultado["atualizados"]:
        quantos = resultado["atualizados"]
        partes.append(f"{quantos} mês(es) revisado(s) pelo IBGE.")
    nulas = texto_das_nulas(resultado["meses_nulos"])
    if nulas:
        partes.append(nulas)
    return " ".join(partes)


def texto_do_erro(erro):
    """`ErroIpca` -> a frase da faixa vermelha.

    Quem falhou muda o texto, e não só o status: dizer "não foi possível falar
    com o IBGE" quando a conversa correu bem e a série é que veio torta manda
    o dono conferir a internet à toa.
    """
    motivo = (erro.motivo or str(erro)).strip()
    if not motivo.endswith((".", "!", "?")):
        motivo += "."

    if erro.etapa == ETAPA_BANCO:
        return f"Falha ao gravar: {motivo}"
    if erro.etapa == ETAPA_DADOS:
        return (f"O IBGE respondeu, mas a série veio fora do esperado: "
                f"{motivo} Nada foi alterado.")
    return f"Não foi possível falar com o IBGE: {motivo} Nada foi alterado."


# --------------------------------------------------------------------------
# 6. Que mês já se espera do IBGE
# --------------------------------------------------------------------------

# O IBGE publica o índice do mês anterior por volta do dia 10. O dia 12 dá dois
# dias de folga: antes dele, quem se espera é o mês retrasado.
DIA_DA_PUBLICACAO = 12


def mes_esperado(hoje):
    """A data de hoje -> o mês mais recente que o IBGE já deve ter publicado.

    Recebe a data por parâmetro, e nunca lê o relógio: assim a regra se
    exercita em qualquer dia do calendário sem mexer no relógio da máquina.
    """
    passos = 1 if hoje.day >= DIA_DA_PUBLICACAO else 2
    return somar_meses(date(hoje.year, hoje.month, 1), -passos)


def pendente(hoje, ultimo_mes):
    """Falta mês a carregar? Falso quando a tabela está vazia.

    Sem nenhum mês não há o que dizer: a tela vazia já convida a carregar, e
    prometer "o IBGE já deve ter publicado agosto" seria pedir um mês de 393.
    """
    return ultimo_mes is not None and ultimo_mes < mes_esperado(hoje)


def texto_da_dica(hoje, ultimo_mes):
    """A linha discreta acima da tabela, ou None quando não há o que dizer."""
    if not pendente(hoje, ultimo_mes):
        return None
    return ("O IBGE já deve ter publicado "
            f"{nome_do_periodo(mes_esperado(hoje))}.")
