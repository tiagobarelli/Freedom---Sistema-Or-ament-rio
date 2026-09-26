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

**A alocação é por classe de alocação** desde a rodada 37: a foto vezes a
composição ATUAL de cada ativo, pelas classes do módulo de Alocação, com
"Não classificado" para o ativo sem composição. Quem faz a conta é
`alocacao/servico.valores_da_foto`, a mesma que dá o "Atual" do
balanceamento — os dois lugares mostram o mesmo número, e leem da mesma
origem. Até a 36 a classe era um texto livre do ativo.

Cinco consultas por carregamento, e são estas: a base do IPCA, a grade da
data, o histórico com `LAG` (cuja primeira linha É a última foto, e é a origem
única do total), o que faltou e o que veio de encerrado na última foto, e a
alocação dela por classe.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from freedom import ipca
from freedom.alocacao.servico import valores_da_foto
from freedom.db import (get_connection, query_all,
                        query_one)
from freedom.main.servico import SEM_VALOR, card
from freedom.util import (MESES_CURTOS, ValorInvalido, chave_alfabetica,
                          com_sinal, converter_valor, data_de_texto,
                          data_por_extenso, formatar_numero, formatar_valor,
                          fracao, nome_do_periodo, parece_zero,
                          reais_com_sinal, somar_meses)

ZERO = Decimal("0.00")
CENTAVO = Decimal("0.01")
CEM = Decimal(100)

# Prefixo dos campos da grade no corpo do POST: um por ativo, `valor_<id>`.
# Fica aqui, e não espalhado entre a rota e o template, porque é contrato
# entre os dois.
PREFIXO_CAMPO = "valor_"

# A linha da alocação para o ativo sem composição. Mesmo texto do bloco do
# balanceamento da Alocação.
NAO_CLASSIFICADO = "Não classificado"


# --------------------------------------------------------------------------
# 1. A data da foto (puras)
# --------------------------------------------------------------------------

def fim_do_mes(dia):
    """O último dia do mês em que `dia` cai. 15/02/2024 -> 29/02/2024. Pura.

    Uma definição só de "fim do mês" no serviço: dela saem a data padrão da
    tela e os dois saltos das setas, e por isso fevereiro e ano bissexto
    acertam nos três sem ninguém escrever 28, 29, 30 ou 31 em lugar nenhum.
    """
    return somar_meses(date(dia.year, dia.month, 1), 1) - timedelta(days=1)


def data_padrao(hoje):
    """Último dia do mês anterior a `hoje`. `date(2026,9,20)` -> 31/08/2026.

    É a data em que faz sentido tirar a foto: o mês fechou e os extratos
    saíram. `hoje` entra por parâmetro, como em toda função de data deste
    projeto — o relógio não é lido aqui dentro.
    """
    return fim_do_mes(somar_meses(date(hoje.year, hoje.month, 1), -1))


def salto_de_mes(data_foto, passos, hoje):
    """A data que a seta de mês abre, ou None quando ela não deve existir.

    Sempre o FIM do mês vizinho, e não "o mesmo dia do mês vizinho": a foto é
    mensal, e é o fim do mês que interessa. Isto também é o que desarma a
    armadilha do `<input type="date">`: mudar o mês de 31/01 para 02 pela mão
    põe o campo em 31/02, que não existe — o Chrome zera o controle, o
    formulário passa a falhar na validação do HTML e os DOIS botões da tela
    param de responder, sem dizer nada (o "Gravar foto" inclusive, porque o
    HTMX valida o que o `hx-include` traz). Pela seta, a data impossível nunca
    chega a existir.

    `None` para frente quando o mês que viria ainda não acabou: `data_valida`
    recusa data futura e cairia no padrão, e uma seta que parece não fazer
    nada é o defeito que esta mudança veio consertar. Para trás não há limite
    — o acervo pode crescer para os anos que o dono quiser.
    """
    alvo = fim_do_mes(somar_meses(date(data_foto.year, data_foto.month, 1),
                                  passos))
    return None if alvo > hoje else alvo


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
    SELECT a.id, a.nome,
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
     ORDER BY a.nome
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
# A correção é por LINHA, no mês da FOTO, e a soma vem depois — o mesmo padrão
# das Análises, com uma diferença de significado: lá se deflaciona uma despesa
# no mês em que ela aconteceu; aqui, um saldo na data em que ele foi medido.
# `integra_ipca` não entra nesta conta: aquela marca é de despesa, e patrimônio
# não tem despesa dentro.
#
# O LEFT JOIN é 1 para 1 (`tb_ipca.mes` é UNIQUE), então nem `count(*)` nem
# `SUM(valor)` mudam por causa dele. O COALESCE no denominador resolve a foto
# posterior à base: fator base/base = 1, porque corrigir para um mês que o
# IBGE ainda não publicou seria inventar inflação.
_CORRIGIDO = ("SUM(s.valor * %(base)s"
              " / COALESCE(i.numero_indice, %(base)s))")
