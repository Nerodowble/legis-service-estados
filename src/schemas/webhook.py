"""
Schemas para o endpoint de webhook / diff.

Filosofia: o serviço é STATELESS — não armazena snapshots. O cliente
(legis-service principal) envia um snapshot do que conhece, e nós
respondemos com a lista de mudanças. Opcionalmente disparamos um POST
para uma callback_url com o mesmo payload de mudanças.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from src.schemas.proposicao import ProposicaoNormalizadaRaw


class SnapshotItem(BaseModel):
    """Um item conhecido pelo cliente, com hash do conteúdo prévio."""

    source: str = Field(..., description="Source da AL (ex: al_pe)")
    id_proposicao_origem: str = Field(..., description="ID nativo da proposição")
    content_hash: str | None = Field(
        None,
        description="Hash sha256 do JSON canônico anterior (opcional). "
        "Se vazio, sempre considerado 'novo'.",
    )


class DiffRequest(BaseModel):
    """
    Request para /webhooks/check: snapshot do cliente + callback opcional.
    """

    snapshot: list[SnapshotItem] = Field(..., max_length=100)
    callback_url: HttpUrl | None = Field(
        None,
        description=(
            "Se fornecida, dispararemos POST com o mesmo payload de resposta "
            "em background (fire-and-forget). Útil pra LegalBot reagir async."
        ),
    )
    incluir_unchanged: bool = Field(
        False,
        description="Se true, response também lista items que NÃO mudaram.",
    )


class DiffEntry(BaseModel):
    """Entrada de mudança detectada (ou explicitamente unchanged)."""

    source: str
    id_proposicao_origem: str
    status_diff: Literal["new", "changed", "unchanged", "not_found", "error"]
    content_hash: str | None = Field(
        None,
        description="Hash atual do conteúdo (mesmo formato do snapshot).",
    )
    proposicao: ProposicaoNormalizadaRaw | None = Field(
        None,
        description="Estado atual da proposição (omitido para unchanged/error).",
    )
    erro: str | None = Field(None, description="Mensagem de erro quando status=error.")


class DiffResponse(BaseModel):
    """Resposta do /webhooks/check."""

    checked: int = Field(..., description="Quantos items foram processados.")
    changes: list[DiffEntry] = Field(default_factory=list)
    summary: dict[str, int] = Field(
        default_factory=dict,
        description="Contagem por status_diff (new/changed/unchanged/not_found/error).",
    )
    callback_scheduled: bool = Field(
        False,
        description="True se callback_url foi enfileirada via BackgroundTasks.",
    )
