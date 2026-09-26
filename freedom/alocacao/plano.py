"""O modo Plano da Alocação: os alvos de cada classe e subclasse, por vigência.

Um **plano** é uma data (`tb_alocacao_planos.vigente_desde`, a chave) e duas
listas de alvo: o de cada classe sobre o total e o de cada subclasse sobre a
classe dela. O plano vigente numa data é o de maior `vigente_desde` menor ou
igual a ela — a regra de `tb_configuracoes`. Plano é entrada do usuário: edita
e se exclui, como configuração e orçamento.

**A grade é o editor**, no contrato da foto de patrimônio: um POST só faz
upsert do que foi preenchido e DELETE do que foi esvaziado, numa transação.
Vazio quer dizer "fora do plano"; **zero é alvo legítimo** ("está no plano e
não deve ter nada"), como no orçamento.

**Nada é gravado se a grade não fecha.** As somas de 100 % são regra da
aplicação (o banco só garante a faixa de cada número), e a validação roda
inteira antes da primeira escrita. Quatro recusas, cada uma com o texto no
bloco que falhou: as classes preenchidas não somam 100 %; as subclasses
preenchidas de uma classe preenchida não somam 100 % (inclusive quando não há
nenhuma, por decisão do dono: a classe no plano precisa da divisão interna);
há subclasse preenchida com a classe dela vazia; a grade inteira está vazia —
o "Salvar" não apaga um plano, quem apaga é "Excluir plano".

**Referência inativa segue a regra do sistema**: aparece marcada se já está
no plano, e nunca entra em linha nova. A grade só lê os campos das linhas que
ela mesma desenhou, então um campo de classe inativa forjado no corpo do POST
não tem onde encaixar e é ignorado.
"""

from datetime import date
from decimal import Decimal

from freedom.alocacao.servico import (PREFIXO_APORTE, PREFIXO_CLASSE,
                                      PREFIXO_SUBCLASSE, ler_percentual,
                                      referencias, rotulo_de_referencia,
                                      soma_de_cem, texto_percentual)
from freedom.configuracoes.servico import PERCENTUAL, texto_para_edicao
from freedom.db import get_connection, query_all
from freedom.util import ValorInvalido, data_por_extenso

# --------------------------------------------------------------------------
# 1. Consultas
# --------------------------------------------------------------------------

_SQL_VIGENCIAS = """
    SELECT vigente_desde FROM tb_alocacao_planos ORDER BY vigente_desde DESC
"""

# As duas listas do plano numa consulta: o nível diz de qual tabela veio a
# linha. `recebe_aporte` só existe na subclasse.
_SQL_LINHAS = """
    SELECT 'classe' AS nivel, classe_id AS id, percentual,
           NULL::boolean AS recebe_aporte
      FROM tb_alocacao_alvos_classes
     WHERE vigente_desde = %(data)s
    UNION ALL
    SELECT 'subclasse', subclasse_id, percentual, recebe_aporte
      FROM tb_alocacao_alvos_subclasses
     WHERE vigente_desde = %(data)s
"""


def vigencias():
    """As datas de todos os planos, da mais nova para a mais velha."""
    return [l["vigente_desde"] for l in query_all(_SQL_VIGENCIAS)]


def vigente_em(datas, dia):
    """A data do plano que vale em `dia`, ou None. Pura.

    O de maior `vigente_desde <= dia`: a regra de vigência de Parâmetros. As
    datas chegam em qualquer ordem; a resposta não depende dela.
    """
    anteriores = [d for d in datas if d <= dia]
    return max(anteriores) if anteriores else None


def linhas_do_plano(data):
    """{"classes": {id: fração}, "subclasses": {id: {percentual, recebe_aporte}}}."""
    classes, subclasses = {}, {}
    for l in query_all(_SQL_LINHAS, {"data": data}):
        if l["nivel"] == "classe":
            classes[l["id"]] = l["percentual"]
        else:
            subclasses[l["id"]] = {"percentual": l["percentual"],
                                   "recebe_aporte": l["recebe_aporte"]}
    return {"classes": classes, "subclasses": subclasses}


