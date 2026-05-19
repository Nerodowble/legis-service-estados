"""Helper para parser XML com lxml."""

from __future__ import annotations

from lxml import etree


def parse_xml(xml_str: str | bytes) -> etree._Element:
    """Parse defensivo: resolve entities desligadas, BOM, etc."""
    if isinstance(xml_str, str):
        xml_str = xml_str.encode("utf-8", errors="replace")
    # Remove BOM se houver
    if xml_str.startswith(b"\xef\xbb\xbf"):
        xml_str = xml_str[3:]
    parser = etree.XMLParser(resolve_entities=False, recover=True, encoding="utf-8")
    return etree.fromstring(xml_str, parser=parser)
