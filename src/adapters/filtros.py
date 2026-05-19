"""
Filtros locais aplicados após o fetch da fonte.

A maioria das ALs não suporta busca nativa por keyword ou autor, então o
adapter aplica os filtros em memória nos items que voltaram. Para filtros
que a fonte SUPORTA nativamente (ano, tipo na maioria dos casos), o filtro
local é idempotente — não fura nada.

Regras:
  - keyword: case-insensitive, casa em ementa OU ementa_detalhada OU status
  - autor:   case-insensitive, casa em qualquer autor.nome
  - numero:  exato (string)
  - ano:     exato (int)
  - tipo:    exato (sigla uppercase)

  Quando filtros.accent_insensitive=True, keyword e autor também são
  normalizados via unicodedata.NFKD (`Petroleo` casa `Petróleo`, `agua`
  casa `água`). Default é False para manter retro-compatibilidade.
"""

from __future__ import annotations

import unicodedata

from src.adapters.base import FiltrosBusca
from src.schemas import ProposicaoNormalizadaRaw


def _normalize_text(s: str | None, *, fold_accents: bool) -> str:
    """Lowercase + opcional Unicode NFKD fold (remove acentos)."""
    if not s:
        return ""
    s = s.lower()
    if fold_accents:
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s


def filtrar_local(
    items: list[ProposicaoNormalizadaRaw], filtros: FiltrosBusca
) -> list[ProposicaoNormalizadaRaw]:
    fold = filtros.accent_insensitive

    if filtros.keyword:
        kw = _normalize_text(filtros.keyword, fold_accents=fold)
        items = [i for i in items if _casa_keyword(i, kw, fold_accents=fold)]
    if filtros.autor:
        autor_kw = _normalize_text(filtros.autor, fold_accents=fold)
        items = [
            i
            for i in items
            if any(
                autor_kw in _normalize_text(a.nome, fold_accents=fold)
                for a in i.autores
            )
        ]
    if filtros.numero:
        items = [i for i in items if (i.numero or "") == filtros.numero]
    if filtros.ano:
        items = [i for i in items if i.ano == filtros.ano]
    if filtros.tipo:
        tipo_kw = filtros.tipo.upper()
        items = [i for i in items if (i.sigla_tipo or "").upper() == tipo_kw]
    return items


def _casa_keyword(
    item: ProposicaoNormalizadaRaw, kw_normalizado: str, *, fold_accents: bool
) -> bool:
    campos = [
        item.ementa,
        item.ementa_detalhada,
        item.status,
        " ".join(a.nome or "" for a in item.autores),
    ]
    for c in campos:
        if kw_normalizado in _normalize_text(c, fold_accents=fold_accents):
            return True
    return False
