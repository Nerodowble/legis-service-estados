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
"""

from __future__ import annotations

from src.adapters.base import FiltrosBusca
from src.schemas import ProposicaoNormalizadaRaw


def filtrar_local(
    items: list[ProposicaoNormalizadaRaw], filtros: FiltrosBusca
) -> list[ProposicaoNormalizadaRaw]:
    if filtros.keyword:
        kw = filtros.keyword.lower()
        items = [i for i in items if _casa_keyword(i, kw)]
    if filtros.autor:
        autor_kw = filtros.autor.lower()
        items = [
            i
            for i in items
            if any((a.nome or "").lower().find(autor_kw) >= 0 for a in i.autores)
        ]
    if filtros.numero:
        items = [i for i in items if (i.numero or "") == filtros.numero]
    if filtros.ano:
        items = [i for i in items if i.ano == filtros.ano]
    if filtros.tipo:
        tipo_kw = filtros.tipo.upper()
        items = [i for i in items if (i.sigla_tipo or "").upper() == tipo_kw]
    return items


def _casa_keyword(item: ProposicaoNormalizadaRaw, kw_lower: str) -> bool:
    campos = [
        item.ementa,
        item.ementa_detalhada,
        item.status,
        " ".join(a.nome or "" for a in item.autores),
    ]
    return any(kw_lower in (c or "").lower() for c in campos)
