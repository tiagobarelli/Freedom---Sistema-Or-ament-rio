"""A versão do sistema e o texto do histórico de versões.

**Fonte única: o `CHANGELOG.md` da raiz.** Não existe constante de versão em
Python, e não pode existir: duas fontes divergem no dia em que alguém edita
uma e esquece a outra. A versão é o primeiro título de nível 2 do arquivo — o
primeiro token depois de `## ` —, então escrever a entrada nova no topo do
changelog é o que faz o número mudar no rodapé.

Arquivo ausente, ilegível ou sem nenhum título é **erro na subida da
aplicação**, e não versão "—": a mesma regra da Independência, onde premissa
que falta vira travessão em vez de um padrão inventado. Aqui nem travessão
serve — um sistema que não sabe que versão é não deve atender.

O arquivo é lido UMA VEZ, no `create_app`. Mudar o changelog exige reiniciar
o servidor; ele muda uma vez por versão, e a alternativa (ler do disco a cada
request) custaria uma leitura em toda tela para nada.
"""

import re

import markdown
from markupsafe import Markup

# O primeiro `## ` de uma linha, e o que vem colado depois dele. `\S+` para o
# número parar no primeiro espaço: o título é "## 0.24 — 20/09/2026" e a
# versão é só o "0.24".
_TITULO = re.compile(r"^## (\S+)", re.MULTILINE)


class ErroVersao(Exception):
    """Falha que impede a aplicação de subir. A mensagem já vai em português."""


def versao_atual(texto):
    """Devolve a versão: o primeiro token depois de `## `, na primeira linha
    que casar. Pura — recebe o texto, não o caminho.

    Parágrafo de abertura antes do primeiro título não atrapalha, e títulos
    seguintes são versões antigas: vale o primeiro, que é o de cima.
    """
    achado = _TITULO.search(texto)
    if achado is None:
        raise ErroVersao(
            "O changelog não tem nenhum título de nível 2: a versão do sistema "
            "é o primeiro token depois de '## ' e não há de onde tirá-la."
        )
    return achado.group(1)


def carregar(caminho):
    """Lê o changelog e devolve `(versão, HTML)`. Chamado uma vez, na subida.

    O HTML sai do Python-Markdown (núcleo, sem extensões) já marcado como
    seguro, e isso é decisão de servidor, não de template: o texto de entrada
    é um arquivo do REPOSITÓRIO, escrito por quem escreve o código, e não
    entrada de usuário. Nenhum caminho do sistema deixa alguém pôr texto aqui
    dentro — se um dia deixar, esta linha é a primeira a rever.
    """
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as erro:
        raise ErroVersao(
            f"Não foi possível ler o changelog em {caminho}: {erro}"
        ) from None

    return versao_atual(texto), Markup(markdown.markdown(texto))
