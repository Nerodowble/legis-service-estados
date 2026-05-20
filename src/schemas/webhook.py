"""
Schemas para o endpoint de webhook / diff.

Filosofia: o serviço é STATELESS — não armazena snapshots. O cliente
(legis-service principal) envia um snapshot do que conhece, e nós
respondemos com a lista de mudanças. Opcionalmente disparamos um POST
para uma callback_url com o mesmo payload de mudanças.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from src.schemas.proposicao import ProposicaoNormalizadaRaw


class SnapshotItem(BaseModel):
    """Um item conhecido pelo cliente, com hash do conteúdo prévio."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "source": "al_pe",
                    "id_proposicao_origem": "16370",
                    "content_hash": "989a61f9bd6c254c…",
                }
            ]
        }
    )

    source: str = Field(
        ...,
        description="Source da AL (ex: al_pe, al_mt, al_ap, ...)",
        examples=["al_pe", "al_mt", "al_ap"],
    )
    id_proposicao_origem: str = Field(
        ...,
        description="ID nativo da proposição.",
        examples=["16370", "108457", "PL-1-2023"],
    )
    content_hash: str | None = Field(
        None,
        description=(
            "Hash sha256 do JSON canônico anterior (opcional). "
            "Se vazio, sempre considerado 'new'."
        ),
        examples=["989a61f9bd6c254c1f3a3c2d…"],
    )


class DiffRequest(BaseModel):
    """
    Request para /webhooks/check: snapshot do cliente + callback opcional.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "snapshot": [
                        {"source": "al_pe", "id_proposicao_origem": "16370",
                         "content_hash": "989a61f9bd6c254c…"},
                        {"source": "al_mt", "id_proposicao_origem": "172857",
                         "content_hash": None},
                    ],
                    "callback_url": "https://legalbot.com/api/webhooks/proposicoes",
                    "incluir_unchanged": False,
                }
            ]
        }
    )

    snapshot: list[SnapshotItem] = Field(
        ...,
        max_length=100,
        description="Lista de até 100 proposições conhecidas, cada uma com hash opcional.",
    )
    callback_url: HttpUrl | None = Field(
        None,
        description=(
            "Se fornecida, dispararemos POST async com o mesmo payload de resposta. "
            "Útil pra LegalBot reagir sem precisar processar o response síncrono."
        ),
        examples=["https://legalbot.com/api/webhooks/proposicoes"],
    )
    incluir_unchanged: bool = Field(
        False,
        description="Se true, response também lista items que NÃO mudaram.",
    )


class DiffEntry(BaseModel):
    """Entrada de mudança detectada (ou explicitamente unchanged)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "source": "al_pe",
                    "id_proposicao_origem": "16370",
                    "status_diff": "changed",
                    "content_hash": "989a61f9bd6c254c…",
                    "proposicao": {
                        "id_proposicao_origem": "16370",
                        "casa_origem": "Assembleia Legislativa do Estado de Pernambuco",
                        "sigla_tipo": "PEC",
                        "numero": "33",
                        "ano": 2026,
                        "ementa": "Altera a Constituição do Estado de Pernambuco...",
                    },
                    "erro": None,
                }
            ]
        }
    )

    source: str
    id_proposicao_origem: str
    status_diff: Literal["new", "changed", "unchanged", "not_found", "error"] = Field(
        ...,
        description=(
            "Resultado da comparação: "
            "**new** = nunca visto (hash vazio); "
            "**changed** = hash diferente do snapshot; "
            "**unchanged** = bate com snapshot; "
            "**not_found** = upstream não acha mais; "
            "**error** = falha técnica (ver campo `erro`)."
        ),
    )
    content_hash: str | None = Field(
        None, description="Hash atual do conteúdo (sha256 do JSON canônico)."
    )
    proposicao: ProposicaoNormalizadaRaw | None = Field(
        None,
        description="Estado atual da proposição (omitido para unchanged/error).",
    )
    erro: str | None = Field(None, description="Mensagem de erro quando status=error.")


class DiffResponse(BaseModel):
    """Resposta do /webhooks/check."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "checked": 2,
                    "changes": [
                        {
                            "source": "al_pe",
                            "id_proposicao_origem": "16370",
                            "status_diff": "changed",
                            "content_hash": "989a61f9bd6c254c…",
                        },
                        {
                            "source": "al_mt",
                            "id_proposicao_origem": "172857",
                            "status_diff": "new",
                            "content_hash": "a1b2c3d4e5f6…",
                        },
                    ],
                    "summary": {"new": 1, "changed": 1},
                    "callback_scheduled": True,
                }
            ]
        }
    )

    checked: int = Field(..., description="Quantos items foram processados.")
    changes: list[DiffEntry] = Field(default_factory=list)
    summary: dict[str, int] = Field(
        default_factory=dict,
        description="Contagem por status_diff.",
    )
    callback_scheduled: bool = Field(
        False,
        description="True se callback_url foi enfileirada via BackgroundTasks.",
    )
