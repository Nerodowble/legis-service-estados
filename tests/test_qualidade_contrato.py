"""
Testes de qualidade do CONTRATO da API.

Invariantes que TODA resposta da API deve respeitar:
  1. envelope tem data/total/total_pages/totals_by_nivel
  2. cada item tem id_proposicao_origem e casa_origem (não-vazios)
  3. nivel_federativo == "estadual" para adapters de AL
  4. dados_adicionais.tipoConteudo == "Proposição" (com Ç e ã)
  5. sigla_tipo, se presente, é UPPERCASE
  6. data_apresentacao, se presente, no formato YYYY-MM-DD
  7. url_inteiro_teor, se presente, começa com http(s)
  8. ementa não tem mojibake (U+FFFD)
  9. autores[].uf bate com a UF do adapter
 10. monitor sempre False (default — não persistimos estado por usuário)
"""

from __future__ import annotations

import re

import pytest
import respx
from httpx import Response

from src.adapters.al_pe import AdapterPE
from src.adapters.base import FiltrosBusca
from src.orquestrador.registry import get_adapter, listar_sources_disponiveis
from src.schemas import ProposicaoNormalizadaRaw, ResponseEnvelope

REGEX_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _assert_invariantes_item(item: ProposicaoNormalizadaRaw, uf_adapter: str):
    # 1. Identificação
    assert item.id_proposicao_origem, "id_proposicao_origem não pode ser vazio"
    assert item.casa_origem, "casa_origem não pode ser vazio"

    # 2. Nível federativo
    assert item.nivel_federativo == "estadual", (
        f"adapter de AL deve sempre marcar nivel_federativo=estadual, "
        f"veio: {item.nivel_federativo!r}"
    )

    # 3. tipoConteudo com acento
    if item.dados_adicionais:
        assert item.dados_adicionais.tipoConteudo == "Proposição", (
            f"tipoConteudo deve ser 'Proposição' (com acentos), "
            f"veio: {item.dados_adicionais.tipoConteudo!r}"
        )

    # 4. sigla uppercase
    if item.sigla_tipo:
        assert item.sigla_tipo == item.sigla_tipo.upper(), (
            f"sigla_tipo deve ser uppercase, veio: {item.sigla_tipo!r}"
        )

    # 5. data ISO
    if item.data_apresentacao:
        assert REGEX_ISO_DATE.match(item.data_apresentacao), (
            f"data_apresentacao deve ser YYYY-MM-DD, veio: {item.data_apresentacao!r}"
        )

    # 6. URL http(s)
    if item.url_inteiro_teor:
        assert item.url_inteiro_teor.startswith(("http://", "https://")), (
            f"url_inteiro_teor deve começar com http(s), veio: {item.url_inteiro_teor!r}"
        )

    # 7. sem mojibake
    if item.ementa:
        assert "�" not in item.ementa, "ementa contém U+FFFD (mojibake)"
    if item.casa_origem:
        assert "�" not in item.casa_origem, "casa_origem contém mojibake"

    # 8. autores UF consistente
    for autor in item.autores:
        if autor.uf:
            assert autor.uf == uf_adapter, (
                f"autor.uf deve ser {uf_adapter}, veio: {autor.uf!r}"
            )

    # 9. monitor é booleano e default False
    assert item.monitor is False or item.monitor is None, (
        "monitor sempre False/None — não persistimos estado por usuário"
    )


def _assert_invariantes_envelope(env: ResponseEnvelope):
    assert env.data is not None
    assert isinstance(env.total, int) and env.total >= 0
    assert isinstance(env.total_pages, int) and env.total_pages >= 1
    assert env.totals_by_nivel is not None
    assert env.totals_by_nivel.estadual >= 0


# ──────────────────────────────────────────────────────────────────────
# Bateria contra adapter ALEPE (XML mockado)
# ──────────────────────────────────────────────────────────────────────