# --------------------------------------------------------------------------
# 2. As linhas da grade (puras)
# --------------------------------------------------------------------------

def blocos_da_grade(arvore, linhas):
    """Que classes e subclasses a grade desenha, na ordem pt-BR. Pura.

    A regra da referência inativa: aparece se já está no plano; se não está,
    fica de fora — e, fora da grade, não recebe linha nova nem por um POST
    forjado, porque a leitura só olha o que está aqui.

    Uma classe aparece se está ativa, se está no plano ou se alguma subclasse
    dela está (o último caso a validação não deixa gravar, mas uma linha
    antiga no banco não pode sumir da tela). Uma subclasse aparece se está no
    plano, ou se está ativa sob uma classe que aparece.
    """
    blocos = []
    for classe in arvore:
        no_plano = classe["id"] in linhas["classes"]
        subs_no_plano = [s for s in classe["subclasses"]
                         if s["id"] in linhas["subclasses"]]
        if not (classe["ativo"] or no_plano or subs_no_plano):
            continue
        blocos.append({
            "classe": classe,
            "subclasses": [s for s in classe["subclasses"]
                           if s["id"] in linhas["subclasses"] or s["ativo"]],
        })
    return blocos


def ler_grade(campos, blocos):
    """O corpo do POST -> (valores, erros de campo, digitado). Pura.

    - `valores`: {"classes": {id: fração}, "subclasses": {id: (fração,
      recebe)}} só dos campos PREENCHIDOS e legíveis;
    - `erros`: {("classe"|"subclasse", id): mensagem};
    - `digitado`: o texto de cada campo e o estado de cada caixa, para a
      grade voltar com o que a pessoa escreveu quando for recusada.

    A caixa "Recebe aporte" desmarcada não manda nada no formulário — é o
    HTML —, e por isso ausência quer dizer "não recebe".
    """
    valores = {"classes": {}, "subclasses": {}}
    erros = {}
    digitado = {"classes": {}, "subclasses": {}, "aporte": {}}

    for bloco in blocos:
        cid = bloco["classe"]["id"]
        texto = (campos.get(f"{PREFIXO_CLASSE}{cid}") or "").strip()
        digitado["classes"][cid] = texto
        try:
            valor = ler_percentual(texto)
        except ValorInvalido as exc:
            erros[("classe", cid)] = str(exc)
        else:
            if valor is not None:
                valores["classes"][cid] = valor

        for sub in bloco["subclasses"]:
            sid = sub["id"]
            texto = (campos.get(f"{PREFIXO_SUBCLASSE}{sid}") or "").strip()
            recebe = campos.get(f"{PREFIXO_APORTE}{sid}") == "1"
            digitado["subclasses"][sid] = texto
            digitado["aporte"][sid] = recebe
            try:
                valor = ler_percentual(texto)
            except ValorInvalido as exc:
                erros[("subclasse", sid)] = str(exc)
            else:
                if valor is not None:
                    valores["subclasses"][sid] = (valor, recebe)
    return valores, erros, digitado


def _texto_soma(fracoes):
    return texto_percentual(sum(fracoes, Decimal(0)))


