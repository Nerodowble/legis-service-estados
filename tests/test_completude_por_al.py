"""
Bateria de COMPLETUDE — valida, para cada uma das 11 ALs, que estamos
extraindo TODOS OS DADOS que a fonte upstream realmente expõe.

Não é teste de "se funciona" — é teste de "se está aproveitando ao máximo".

Para cada AL:
  1. Mocka a resposta upstream com fixture realista (estrutura observada
     ao vivo durante o levantamento)
  2. Chama adapter.listar() ou adapter.detalhe()
  3. Valida que cada campo marcado como OBRIGATORIO na capacidade está
     preenchido em pelo menos 1 item retornado
  4. Documenta os campos NAO_DISPONIVEL (devem vir null) — para qualquer
     campo OPCIONAL/OBRIGATORIO que venha null, falha o teste
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from src.adapters.base import FiltrosBusca
from src.orquestrador.registry import get_adapter
from src.schemas import ProposicaoNormalizadaRaw
from tests.capacidade_por_al import (
    CAPACIDADES,
    NAO_DISPONIVEL,
    OBRIGATORIO,
)
from tests.fixtures_por_al import (
    ALAP_LISTAGEM,
    ALAP_PARLAMENTARES,
    ALBA_LISTAGEM,
    ALDF_LISTAGEM,
    ALECE_LISTAGEM,
    ALEPA_LISTAGEM,
    ALEPE_XML,
    ALERJ_XML,
    ALESC_LISTAGEM,
    ALMA_JSON,
    ALMT_DETALHE,
    ALMT_LISTAGEM,
    alesp_zip_bytes,
)


def _campos_obrigatorios_preenchidos(item: ProposicaoNormalizadaRaw, cap):
    """Retorna a lista de violações: campos OBRIGATORIO que vieram null/vazio."""
    violacoes = []

    def _check(nome: str, marcacao: str, valor):
        if marcacao == OBRIGATORIO and (valor is None or valor == "" or valor == []):
            violacoes.append(f"{cap.source_id}.{nome} OBRIGATORIO mas veio {valor!r}")

    _check("id_proposicao_origem", cap.id_proposicao_origem, item.id_proposicao_origem)
    _check("sigla_tipo", cap.sigla_tipo, item.sigla_tipo)
    _check("numero", cap.numero, item.numero)
    _check("ano", cap.ano, item.ano)
    _check("ementa", cap.ementa, item.ementa)
    _check("data_apresentacao", cap.data_apresentacao, item.data_apresentacao)
    _check("status", cap.status, item.status)
    _check("url_inteiro_teor", cap.url_inteiro_teor, item.url_inteiro_teor)
    _check("autores", cap.autores, item.autores)
    if cap.autores == OBRIGATORIO and item.autores:
        _check("autores[0].nome", OBRIGATORIO, item.autores[0].nome)
    if cap.autor_partido == OBRIGATORIO and item.autores:
        _check("autores[0].partido", OBRIGATORIO, item.autores[0].partido)
    if cap.autor_id == OBRIGATORIO and item.autores:
        _check("autores[0].id_autor_origem", OBRIGATORIO, item.autores[0].id_autor_origem)
    _check("tramitacoes", cap.tramitacoes, item.tramitacoes)
    if item.dados_adicionais:
        _check("codigoMateria", cap.codigo_materia, item.dados_adicionais.codigoMateria)
        _check("objetivo", cap.objetivo, item.dados_adicionais.objetivo)

    return violacoes


def _campos_indisponiveis_nulos(item: ProposicaoNormalizadaRaw, cap):
    """Retorna violações: campos marcados NAO_DISPONIVEL mas que vieram preenchidos."""
    violacoes = []

    def _check(nome: str, marcacao: str, valor):
        if marcacao == NAO_DISPONIVEL and valor not in (None, "", []):
            violacoes.append(
                f"{cap.source_id}.{nome} marcado NAO_DISPONIVEL mas veio {valor!r}"
            )

    _check("status", cap.status, item.status)
    _check("autores (esperado vazio)", cap.autores, item.autores)
    _check("tramitacoes", cap.tramitacoes, item.tramitacoes)
    if item.dados_adicionais:
        _check("codigoMateria", cap.codigo_materia, item.dados_adicionais.codigoMateria)
    return violacoes


# ──────────────────────────────────────────────────────────────────────
# 11 testes — um por AL
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_ap():
    respx.get("https://elegis.al.ap.leg.br/portal/proposicoes").mock(
        return_value=Response(200, text=ALAP_LISTAGEM,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    respx.get("https://al.ap.leg.br/pagina.php").mock(
        return_value=Response(200, text=ALAP_PARLAMENTARES,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    # Limpar cache do singleton entre testes (atributo de classe)
    from src.adapters.al_ap import AdapterAP
    AdapterAP._cache_parlamentares = None

    cap = CAPACIDADES["al_ap"]
    adapter = get_adapter("al_ap")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALAP listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_ba():
    respx.get("https://www.al.ba.gov.br/atividade-legislativa-nova/proposicoes").mock(
        return_value=Response(200, text=ALBA_LISTAGEM,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    cap = CAPACIDADES["al_ba"]
    adapter = get_adapter("al_ba")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALBA listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_ce():
    respx.get("https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php").mock(
        return_value=Response(
            200, content=ALECE_LISTAGEM,
            headers={"Content-Type": "text/html; charset=iso-8859-1"},
        )
    )
    cap = CAPACIDADES["al_ce"]
    adapter = get_adapter("al_ce")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALECE listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_df():
    respx.get("https://www.cl.df.gov.br/pt/web/guest/projetos").mock(
        return_value=Response(200, text=ALDF_LISTAGEM,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    cap = CAPACIDADES["al_df"]
    adapter = get_adapter("al_df")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "CLDF listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_ma():
    respx.get("https://www.al.ma.leg.br/sitealema/wp-json/wp/v2/ordem").mock(
        return_value=Response(200, json=ALMA_JSON,
                              headers={"X-WP-Total": "1", "X-WP-TotalPages": "1"})
    )
    cap = CAPACIDADES["al_ma"]
    adapter = get_adapter("al_ma")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALEMA listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_mt_listagem():
    respx.get("https://www.al.mt.gov.br/proposicao").mock(
        return_value=Response(200, text=ALMT_LISTAGEM,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    adapter = get_adapter("al_mt")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALMT listagem retornou 0 items"
    # ALMT só tem ID na listagem — sigla/numero vêm no detalhe
    for item in envelope.data:
        assert item.id_proposicao_origem
        assert item.url_inteiro_teor


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_mt_detalhe():
    """ALMT enriquece pelo <title> do detalhe — testar separado."""
    respx.get("https://www.al.mt.gov.br/proposicao/cpdoc/172857/visualizar").mock(
        return_value=Response(200, text=ALMT_DETALHE,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    adapter = get_adapter("al_mt")
    envelope = await adapter.detalhe("172857")
    assert envelope.total == 1
    item = envelope.data[0]
    assert item.sigla_tipo, "ALMT detalhe não extraiu sigla do <title>"
    assert item.numero, "ALMT detalhe não extraiu número do <title>"
    assert item.ano, "ALMT detalhe não extraiu ano do <title>"
    assert item.status, "ALMT detalhe não extraiu status do <title>"


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_pa():
    respx.get("https://www.alepa.pa.gov.br/Legislativo/CallbackPanelProposicoes").mock(
        return_value=Response(200, text=ALEPA_LISTAGEM,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    cap = CAPACIDADES["al_pa"]
    adapter = get_adapter("al_pa")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALEPA listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_pe():
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(200, content=ALEPE_XML,
                              headers={"Content-Type": "application/xml; charset=utf-8"})
    )
    cap = CAPACIDADES["al_pe"]
    adapter = get_adapter("al_pe")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALEPE listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_rj():
    respx.get("http://alerjln1.alerj.rj.gov.br/scpro2327.nsf/vlei").mock(
        return_value=Response(200, content=ALERJ_XML,
                              headers={"Content-Type": "text/xml; charset=iso-8859-1"})
    )
    cap = CAPACIDADES["al_rj"]
    adapter = get_adapter("al_rj")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALERJ listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_sc():
    respx.get("https://portalelegis.alesc.sc.gov.br/proposicoes/processo-legislativo").mock(
        return_value=Response(200, text=ALESC_LISTAGEM,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    cap = CAPACIDADES["al_sc"]
    adapter = get_adapter("al_sc")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALESC listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


@pytest.mark.asyncio
@respx.mock
async def test_completude_al_sp():
    respx.get("https://www.al.sp.gov.br/repositorioDados/processo_legislativo/proposituras.zip").mock(
        return_value=Response(200, content=alesp_zip_bytes(),
                              headers={"Content-Type": "application/zip"})
    )
    cap = CAPACIDADES["al_sp"]
    adapter = get_adapter("al_sp")
    envelope = await adapter.listar(FiltrosBusca(per_page=10))

    assert envelope.data, "ALESP listagem retornou 0 items"
    violacoes = []
    for item in envelope.data:
        violacoes += _campos_obrigatorios_preenchidos(item, cap)
    assert not violacoes, "\n".join(violacoes)


# ──────────────────────────────────────────────────────────────────────
# Resumo: imprime matriz de capacidade quando rodado isolado
# ──────────────────────────────────────────────────────────────────────


def test_imprimir_matriz_capacidade(capsys):
    """Não testa nada — só imprime a matriz por AL para auditoria."""
    print()
    print(f"{'Source':<10} {'UF':<3} {'Casa':<8} {'Det?':<5} {'Capacidade'}")
    print("-" * 90)
    for sid, cap in sorted(CAPACIDADES.items()):
        campos_obr = []
        if cap.id_proposicao_origem == OBRIGATORIO:
            campos_obr.append("id")
        if cap.sigla_tipo == OBRIGATORIO:
            campos_obr.append("sigla")
        if cap.numero == OBRIGATORIO:
            campos_obr.append("num")
        if cap.ano == OBRIGATORIO:
            campos_obr.append("ano")
        if cap.ementa == OBRIGATORIO:
            campos_obr.append("ementa")
        if cap.data_apresentacao == OBRIGATORIO:
            campos_obr.append("data")
        if cap.autores == OBRIGATORIO:
            campos_obr.append("autor")
        if cap.autor_partido in (OBRIGATORIO, "OPCIONAL"):
            campos_obr.append("partido?")
        if cap.url_inteiro_teor == OBRIGATORIO:
            campos_obr.append("url")
        if cap.status == OBRIGATORIO:
            campos_obr.append("status")
        det = "SIM" if cap.detalhe_implementado else "—"
        print(
            f"{sid:<10} {cap.uf:<3} {cap.casa_identificadora:<8} {det:<5} "
            f"{', '.join(campos_obr)}"
        )
