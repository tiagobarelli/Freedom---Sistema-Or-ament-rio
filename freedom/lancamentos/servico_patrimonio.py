"""Patrimônio: a foto mensal dos ativos, e o que se lê dela.

Uma **foto** é o conjunto de valores dos ativos numa data. O sistema não
controla saldo e não calcula rendimento: a foto é **digitada**, mensalmente,
pelo dono — é exatamente o que ele vê no extrato de cada aplicação naquele
dia. Nada aqui cruza com despesa ou receita.

**A grade da foto É o editor.** Não há tela de "novo snapshot": abre-se uma
data, os campos vêm preenchidos (com o que já foi gravado, ou com o último
valor conhecido como sugestão) e "Gravar foto" acerta o banco de uma vez.

O contrato da gravação, numa transação só: **depois de gravar, o banco tem
para aquela data exatamente as linhas dos campos preenchidos, entre os ativos
da grade.** Preenchido grava ou atualiza (upsert em `(data, ativo_id)`, com o
`WHERE` que não reescreve linha igual); vazio apaga a linha se ela existia. E
**campo vazio quer dizer "fora da foto", nunca zero** — a distinção é o
coração da tela: zero é "este ativo existe e hoje vale nada", vazio é "não sei
/ não tinha". Zero é entrada legítima aqui e proibida no lançamento de
despesa, a mesma assimetria deliberada que o orçamento já tem (por isso o zero
é tratado por `parece_zero` ANTES de `converter_valor`, que o recusaria).

**Ativo encerrado** (`ativo = FALSE`) é posição encerrada, não cadastro
errado: some da grade e não recebe linha nova, mas as fotos antigas dele
continuam lá e continuam contando no total e na alocação. Desativar um ativo
que ainda tem valor é decisão do dono, e a nota do card avisa que ele está no
número.

Os cards, a alocação e o histórico falam sempre da **última foto do acervo**,
e não da data aberta na grade: a pergunta deles é "quanto a casa tem", que não
muda por alguém estar olhando um mês antigo.

Três consultas por carregamento, e são estas: a grade da data, o histórico com
`LAG` (cuja primeira linha É a última foto, e é a origem única do total) e a
alocação por classe com o que faltou e o que veio de encerrado, numa varredura
só por `GROUPING SETS`.
"""

from datetime import date, timedelta
from decimal import Decimal

from freedom.db import get_connection, query_all
from freedom.main.servico import SEM_VALOR, card
from freedom.util import (ValorInvalido, converter_valor, data_por_extenso,
                          formatar_numero, formatar_valor, fracao, parece_zero)

ZERO = Decimal("0.00")

# Prefixo dos campos da grade no corpo do POST: um por ativo, `valor_<id>`.
# Fica aqui, e não espalhado entre a rota e o template, porque é contrato
# entre os dois.
PREFIXO_CAMPO = "valor_"


# --------------------------------------------------------------------------
# 1. A data da foto (puras)
# --------------------------------------------------------------------------

def data_padrao(hoje):
    """Último dia do mês anterior a `hoje`. `date(2026,9,20)` -> 31/08/2026.

    É a data em que faz sentido tirar a foto: o mês fechou e os extratos
    saíram. `hoje` entra por parâmetro, como em toda função de data deste
    projeto — o relógio não é lido aqui dentro.
    """
    return date(hoje.year, hoje.month, 1) - timedelta(days=1)


def data_de_texto(texto):
    """'2026-08-31' -> date; qualquer outra coisa -> None.

    Pública porque a rota de exclusão também lê uma data do caminho, e ler
    data é uma coisa só no sistema inteiro."""
    try:
        return date.fromisoformat((texto or "").strip())
    except (ValueError, TypeError):
        return None


def data_valida(texto, hoje):
    """A data que a tela abre. Nunca levanta e nunca mostra erro. Pura.

    Texto ilegível ou data futura caem no padrão em silêncio — é a regra do
    ano inválido da Visão Anual. **Aqui, e só aqui**: no POST a data futura é
    recusada com erro de campo, porque ali alguém digitou e apertou "Gravar
    foto", e uma foto gravada em silêncio noutra data seria pior que um erro.
    """
    escolhida = data_de_texto(texto)
    if escolhida is None or escolhida > hoje:
        return data_padrao(hoje)
    return escolhida


def erro_da_data(texto, hoje):
    """A mensagem do campo de data no POST, ou None. Pura.

    Só duas recusas, e as duas são do usuário: texto que não é data e data no
    futuro. `tb_patrimonio_snapshots.data` não tem CHECK nenhum — esta regra é
    da aplicação, como diz o `.md` do banco.
    """
    escolhida = data_de_texto(texto)
    if escolhida is None:
        return "Informe a data da foto no formato AAAA-MM-DD."
    if escolhida > hoje:
        return "A data da foto não pode ser no futuro."
    return None


