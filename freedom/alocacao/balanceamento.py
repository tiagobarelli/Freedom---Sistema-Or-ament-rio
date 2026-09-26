"""O modo Balanceamento da Alocação: onde a carteira está contra o plano.

Leitura pura: nada daqui grava. Lê a **última foto** de patrimônio, aplicada
à composição atual de cada ativo (`servico.valores_da_foto`), e o **plano
vigente hoje**, e diz, linha a linha, quanto cada classe e subclasse tem, quanto
deveria ter e quanto falta ou sobra.

Dois níveis, a mesma tabela: o nível 1 são as classes sobre o total investido;
abaixo dele, um bloco por classe com as subclasses sobre o total da classe.

**Total investido é só o classificado.** Ativo sem composição fica num bloco
próprio, "Não classificado", fora dos totais, do percentual e do rateio: não
se sabe de que classe ele é, e pôr o valor dele em qualquer uma mentiria.

**Atual (%) não conta o caixa digitado**, e é diferença deliberada da
planilha do dono, onde a proporção atual cai quando se digita caixa. Aqui o
atual é o que a foto diz; o caixa só entra no rateio do aporte.

**Nenhum número desta tela é vermelho**: desvio não é prejuízo. O que sai da
tolerância ganha o âmbar (o par `--orange-ink` / `--orange`), e só a coluna
Situação.

**O aporte vive na URL** (`?aporte=…&caixa_<id>=…`), como a simulação da
Independência: nada é gravado, e a conta é reproduzível por link.

Cinco consultas: as vigências de plano, as linhas do vigente, as
referências, a foto e a tolerância vigente.
"""

from decimal import Decimal

from freedom.alocacao import plano as planos
from freedom.alocacao.servico import (arredondar, centavos, referencias,
                                      rotulo_de_referencia, texto_percentual,
                                      valores_da_foto)
from freedom.configuracoes.servico import PERCENTUAL, formatar, valor_vigente
from freedom.main.servico import SEM_VALOR
from freedom.util import (ValorInvalido, com_sinal, converter_valor,
                          data_por_extenso, formatar_numero, formatar_valor,
                          parece_zero, reais_com_sinal)

ZERO = Decimal(0)
CEM = Decimal(100)

# O parâmetro de Parâmetros que diz quanto uma linha pode se afastar do alvo.
CHAVE_TOLERANCIA = "TOL"

# Nomes dos campos do aporte na query string. O do nível 1 é um só; o de cada
# bloco leva o id da classe.
CAMPO_APORTE = "aporte"
PREFIXO_CAIXA = "caixa_"

FRASE_SEM_ELEGIVEL = "Nenhuma linha que recebe aporte está abaixo do alvo."

# A classe CSS da Situação. Quem decide a cor é o nome que sai daqui; o CSS só
# pinta (5.25).
DENTRO = "situacao--dentro"
FORA = "situacao--fora"


# --------------------------------------------------------------------------
# 1. O rateio (pura) — a mesma conta nos dois níveis
# --------------------------------------------------------------------------

