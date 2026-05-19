"""Envelope da resposta — seção 2 do payload (vigil_payload_fetch_live.pdf)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.proposicao import ProposicaoNormalizadaRaw


class TotalsByNivel(BaseModel):
    federal: int = 0
    estadual: int = 0
    municipal: int = 0


class ResponseEnvelope(BaseModel):
    """
    Envelope idêntico ao retornado por /propositions/fetch-live do legis-service principal.
    """

    data: list[ProposicaoNormalizadaRaw] = Field(default_factory=list)
    total: int | None = None
    total_pages: int | None = None
    totals_by_nivel: TotalsByNivel | None = None