# --------------------------------------------------------------------------
# 2. Consultas
# --------------------------------------------------------------------------

# A grade de uma data: um ativo em carteira por linha, com o valor gravado
# naquela data (se houver) e o último valor ANTERIOR a ela, com a data dele.
#
# O LATERAL é o que dá o "último anterior" por ativo numa varredura só; um
# DISTINCT ON sobre a tabela inteira traria todas as datas para depois jogar
# fora. `p.data < %(data)s` é estrito de propósito: o valor da própria data
# já vem pela outra junção, e repeti-lo na coluna de apoio confundiria quem
# compara o que era com o que é.
_SQL_GRADE = """
    SELECT a.id, a.nome, a.classe,
           s.valor    AS valor_na_data,
           ult.data   AS ultima_data,
           ult.valor  AS ultimo_valor
      FROM tb_ativos a
      LEFT JOIN tb_patrimonio_snapshots s
             ON s.ativo_id = a.id AND s.data = %(data)s
      LEFT JOIN LATERAL (
            SELECT p.data, p.valor
              FROM tb_patrimonio_snapshots p
             WHERE p.ativo_id = a.id AND p.data < %(data)s
             ORDER BY p.data DESC
             LIMIT 1
      ) ult ON TRUE
     WHERE a.ativo
     ORDER BY a.classe, a.nome
"""

# O histórico inteiro, mais recente primeiro. Sem paginação: são fotos
# MENSAIS, e dez anos dão 120 linhas.
#
# A janela roda depois do GROUP BY, então `LAG(SUM(valor))` é a soma da foto
# anterior — o Δ sai do banco, e não de uma subtração em Python sobre a
# página. A ordem da janela é crescente (é assim que "anterior" se define) e a
# da saída é decrescente (é assim que a tabela se lê).
#
# A PRIMEIRA linha é a última foto, e é dela que saem os dois cards: total e
# Δ têm origem única, e por isso o card e o rodapé não têm como divergir.
_SQL_HISTORICO = """
    SELECT data,
           count(*)   AS ativos,
           SUM(valor) AS total,
           SUM(valor) - LAG(SUM(valor)) OVER (ORDER BY data) AS delta
      FROM tb_patrimonio_snapshots
     GROUP BY data
     ORDER BY data DESC
"""

# Alocação por classe na última foto, mais o que a tela precisa dizer sobre
# ela, numa varredura só.
#
# O conjunto de linhas é "ativo em carteira (tenha ou não valor na última
# foto) OU linha da última foto de ativo encerrado" — é o `WHERE` do CTE. Daí:
#
# - as linhas por classe dão a alocação;
# - a linha do `()` dá a lista dos que FALTAM (em carteira, sem valor na foto)
#   e quantos ENCERRADOS entraram no total.
#
# `GROUPING SETS ((classe), ())` responde as duas perguntas na mesma passagem.
# O total do `()` não é usado: quem diz quanto a casa tem é o histórico, e um
# número com duas origens é um número que um dia diverge.
_SQL_RESUMO = """
    WITH ultima AS (
        SELECT max(data) AS data FROM tb_patrimonio_snapshots
    ),
    linhas AS (
        SELECT a.nome, a.classe, a.ativo, s.valor
          FROM tb_ativos a
          LEFT JOIN tb_patrimonio_snapshots s
                 ON s.ativo_id = a.id
                AND s.data = (SELECT data FROM ultima)
         WHERE a.ativo OR s.valor IS NOT NULL
    )
    SELECT classe,
           COALESCE(SUM(valor), 0) AS valor,
           array_agg(nome ORDER BY nome)
               FILTER (WHERE valor IS NULL AND ativo) AS faltando,
           count(*) FILTER (WHERE valor IS NOT NULL AND NOT ativo) AS encerrados
      FROM linhas
     GROUP BY GROUPING SETS ((classe), ())
     ORDER BY classe NULLS LAST
"""


def grade_da_data(data_foto):
    return query_all(_SQL_GRADE, {"data": data_foto})


def historico():
    return query_all(_SQL_HISTORICO)


def resumo_da_ultima():
    """(linhas por classe, linha do total) da última foto."""
    linhas = query_all(_SQL_RESUMO)
    return ([l for l in linhas if l["classe"] is not None],
            next((l for l in linhas if l["classe"] is None), None))