def ratear(linhas, caixa):
    """Quanto do caixa vai para cada linha, ou None quando não há a quem dar.

    `linhas` é uma sequência de `(alvo, valor, recebe)`: o alvo em fração (ou
    None, para a linha que tem valor mas não está no plano), o valor atual e
    se a linha recebe aporte. No nível 1 toda classe do plano recebe; no
    bloco, só a subclasse com "Recebe aporte" marcada.

    A regra, igual nos dois níveis:

    - T = soma dos valores do bloco + caixa;
    - déficit de cada linha = alvo × T − valor;
    - elegíveis: as linhas que recebem aporte com déficit > 0;
    - cada elegível leva déficit ÷ soma dos déficits elegíveis × caixa, e as
      demais levam zero.

    Devolve uma lista de `Decimal` na ordem de `linhas`, **sem arredondar**:
    o corte a centavos é do ponto exibido, com ROUND_HALF_UP, e a soma do que
    se exibe pode diferir do caixa em um centavo — isso não se corrige, porque
    corrigir seria inventar um centavo numa linha que não o pediu.

    `None` quando há caixa e nenhuma linha elegível: a resposta aí é uma
    frase, e não uma coluna de zeros que pareceria conta feita. Caixa zero
    sem elegível é só zero para todo mundo.

    A soma dos alvos não é validada aqui: quem garante os 100 % é a gravação
    do plano, e a planilha do dono tem bloco que soma 99,5 %.
    """
    total = sum((valor for _, valor, _ in linhas), ZERO) + caixa
    deficits = []
    for alvo, valor, recebe in linhas:
        deficit = alvo * total - valor if recebe and alvo is not None else None
        deficits.append(deficit if deficit is not None and deficit > 0 else None)

    soma = sum((d for d in deficits if d is not None), ZERO)
    if soma == 0:
        return None if caixa > 0 else [ZERO] * len(linhas)
    return [d / soma * caixa if d is not None else ZERO for d in deficits]


def situacao(atual, alvo, tolerancia):
    """(texto, classe) da coluna Situação, ou None quando ela não existe. Pura.

    A tolerância é desvio RELATIVO ao próprio alvo: uma linha está fora
    quando |atual − alvo| > TOL × alvo. No limite exato, está dentro. Com alvo
    zero qualquer valor positivo está fora — e zero com alvo zero, dentro.

    Sem tolerância vigente a coluna some inteira (None aqui), e a tela diz
    por quê: nunca um padrão inventado. Linha que tem valor e não está no
    plano não tem alvo, e fica fora por definição.
    """
    if tolerancia is None:
        return None
    if alvo is None:
        return "Sem alvo", FORA
    if atual is None:
        return SEM_VALOR, DENTRO
    if abs(atual - alvo) > tolerancia * alvo:
        return ("Acima" if atual > alvo else "Abaixo"), FORA
    return "Dentro", DENTRO


# --------------------------------------------------------------------------
# 2. Leitura do aporte (pura)
# --------------------------------------------------------------------------

def ler_caixa(texto):
    """Texto de um campo de aporte -> (valor | None, erro | None). Pura.

    Vazio é "não pedi a conta", e a coluna fica em travessão. Zero é conta
    legítima (dá zero para todos) e passa por `parece_zero` antes de
    `converter_valor`, que o recusaria — a mesma assimetria do orçamento e da
    foto. Texto que não é dinheiro vira erro no campo, e a coluna também fica
    em travessão.
    """
    bruto = (texto or "").strip()
    if not bruto:
        return None, None
    if parece_zero(bruto):
        return ZERO, None
    try:
        return converter_valor(bruto), None
    except ValorInvalido as exc:
        return None, str(exc)


def _campo(args, nome):
    texto = (args.get(nome) or "").strip()
    valor, erro = ler_caixa(texto)
    return {"nome": nome, "texto": texto, "valor": valor, "erro": erro}


# --------------------------------------------------------------------------
# 3. Composição (pura)
# --------------------------------------------------------------------------

def _reais(valor):
    return f"R$ {formatar_valor(centavos(valor))}"


def _desvio(atual, alvo):
    """'+1,25' / '-0,80' em pontos percentuais, ou travessão."""
    if atual is None or alvo is None:
        return SEM_VALOR
    pontos = arredondar((atual - alvo) * CEM, 2)
    return com_sinal(formatar_numero(pontos, 2), pontos)


