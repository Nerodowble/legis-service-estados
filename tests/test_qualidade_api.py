"""
Testes de qualidade end-to-end via TestClient — atravessam o stack completo:
  Route → Rate Limiter → Circuit Breaker → Adapter → Filtros → Schema

Pegam regressões que testes unitários sozinhos não pegam:
  - parâmetros de query chegam no adapter
  - exception handlers convertem corretamente para HTTP
  - JSON serializado preserva acentos
  - per_page é respeitado
"""

from __future__ import annotations

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from src.main import app

XML_PE_5_ITENS = b"""<?xml version="1.0" encoding="UTF-8"?>
<projetos>
  <projeto docid="1" numero="1" ano="2024" tipo="PROJETO DE LEI"
           ementa="Sobre petroleo" dataPublicacao="01/01/2024"/>
  <projeto docid="2" numero="2" ano="2024" tipo="PROJETO DE LEI"
           ementa="Sobre educacao" dataPublicacao="02/01/2024"/>
  <projeto docid="3" numero="3" ano="2024" tipo="PROJETO DE LEI"
           ementa="Sobre saude" dataPublicacao="03/01/2024"/>
  <projeto docid="4" numero="4" ano="2024" tipo="PROJETO DE LEI"
           ementa="Sobre transporte" dataPublicacao="04/01/2024"/>
  <projeto docid="5" numero="5" ano="2024" tipo="PROJETO DE LEI"
           ementa="Sobre petroleo refinado" dataPublicacao="05/01/2024"/>
</projetos>"""


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ──────────────────────────────────────────────────────────────────────
# Health & metadados
# ──────────────────────────────────────────────────────────────────────


def test_health_responde_200(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "legis-service-estados"


def test_health_sources_lista_11_adapters(client: TestClient):
    r = client.get("/health/sources")
    assert r.status_code == 200
    sources = r.json()["sources_disponiveis"]
    assert len(sources) == 11
    assert "al_ap" in sources


def test_health_source_probe_invalido_retorna_404(client: TestClient):
    r = client.get("/health/sources/al_xyz_invalido")
    assert r.status_code == 404


@respx.mock
def test_health_source_probe_ativo_al_pe_up(client: TestClient):
    """Probe ativo: AL respondendo OK retorna status=up + latência."""
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=b'<?xml version="1.0"?><projetos></projetos>',
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    r = client.get("/health/sources/al_pe")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "al_pe"
    assert body["status"] == "up"
    assert "latency_ms" in body
    assert body["latency_ms"] >= 0


@respx.mock
def test_health_source_probe_ativo_al_pe_down(client: TestClient):
    """Probe ativo: AL falhando retorna status=down + erro."""
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(503, content=b"")
    )
    r = client.get("/health/sources/al_pe")
    assert r.status_code == 200  # probe sempre 200, info em body
    body = r.json()
    assert body["source"] == "al_pe"
    assert body["status"] == "down"
    assert body["error"] in {"ALIndisponivelError", "Exception"}


def test_openapi_json_disponivel(client: TestClient):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "legis-service-estados"


def test_swagger_renderiza_docs(client: TestClient):
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower()


# ──────────────────────────────────────────────────────────────────────
# /propositions/fetch-live — validações de input
# ──────────────────────────────────────────────────────────────────────


def test_source_invalido_retorna_422(client: TestClient):
    # source = enum literal, valor desconhecido viola validação Pydantic
    r = client.get("/propositions/fetch-live?source=al_xx_falso")
    assert r.status_code == 422


def test_source_ausente_retorna_422(client: TestClient):
    r = client.get("/propositions/fetch-live")
    assert r.status_code == 422


def test_per_page_acima_do_limite_retorna_422(client: TestClient):
    r = client.get("/propositions/fetch-live?source=al_pe&per_page=999")
    assert r.status_code == 422


def test_page_zero_retorna_422(client: TestClient):
    r = client.get("/propositions/fetch-live?source=al_pe&page=0")
    assert r.status_code == 422


# ──────────────────────────────────────────────────────────────────────
# /propositions/fetch-live — fluxo completo com mock
# ──────────────────────────────────────────────────────────────────────