# --------------------------------------------------------------------------
# 3. Leitura da grade (pura) e gravação
# --------------------------------------------------------------------------

def ler_valores(campos, ativos):
    """O corpo do POST -> (valores, erros, digitado). Pura.

    - `valores`: {ativo_id: Decimal} dos campos PREENCHIDOS;
    - `erros`: {ativo_id: mensagem} dos que não viraram número;
    - `digitado`: {ativo_id: texto} de tudo, para o campo voltar com o que a
      pessoa escreveu quando houver erro.

    Só os ativos da GRADE são lidos: um `valor_<id>` de ativo encerrado que
    chegue num corpo forjado não tem onde encaixar e é ignorado — é o que
    garante que a gravação não toca em linha de posição encerrada.

    Zero passa por `parece_zero` antes de `converter_valor`, que o recusaria:
    posição zerada é informação, e é diferente de campo vazio, que quer dizer
    "fora desta foto".
    """
    valores, erros, digitado = {}, {}, {}
    for ativo in ativos:
        bruto = (campos.get(f"{PREFIXO_CAMPO}{ativo['id']}") or "").strip()
        digitado[ativo["id"]] = bruto
        if not bruto:
            continue                      # vazio = fora da foto, nunca zero
        try:
            valores[ativo["id"]] = (ZERO if parece_zero(bruto)
                                    else converter_valor(bruto))
        except ValorInvalido as exc:
            erros[ativo["id"]] = str(exc)
    return valores, erros, digitado


# Upsert dos preenchidos. O `WHERE` do DO UPDATE é o que faz a linha idêntica
# não ser reescrita — e, por não ser reescrita, não voltar no RETURNING: é daí
# que sai o "regravei e nada mudou". `xmax = 0` é verdadeiro na linha que
# nasceu neste comando e falso na que foi atualizada.
_SQL_UPSERT = """
    WITH entrada AS (
        SELECT * FROM unnest(%(ids)s::int[], %(valores)s::numeric[])
          AS t(ativo_id, valor)
    ),
    gravado AS (
        INSERT INTO tb_patrimonio_snapshots (data, ativo_id, valor)
        SELECT %(data)s, ativo_id, valor FROM entrada
        ON CONFLICT (data, ativo_id) DO UPDATE
           SET valor = EXCLUDED.valor
         WHERE tb_patrimonio_snapshots.valor IS DISTINCT FROM EXCLUDED.valor
        RETURNING (xmax = 0) AS nasceu
    )
    SELECT count(*) FILTER (WHERE nasceu)     AS gravados,
           count(*) FILTER (WHERE NOT nasceu) AS atualizados
      FROM gravado
"""

# ...e o outro lado do contrato: campo vazio apaga a linha, se ela existia.
# `ativo_id = ANY(...)` limita o DELETE aos ativos DA GRADE — linha de ativo
# encerrado naquela data não é alcançada nem por engano.
_SQL_REMOVER = """
    DELETE FROM tb_patrimonio_snapshots
     WHERE data = %(data)s AND ativo_id = ANY(%(ids)s::int[])
    RETURNING id
"""


def gravar_foto(data_foto, valores, vazios):
    """Acerta a foto da data numa transação só. Devolve as três contagens.

    Ou os dois comandos valem, ou nenhum vale: uma foto meio gravada — com os
    novos dentro e os removidos ainda lá — seria um total errado na tela
    seguinte, e ninguém saberia.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(_SQL_UPSERT, {"data": data_foto,
                                  "ids": list(valores),
                                  "valores": list(valores.values())})
        contagens = cur.fetchone()
        cur.execute(_SQL_REMOVER, {"data": data_foto, "ids": list(vazios)})
        contagens["removidos"] = len(cur.fetchall())
    return contagens


def excluir_foto(data_foto):
    """Apaga a foto inteira de uma data. Devolve quantas linhas saíram.

    A foto é a unidade: apagar "uma linha da foto" é esvaziar o campo dela na
    grade, que é o caminho normal. Aqui a pessoa está dizendo que a data
    inteira não devia existir.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tb_patrimonio_snapshots WHERE data = %s"
                    " RETURNING id", (data_foto,))
        return len(cur.fetchall())



# --------------------------------------------------------------------------
# 4. Composição (pura)
# --------------------------------------------------------------------------

def _plural(quantidade, um, varios):
    return f"{quantidade} {um if quantidade == 1 else varios}"