# Sem IPCA carregado não há a que corrigir. A coluna existe para a composição
# não ter dois caminhos, e vale o nominal — a caixa da tela vem desabilitada.
_SEM_CORRECAO = "SUM(s.valor)"

_SQL_HISTORICO = """
    SELECT s.data,
           count(*)     AS ativos,
           SUM(s.valor) AS total,
           SUM(s.valor) - LAG(SUM(s.valor)) OVER (ORDER BY s.data) AS delta,
           {corrigido}  AS corrigido
      FROM tb_patrimonio_snapshots s
      LEFT JOIN tb_ipca i ON i.mes = date_trunc('month', s.data)::date
     GROUP BY s.data
     ORDER BY s.data DESC
"""

# O que a tela precisa dizer sobre a última foto além do total: quais ativos
# em carteira ficaram DE FORA dela e quantas posições ENCERRADAS ainda estão
# dentro.
#
# O conjunto de linhas é "ativo em carteira (tenha ou não valor na última
# foto) OU linha da última foto de ativo encerrado" — é o `WHERE` do CTE.
# Até a rodada 36 esta mesma varredura dava também a alocação por classe, por
# `GROUPING SETS`; a classe virou composição na 37, e a alocação saiu para
# `alocacao/servico.valores_da_foto`, que é a origem que o balanceamento lê.
_SQL_RESUMO = """
    WITH ultima AS (
        SELECT max(data) AS data FROM tb_patrimonio_snapshots
    ),
    linhas AS (
        SELECT a.nome, a.ativo, s.valor
          FROM tb_ativos a
          LEFT JOIN tb_patrimonio_snapshots s
                 ON s.ativo_id = a.id
                AND s.data = (SELECT data FROM ultima)
         WHERE a.ativo OR s.valor IS NOT NULL
    )
    SELECT array_agg(nome ORDER BY nome)
               FILTER (WHERE valor IS NULL AND ativo) AS faltando,
           count(*) FILTER (WHERE valor IS NOT NULL AND NOT ativo) AS encerrados
      FROM linhas
"""


def grade_da_data(data_foto):
    return query_all(_SQL_GRADE, {"data": data_foto})


def historico(base):
    """Uma linha por foto, com o total nominal e o corrigido.

    As DUAS somas saem sempre, com a caixa ligada ou desligada: a caixa liga a
    exibição da segunda linha do gráfico e da coluna da tabela, não um segundo
    caminho de código — é a mesma decisão da correção pelo IPCA das Análises.
    """
    sql = _SQL_HISTORICO.format(
        corrigido=_CORRIGIDO if base is not None else _SEM_CORRECAO)
    return query_all(sql, {"base": base})


# A última foto em três números, numa consulta só: a data, o total de TODAS as
# linhas dela e quantos ativos em carteira ficaram de fora.
#
# Existe para a Independência financeira (rodada 31), que precisa do ponto de
# partida e não do resto da tela: importar esta função é mais honesto do que
# reproduzir lá o `max(data)` e a soma. A tela de Patrimônio continua lendo o
# total da PRIMEIRA linha do histórico, que é a origem do card e do Δ dela —
# os dois números são o mesmo por construção, e a validação confere.
#
# `max(data)` sobre tabela vazia é NULL: as duas subconsultas comparam com
# NULL, não casam nada, e a função devolve None em vez de uma foto de zero.
_SQL_ULTIMA_FOTO = """
    WITH ultima AS (
        SELECT max(data) AS data FROM tb_patrimonio_snapshots
    )
    SELECT u.data,
           COALESCE((SELECT SUM(s.valor)
                       FROM tb_patrimonio_snapshots s
                      WHERE s.data = u.data), 0) AS total,
           (SELECT count(*)
              FROM tb_ativos a
             WHERE a.ativo
               AND NOT EXISTS (SELECT 1
                                 FROM tb_patrimonio_snapshots s
                                WHERE s.ativo_id = a.id
                                  AND s.data = u.data)) AS faltando
      FROM ultima u
"""