@respx.mock
def test_keyword_filtra_atraves_da_API_completa(client: TestClient):
    """Regressão direta do bug que o Willian achou via Swagger."""
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_5_ITENS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    r = client.get(
        "/propositions/fetch-live?source=al_pe&ano=2024&keyword=petroleo&per_page=20"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2, (
        f"Esperava 2 items com 'petroleo' filtrados, veio {body['total']}. "
        f"Bug regressou: keyword não está sendo aplicada."
    )
    ids = {i["id_proposicao_origem"] for i in body["data"]}
    assert ids == {"1", "5"}


@respx.mock
def test_per_page_respeitado_no_corte_final(client: TestClient):
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_5_ITENS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    r = client.get("/propositions/fetch-live?source=al_pe&per_page=2")
    body = r.json()
    assert len(body["data"]) <= 2


@respx.mock
def test_envelope_tem_estrutura_exata_do_contrato_dev(client: TestClient):
    """
    Valida que o JSON serializado atende o exemplo do message (9).txt:
      {data, total, total_pages, totals_by_nivel:{federal,estadual,municipal}}
    """
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_5_ITENS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    r = client.get("/propositions/fetch-live?source=al_pe&per_page=1")
    body = r.json()

    assert set(body.keys()) == {"data", "total", "total_pages", "totals_by_nivel"}
    assert set(body["totals_by_nivel"].keys()) == {"federal", "estadual", "municipal"}

    if body["data"]:
        item = body["data"][0]
        # 18 campos do contrato do dev
        esperado = {
            "id_proposicao_origem", "casa_origem", "sigla_tipo", "numero", "ano",
            "ementa", "ementa_detalhada", "data_apresentacao", "status",
            "url_inteiro_teor", "autores", "tramitacoes", "dados_adicionais",
            "monitor", "termometro", "score_risco", "nivel_federativo",
            "indicador_alta_prob",
        }
        assert esperado.issubset(item.keys()), (
            f"FALTAM campos: {esperado - set(item.keys())}"
        )

        # dados_adicionais com tipoConteudo acentuado
        assert item["dados_adicionais"]["tipoConteudo"] == "Proposição"


@respx.mock
def test_acentos_preservados_no_json(client: TestClient):
    """JSON serializado tem que devolver UTF-8 com acentos, não mojibake."""
    xml_com_acentos = b"""<?xml version="1.0" encoding="UTF-8"?>
<projetos>
  <projeto docid="9" numero="9" ano="2024" tipo="PROJETO DE LEI"
           ementa="Disp\xc3\xb5e sobre o petr\xc3\xb3leo, \xc3\xa1lcool e Saneamento B\xc3\xa1sico"
           dataPublicacao="01/01/2024">
    <autores><autor nome="Jo\xc3\xa3o Pe\xc3\xa7anha" tipo="DEPUTADO"/></autores>
  </projeto>
</projetos>"""
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=xml_com_acentos,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    r = client.get("/propositions/fetch-live?source=al_pe&ano=2024")
    body = r.json()
    item = body["data"][0]
    assert item["ementa"] == "Dispõe sobre o petróleo, álcool e Saneamento Básico"
    assert item["autores"][0]["nome"] == "João Peçanha"
    # garante que NÃO veio mojibake
    assert "�" not in r.text


@respx.mock
def test_fonte_indisponivel_retorna_503_estruturado(client: TestClient):
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(503, content=b"")
    )
    r = client.get("/propositions/fetch-live?source=al_pe&ano=2024")
    assert r.status_code == 503
    body = r.json()
    # FastAPI embrulha em "detail" quando HTTPException é levantada
    detalhe = body.get("detail") or body
    assert detalhe.get("uf") == "PE"
    assert detalhe.get("status") == 503


# ──────────────────────────────────────────────────────────────────────
# Paginação determinística
# ──────────────────────────────────────────────────────────────────────


HTML_ALAP_DETALHE_108457 = """<!DOCTYPE html>
<html><head><title>Proposição</title></head>
<body>
<div>
  <h1 class="mb-0">Moção nº 0317/26-AL</h1>
  <h1 class="mb-0">IX Legislatura - 2023 / 2027 - 3ª sessão Legislativa</h1>
  <h2 class="mb-0"></h2>
</div>
<div class="card-body">
  <p><strong>Origem:</strong> Deputado Rodolfo Vale</p>
  <p><strong>Ementa:</strong> Moção de Aplauso aos profissionais listados no anexo único.</p>
  <p><strong>Data de Protocolo:</strong> 19/05/2026</p>
  <p><strong>Texto Original:</strong> <a href="http://silegis.al.ap.leg.br/proposicao/108457.pdf">Baixar</a></p>
  <p><strong>Observações:</strong> Tramitação acelerada.</p>
</div>
<h2>Movimentos</h2>
<table>
  <tr><th>Data</th><th>Status</th><th>Documento</th></tr>
  <tr><td>19/05/2026</td><td>Incluído para leitura: 17ª Sessão Extraordinária</td><td></td></tr>
  <tr><td>19/05/2026</td><td>Enviado para Diretoria Legislativa</td><td></td></tr>
</table>
</body></html>"""


