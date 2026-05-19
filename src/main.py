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
from fastapi.responses import JSONResponse

from src.config import settings
from src.errors import (
    ALBloqueadaError,
    ALIndisponivelError,
    ParserFalhouError,
    ProposicaoNaoEncontradaError,
)
from src.observability.logger import logger
from src.observability.metrics import setup_metrics
from src.routes import health_router, propositions_router


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
        "endpoint": "/propositions/fetch-live?source=al_xx&page=1&per_page=20",
    }
