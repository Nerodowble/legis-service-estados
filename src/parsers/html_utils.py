"""Helpers para parser HTML com selectolax (10x mais rápido que BeautifulSoup)."""

from __future__ import annotations

import re

from selectolax.parser import HTMLParser, Node


def parse_html(html: str) -> HTMLParser:
    return HTMLParser(html)


def primeiro_texto(node: Node | None, selector: str) -> str | None:
    """Texto do primeiro nó que casa com o selector, ou None."""
    if node is None:
        return None
    found = node.css_first(selector)
    if found is None:
        return None
    return normalizar_texto(found.text(strip=True))


def normalizar_texto(s: str | None) -> str | None:
    """Comprime whitespace e remove caracteres invisíveis."""
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\xa0", " ").strip()  # nbsp -> espaço
    return s or None


def extrair_label_valor(tree: HTMLParser, label: str) -> str | None:
    """
    Para HTMLs com padrão <dt>Label</dt><dd>Valor</dd> ou similares,
    encontra o <dd> imediatamente após um <dt> contendo `label`.
    """
    for dt in tree.css("dt"):
        if label.lower() in (dt.text(strip=True) or "").lower():
            dd = dt.next  # próximo sibling
            while dd is not None and dd.tag != "dd":
                dd = dd.next
            if dd is not None:
                return normalizar_texto(dd.text(strip=True))
    return None
