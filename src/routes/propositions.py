"""
Rota /propositions/fetch-live — compatível com o contrato esperado pelo
legis-service principal (vigil_payload_fetch_live).

Query params suportados:
  source: identificador da AL (al_ap, al_ba, ...) ou "al_estados" (agrega todos)
  page, per_page: paginação
  ano, keyword, autor, numero, tipo, tema: filtros
  data_inicio, data_fim: janela temporal (YYYY-MM-DD)

A camada de orquestração aplica:
  - rate limiter por origem
  - circuit breaker por origem
  - retry exponencial em falhas transitórias
"""

from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from src.adapters.base import FiltrosBusca
from src.errors import (
    ALBloqueadaError,
    ALIndisponivelError,
    ParserFalhouError,
    ProposicaoNaoEncontradaError,
)
from src.observability.logger import logger
from src.orquestrador.circuit_breaker import breakers, call_async_safe
from src.orquestrador.rate_limiter import rate_limiters
from src.orquestrador.registry import get_adapter, listar_sources_disponiveis
from src.schemas import ProposicaoNormalizadaRaw, ResponseEnvelope, TotalsByNivel

router = APIRouter(prefix="/propositions", tags=["propositions"])

SourceLiteral = Literal[
    "al_ap", "al_ba", "al_ce", "al_df", "al_ma", "al_mt",
    "al_pa", "al_pe", "al_rj", "al_sc", "al_sp",
    "al_estados",
]


@router.get("/fetch-live", response_model=ResponseEnvelope)
async def fetch_live(
    source: SourceLiteral = Query(..., description="Source da AL ou 'al_estados' para agregar"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ano: int | None = Query(None),
    keyword: str | None = Query(None),
    autor: str | None = Query(None),
    numero: str | None = Query(None),
    tipo: str | None = Query(None, description="Sigla, ex: PL, PEC, IND"),
    tema: str | None = Query(None),
    data_inicio: str | None = Query(None, description="YYYY-MM-DD"),
    data_fim: str | None = Query(None, description="YYYY-MM-DD"),
) -> ResponseEnvelope:
    filtros = FiltrosBusca(
        page=page,
        per_page=per_page,
        ano=ano,
        keyword=keyword,
        autor=autor,
        numero=numero,
        tipo=tipo,
        tema=tema,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    if source == "al_estados":
        return await _fetch_agregado(filtros)

    return await _fetch_single(source, filtros)


@router.get("/fetch-live/{source}/{id_proposicao}", response_model=ResponseEnvelope)
async def fetch_detalhe(source: SourceLiteral, id_proposicao: str) -> ResponseEnvelope:
    """Busca uma proposição específica pelo ID nativo da AL."""
    if source == "al_estados":
        raise HTTPException(400, "Detalhe exige source específico (não 'al_estados')")

    try:
        adapter = get_adapter(source)
    except KeyError as e:
        raise HTTPException(404, f"Source desconhecido: {source}") from e

    limiter = rate_limiters.get(source)
    breaker = breakers.get(source)

    async with limiter:
        try:
            envelope = await call_async_safe(breaker, adapter.detalhe, id_proposicao)
        except ProposicaoNaoEncontradaError:
            raise HTTPException(404, f"Proposição {id_proposicao} não encontrada em {source}") from None
        except ALBloqueadaError as e:
            raise HTTPException(451, {"uf": e.uf, "motivo_legal": e.motivo_legal}) from e
        except ALIndisponivelError as e:
            raise HTTPException(503, {"uf": e.uf, "status": e.status, "motivo": e.motivo}) from e
        except ParserFalhouError as e:
            raise HTTPException(502, {"uf": e.uf, "detalhe": e.detalhe}) from e

    return envelope


async def _fetch_single(source: str, filtros: FiltrosBusca) -> ResponseEnvelope:
    try:
        adapter = get_adapter(source)
    except KeyError as e:
        raise HTTPException(404, f"Source desconhecido: {source}") from e

    limiter = rate_limiters.get(source)
    breaker = breakers.get(source)

    async with limiter:
        try:
            envelope = await call_async_safe(breaker, adapter.listar, filtros)
        except ALBloqueadaError as e:
            raise HTTPException(451, {"uf": e.uf, "motivo_legal": e.motivo_legal}) from e
        except ALIndisponivelError as e:
            logger.warning("al_indisponivel", source=source, status=e.status, motivo=e.motivo)
            raise HTTPException(503, {"uf": e.uf, "status": e.status, "motivo": e.motivo}) from e
        except ParserFalhouError as e:
            logger.error("parser_falhou", source=source, detalhe=e.detalhe)
            raise HTTPException(502, {"uf": e.uf, "detalhe": e.detalhe}) from e
        except Exception as e:
            logger.exception("erro_inesperado", source=source, erro=str(e))
            raise HTTPException(500, "Erro inesperado no adapter") from e

    return envelope


async def _fetch_agregado(filtros: FiltrosBusca) -> ResponseEnvelope:
    """
    source=al_estados: dispara todas as ALs em paralelo (com fan-out limitado)
    e mescla resultados. Falhas individuais NÃO derrubam o agregado.
    """
    sources = listar_sources_disponiveis()
    tarefas = [_fetch_safe(sid, filtros) for sid in sources]
    resultados = await asyncio.gather(*tarefas)

    todos_items: list[ProposicaoNormalizadaRaw] = []
    total_agregado = 0
    for envelope in resultados:
        if envelope is None:
            continue
        todos_items.extend(envelope.data)
        total_agregado += envelope.total or 0

    return ResponseEnvelope(
        data=todos_items[: filtros.per_page * 27],  # bound defensivo
        total=total_agregado,
        total_pages=1,
        totals_by_nivel=TotalsByNivel(estadual=len(todos_items)),
    )


async def _fetch_safe(source_id: str, filtros: FiltrosBusca) -> ResponseEnvelope | None:
    """Wrapper que captura todas as exceções para não derrubar o agregado."""
    try:
        adapter = get_adapter(source_id)
        limiter = rate_limiters.get(source_id)
        breaker = breakers.get(source_id)
        async with limiter:
            return await call_async_safe(breaker, adapter.listar, filtros)
    except Exception as e:
        logger.warning("al_estados_skip", source=source_id, erro=str(e))
        return None
