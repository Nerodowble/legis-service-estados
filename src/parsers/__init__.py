from src.parsers.encoding import decode_response, fetch_com_encoding
from src.parsers.html_utils import normalizar_texto, parse_html, primeiro_texto
from src.parsers.xml_utils import parse_xml

__all__ = [
    "decode_response",
    "fetch_com_encoding",
    "normalizar_texto",
    "parse_html",
    "parse_xml",
    "primeiro_texto",
]