def validar(valores, blocos):
    """As recusas de soma, ou {} se a grade fecha. Pura.

    Só roda quando todo campo foi lido — com um campo ilegível no meio, a
    soma diria um número que ninguém digitou. Devolve:

    - "geral": a grade inteira está vazia;
    - "classes": as classes preenchidas não somam 100 %;
    - "blocos": {classe_id: mensagem} — a soma das subclasses de uma classe
      preenchida, ou subclasse preenchida sob classe vazia.
    """
    classes, subclasses = valores["classes"], valores["subclasses"]
    if not classes and not subclasses:
        return {"geral": "A grade está vazia. Salvar não apaga um plano: "
                         "para isso, use Excluir plano."}

    recusas = {"blocos": {}}
    # Sem classe nenhuma preenchida a soma é zero, e a recusa vale do mesmo
    # jeito: há subclasse preenchida (senão a grade estaria vazia), e ela
    # também leva a recusa do bloco dela.
    if not soma_de_cem(classes.values()):
        recusas["classes"] = (f"As classes somam {_texto_soma(classes.values())};"
                              " precisam somar 100%.")

    for bloco in blocos:
        classe = bloco["classe"]
        preenchidas = [subclasses[s["id"]][0] for s in bloco["subclasses"]
                       if s["id"] in subclasses]
        if classe["id"] in classes:
            if not soma_de_cem(preenchidas):
                recusas["blocos"][classe["id"]] = (
                    f"As subclasses de {classe['nome']} somam "
                    f"{_texto_soma(preenchidas)}; precisam somar 100%.")
        elif preenchidas:
            recusas["blocos"][classe["id"]] = (
                f"{classe['nome']} está vazia, mas tem subclasse preenchida. "
                "Preencha o alvo da classe ou esvazie as subclasses.")

    if not recusas["blocos"]:
        del recusas["blocos"]
    return recusas


def montar_grade(blocos, linhas, digitado=None, erros=None, recusas=None):
    """As linhas da grade, com o texto de cada campo pronto. Pura.

    Num GET o campo mostra o que está gravado, na unidade em que se digita
    (`37`, e não `0,37` — senão salvar sem mexer dividiria por 100 de novo,
    a armadilha que Parâmetros já resolveu com `texto_para_edicao`). Depois
    de uma recusa, mostra o que foi digitado.

    Subclasse fora do plano nasce com "Recebe aporte" marcada: é o padrão da
    coluna no banco, e o caso comum.
    """
    erros = erros or {}
    recusas = recusas or {}
    erros_bloco = recusas.get("blocos", {})

    def texto(fracao):
        return "" if fracao is None else texto_para_edicao(fracao, PERCENTUAL)

    montados = []
    for bloco in blocos:
        classe = bloco["classe"]
        cid = classe["id"]
        campo = (digitado["classes"][cid] if digitado
                 else texto(linhas["classes"].get(cid)))
        subs = []
        for sub in bloco["subclasses"]:
            sid = sub["id"]
            gravada = linhas["subclasses"].get(sid)
            if digitado:
                campo_sub = digitado["subclasses"][sid]
                recebe = digitado["aporte"][sid]
            else:
                campo_sub = texto(gravada["percentual"] if gravada else None)
                recebe = gravada["recebe_aporte"] if gravada else True
            subs.append({
                "id": sid,
                "rotulo": rotulo_de_referencia(sub["nome"], sub["ativo"]),
                "campo": campo_sub,
                "recebe": recebe,
                "erro": erros.get(("subclasse", sid)),
            })
        montados.append({
            "id": cid,
            "rotulo": rotulo_de_referencia(classe["nome"], classe["ativo"]),
            "campo": campo,
            "erro": erros.get(("classe", cid)),
            "subclasses": subs,
            "erro_bloco": erros_bloco.get(cid),
        })
    return montados


# --------------------------------------------------------------------------
# 3. Escritas
# --------------------------------------------------------------------------

class PlanoInexistente(Exception):
    """A data do caminho não é plano nenhum."""


# Upsert das linhas preenchidas. O `WHERE` do DO UPDATE é o que faz a linha
# idêntica não ser reescrita e, por isso, não voltar no RETURNING: é daí que
# sai o "nada mudou" do aviso — o mesmo desenho do upsert da foto.
_SQL_UPSERT_CLASSES = """
    WITH entrada AS (
        SELECT * FROM unnest(%(ids)s::int[], %(pcts)s::numeric[])
          AS t(classe_id, percentual)
    ),
    gravado AS (
        INSERT INTO tb_alocacao_alvos_classes
               (vigente_desde, classe_id, percentual)
        SELECT %(data)s, classe_id, percentual FROM entrada
        ON CONFLICT (vigente_desde, classe_id) DO UPDATE
           SET percentual = EXCLUDED.percentual
         WHERE tb_alocacao_alvos_classes.percentual
               IS DISTINCT FROM EXCLUDED.percentual
        RETURNING (xmax = 0) AS nasceu
    )
    SELECT count(*) FILTER (WHERE nasceu)     AS gravados,
           count(*) FILTER (WHERE NOT nasceu) AS atualizados
      FROM gravado
"""

