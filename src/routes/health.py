"""
Health endpoints.

  GET /health                  → liveness simples (sempre 200 se app sobe)
  GET /health/ready            → readiness (deps básicas)
  GET /health/sources          → estado dos circuit breakers (passivo, instantâneo)
  GET /health/sources/{source} → probe ATIVO: faz fetch leve nessa AL e devolve latência
  GET /health/sources/check    → probe ATIVO em todas as 11 ALs em paralelo (DEMORADO)
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, HTTPException

from src.adapters.base import FiltrosBusca
from src.config import settings
from src.orquestrador.circuit_breaker import breakers
from src.orquestrador.registry import get_adapter, listar_sources_disponiveis

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
    Retorna estado do circuit breaker por AL (PASSIVO — não faz fetch).
    closed = ok, open = bloqueado, half-open = testando reconexão.
    """
    estados = breakers.get_estado_resumido()
    return {
        "sources_disponiveis": listar_sources_disponiveis(),
        "breakers": estados,
    }


async def _probe_source(source_id: str) -> dict:
    """Probe ativo: tenta listar 1 item; mede latência e captura erros."""
    inicio = time.perf_counter()
    try:
        adapter = get_adapter(source_id)
    except KeyError:
        return {
            "source": source_id,
            "status": "unknown",
            "error": "source desconhecido",
            "latency_ms": 0,
        }

    try:
        envelope = await adapter.listar(FiltrosBusca(per_page=1))
        latencia = round((time.perf_counter() - inicio) * 1000, 1)
        return {
            "source": source_id,
            "status": "up",
            "items_retornados": len(envelope.data),
            "total_upstream": envelope.total,
            "latency_ms": latencia,
            "breaker": breakers.get(source_id).current_state,
        }
    except Exception as e:
        latencia = round((time.perf_counter() - inicio) * 1000, 1)
        return {
            "source": source_id,
            "status": "down",
            "error": type(e).__name__,
            "detail": str(e)[:200],
            "latency_ms": latencia,
            "breaker": breakers.get(source_id).current_state,
        }


@router.get("/health/sources/check")
async def sources_probe_todos() -> dict:
    """
    Probe ATIVO em TODAS as 11 ALs em paralelo. Demora alguns segundos.
    Útil para dashboard de monitoramento (NÃO usar em hot path).

    IMPORTANTE: declarada ANTES de /{source} para que "check" não case
    como path param do endpoint dinâmico.
    """
    sources = listar_sources_disponiveis()
    resultados = await asyncio.gather(*(_probe_source(s) for s in sources))
    ups = sum(1 for r in resultados if r["status"] == "up")
    return {
        "checked_at_unix": int(time.time()),
        "summary": {
            "total": len(resultados),
            "up": ups,
            "down": len(resultados) - ups,
        },
        "sources": resultados,
    }


@router.get("/health/sources/{source}")
async def source_probe(source: str) -> dict:
    """
    Probe ATIVO: faz fetch leve (per_page=1) na AL especificada.
    Retorna up/down + latência + estado do breaker.
    """
    if source not in listar_sources_disponiveis():
        raise HTTPException(404, f"source desconhecido: {source}")
    return await _probe_source(source)