def ultima_foto():
    """(data, total, faltando) da última foto, ou None se não há foto nenhuma.

    `total` soma TODAS as linhas da data, encerrados inclusive — é a
    definição do `.md` do banco para patrimônio, e a decisão do dono para a
    independência: todo ativo lançado rende.
    """
    linha = query_one(_SQL_ULTIMA_FOTO)
    return linha if linha and linha["data"] is not None else None


def resumo_da_ultima():
    """{faltando, encerrados} da última foto: a nota do card do total."""
    return query_one(_SQL_RESUMO)


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

def _centavos(valor):
    """Corta a centavos, ROUND_HALF_UP, e só aqui.

    Os valores gravados já são `NUMERIC(14,2)` e não precisam disto; quem
    precisa é o TOTAL CORRIGIDO, que sai de uma divisão por número-índice em
    SQL e volta com a precisão do NUMERIC. O corte é a última coisa que
    acontece, como nas Análises.
    """
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _plural(quantidade, um, varios):
    return f"{quantidade} {um if quantidade == 1 else varios}"


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
            apoio = (com_sinal(formatar_numero(pct, 1) + "%", delta)
                     + " · " + apoio)
        variacao = card(
            "Variação vs foto anterior", texto=reais_com_sinal(delta),
            classe="kpi__valor--negativo" if delta < 0 else None,
            apoio=apoio)

    return [
        card("Patrimônio na última foto", valor=ultima["total"],
             apoio=data_por_extenso(ultima["data"]),
             nota={"texto": nota, "classe": None} if nota else None),
        variacao,
    ]


def montar_alocacao(foto, total):
    """Classe · Valor · % da última foto, com o rodapé. Pura.

    As classes são as do módulo de Alocação: a foto vezes a composição atual
    de cada ativo (`alocacao/servico.valores_da_foto`). O ativo sem
    composição entra inteiro numa linha própria, "Não classificado", no fim
    — ele está no patrimônio, e sumir com ele faria as barras não fecharem.

    Só linha com valor **maior que zero**: uma classe inteira zerada não é
    alocação, é uma linha de 0,0 % ocupando espaço — e a posição zerada
    continua contada no total, que é o que importa.

    O denominador é o total da ÚLTIMA FOTO vindo do histórico, o mesmo do
    card: a soma das barras fecha em 100 % porque as composições fecham em
    100 %. O valor de uma classe tem até oito casas (valor × fração), e o
    corte a centavos é aqui, no ponto exibido.
    """
    if not total or foto is None:
        return None
    nomes = foto["nomes_classes"]
    linhas = sorted(
        ((nomes[cid], valor) for cid, valor in foto["classes"].items()),
        key=lambda par: chave_alfabetica(par[0]))
    linhas.append((NAO_CLASSIFICADO, foto["total_nao_classificado"]))
    classes = [
        {"classe": nome, "valor": _centavos(valor),
         "pct": fracao(valor, total) or ZERO}
        for nome, valor in linhas if valor > 0
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
            "corrigido": _centavos(l["corrigido"]),
            "delta": (SEM_VALOR if l["delta"] is None
                      else reais_com_sinal(l["delta"])),
            # Travessão nunca é vermelho: a classe só entra quando há número.
            "delta_negativo": l["delta"] is not None and l["delta"] < 0,
        }
        for l in linhas
    ]


# --------------------------------------------------------------------------
# 5. O que vai para o gráfico
# --------------------------------------------------------------------------

# Com uma foto só não há evolução a desenhar: um ponto solto não é uma linha, e
# o histórico logo abaixo já mostra o número.
MINIMO_GRAFICO = 2