def montar_linhas(entradas, total, caixa, tolerancia):
    """As linhas de uma tabela — o nível 1 ou um bloco. Pura.

    `entradas` é [{"rotulo", "alvo", "valor", "recebe"}]; `total` é o
    denominador do Atual (%) — o total investido no nível 1, o da classe no
    bloco — e nunca inclui o caixa. `caixa` é o do campo daquela tabela, ou
    None quando ele está vazio ou inválido.

    Devolve (linhas, partes, frase): as linhas com todo texto pronto, as
    partes do rateio sem arredondar (o nível 1 as passa aos blocos como dica)
    e a frase de "nenhuma elegível", quando for o caso.
    """
    partes = None
    frase = None
    if caixa is not None:
        partes = ratear([(e["alvo"], e["valor"], e["recebe"]) for e in entradas],
                        caixa)
        if partes is None:
            frase = FRASE_SEM_ELEGIVEL

    linhas = []
    for i, e in enumerate(entradas):
        atual = e["valor"] / total if total else None
        alvo = e["alvo"]
        estado = situacao(atual, alvo, tolerancia)
        linhas.append({
            "rotulo": e["rotulo"],
            "alvo": texto_percentual(alvo) or SEM_VALOR,
            "atual": _reais(e["valor"]),
            "atual_pct": texto_percentual(atual) or SEM_VALOR,
            "desvio": _desvio(atual, alvo),
            # Sem o caixa: é o que a foto diz que falta (+) ou sobra (-).
            "ajuste": (reais_com_sinal(centavos(alvo * total - e["valor"]))
                       if alvo is not None else SEM_VALOR),
            "situacao": ({"texto": estado[0], "classe": estado[1]}
                         if estado else None),
            "aporte": _reais(partes[i]) if partes else SEM_VALOR,
        })
    return linhas, partes, frase


def _rodape(total):
    return {"atual": _reais(total), "atual_pct": "100,00%" if total else SEM_VALOR}


def montar(foto, data_plano, linhas_plano, arvore, tolerancia, args):
    """Tudo o que o modo Balanceamento mostra, com texto e classe decididos.

    Pura: recebe o que o banco trouxe e a query string.
    """
    alvos_classes = linhas_plano["classes"]
    alvos_subclasses = linhas_plano["subclasses"]
    valores_classes = foto["classes"] if foto else {}
    valores_subclasses = foto["subclasses"] if foto else {}
    total = foto["total"] if foto else ZERO

    aporte = _campo(args, CAMPO_APORTE)

    # Nível 1: a classe que está no plano ou que tem valor na foto. A que tem
    # valor e não está no plano entra no total, fica com alvo "—", nunca
    # recebe aporte e fica fora.
    classes = [c for c in arvore
               if c["id"] in alvos_classes or c["id"] in valores_classes]
    entradas_1 = [{
        "rotulo": rotulo_de_referencia(c["nome"], c["ativo"]),
        "alvo": alvos_classes.get(c["id"]),
        "valor": valores_classes.get(c["id"], ZERO),
        "recebe": c["id"] in alvos_classes,
    } for c in classes]
    linhas_1, partes_1, frase_1 = montar_linhas(
        entradas_1, total, aporte["valor"], tolerancia)

    blocos = []
    for i, classe in enumerate(classes):
        subs = [s for s in classe["subclasses"]
                if s["id"] in alvos_subclasses or s["id"] in valores_subclasses]
        entradas = [{
            "rotulo": rotulo_de_referencia(s["nome"], s["ativo"]),
            "alvo": (alvos_subclasses[s["id"]]["percentual"]
                     if s["id"] in alvos_subclasses else None),
            "valor": valores_subclasses.get(s["id"], ZERO),
            "recebe": (s["id"] in alvos_subclasses
                       and alvos_subclasses[s["id"]]["recebe_aporte"]),
        } for s in subs]
        total_classe = valores_classes.get(classe["id"], ZERO)
        caixa = _campo(args, f"{PREFIXO_CAIXA}{classe['id']}")
        linhas, _, frase = montar_linhas(entradas, total_classe,
                                         caixa["valor"], tolerancia)
        blocos.append({
            "id": classe["id"],
            "titulo": entradas_1[i]["rotulo"],
            "linhas": linhas,
            "rodape": _rodape(total_classe),
            "campo": caixa,
            # A parte que o nível 1 sugeriu para esta classe, ao lado do campo
            # dela. Só quando o nível 1 fez a conta: com a frase, não há
            # parte nenhuma a sugerir.
            "dica": (f"Sugestão do nível 1: {_reais(partes_1[i])}"
                     if partes_1 else None),
            "frase": frase,
        })

    nao_classificados = None
    if foto and foto["nao_classificados"]:
        nao_classificados = {
            "linhas": [{"nome": a["nome"], "valor": _reais(a["valor"])}
                       for a in foto["nao_classificados"]],
            "total": _reais(foto["total_nao_classificado"]),
        }

    return {
        "subtitulo": (f"Foto de {data_por_extenso(foto['data'])} · plano "
                      f"vigente desde {data_por_extenso(data_plano)}"),
        "tem_tolerancia": tolerancia is not None,
        "nota_nivel1": "sobre o total investido" + (
            f" · tolerância de {formatar(tolerancia, PERCENTUAL)} do alvo"
            if tolerancia is not None else ""),
        "nota_tolerancia": (
            None if tolerancia is not None else
            "A tolerância da alocação (TOL) não está cadastrada em "
            "Parâmetros. Sem ela não há como dizer o que está fora do alvo, "
            "e a coluna Situação não aparece."),
        "nota_nao_classificado": (
            "Estes ativos não têm composição, e por isso não entram em conta "
            "nenhuma desta tela: nem no total investido, nem no percentual, "
            "nem no rateio do aporte. A composição se define no cadastro do "
            "ativo."),
        "nivel1": {"linhas": linhas_1, "rodape": _rodape(total),
                   "campo": aporte, "frase": frase_1},
        "blocos": blocos,
        "nao_classificados": nao_classificados,
        "campo_aporte": CAMPO_APORTE,
    }


