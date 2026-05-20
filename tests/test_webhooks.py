"""
Testes do endpoint POST /webhooks/check.

Cobre:
  - snapshot vazio → 200 com checked=0
  - source inválido → 422
  - item sem hash → status_diff=new
  - item com hash igual ao atual → status_diff=unchanged
  - item com hash diferente → status_diff=changed
  - item não encontrado no upstream → status_diff=not_found
  - callback_url → callback_scheduled=true + POST async disparado
"""

from __future__ import annotations

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from src.main import app
from src.routes.webhooks import _hash_proposicao
from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


XML_PE_UM_PROJETO = b"""<?xml version="1.0" encoding="UTF-8"?>
<projetos>
  <projeto docid="13539" numero="3" ano="2024"
           tipo="PROJETO DE LEI ORDINARIA"
           ementa="Susta o Decreto X" dataPublicacao="14/06/2024">
    <autores><autor nome="Coronel Alberto" tipo="DEPUTADO"/></autores>
  </projeto>
</projetos>"""


def _mock_alepe_endpoints():
    """Mock dos 3 endpoints do detalhe ALEPE (projetos/indicacoes/requerimentos)."""
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/").mock(
        return_value=Response(200, content=XML_PE_UM_PROJETO,
                              headers={"Content-Type": "application/xml"})
    )
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/parlamentares/").mock(
        return_value=Response(200, json=[])
    )
    for ep in ("indicacoes", "requerimentos"):
        respx.get(f"https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/{ep}/").mock(
            return_value=Response(404, content=b"")
        )


def test_webhook_check_snapshot_vazio(client: TestClient):
    r = client.post("/webhooks/check", json={"snapshot": []})
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] == 0
    assert body["changes"] == []
    assert body["callback_scheduled"] is False


def test_webhook_check_source_invalido(client: TestClient):
    r = client.post(
        "/webhooks/check",
        json={"snapshot": [
            {"source": "al_xx_falso", "id_proposicao_origem": "1"}
        ]},
    )
    assert r.status_code == 422


@respx.mock
def test_webhook_check_item_sem_hash_marca_new(client: TestClient):
    _mock_alepe_endpoints()
    r = client.post(
        "/webhooks/check",
        json={"snapshot": [
            {"source": "al_pe", "id_proposicao_origem": "13539"}
        ]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] == 1
    assert len(body["changes"]) == 1
    entry = body["changes"][0]
    assert entry["status_diff"] == "new"
    assert entry["content_hash"] is not None
    assert entry["proposicao"]["id_proposicao_origem"] == "13539"


@respx.mock
def test_webhook_check_item_com_hash_igual_marca_unchanged(client: TestClient):
    _mock_alepe_endpoints()

    # Primeiro fetch para descobrir o hash atual
    r1 = client.post(
        "/webhooks/check",
        json={"snapshot": [
            {"source": "al_pe", "id_proposicao_origem": "13539"}
        ]},
    )
    hash_atual = r1.json()["changes"][0]["content_hash"]

    # Segunda chamada com o mesmo hash → unchanged (omitido do response default)
    r2 = client.post(
        "/webhooks/check",
        json={"snapshot": [
            {"source": "al_pe", "id_proposicao_origem": "13539",
             "content_hash": hash_atual}
        ]},
    )
    body2 = r2.json()
    assert body2["checked"] == 1
    assert body2["changes"] == []  # default não inclui unchanged
    assert body2["summary"]["unchanged"] == 1


@respx.mock
def test_webhook_check_incluir_unchanged_lista_todos(client: TestClient):
    _mock_alepe_endpoints()

    r1 = client.post(
        "/webhooks/check",
        json={"snapshot": [
            {"source": "al_pe", "id_proposicao_origem": "13539"}
        ]},
    )
    hash_atual = r1.json()["changes"][0]["content_hash"]

    r2 = client.post(
        "/webhooks/check",
        json={
            "snapshot": [
                {"source": "al_pe", "id_proposicao_origem": "13539",
                 "content_hash": hash_atual}
            ],
            "incluir_unchanged": True,
        },
    )
    body2 = r2.json()
    assert len(body2["changes"]) == 1
    assert body2["changes"][0]["status_diff"] == "unchanged"


@respx.mock
def test_webhook_check_hash_diferente_marca_changed(client: TestClient):
    _mock_alepe_endpoints()
    r = client.post(
        "/webhooks/check",
        json={"snapshot": [
            {"source": "al_pe", "id_proposicao_origem": "13539",
             "content_hash": "hash_antigo_qualquer_xyz"}
        ]},
    )
    body = r.json()
    assert body["changes"][0]["status_diff"] == "changed"
    assert body["changes"][0]["proposicao"] is not None
    assert body["changes"][0]["content_hash"] != "hash_antigo_qualquer_xyz"


@respx.mock
def test_webhook_check_item_inexistente_marca_not_found(client: TestClient):
    # ALEPE responde com lista vazia em todos os 3 endpoints
    for ep in ("projetos", "indicacoes", "requerimentos"):
        respx.get(f"https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/{ep}/").mock(
            return_value=Response(
                200,
                content=b'<?xml version="1.0"?><projetos></projetos>',
                headers={"Content-Type": "application/xml"},
            )
        )
    respx.get("https://dadosabertos.alepe.pe.gov.br/api/v1/parlamentares/").mock(
        return_value=Response(200, json=[])
    )

    r = client.post(
        "/webhooks/check",
        json={"snapshot": [
            {"source": "al_pe", "id_proposicao_origem": "99999"}
        ]},
    )
    body = r.json()
    assert body["changes"][0]["status_diff"] == "not_found"


@respx.mock
def test_webhook_check_callback_url_dispara_post(client: TestClient):
    _mock_alepe_endpoints()
    callback_route = respx.post("https://example.com/legalbot-webhook").mock(
        return_value=Response(200, json={"ok": True})
    )

    r = client.post(
        "/webhooks/check",
        json={
            "snapshot": [
                {"source": "al_pe", "id_proposicao_origem": "13539"}
            ],
            "callback_url": "https://example.com/legalbot-webhook",
        },
    )
    assert r.status_code == 200
    assert r.json()["callback_scheduled"] is True
    # BackgroundTasks no TestClient são sincronizadas após o response
    # Aguardar um tick para o background task disparar
    # (TestClient já aguarda BackgroundTasks por padrão no FastAPI)
    assert callback_route.called


def test_hash_proposicao_estavel_e_ignora_campos_volateis():
    """Mesma proposição com 'monitor' ou 'termometro' diferentes → mesmo hash."""
    p1 = ProposicaoNormalizadaRaw(
        id_proposicao_origem="X",
        casa_origem="Y",
        sigla_tipo="PL",
        numero="1",
        ano=2024,
        ementa="ementa",
        autores=[Autor(nome="A", uf="PE", tipo="Deputado")],
        dados_adicionais=DadosAdicionais(casaIdentificadora="ALEPE", enteIdentificador="PE",
                                          tipoConteudo="Proposição", tipoDocumento="PL"),
        nivel_federativo="estadual",
        monitor=False,
        termometro=None,
    )
    p2 = p1.model_copy(update={"monitor": True, "termometro": 85.0})
    assert _hash_proposicao(p1) == _hash_proposicao(p2)