_SQL_UPSERT_SUBCLASSES = """
    WITH entrada AS (
        SELECT * FROM unnest(%(ids)s::int[], %(pcts)s::numeric[],
                             %(recebe)s::boolean[])
          AS t(subclasse_id, percentual, recebe_aporte)
    ),
    gravado AS (
        INSERT INTO tb_alocacao_alvos_subclasses
               (vigente_desde, subclasse_id, percentual, recebe_aporte)
        SELECT %(data)s, subclasse_id, percentual, recebe_aporte FROM entrada
        ON CONFLICT (vigente_desde, subclasse_id) DO UPDATE
           SET percentual = EXCLUDED.percentual,
               recebe_aporte = EXCLUDED.recebe_aporte
         WHERE (tb_alocacao_alvos_subclasses.percentual,
                tb_alocacao_alvos_subclasses.recebe_aporte)
               IS DISTINCT FROM (EXCLUDED.percentual, EXCLUDED.recebe_aporte)
        RETURNING (xmax = 0) AS nasceu
    )
    SELECT count(*) FILTER (WHERE nasceu)     AS gravados,
           count(*) FILTER (WHERE NOT nasceu) AS atualizados
      FROM gravado
"""

# ...e o outro lado do contrato: vazio apaga a linha, se ela existia. O
# `= ANY(...)` limita o DELETE às linhas que a GRADE desenhou.
_SQL_REMOVER_CLASSES = """
    DELETE FROM tb_alocacao_alvos_classes
     WHERE vigente_desde = %(data)s AND classe_id = ANY(%(ids)s::int[])
    RETURNING id
"""

_SQL_REMOVER_SUBCLASSES = """
    DELETE FROM tb_alocacao_alvos_subclasses
     WHERE vigente_desde = %(data)s AND subclasse_id = ANY(%(ids)s::int[])
    RETURNING id
"""


def gravar(data, valores, blocos):
    """Acerta o plano da data numa transação só. Devolve as três contagens.

    Ou tudo vale, ou nada vale: um plano meio gravado seria um plano que não
    soma 100 % no banco, justamente o que a validação acabou de impedir.
    """
    classes, subclasses = valores["classes"], valores["subclasses"]
    ids_classes = [b["classe"]["id"] for b in blocos]
    ids_subclasses = [s["id"] for b in blocos for s in b["subclasses"]]

    contagens = {"gravados": 0, "atualizados": 0, "removidos": 0}
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM tb_alocacao_planos WHERE vigente_desde = %s"
                    " FOR UPDATE", (data,))
        if cur.fetchone() is None:
            raise PlanoInexistente(data)

        cur.execute(_SQL_UPSERT_CLASSES, {
            "data": data, "ids": list(classes), "pcts": list(classes.values())})
        _somar(contagens, cur.fetchone())
        cur.execute(_SQL_UPSERT_SUBCLASSES, {
            "data": data, "ids": list(subclasses),
            "pcts": [v for v, _ in subclasses.values()],
            "recebe": [r for _, r in subclasses.values()]})
        _somar(contagens, cur.fetchone())

        cur.execute(_SQL_REMOVER_CLASSES, {
            "data": data, "ids": [i for i in ids_classes if i not in classes]})
        contagens["removidos"] += len(cur.fetchall())
        cur.execute(_SQL_REMOVER_SUBCLASSES, {
            "data": data,
            "ids": [i for i in ids_subclasses if i not in subclasses]})
        contagens["removidos"] += len(cur.fetchall())
    return contagens


