"""Utilidades pequenas compartilhadas entre blueprints."""

from urllib.parse import urlparse


def destino_interno(valor):
    """Devolve `valor` se for um caminho interno seguro, senão None.

    Usado pelo `?next=` do login e pelo `?retorno=` da edição de despesa:
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
