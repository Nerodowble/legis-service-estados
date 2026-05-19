"""Fixtures comuns para os testes."""

import pytest


@pytest.fixture
def html_alepe_xml_minimo() -> bytes:
    # Estrutura real do dadosabertos.alepe.pe.gov.br confirmada ao vivo 2026-05-19
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<projetos>
  <projeto docid="123" numero="456" ano="2024" tipo="PROJETO DE LEI ORDINARIA" ementa="Teste de ementa" dataPublicacao="15/03/2024">
    <autores><autor nome="Deputado Fulano" tipo="DEPUTADO"/></autores>
  </projeto>
</projetos>"""


@pytest.fixture
def html_almt_listagem() -> str:
    """Página HTML mínima do HermesLegis com 1 proposição."""
    return """<!DOCTYPE html>
<html><body>
<table>
  <tr class="proposicao-row">
    <td><a href="/proposicao/cpdoc/12345/visualizar">PL 1/2026</a></td>
    <td>Dep. Eduardo Botelho</td>
    <td>Ementa qualquer</td>
    <td>2026-02-01</td>
  </tr>
</table>
</body></html>"""
