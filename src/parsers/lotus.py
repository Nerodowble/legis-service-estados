"""
Parser específico para XML do IBM Lotus Notes/Domino (ALERJ).

Lotus retorna <viewentries><viewentry><entrydata columnnumber="N">...
Cada `columnnumber` corresponde a uma coluna pré-definida da view no servidor.
Como não há nome semântico das colunas, precisamos saber a ordem por view.

Mapeamentos extraídos por inspeção empírica das views públicas da ALERJ.
"""

from __future__ import annotations

import re
from typing import Any

from src.parsers.xml_utils import parse_xml

# Mapas {nome_view: [nome_campo_por_columnnumber]}
COLUNAS_POR_VIEW: dict[str, list[str]] = {
    # scpro2327.nsf — legislatura corrente (2023-2027)
    "vlei": ["numero", "autor", "ementa", "data_apresentacao", "situacao"],
    "vleicomp": ["numero", "autor", "ementa", "data_apresentacao", "situacao"],
    "vMensagem": ["numero", "origem", "ementa", "data_apresentacao", "situacao"],
    "vindicacao": ["numero", "autor", "ementa", "data_apresentacao", "situacao"],
    "vemenda": ["numero", "autor", "ementa", "data_apresentacao", "situacao"],
    "vdecreto": ["numero", "autor", "ementa", "data_apresentacao", "situacao"],
    "vveto": ["numero", "origem", "ementa", "data_apresentacao", "situacao"],
    "vresolucao": ["numero", "autor", "ementa", "data_apresentacao", "situacao"],
}


def _texto_entrydata(ed: Any) -> str | None:
    """Extrai valor de <entrydata> independente do tipo interno (text/number/datetime)."""
    for tag in ("text", "number"):
        el = ed.find(tag)
        if el is not None and el.text:
            return el.text.strip()
    dt = ed.find("datetime")
    if dt is not None and dt.text:
        return _converter_datetime_lotus(dt.text.strip())
    return None


def _converter_datetime_lotus(s: str) -> str:
    """
    Lotus datetime: '20240315T100000,00-03' -> ISO '2024-03-15T10:00:00-03:00'.
    """
    m = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2}),\d+([-+]\d+)?", s)
    if not m:
        return s
    tz = m.group(7) or ""
    if tz and len(tz) == 3:
        tz = f"{tz}:00"
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:{m.group(6)}{tz}"


def parse_view_entries(xml: str, view_name: str) -> tuple[int, list[dict[str, str | None]]]:
    """
    Parseia ?ReadViewEntries do Lotus Notes.

    Returns:
        (total_entries, lista_de_dicts)

    Cada dict tem os campos definidos em COLUNAS_POR_VIEW[view_name]
    + `_unid` (identificador único do documento).
    """
    root = parse_xml(xml)
    total = int(root.get("toplevelentries", "0"))

    colunas = COLUNAS_POR_VIEW.get(view_name, [])
    items: list[dict[str, str | None]] = []

    for entry in root.findall("viewentry"):
        registro: dict[str, str | None] = {"_unid": entry.get("unid")}

        for ed in entry.findall("entrydata"):
            col_num = int(ed.get("columnnumber", -1))
            nome_campo = colunas[col_num] if 0 <= col_num < len(colunas) else f"col_{col_num}"
            registro[nome_campo] = _texto_entrydata(ed)

        items.append(registro)

    return total, items