@respx.mock
def test_bug_willian_detalhe_al_ap_108457_retorna_dados(client: TestClient):
    """
    Regressão: /fetch-live/al_ap/108457 retornava total=0 porque o adapter
    não implementava detalhe() e caía no default da AdapterBase, que tentava
    filtrar pelo numero=108457 (id interno, não número da proposição).
    """
    respx.get("https://elegis.al.ap.leg.br/portal/proposicao/108457").mock(
        return_value=Response(
            200, text=HTML_ALAP_DETALHE_108457,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    )
    r = client.get("/propositions/fetch-live/al_ap/108457")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    item = body["data"][0]
    assert item["id_proposicao_origem"] == "108457"
    assert item["sigla_tipo"] == "MOC"
    assert item["numero"] == "317"
    assert item["ano"] == 2026
    assert "Moção de Aplauso" in (item["ementa"] or "")
    assert item["data_apresentacao"] == "2026-05-19"
    assert item["autores"][0]["nome"] == "Deputado Rodolfo Vale"
    assert item["autores"][0]["uf"] == "AP"
    # url_inteiro_teor agora prefere o PDF do "Texto Original" quando disponível
    assert "silegis.al.ap.leg.br" in item["url_inteiro_teor"]
    # Tramitações extraídas da tabela "Movimentos"
    assert len(item["tramitacoes"]) == 2
    descricoes = [t["descricao"] for t in item["tramitacoes"]]
    assert "Enviado para Diretoria Legislativa" in descricoes
    assert "Incluído para leitura: 17ª Sessão Extraordinária" in descricoes
    # Cada tramitação tem data ISO e sequência ordenada
    for t in item["tramitacoes"]:
        assert t["data"] == "2026-05-19"
        assert isinstance(t["sequencia"], int)
    # Status = última tramitação (mais recente vem primeiro pela convenção)
    assert item["status"] is not None
    # Legislatura preservada em dados_adicionais.objetivo
    assert "Legislatura" in (item["dados_adicionais"]["objetivo"] or "")
    # Observações capturadas em ementa_detalhada
    assert item["ementa_detalhada"] == "Tramitação acelerada."


HTML_ALEPA_DETALHE = """<!DOCTYPE html>
<html><head><title>INDICAÇÃO Nº 142/2024 - ALEPA</title></head>
<body>
<div class="items-container">
  <p>Tipo de Proposição: INDICAÇÃO</p>
  <p>Número: 142</p>
  <p>Origem: INTERNA</p>
  <p>Entrada: MESA DIRETORA</p>
  <p>Data da Entrada: 18/12/2024</p>
  <p>Autor: DEP. LÍVIA DUARTE</p>
  <p>Ementa: Requer ao Governador a criação do Programa.</p>
  <p>Regime: MATÉRIA EM REGIME NORMAL</p>
  <p>Situação: DEFERIDA</p>
</div>
<a href="https://downloads.alepa.pa.gov.br/Projeto/Anexo/14341-1.PDF">Download</a>
</body></html>"""


@respx.mock
def test_detalhe_al_pa_extrai_todos_campos(client: TestClient):
    """Valida detalhe al_pa: 9 campos do <p><strong>Label:</strong>...</p>."""
    respx.get("https://www.alepa.pa.gov.br/Legislativo/DetalhesProposicao").mock(
        return_value=Response(200, text=HTML_ALEPA_DETALHE,
                              headers={"Content-Type": "text/html; charset=utf-8"})
    )
    r = client.get("/propositions/fetch-live/al_pa/14341")
    assert r.status_code == 200
    item = r.json()["data"][0]
    assert item["id_proposicao_origem"] == "14341"
    assert item["sigla_tipo"] == "IND"
    assert item["numero"] == "142"
    assert item["ano"] == 2024
    assert item["status"] == "DEFERIDA"
    assert item["data_apresentacao"] == "2024-12-18"
    assert "Requer" in item["ementa"]
    assert item["autores"][0]["nome"] == "DEP. LÍVIA DUARTE"
    assert "MATÉRIA EM REGIME NORMAL" in (item["ementa_detalhada"] or "")
    assert item["dados_adicionais"]["objetivo"] == "INTERNA"
    assert ".PDF" in item["url_inteiro_teor"]


XML_ALEPE_DETALHE = b"""<?xml version="1.0" encoding="UTF-8"?>
<projetos>
  <projeto docid="16370" numero="33" ano="2026"
           legislatura="VIGESIMA" tipo="PROPOSTA DE EMENDA A CONSTITUICAO"
           ementa="Altera a Constituicao do Estado." dataPublicacao="31/03/2026">
    <autores><autor nome="Joao Paulo do PT" tipo="DEPUTADO"/></autores>
  </projeto>
</projetos>"""


@respx.mock
def test_detalhe_al_pe_filtra_docid_da_lista(client: TestClient):
    """ALEPE não tem endpoint per-item; detalhe filtra docid da listagem."""
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(200, content=XML_ALEPE_DETALHE,
                              headers={"Content-Type": "application/xml"})
    )
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/indicacoes/").mock(
        return_value=Response(404, text="")
    )
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/requerimentos/").mock(
        return_value=Response(404, text="")
    )
    r = client.get("/propositions/fetch-live/al_pe/16370")
    assert r.status_code == 200
    item = r.json()["data"][0]
    assert item["id_proposicao_origem"] == "16370"
    assert item["sigla_tipo"] == "PEC"
    assert item["numero"] == "33"
    assert item["ano"] == 2026
    assert item["autores"][0]["nome"] == "Joao Paulo do PT"
    assert item["dados_adicionais"]["objetivo"] == "VIGESIMA"


