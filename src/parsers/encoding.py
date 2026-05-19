"""
Detecção e decodificação de encoding.

Necessário porque CE usa ISO-8859-1, MA usa ISO-8859-15, e alguns
sistemas Lotus Notes (RJ) variam entre views.
"""

from __future__ import annotations

import re

import httpx


def _detectar_charset(body_bytes: bytes, content_type: str) -> str:
    """Estratégia em 3 camadas para descobrir o encoding correto."""
    # 1. Content-Type header
    m = re.search(r"charset=([^;]+)", content_type or "", re.IGNORECASE)
    if m:
        return m.group(1).strip().lower()

    # 2. Meta tag no HTML / declaração XML (primeiros 2KB)
    head = body_bytes[:2048].decode("ascii", errors="ignore")
    candidatos = [
        r'<meta\s+charset=["\']?([^"\'\s>]+)',
        r'<meta\s+http-equiv=["\']content-type["\']\s+content=["\'][^"\']*charset=([^"\';\s]+)',
        r'<\?xml[^>]*encoding=["\']([^"\']+)',
    ]
    for padrao in candidatos:
        m = re.search(padrao, head, re.IGNORECASE)
        if m:
            return m.group(1).lower()

    # 3. Default
    return "utf-8"


def decode_response(response: httpx.Response) -> str:
    """
    Decodifica response.content respeitando o encoding correto.

    Estratégia robusta: alguns servidores legados (ex: ALECE) declaram
    `ISO-8859-1` no Content-Type mas na verdade servem UTF-8. Se o decode
    pelo header declarado produzir muitos U+FFFD, testamos UTF-8 e
    preferimos o que minimizar mojibake.
    """
    charset = _detectar_charset(response.content, response.headers.get("content-type", ""))

    def _safe_decode(enc: str) -> tuple[str, int]:
        try:
            decoded = response.content.decode(enc, errors="replace")
        except LookupError:
            return "", 10**9
        # contar caracteres "replacement" (U+FFFD = '�' = '?')
        bad = decoded.count("�")
        return decoded, bad

    declarado, bad_declarado = _safe_decode(charset)

    # Otimização: se declarado é UTF-8 e funciona perfeito, retorna logo
    if charset.startswith("utf") and bad_declarado == 0:
        return declarado

    # Tentar UTF-8 strict — se passar sem erro, é UTF-8 de fato (servidor mentiu)
    try:
        utf8_strict = response.content.decode("utf-8")
        return utf8_strict
    except UnicodeDecodeError:
        pass

    # Conteúdo NÃO é UTF-8 válido — usar o declarado (ou fallback iso-8859-1)
    if declarado:
        return declarado
    return response.content.decode("iso-8859-1", errors="replace")


async def fetch_com_encoding(
    client: httpx.AsyncClient,
    url: str,
    **kwargs,
) -> str:
    """GET com decode automático."""
    response = await client.get(url, **kwargs)
    response.raise_for_status()
    return decode_response(response)
