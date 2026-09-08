"""Consulta de despesas com filtros.

Uma rota só serve a página inteira e o fragmento de resultados: o que muda é
o template renderizado, não a lógica de consulta.
"""

import math

from flask import render_template, request, url_for
from flask_login import login_required

from freedom.lancamentos import bp
from freedom.lancamentos.servico import (
    ESSENCIAL,
    NAO_ESSENCIAL,
    ORDENS,
    POR_PAGINA,
    deslocar_mes,
    id_valido,
    mes_corrente,
    mes_valido,
    meses_com_lancamento,
    opcoes_de_filtro,
    pagina_de_despesas,
    pagina_pedida,
    resumo_por_categoria,
    rotulo_mes,
    so_fragmento,
    totais_do_filtro,
)

# Parâmetros que compõem o estado da tela e viajam na URL.
PARAMETROS = ("mes", "pessoa_id", "categoria_id", "conta_id",
              "essencialidade", "q", "ordem", "pagina")


def ler_filtros(args, opcoes):
    """Lê e valida a query string. Nada aqui pode gerar 500.

    Qualquer parâmetro sem sentido (mes=abc, pagina=0, pessoa_id=99999,
    essencialidade=xyz) volta para o padrão em silêncio.
    """
    mes = args.get("mes")
    filtros = {
        "mes": (mes if mes_valido(mes) else mes_corrente()),
        "pessoa_id": id_valido(args, "pessoa_id", opcoes["pessoas"]),
        "categoria_id": id_valido(args, "categoria_id", opcoes["categorias"]),
        "conta_id": id_valido(args, "conta_id", opcoes["contas"]),
        "essencialidade": (
            args.get("essencialidade")
            if args.get("essencialidade") in (ESSENCIAL, NAO_ESSENCIAL)
            else None
        ),
        "q": (args.get("q") or "").strip()[:100] or None,
        "ordem": args.get("ordem") if args.get("ordem") in ORDENS else "data",
    }
    filtros["mes"] = int(filtros["mes"])
    return filtros


def query_string(filtros, pagina=None, **troca):
    """Monta a query string desta tela, para links e para o parâmetro retorno."""
    dados = dict(filtros)
    dados["pagina"] = pagina or 1
    dados.update(troca)
    # O mês viaja sempre (a tela é sempre de um mês) e a página 1, por ser o
    # padrão, fica fora. O `== 1` é testado só na página, pelo nome: um filtro
    # de pessoa, categoria ou conta de id 1 também vale 1 e sumiria da URL.
    return {
        k: v for k, v in dados.items()
        if k == "mes" or (v not in (None, "")
                          and not (k == "pagina" and v == 1))
    }


def _contexto(args):
    """Tudo que o bloco de resultados precisa, já filtrado e paginado."""
    opcoes = opcoes_de_filtro()
    filtros = ler_filtros(args, opcoes)

    totais = totais_do_filtro(filtros)
    quantidade = totais["quantidade"]
    paginas = max(1, math.ceil(quantidade / POR_PAGINA))

    # Página além do fim volta para a última: pagina=9999 não pode dar erro
    # nem tela em branco.
    pagina = min(pagina_pedida(args), paginas)

    linhas = pagina_de_despesas(filtros, pagina) if quantidade else []
    primeiro = (pagina - 1) * POR_PAGINA + 1 if quantidade else 0
    ultimo = primeiro + len(linhas) - 1 if quantidade else 0

    return {
        "filtros": filtros,
        "opcoes": opcoes,
        "totais": totais,
        "resumo": resumo_por_categoria(filtros),
        "linhas": linhas,
        "pagina": pagina,
        "paginas": paginas,
        "primeiro": primeiro,
        "ultimo": ultimo,
        "quantidade": quantidade,
        "rotulo_mes": rotulo_mes(filtros["mes"]),
        "mes_anterior": deslocar_mes(filtros["mes"], -1),
        "mes_seguinte": deslocar_mes(filtros["mes"], 1),
        "meses": meses_com_lancamento(filtros["mes"]),
        "query_string": query_string,
        # Caminho de volta para a edição preservar filtros e página.
        "retorno": url_for("lancamentos.despesas_consulta",
                           **query_string(filtros, pagina)),
    }


@bp.route("/despesas/consulta")
@login_required
def despesas_consulta():
    contexto = _contexto(request.args)
    modelo = ("lancamentos/_resultados.html" if so_fragmento()
              else "lancamentos/consulta.html")
    return render_template(modelo, **contexto)


def resultados_apos_exclusao(args):
    """Bloco de resultados re-renderizado, para a exclusão feita na consulta.

    Apagar uma linha mexe em totais, resumo e paginação de uma vez; devolver
    só a <tr> deixaria os três desatualizados.
    """
    return render_template("lancamentos/_resultados.html", **_contexto(args))
