"""
Health endpoints.

  GET /health         → liveness simples (sempre 200 se app sobe)
  GET /health/ready   → readiness (deps básicas)
  GET /health/sources → estado de cada AL (breaker state + last check opcional)
"""

from __future__ import annotations

from fastapi import APIRouter

from src.config import settings
from src.orquestrador.circuit_breaker import breakers
from src.orquestrador.registry import listar_sources_disponiveis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


@router.get("/health/ready")
async def ready() -> dict:
    return {"status": "ready"}


@router.get("/health/sources")
async def sources_health() -> dict:
    """
    Retorna estado do circuit breaker por AL.
    closed = ok, open = bloqueado, half-open = testando reconexão.
    """
    estados = breakers.get_estado_resumido()
    return {
        "sources_disponiveis": listar_sources_disponiveis(),
        "breakers": estados,
    }