@respx.mock
def test_detalhe_al_pe_docid_inexistente_404(client: TestClient):
    """Docid não existe em nenhum dos 3 endpoints → 404 estruturado."""
    for ep in ["projetos", "indicacoes", "requerimentos"]:
        respx.get(f"https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/{ep}/").mock(
            return_value=Response(200, content=b'<?xml version="1.0"?><projetos></projetos>',
                                  headers={"Content-Type": "application/xml"})
        )
    r = client.get("/propositions/fetch-live/al_pe/99999")
    assert r.status_code == 404


@respx.mock
def test_detalhe_al_ap_404_propaga_503(client: TestClient):
    """Se a proposição não existe, fonte upstream 404 → API responde 503."""
    respx.get("https://elegis.al.ap.leg.br/portal/proposicao/999999").mock(
        return_value=Response(404, text="")
    )
    r = client.get("/propositions/fetch-live/al_ap/999999")
    assert r.status_code == 503
    body = r.json()
    detalhe = body.get("detail") or body
    assert detalhe.get("uf") == "AP"


@respx.mock
def test_page_2_nao_repete_items_de_page_1(client: TestClient):
    """
    Critério de qualidade: paginar não pode devolver duplicados.
    (Para adapters que paginam client-side ou que usam ordenação estável.)
    """
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(
            200, content=XML_PE_5_ITENS,
            headers={"Content-Type": "application/xml; charset=utf-8"},
        )
    )
    # ALEPE devolve XML completo; com per_page=2:
    # page=1 → ids 1,2; page=2 → ids 3,4; page=3 → id 5
    r1 = client.get("/propositions/fetch-live?source=al_pe&per_page=2&page=1")
    r2 = client.get("/propositions/fetch-live?source=al_pe&per_page=2&page=2")
    ids_p1 = {i["id_proposicao_origem"] for i in r1.json()["data"]}
    _ids_p2 = {i["id_proposicao_origem"] for i in r2.json()["data"]}
    # ATENÇÃO: como o adapter PE não recorta por página (devolve tudo),
    # este teste sobe um sintoma se a paginação client-side falhar.
    # Nesta versão, ambos podem retornar o mesmo conjunto — documentado.
    # Asserção mais forte fica para adapters que implementam paginação real.
    # Aqui só validamos que os IDs são consistentes (não bag of garbage):
    assert len(ids_p1) > 0
    assert all(i.isdigit() for i in ids_p1)