# --------------------------------------------------------------------------
# 4. A tela no modo Balanceamento
# --------------------------------------------------------------------------

def _vazio(titulo, texto, rotulo_link, destino, plano=None):
    """O estado vazio e para onde ele leva. `destino` é "plano" ou
    "patrimonio": quem transforma isso em URL é o template, porque o serviço
    não monta rota; `plano` é a vigência que o modo Plano deve abrir."""
    return {"subtitulo": None,
            "vazio": {"titulo": titulo, "texto": texto,
                      "rotulo_link": rotulo_link, "destino": destino,
                      "plano": plano}}


def painel(args, hoje):
    """Da URL ao que o template mostra. Cinco consultas, nenhuma a mais.

    Três estados vazios, na ordem em que se resolvem: sem plano vigente hoje
    (o prompt da tela é ir montar um), plano vigente sem alvo nenhum (criado
    sem plano anterior e ainda não preenchido) e sem foto de patrimônio.
    """
    datas = planos.vigencias()
    vigente = planos.vigente_em(datas, hoje)
    if vigente is None:
        futuro = min(datas) if datas else None
        texto = ("Monte o plano de alocação: o alvo de cada classe e, dentro "
                 "dela, o de cada subclasse.")
        if futuro is not None:
            texto = (f"O primeiro plano só vale a partir de "
                     f"{data_por_extenso(futuro)}. " + texto)
        return _vazio("Nenhum plano vigente", texto, "Montar o plano", "plano")

    linhas_plano = planos.linhas_do_plano(vigente)
    if not linhas_plano["classes"]:
        return _vazio(
            "O plano vigente não tem alvos",
            f"O plano de {data_por_extenso(vigente)} foi criado vazio. "
            "Preencha a grade dele para o balanceamento ter com o que comparar.",
            "Preencher o plano", "plano", vigente.isoformat())

    foto = valores_da_foto()
    if foto is None:
        return _vazio(
            "Sem foto de patrimônio",
            "O balanceamento compara o plano com a última foto dos ativos, e "
            "ainda não há foto nenhuma.",
            "Lançar foto em Patrimônio", "patrimonio")

    tolerancia = valor_vigente(CHAVE_TOLERANCIA, hoje)
    return montar(foto, vigente, linhas_plano, referencias(),
                  tolerancia["valor"] if tolerancia else None, args)