def _somar(contagens, linha):
    contagens["gravados"] += linha["gravados"]
    contagens["atualizados"] += linha["atualizados"]


def criar(data):
    """Abre um plano na data, copiando o que vale nela. Devolve a origem.

    Copia o plano VIGENTE naquela data — o de maior `vigente_desde` anterior
    —, e não o mais recente: um plano novo no meio da série herda o que valia
    ali. Sem plano anterior, nasce vazio, e a grade é para preencher.

    A cópia leva as linhas como estão, referência inativa inclusive, como a
    cópia do mês anterior no orçamento: uma cópia não é linha nova escolhida
    por ninguém, e tirar uma linha dela deixaria o plano novo sem fechar
    100 %. Uma transação: ou nasce o plano com as linhas, ou nada.

    Data repetida estoura a PK de `tb_alocacao_planos`, e quem traduz é a rota.
    """
    origem = vigente_em(vigencias(), data)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO tb_alocacao_planos (vigente_desde)"
                    " VALUES (%s)", (data,))
        if origem is not None:
            cur.execute(
                "INSERT INTO tb_alocacao_alvos_classes"
                "       (vigente_desde, classe_id, percentual)"
                " SELECT %(data)s, classe_id, percentual"
                "   FROM tb_alocacao_alvos_classes"
                "  WHERE vigente_desde = %(origem)s",
                {"data": data, "origem": origem})
            cur.execute(
                "INSERT INTO tb_alocacao_alvos_subclasses"
                "       (vigente_desde, subclasse_id, percentual, recebe_aporte)"
                " SELECT %(data)s, subclasse_id, percentual, recebe_aporte"
                "   FROM tb_alocacao_alvos_subclasses"
                "  WHERE vigente_desde = %(origem)s",
                {"data": data, "origem": origem})
    return origem


