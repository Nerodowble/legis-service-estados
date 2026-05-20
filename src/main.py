"""
Entrypoint FastAPI.

Composição:
  - Registra rotas (/propositions, /health)
  - Instrumenta observabilidade (OTEL se configurado)
  - Handlers globais para exceções de domínio
  - CORS aberto para o domínio do front da LegalBot (ajustar em prod)

Stateless: sem conexão a DB, Redis ou disco. Cada request vai direto à AL
através do adapter correspondente.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.config import settings
from src.errors import (
    ALBloqueadaError,
    ALIndisponivelError,
    ParserFalhouError,
    ProposicaoNaoEncontradaError,
)
from src.observability.logger import logger
from src.observability.metrics import setup_metrics
from src.routes import health_router, propositions_router, webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", service=settings.APP_NAME, env=settings.APP_ENV)
    yield
    logger.info("shutdown", service=settings.APP_NAME)


app = FastAPI(
    title="legis-service-estados",
    description=(
        "Microserviço stateless de proposições de Assembleias Legislativas "
        "estaduais brasileiras. Compatível com o contrato de "
        "ProposicaoNormalizadaRaw consumido pelo legis-service principal."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajustar em produção para domínios LegalBot
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# Rotas
app.include_router(health_router)
app.include_router(propositions_router)
app.include_router(webhooks_router)


# Observabilidade
setup_metrics(app)


# Exception handlers globais (uniformizam payloads de erro)
@app.exception_handler(ALBloqueadaError)
async def _al_bloqueada(_: Request, exc: ALBloqueadaError) -> JSONResponse:
    return JSONResponse(
        status_code=451,
        content={"uf": exc.uf, "motivo_legal": exc.motivo_legal, "tipo": "AL_BLOQUEADA"},
    )


@app.exception_handler(ALIndisponivelError)
async def _al_indisponivel(_: Request, exc: ALIndisponivelError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "uf": exc.uf,
            "status": exc.status,
            "motivo": exc.motivo,
            "tipo": "AL_INDISPONIVEL",
        },
    )


@app.exception_handler(ParserFalhouError)
async def _parser_falhou(_: Request, exc: ParserFalhouError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"uf": exc.uf, "detalhe": exc.detalhe, "tipo": "PARSER_FALHOU"},
    )


@app.exception_handler(ProposicaoNaoEncontradaError)
async def _nao_encontrada(_: Request, exc: ProposicaoNaoEncontradaError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "uf": exc.uf,
            "id_fonte": exc.id_fonte,
            "tipo": "PROPOSICAO_NAO_ENCONTRADA",
        },
    )


@app.get("/")
async def root() -> dict:
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "endpoint": "/propositions/fetch-live?source=al_xx&page=1&per_page=20",
    }


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request) -> Response:
    """
    Endpoint Prometheus em formato text/plain.
    Atualiza gauges de circuit breaker antes de devolver o snapshot.

    Suporta cache HTTP via ETag/If-None-Match:
      - Calcula ETag (sha256 do payload, weak)
      - Compara com `If-None-Match` do cliente
      - Devolve 304 Not Modified quando o conteúdo não mudou
        (economiza banda do scrape Prometheus a cada N segundos)
    """
    import hashlib

    from src.observability import atualizar_gauges_breakers
    from src.orquestrador.circuit_breaker import breakers

    atualizar_gauges_breakers(breakers.get_estado_resumido())
    payload = generate_latest()

    # ETag fraco (W/ prefix) — scrape do Prometheus muda a cada request
    # de qualquer counter/histogram, mas se nenhum métrica mudou desde a
    # última coleta, o consumidor pode pular o parse.
    etag_val = hashlib.sha256(payload).hexdigest()[:16]
    etag = f'W/"{etag_val}"'

    if_none_match = request.headers.get("if-none-match", "")
    if if_none_match and if_none_match.strip() == etag:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "max-age=5"})

    return Response(
        content=payload,
        media_type=CONTENT_TYPE_LATEST,
        headers={"ETag": etag, "Cache-Control": "max-age=5"},
    )