def para_grafico(fotos, corrigir, base_mes):
    """As duas séries da evolução, ou None. Pura.

    É o ÚNICO lugar desta tela em que `Decimal` vira `float`, e só depois do
    corte a centavos: o JavaScript recebe número pronto e não faz conta.

    As duas séries vão SEMPRE, com a caixa ligada ou desligada — `corrigir`
    diz só qual delas se desenha. É o que permite ligar e desligar sem uma
    segunda ida ao servidor... e é também o que obriga o script a respeitar a
    marca ao redesenhar depois de um swap.

    A ordem aqui é CRESCENTE, ao contrário da tabela: uma série no tempo se lê
    da esquerda para a direita, e a tabela, de cima para baixo.
    """
    if len(fotos) < MINIMO_GRAFICO:
        return None

    crescente = list(reversed(fotos))
    return {
        "rotulos": [f["data_texto"] for f in crescente],
        "series": [
            {"rotulo": "Nominal",
             "valores": [float(f["total"]) for f in crescente]},
            {"rotulo": rotulo_corrigido(base_mes),
             "valores": [float(f["corrigido"]) for f in crescente]},
        ],
        "corrigir": corrigir,
    }


# --------------------------------------------------------------------------
# 5b. A tendencia (pura)
# --------------------------------------------------------------------------

# Cinco anos de projecao, em meses.
MESES_PROJETADOS = 60

# Abaixo disto uma curva ajustada nao diz nada: com tres pontos o ajuste passa
# quase exatamente por eles e o R² sai perto de 1 sem significar coisa
# alguma. Meio ano de fotos é o mínimo para a palavra "tendência" valer.
MINIMO_TENDENCIA = 6


def _meses_entre(inicio, fim):
    """Quantos meses separam dois dias-1. Pura."""
    return (fim.year - inicio.year) * 12 + (fim.month - inicio.month)


def ajuste_exponencial(pontos):
    """Mínimos quadrados de `ln(y) = ln(a) + b·x`, ou None. Pura.

    É exatamente o que a "linha de tendência exponencial" do Excel faz: em vez
    de ajustar a exponencial diretamente, ela lineariza tomando o logaritmo e
    ajusta uma reta.

    O **R², porém, o Excel NÃO calcula na escala do logaritmo** — ele mostra o
    quadrado da correlação entre o valor observado e o ajustado, de volta na
    escala original. A diferença não é pequena: na série do dono, a mesma
    curva dá 0,833 pela primeira definição e 0,956 pela segunda, e é a
    segunda que aparece na planilha dele (0,954 até julho/2026, conferido
    linha a linha). Como o objetivo declarado era espelhar a planilha, é a do
    Excel que vale aqui.

    Tudo em `Decimal`, como o resto do sistema: `Decimal` tem `ln` e `exp`, e
    foi assim que a rodada 29 fez o modelo da independência.

    Devolve `(ln_a, b, r2)` — o logaritmo do coeficiente, e não ele próprio,
    porque quem usa precisa de `exp(ln_a + b·x)` e passar pelo `a` no meio só
    perderia precisão.

    `None` quando não há como ajustar: menos de dois `x` distintos (a reta
    seria vertical). Valor zero ou negativo não chega aqui — quem os filtra é
    `montar_tendencia`, porque `ln` não os aceita e uma posição zerada é
    informação legítima na foto.
    """
    xs = [Decimal(x) for x, _ in pontos]
    ls = [valor.ln() for _, valor in pontos]
    n = Decimal(len(pontos))

    soma_x, soma_l = sum(xs), sum(ls)
    denominador = n * sum(x * x for x in xs) - soma_x * soma_x
    if denominador == 0:
        return None

    b = (n * sum(x * l for x, l in zip(xs, ls)) - soma_x * soma_l) / denominador
    ln_a = (soma_l - b * soma_x) / n

    # R² à moda do Excel: quadrado da correlação entre observado e ajustado.
    # `corr² = cov² / (var_obs · var_aj)` evita a raiz quadrada que a
    # correlação pediria, e com ela um arredondamento a mais.
    ys = [valor for _, valor in pontos]
    ajustados = [(ln_a + b * x).exp() for x in xs]
    media_y, media_a = sum(ys) / n, sum(ajustados) / n
    var_y = sum((y - media_y) ** 2 for y in ys)
    var_a = sum((a - media_a) ** 2 for a in ajustados)
    if var_y == 0 or var_a == 0:
        # Série constante: não há variação a explicar, e nem a explicar com.
        return ln_a, b, Decimal(1)
    covariancia = sum((y - media_y) * (a - media_a)
                      for y, a in zip(ys, ajustados))
    return ln_a, b, covariancia * covariancia / (var_y * var_a)