def excluir(data):
    """Apaga as linhas e o plano, nessa ordem, numa transação.

    As FKs são `ON DELETE RESTRICT` de propósito, como no orçamento: apagar o
    plano com linhas dentro tem de ser um ato deliberado de quem escreveu
    isto, não uma cascata. Devolve False se a data não era plano nenhum.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM tb_alocacao_alvos_subclasses"
                    " WHERE vigente_desde = %s", (data,))
        cur.execute("DELETE FROM tb_alocacao_alvos_classes"
                    " WHERE vigente_desde = %s", (data,))
        cur.execute("DELETE FROM tb_alocacao_planos"
                    " WHERE vigente_desde = %s RETURNING vigente_desde", (data,))
        return cur.fetchone() is not None


# --------------------------------------------------------------------------
# 4. Textos (puros)
# --------------------------------------------------------------------------

def _plural(n, um, varios):
    return f"{n} {um if n == 1 else varios}"


def texto_do_aviso(data, contagens):
    """'Plano de 1 de janeiro de 2026: 3 gravados · 1 removido'. Puro.

    As contagens vêm do BANCO (dos RETURNING), nunca do que a tela achava
    que ia acontecer: salvar sem mexer em nada não reescreve linha nenhuma, e
    o aviso diz "nada mudou".
    """
    partes = [_plural(n, um, varios) for n, um, varios in (
        (contagens["gravados"], "gravado", "gravados"),
        (contagens["atualizados"], "atualizado", "atualizados"),
        (contagens["removidos"], "removido", "removidos"),
    ) if n]
    return (f"Plano de {data_por_extenso(data)}: "
            + (" · ".join(partes) if partes else "nada mudou"))


def texto_da_criacao(data, origem):
    """O flash de "Criar plano". Diz de onde vieram os alvos."""
    if origem is None:
        return (f"Plano de {data_por_extenso(data)} criado vazio: não havia "
                "plano antes dele. Preencha a grade.")
    return (f"Plano de {data_por_extenso(data)} criado com os alvos do plano "
            f"de {data_por_extenso(origem)}.")


def situacao(data, vigente, hoje):
    """('Vigente' | 'Futuro' | 'Substituído', classe do badge). Puro."""
    if data == vigente:
        return "Vigente", "badge--ativo"
    if data > hoje:
        return "Futuro", "badge--destaque"
    return "Substituído", "badge--inativo"


def _rotulo_da_opcao(data, vigente, hoje):
    """'1 de janeiro de 2026 (vigente)' / '... (futuro)'. Puro."""
    marca = (" (vigente)" if data == vigente
             else " (futuro)" if data > hoje else "")
    return data_por_extenso(data) + marca


# --------------------------------------------------------------------------
# 5. A tela no modo Plano
# --------------------------------------------------------------------------

def plano_escolhido(texto, datas, hoje):
    """A vigência que a tela abre. Nunca levanta. Pura.

    `?plano=` que é um plano existente vale; qualquer outra coisa cai no
    padrão em silêncio (a regra do ano inválido da Visão Anual): o vigente
    hoje, senão o mais novo — que só pode ser futuro —, senão nenhum.
    """
    try:
        pedido = date.fromisoformat((texto or "").strip())
    except (TypeError, ValueError):
        pedido = None
    if pedido in datas:
        return pedido
    return vigente_em(datas, hoje) or (max(datas) if datas else None)


def painel(args, hoje, digitado=None, erros=None, recusas=None, aviso=None,
           data=None):
    """Tudo o que o modo Plano mostra. Três consultas.

    `digitado`, `erros`, `recusas` e `aviso` só vêm do POST de gravação, que
    também traz a `data` do caminho — num GET ela sai de `?plano=`.
    """
    datas = vigencias()
    vigente = vigente_em(datas, hoje)
    escolhido = data or plano_escolhido(args.get("plano"), datas, hoje)

    contexto = {
        "subtitulo": ("O alvo de cada classe sobre o total e, dentro dela, o "
                      "de cada subclasse. Cada plano vale a partir da data "
                      "dele."),
        "opcoes": [{"valor": d.isoformat(),
                    "rotulo": _rotulo_da_opcao(d, vigente, hoje)}
                   for d in datas],
        "criar_padrao": hoje.isoformat(),
        # Os nomes dos campos da grade: contrato entre `ler_grade` e o
        # template, escrito uma vez só (em `alocacao/servico.py`).
        "prefixos": {"classe": PREFIXO_CLASSE, "subclasse": PREFIXO_SUBCLASSE,
                     "aporte": PREFIXO_APORTE},
        "plano": None,
    }
    if escolhido is None:
        return contexto

    linhas = linhas_do_plano(escolhido)
    blocos = blocos_da_grade(referencias(), linhas)
    rotulo, badge = situacao(escolhido, vigente, hoje)
    recusas = recusas or {}
    contexto["plano"] = {
        "data": escolhido,
        "data_texto": escolhido.isoformat(),
        "extenso": data_por_extenso(escolhido),
        "situacao": rotulo,
        "badge": badge,
        "grade": montar_grade(blocos, linhas, digitado, erros, recusas),
        "tem_referencias": bool(blocos),
        "erro_classes": recusas.get("classes"),
        "erro_geral": recusas.get("geral"),
        "aviso": aviso,
    }
    return contexto


def gravar_da_tela(data, campos, hoje):
    """O POST da grade, da leitura ao contexto da resposta.

    Lê só o que a grade desenhou, valida tudo e grava só se tudo fechou. A
    resposta é sempre a grade — com o aviso, ou com as recusas no lugar.
    """
    linhas = linhas_do_plano(data)
    blocos = blocos_da_grade(referencias(), linhas)
    valores, erros, digitado = ler_grade(campos, blocos)
    recusas = {} if erros else validar(valores, blocos)
    if erros or recusas:
        return painel({}, hoje, digitado=digitado, erros=erros,
                      recusas=recusas, data=data)
    contagens = gravar(data, valores, blocos)
    return painel({}, hoje, aviso=texto_do_aviso(data, contagens), data=data)