def _com_sinal(texto, valor):
    """Põe o '+' na frente do texto de um número positivo.

    Recebe o texto JÁ FORMATADO, e não o número, porque serve a duas unidades
    nesta tela — reais e pontos percentuais — e o formatador de cada uma é
    outro. (A `_com_sinal` da Independência financeira é outra função: ela
    formata e assina, sempre em uma casa decimal. Se um terceiro caso
    aparecer, é hora de as duas virarem uma em `util.py`.)

    O '-' não é posto aqui: ele já vem de `formatar_numero`, e escrever o
    sinal negativo à mão criaria uma segunda grafia do menos.
    """
    return ("+" if valor > 0 else "") + texto


def _reais_com_sinal(valor):
    """'+R$ 1.234,56' / '-R$ 1.234,56'.

    O sinal vem NA FRENTE do R$, e não depois (como a macro `reais` faz para
    um valor negativo), porque esta coluna não é uma quantia: é uma variação,
    e o que se lê primeiro é se subiu ou desceu. Por isso o texto nasce
    inteiro aqui, e o template não chama a macro.
    """
    if valor < 0:
        return f"-R$ {formatar_valor(-valor)}"
    return f"+R$ {formatar_valor(valor)}"


def _texto_do_campo(linha, data_tem_foto):
    """O que vai dentro do `<input>` de uma linha da grade. Puro.

    Com foto na data, o valor GRAVADO — e vazio quando aquele ativo não está
    nela, porque vazio é o que quer dizer "fora da foto". Sem foto na data, o
    último valor conhecido entra como SUGESTÃO: quem tira a foto do mês
    costuma mexer em poucos ativos, e digitar tudo de novo seria o caminho
    mais longo para o mesmo número.
    """
    if data_tem_foto:
        valor = linha["valor_na_data"]
    else:
        valor = linha["ultimo_valor"]
    return "" if valor is None else formatar_valor(valor)


def montar_grade(linhas, data_foto, datas_com_foto, digitado=None, erros=None):
    """As linhas da grade, com texto e travessão prontos. Pura.

    `digitado` e `erros` só vêm preenchidos quando a gravação foi recusada: aí
    o campo volta com o que a pessoa escreveu, e não com o que está no banco —
    corrigir um valor exige vê-lo.
    """
    digitado = digitado or {}
    erros = erros or {}
    data_tem_foto = data_foto in datas_com_foto

    grade = []
    for linha in linhas:
        ultimo = linha["ultimo_valor"]
        grade.append({
            "id": linha["id"],
            "nome": linha["nome"],
            "classe": linha["classe"],
            "ultimo": (SEM_VALOR if ultimo is None
                       else f"R$ {formatar_valor(ultimo)}"),
            # A data do último valor acompanha o número: sem ela, "R$ 1.000"
            # pode ser do mês passado ou de dois anos atrás.
            "ultimo_data": (linha["ultima_data"].strftime("%d/%m/%Y")
                            if linha["ultima_data"] else None),
            "campo": digitado.get(linha["id"],
                                  _texto_do_campo(linha, data_tem_foto)),
            "erro": erros.get(linha["id"]),
        })
    return grade


def texto_do_aviso(data_foto, contagens):
    """'Foto de 31 de agosto de 2026: 1 gravado · 2 removidos'. Puro.

    Zeros são omitidos, e as contagens vêm do BANCO (do `RETURNING` do upsert
    e do `RETURNING` do DELETE), nunca do que a tela achava que ia acontecer:
    regravar sem mexer em nada não reescreve linha nenhuma, e o aviso tem de
    dizer isso.
    """
    partes = [
        _plural(n, um, varios)
        for n, um, varios in (
            (contagens["gravados"], "gravado", "gravados"),
            (contagens["atualizados"], "atualizado", "atualizados"),
            (contagens["removidos"], "removido", "removidos"),
        ) if n
    ]
    return (f"Foto de {data_por_extenso(data_foto)}: "
            + (" · ".join(partes) if partes else "nada mudou"))


def texto_da_exclusao(data_foto, quantas):
    """'Foto de 31 de agosto de 2026 excluída: 3 linhas.' Puro.

    A contagem vem do `RETURNING` do DELETE, como a da gravação: quem sabe
    quantas linhas saíram é o banco.
    """
    return (f"Foto de {data_por_extenso(data_foto)} excluída: "
            + _plural(quantas, "linha", "linhas") + ".")


def _nota_do_total(total_resumo):
    """A terceira linha do card do patrimônio, ou None. Pura.

    Duas coisas que o número não conta sozinho e quem olha precisa saber:
    quais ativos em carteira ficaram DE FORA da foto (o total é só o que foi
    lançado — ativo sem valor não carrega o valor antigo, por decisão do dono)
    e quantas posições ENCERRADAS ainda estão dentro dele.
    """
    if total_resumo is None:
        return None
    partes = []
    faltando = total_resumo["faltando"] or []
    if faltando:
        partes.append("Faltam na foto: " + ", ".join(faltando))
    encerrados = total_resumo["encerrados"]
    if encerrados:
        partes.append("inclui " + _plural(encerrados, "encerrado", "encerrados"))
    return " · ".join(partes) or None


