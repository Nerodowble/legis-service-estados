"""
Teste de exemplo (respx) — Adapter PE.
PE é uma boa escolha por ter API XML estável e contrato simples.
"""

import pytest
import respx
from httpx import Response

from src.adapters.al_pe import AdapterPE
from src.adapters.base import FiltrosBusca


@pytest.mark.asyncio
@respx.mock
async def test_adapter_pe_parse_xml_minimo(html_alepe_xml_minimo: bytes):
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200,
            content=html_alepe_xml_minimo,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )

    adapter = AdapterPE()
    envelope = await adapter.listar(FiltrosBusca(ano=2024, tipo="PL"))

    assert envelope.total == 1
    assert len(envelope.data) == 1

    item = envelope.data[0]
    assert item.id_proposicao_origem == "123"
    assert item.numero == "456"
    assert item.ano == 2024
    assert item.ementa == "Teste de ementa"
    assert item.sigla_tipo == "PL"  # mapeado de "PROJETO DE LEI ORDINARIA"
    assert item.data_apresentacao == "2024-03-15"  # converte DD/MM/YYYY para ISO
    assert item.nivel_federativo == "estadual"
    assert item.dados_adicionais.casaIdentificadora == "ALEPE"
    assert len(item.autores) == 1
    assert item.autores[0].nome == "Deputado Fulano"
    assert item.autores[0].uf == "PE"


@pytest.mark.asyncio
@respx.mock
async def test_adapter_pe_propaga_503_como_al_indisponivel():
    from src.errors import ALIndisponivelError

    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(503, content=b"")
    )

    adapter = AdapterPE()
    with pytest.raises(ALIndisponivelError) as exc_info:
        await adapter.listar(FiltrosBusca(ano=2024))

    assert exc_info.value.uf == "PE"
    assert exc_info.value.status == 503
