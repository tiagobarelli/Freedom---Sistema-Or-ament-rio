"""As rotas das duas Análises: por subcategoria e por prioridade.

Só orquestram. Cada uma lê da URL o que é dela — a subcategoria ou a faixa —,
monta o `Recorte` e entrega o resto a `servico_analise.painel()`, que é o
mesmo caminho para as duas: período, agrupamento, correção, consulta,
composição e gráfico. Nada de conta nem de texto mora aqui.

**A URL é o estado.** Tudo por GET, recarga da página inteira, sem HTMX: a
tela é reproduzível por link, o botão voltar desfaz o último filtro e abrir a
mesma URL em outra aba dá a mesma tela. Parâmetro inválido cai no padrão em
silêncio, como o ano da Visão Anual — menos o período personalizado, onde um
mês malformado ou invertido é erro de formulário, porque ali o usuário digitou
algo e merece saber o que houve.

As duas telas não são a mesma pergunta com outro filtro, e é por isso que são
duas: a por subcategoria olha uma linha do orçamento inteira, com tudo o que
foi lançado nela; a por prioridade olha o que a casa considera essencial ou
adiável, e só sobre o que integra a série histórica — daí o aviso fixo dela,
que existe para ninguém comparar os dois totais achando que deviam bater.
"""

from datetime import date

from flask import render_template, request
from flask_login import login_required

from freedom.main import servico_analise as servico
from freedom.main.routes import bp


@bp.route("/analise/subcategoria")
@login_required
def analise_subcategoria():
    sub_id = request.args.get("sub", type=int)
    recorte = servico.recorte_da_subcategoria(sub_id)
    return render_template(
        "main/analise.html",
        grupos=servico.subcategorias_com_lancamento(),
        sub=sub_id if recorte else None,
        **servico.painel(request.args, recorte, date.today()),
    )


@bp.route("/analise/prioridade")
@login_required
def analise_prioridade():
    """Uma faixa de essencialidade ou prioridade por vez, sem mistura.

    Sem padrão quando a faixa não vem ou não existe: as cinco respondem
    perguntas diferentes, e escolher uma pela pessoa seria mostrar um número
    que ela não pediu.
    """
    faixa = servico.faixa_valida(request.args.get("faixa"))
    return render_template(
        "main/analise_prioridade.html",
        faixas=servico.FAIXAS,
        faixa=faixa,
        **servico.painel(request.args, servico.recorte_da_faixa(faixa),
                         date.today()),
    )