def montar_cards(historico_linhas, total_resumo):
    """Os dois `.kpi`, pelo helper `card` da Visão Anual. Puro.

    Os dois falam da ÚLTIMA foto e saem da MESMA linha do histórico — a
    primeira. O Δ do card é o mesmo texto da coluna Δ da tabela de fotos, e
    não outro formatado igual: é a mesma string.
    """
    if not historico_linhas:
        return None

    ultima = historico_linhas[0]
    nota = _nota_do_total(total_resumo)

    delta = ultima["delta"]
    if delta is None:
        variacao = card("Variação vs foto anterior", texto=SEM_VALOR,
                        apoio="esta é a primeira foto do acervo")
    else:
        anterior = ultima["total"] - delta
        pct = fracao(delta, anterior)
        apoio = "vs " + data_por_extenso(historico_linhas[1]["data"])
        if pct is not None:
            apoio = (_com_sinal(formatar_numero(pct, 1) + "%", delta)
                     + " · " + apoio)
        variacao = card(
            "Variação vs foto anterior", texto=_reais_com_sinal(delta),
            classe="kpi__valor--negativo" if delta < 0 else None,
            apoio=apoio)

    return [
        card("Patrimônio na última foto", valor=ultima["total"],
             apoio=data_por_extenso(ultima["data"]),
             nota={"texto": nota, "classe": None} if nota else None),
        variacao,
    ]


def montar_alocacao(linhas_resumo, total):
    """Classe · Valor · % da última foto, com o rodapé. Pura.

    Só classe com valor **maior que zero**: uma classe inteira zerada não é
    alocação, é uma linha de 0,0 % ocupando espaço — e a posição zerada
    continua contada no total, que é o que importa.

    O denominador é o total da ÚLTIMA FOTO vindo do histórico, o mesmo do
    card: a soma das barras fecha em 100 % porque é a mesma conta.
    """
    if not total:
        return None
    classes = [
        {"classe": l["classe"], "valor": l["valor"],
         "pct": fracao(l["valor"], total) or ZERO}
        for l in linhas_resumo if l["valor"] > 0
    ]
    if not classes:
        return None
    return {"classes": classes, "total": total,
            "pct_total": fracao(total, total) or ZERO}


def montar_historico(linhas):
    """Uma linha por data, mais recente primeiro. Pura."""
    return [
        {
            "data": l["data"],
            "data_texto": l["data"].strftime("%d/%m/%Y"),
            "data_extenso": data_por_extenso(l["data"]),
            "ativos": l["ativos"],
            "total": l["total"],
            "delta": (SEM_VALOR if l["delta"] is None
                      else _reais_com_sinal(l["delta"])),
            # Travessão nunca é vermelho: a classe só entra quando há número.
            "delta_negativo": l["delta"] is not None and l["delta"] < 0,
        }
        for l in linhas
    ]


# --------------------------------------------------------------------------
# 5. A tela inteira
# --------------------------------------------------------------------------

def painel(data_foto, digitado=None, erros=None, aviso=None,
           erro_data=None):
    """Tudo o que a tela mostra. Três consultas, nenhuma a mais.

    `digitado`, `erros` e `aviso` vêm só do POST; num GET a grade sai do
    banco e não há nada a avisar. Não recebe `hoje`: quem precisa da data de
    hoje é a leitura da data pedida (`data_valida`, `erro_da_data`), e ela
    acontece na rota, antes daqui — a composição só monta o que vai à tela.
    """
    linhas_grade = grade_da_data(data_foto)
    historico_linhas = historico()
    resumo_linhas, total_resumo = resumo_da_ultima()

    datas = {l["data"] for l in historico_linhas}
    total = historico_linhas[0]["total"] if historico_linhas else None

    return {
        "data_foto": data_foto,
        "data_texto": data_foto.isoformat(),
        "data_extenso": data_por_extenso(data_foto),
        "erro_data": erro_data,
        "prefixo_campo": PREFIXO_CAMPO,
        "grade": montar_grade(linhas_grade, data_foto, datas, digitado, erros),
        "tem_ativos": bool(linhas_grade),
        "aviso": aviso,
        "cards": montar_cards(historico_linhas, total_resumo),
        "alocacao": montar_alocacao(resumo_linhas, total),
        "fotos": montar_historico(historico_linhas),
    }