def montar_tendencia(fotos, corrigir, base_mes, rotulo_serie):
    """A série observada, a curva ajustada e cinco anos de projeção. Pura.

    O eixo é uma grade MENSAL contínua, do primeiro mês com foto até cinco
    anos depois do último — e não uma marca por foto, como no gráfico de cima.
    A diferença importa: se faltar um mês, a marca dele continua no eixo e a
    curva ajustada não ganha um degrau falso. A série observada leva `None`
    nos meses sem foto e nos sessenta do futuro; ali `None` quer dizer mesmo
    "não há medida", que é coisa diferente do zero da foto.

    Ajusta sobre a série que a caixa do IPCA escolheu: com ela ligada, a
    projeção sai em poder de compra do mês base, que é o que se compara com o
    número de independência.
    """
    if len(fotos) < MINIMO_TENDENCIA:
        return None

    crescente = list(reversed(fotos))
    chave = "corrigido" if corrigir else "total"
    # `ln` não aceita zero nem negativo. Uma foto inteira zerada é possível
    # (todas as posições zeradas) e não pode derrubar a tela: ela sai do
    # ajuste e a nota de rodapé conta quantas saíram.
    usaveis = [f for f in crescente if f[chave] > 0]
    if len(usaveis) < MINIMO_TENDENCIA:
        return None

    primeiro = date(crescente[0]["data"].year, crescente[0]["data"].month, 1)
    ajuste = ajuste_exponencial(
        [(_meses_entre(primeiro, f["data"]), f[chave]) for f in usaveis])
    if ajuste is None:
        return None
    ln_a, b, r2 = ajuste

    ultimo = crescente[-1]["data"]
    total_meses = _meses_entre(primeiro, ultimo) + MESES_PROJETADOS
    por_mes = {_meses_entre(primeiro, f["data"]): f[chave] for f in crescente}

    rotulos, serie, tendencia = [], [], []
    for x in range(total_meses + 1):
        mes = somar_meses(primeiro, x)
        rotulos.append(f"{MESES_CURTOS[mes.month - 1].lower()}/{mes.year % 100:02d}")
        valor = por_mes.get(x)
        serie.append(float(_centavos(valor)) if valor is not None else None)
        tendencia.append(float(_centavos((ln_a + b * Decimal(x)).exp())))

    # Crescimento ANUAL, que é como se fala de patrimônio; `b` é o logaritmo
    # do crescimento mensal.
    ao_ano = (b * 12).exp() - 1

    return {
        "rotulos": rotulos,
        "serie": {"rotulo": rotulo_serie, "valores": serie},
        "tendencia": {"rotulo": "Tendência", "valores": tendencia},
        "primeiro_projetado": _meses_entre(primeiro, ultimo) + 1,
        "anos": MESES_PROJETADOS // 12,
        # O subtítulo inteiro, pronto: a que preços, a que ritmo, com que
        # aderência e onde a curva chega. Quatro fatos, uma linha.
        "subtitulo": " · ".join(
            ([f"a preços de {nome_do_periodo(base_mes)}"] if corrigir else [])
            + [f"{formatar_numero(ao_ano * CEM, 1)}% ao ano",
               f"R² {formatar_numero(r2, 3)}",
               f"R$ {formatar_valor(_centavos((ln_a + b * Decimal(total_meses)).exp()))}"
               f" em {nome_do_periodo(somar_meses(primeiro, total_meses))}"]),
        "fora": len(crescente) - len(usaveis),
    }


