"""
Métricas + traces via OpenTelemetry.

Se OTEL_EXPORTER_OTLP_ENDPOINT estiver definido, exporta para collector.
Caso contrário, instrumentação fica no-op (sem custo adicional).
"""

from __future__ import annotations

from fastapi import FastAPI

from src.config import settings
from src.observability.logger import logger


def setup_metrics(app: FastAPI) -> None:
    """
    Instrumenta a aplicação. Idempotente — pode ser chamado múltiplas vezes.
    Falhas no setup NÃO derrubam a aplicação: apenas logam warning.
    """
    if not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        logger.info("otel_desabilitado", motivo="endpoint vazio")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

        logger.info("otel_configurado", endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    except Exception as e:
        logger.warning("otel_setup_falhou", erro=str(e))
