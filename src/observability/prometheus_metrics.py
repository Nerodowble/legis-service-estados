"""
Métricas Prometheus expostas em /metrics.

Convenções de nome (Prometheus best practices):
  - sufixo _total para Counter
  - sufixo _seconds para histogramas de tempo
  - labels minúsculas (source, status_code)

Cardinalidade controlada: labels com valor fixo conhecido (sources_disponiveis).
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from prometheus_client import Counter, Gauge, Histogram

# ─── Counters ────────────────────────────────────────────────────────────

propositions_requests_total = Counter(
    "legis_estados_requests_total",
    "Total de requests para um source (qualquer endpoint).",
    labelnames=("source", "operacao", "outcome"),
)

propositions_items_returned_total = Counter(
    "legis_estados_items_returned_total",
    "Total acumulado de items retornados (após filtros e paginação).",
    labelnames=("source", "operacao"),
)

upstream_errors_total = Counter(
    "legis_estados_upstream_errors_total",
    "Erros upstream por tipo (timeout, connect, http_5xx, parser).",
    labelnames=("source", "tipo"),
)

# ─── Histograms ──────────────────────────────────────────────────────────

upstream_duration_seconds = Histogram(
    "legis_estados_upstream_duration_seconds",
    "Latência do fetch upstream (adapter → fonte).",
    labelnames=("source", "operacao"),
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# ─── Gauges ──────────────────────────────────────────────────────────────

circuit_breaker_state = Gauge(
    "legis_estados_circuit_breaker_state",
    "Estado do circuit breaker: 0=closed, 1=half_open, 2=open.",
    labelnames=("source",),
)


_BREAKER_STATE_MAP = {"closed": 0, "half-open": 1, "open": 2}


def atualizar_gauges_breakers(estados: dict[str, str]) -> None:
    """Atualiza o gauge de circuit breaker a partir do dict retornado por
    BreakerRegistry.get_estado_resumido()."""
    for source, estado in estados.items():
        valor = _BREAKER_STATE_MAP.get(estado, -1)
        if valor >= 0:
            circuit_breaker_state.labels(source=source).set(valor)


@contextmanager
def medir_upstream(source: str, operacao: str = "listar"):
    """
    Context manager que mede latência e registra outcome.

    Uso:
        with medir_upstream("al_pe", "listar") as ctx:
            envelope = await adapter.listar(filtros)
            ctx.items = len(envelope.data)
    """

    class _Ctx:
        items: int = 0
        outcome: str = "ok"
        erro_tipo: str | None = None

    ctx = _Ctx()
    inicio = time.perf_counter()
    try:
        yield ctx
    except Exception as e:
        ctx.outcome = "erro"
        ctx.erro_tipo = type(e).__name__
        raise
    finally:
        duracao = time.perf_counter() - inicio
        upstream_duration_seconds.labels(source=source, operacao=operacao).observe(duracao)
        propositions_requests_total.labels(
            source=source, operacao=operacao, outcome=ctx.outcome
        ).inc()
        if ctx.items:
            propositions_items_returned_total.labels(source=source, operacao=operacao).inc(
                ctx.items
            )
        if ctx.erro_tipo:
            upstream_errors_total.labels(source=source, tipo=ctx.erro_tipo).inc()