XML_PE_MULTIPLOS = b"""<?xml version="1.0" encoding="UTF-8"?>
<projetos>
  <projeto docid="100" numero="1" ano="2024" tipo="PROJETO DE LEI ORDINARIA"
           ementa="Dispoe sobre subsidio ao petroleo" dataPublicacao="01/03/2024">
    <autores><autor nome="Maria Silva" tipo="DEPUTADO"/></autores>
  </projeto>
  <projeto docid="101" numero="2" ano="2024" tipo="PROJETO DE LEI ORDINARIA"
           ementa="Regulamenta educacao infantil" dataPublicacao="15/04/2024">
    <autores><autor nome="Joao Pereira" tipo="DEPUTADO"/></autores>
  </projeto>
  <projeto docid="102" numero="3" ano="2024" tipo="PROJETO DE LEI COMPLEMENTAR"
           ementa="Alteracao de regras do PETROLEO no Estado" dataPublicacao="22/06/2024">
    <autores><autor nome="Carla Mendes" tipo="DEPUTADO"/></autores>
  </projeto>
</projetos>"""


@pytest.mark.asyncio
@respx.mock
async def test_invariantes_envelope_alepe():
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_MULTIPLOS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    envelope = await AdapterPE().listar(FiltrosBusca(ano=2024))
    _assert_invariantes_envelope(envelope)
    for item in envelope.data:
        _assert_invariantes_item(item, "PE")


@pytest.mark.asyncio
@respx.mock
async def test_keyword_filtra_no_endpoint_completo_alepe():
    """Regressão direta do bug: keyword DEVE filtrar resultados."""
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_MULTIPLOS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    # 3 projetos no XML; só 2 mencionam petroleo
    envelope = await AdapterPE().listar(FiltrosBusca(ano=2024, keyword="petroleo"))
    assert envelope.total == 2, f"Esperava 2 items com 'petroleo', veio {envelope.total}"
    ids = {i.id_proposicao_origem for i in envelope.data}
    assert ids == {"100", "102"}


@pytest.mark.asyncio
@respx.mock
async def test_keyword_inexistente_retorna_vazio_alepe():
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_MULTIPLOS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    envelope = await AdapterPE().listar(
        FiltrosBusca(ano=2024, keyword="termoQueNaoExisteEmLugarNenhum")
    )
    assert envelope.total == 0
    assert envelope.data == []


@pytest.mark.asyncio
@respx.mock
async def test_filtro_autor_funciona_alepe():
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_MULTIPLOS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    envelope = await AdapterPE().listar(FiltrosBusca(autor="silva"))
    assert envelope.total == 1
    assert envelope.data[0].autores[0].nome == "Maria Silva"


@pytest.mark.asyncio
@respx.mock
async def test_filtro_numero_exato():
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_MULTIPLOS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    envelope = await AdapterPE().listar(FiltrosBusca(numero="2"))
    assert envelope.total == 1
    assert envelope.data[0].id_proposicao_origem == "101"


# ──────────────────────────────────────────────────────────────────────
# Registry: todos os adapters batem invariantes estáticas
# ──────────────────────────────────────────────────────────────────────


def test_todos_adapters_declaram_uf_de_2_letras():
    for sid in listar_sources_disponiveis():
        adapter = get_adapter(sid)
        assert len(adapter.UF) == 2, f"{sid}: UF={adapter.UF!r} deveria ter 2 letras"
        assert adapter.UF == adapter.UF.upper()


def test_todos_adapters_tem_source_id_no_padrao_al_xx():
    for sid in listar_sources_disponiveis():
        adapter = get_adapter(sid)
        assert sid.startswith("al_"), f"source_id deve começar com 'al_': {sid}"
        assert adapter.SOURCE_ID == sid


def test_todos_adapters_apontam_para_host_seguro_ou_http_documentado():
    """Apenas ALERJ usa HTTP (Lotus Notes legado documentado)."""
    excecoes_http = {"al_rj"}
    for sid in listar_sources_disponiveis():
        adapter = get_adapter(sid)
        if sid in excecoes_http:
            continue
        assert adapter.HOST_PRINCIPAL.startswith("https://"), (
            f"{sid}: HOST_PRINCIPAL deve ser HTTPS (exceto exceções documentadas), "
            f"veio: {adapter.HOST_PRINCIPAL}"
        )