def _nota_fotos_fora(tendencia):
    """"1 foto com total zero ficou de fora do ajuste", ou None. Pura.

    `ln` não aceita zero, e uma foto inteiramente zerada é entrada legítima —
    dizer quantas saíram é mais honesto do que ajustar sobre um conjunto que
    não é o que a tabela mostra.
    """
    if not tendencia or not tendencia["fora"]:
        return None
    n = tendencia["fora"]
    return (f"{n} foto com total zero ficou" if n == 1
            else f"{n} fotos com total zero ficaram") + " de fora do ajuste."


def rotulo_corrigido(base_mes):
    """'A preços de agosto de 2026', ou None sem IPCA carregado."""
    return (f"A preços de {nome_do_periodo(base_mes)}"
            if base_mes is not None else None)


# --------------------------------------------------------------------------
# 6. A tela inteira
# --------------------------------------------------------------------------

def painel(data_foto, hoje, corrigir=False, digitado=None, erros=None,
           aviso=None, erro_data=None):
    """Tudo o que a tela mostra. Cinco consultas, nenhuma a mais.

    `digitado`, `erros` e `aviso` vêm só do POST; num GET a grade sai do
    banco e não há nada a avisar. `hoje` entra por parâmetro, como em toda
    função de data daqui: é ele que decide se a seta do mês seguinte existe.

    `corrigir` já chega decidido pela rota: é a caixa marcada E haver IPCA
    carregado. Sem base não há o que corrigir, e a caixa vem desabilitada.
    """
    base = ipca.base_de_correcao()
    numero_base = base["numero_indice"] if base else None
    base_mes = base["mes"] if base else None

    linhas_grade = grade_da_data(data_foto)
    historico_linhas = historico(numero_base)
    total_resumo = resumo_da_ultima()

    datas = {l["data"] for l in historico_linhas}
    total = historico_linhas[0]["total"] if historico_linhas else None
    fotos = montar_historico(historico_linhas)

    return {
        "data_foto": data_foto,
        "data_texto": data_foto.isoformat(),
        "data_extenso": data_por_extenso(data_foto),
        # As duas setas, já resolvidas: `None` na da frente quer dizer "não
        # há mês seguinte fechado", e o template a desenha fora de uso.
        "mes_anterior": salto_de_mes(data_foto, -1, hoje),
        "mes_seguinte": salto_de_mes(data_foto, 1, hoje),
        "erro_data": erro_data,
        "prefixo_campo": PREFIXO_CAMPO,
        "grade": montar_grade(linhas_grade, data_foto, datas, digitado, erros),
        "tem_ativos": bool(linhas_grade),
        "aviso": aviso,
        "cards": montar_cards(historico_linhas, total_resumo),
        "alocacao": montar_alocacao(valores_da_foto(), total),
        "fotos": fotos,
        # A caixa só liga de fato com IPCA carregado; sem ele o template a
        # desabilita e diz onde carregar.
        "corrigir": corrigir,
        "tem_ipca": base is not None,
        "rotulo_corrigido": rotulo_corrigido(base_mes),
        # O mesmo fato em duas vozes: rótulo de série e de coluna abre com
        # maiúscula, subtítulo de cartão entra em minúscula porque vem logo
        # abaixo do título. Quem decide é aqui, não um filtro no Jinja.
        "subtitulo_grafico": (f"a preços de {nome_do_periodo(base_mes)}"
                              if corrigir and base_mes else None),
        "nota_corrigido": (
            f"Corrigido a preços de {nome_do_periodo(base_mes)}; fotos "
            "posteriores a esse mês usam fator 1." if base_mes else None),
        "grafico": para_grafico(fotos, corrigir, base_mes),
        "tendencia": montar_tendencia(
            fotos, corrigir, base_mes,
            rotulo_corrigido(base_mes) if corrigir else "Nominal"),
        "nota_tendencia": (
            "A curva pontilhada é o ajuste exponencial dos pontos observados, "
            f"estendido por {MESES_PROJETADOS // 12} anos: é o que aconteceria "
            "se o ritmo do passado se repetisse, e não uma previsão. Ela não "
            "sabe de aporte, de meta nem de mercado. O R² é o mesmo que o "
            "Excel mostra na linha de tendência exponencial: o quadrado da "
            "correlação entre o valor observado e o ajustado."),
        "nota_fotos_fora": _nota_fotos_fora(
            montar_tendencia(fotos, corrigir, base_mes, "")),
    }
