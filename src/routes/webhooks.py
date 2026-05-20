"""
Endpoints de webhook / diff.

  POST /webhooks/check
    Recebe um snapshot {source, id, content_hash}[] e devolve quais
    mudaram. Opcionalmente dispara POST async para callback_url.

Princípio: o serviço continua STATELESS. Quem mantém estado é o cliente
(o legis-service principal armazena hashes dos PLs monitorados pelos
usuários LegalBot). Aqui só comparamos contra a fonte ao vivo.
"""

from __future__ import annotations

import asyncio
import hashlib
import json

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.config import settings
from src.errors import ProposicaoNaoEncontradaError
from src.observability.logger import logger
from src.orquestrador.circuit_breaker import breakers, call_async_safe
from src.orquestrador.rate_limiter import rate_limiters
from src.orquestrador.registry import get_adapter, listar_sources_disponiveis
from src.schemas.proposicao import ProposicaoNormalizadaRaw
from src.schemas.webhook import (
    DiffEntry,
    DiffRequest,
    DiffResponse,
    SnapshotItem,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _hash_proposicao(p: ProposicaoNormalizadaRaw) -> str:
    """
    Hash sha256 do JSON canônico da proposição.

    Excluímos campos que mudam por design entre snapshots
    (monitor, campos VIGIL — calculados externamente).
    """
    payload = p.model_dump(
        exclude={"monitor", "termometro", "score_risco", "indicador_alta_prob"}
    )
    canonico = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


async def _verificar_item(item_snap: SnapshotItem) -> DiffEntry:
    """Busca a proposição atual e compara com o hash do snapshot."""
    source = item_snap.source
    id_origem = item_snap.id_proposicao_origem

    try:
        adapter = get_adapter(source)
    except KeyError:
        return DiffEntry(
            source=source,
            id_proposicao_origem=id_origem,
            status_diff="error",
            erro=f"source desconhecido: {source}",
        )

    limiter = rate_limiters.get(source)
    breaker = breakers.get(source)
    try:
        async with limiter:
            envelope = await call_async_safe(breaker, adapter.detalhe, id_origem)
    except ProposicaoNaoEncontradaError:
        return DiffEntry(
            source=source,
            id_proposicao_origem=id_origem,
            status_diff="not_found",
        )
    except Exception as e:
        return DiffEntry(
            source=source,
            id_proposicao_origem=id_origem,
            status_diff="error",
            erro=str(e)[:200],
        )

    if not envelope.data:
        return DiffEntry(
            source=source,
            id_proposicao_origem=id_origem,
            status_diff="not_found",
        )

    prop = envelope.data[0]
    hash_atual = _hash_proposicao(prop)

    if not item_snap.content_hash:
        status = "new"
    elif item_snap.content_hash == hash_atual:
        status = "unchanged"
    else:
        status = "changed"

    return DiffEntry(
        source=source,
        id_proposicao_origem=id_origem,
        status_diff=status,
        content_hash=hash_atual,
        proposicao=prop if status != "unchanged" else None,
    )


async def _disparar_callback(callback_url: str, payload: dict) -> None:
    """POST assíncrono fire-and-forget. Falhas só vão pro log."""
    try:
        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
        ) as client:
            r = await client.post(callback_url, json=payload)
            logger.info(
                "webhook_callback_enviado",
                url=callback_url,
                status=r.status_code,
                bytes=len(r.content),
            )
    except Exception as e:
        logger.warning(
            "webhook_callback_falhou",
            url=callback_url,
            erro=str(e),
        )


@router.post(
    "/check",
    response_model=DiffResponse,
    summary="Diff de proposições conhecidas vs estado atual",
    description=(
        "Recebe um snapshot do cliente (legis-service principal monitora "
        "PLs por usuário) e devolve quais mudaram desde a última verificação.\n\n"
        "**Stateless**: o serviço não armazena snapshots. Quem mantém estado "
        "é o cliente (envia `content_hash` do que conhece, recebe diff).\n\n"
        "**Callback opcional**: se `callback_url` for fornecida, dispararemos "
        "um POST async (BackgroundTasks) com o mesmo payload de response. "
        "Útil para reagir a mudanças sem manter conexão.\n\n"
        "**Limite**: snapshot máx 100 items por request (controle de fan-out)."
    ),
    responses={
        200: {"description": "Diff calculado; ver `changes` e `summary`."},
        422: {"description": "Validação (source desconhecido, snapshot > 100, callback_url inválida)."},
    },
)
async def webhook_check(req: DiffRequest, bg: BackgroundTasks) -> DiffResponse:
    sources_validos = set(listar_sources_disponiveis())
    for item in req.snapshot:
        if item.source not in sources_validos:
            raise HTTPException(422, f"source desconhecido: {item.source}")

    # Fan-out paralelo
    resultados = await asyncio.gather(
        *(_verificar_item(s) for s in req.snapshot),
        return_exceptions=False,
    )

    # Filtrar resposta conforme flag
    if req.incluir_unchanged:
        changes = list(resultados)
    else:
        changes = [r for r in resultados if r.status_diff != "unchanged"]

    summary: dict[str, int] = {}
    for r in resultados:
        summary[r.status_diff] = summary.get(r.status_diff, 0) + 1

    response = DiffResponse(
        checked=len(resultados),
        changes=changes,
        summary=summary,
        callback_scheduled=False,
    )

    # Callback opcional via BackgroundTasks (não bloqueia o response)
    if req.callback_url:
        bg.add_task(
            _disparar_callback,
            str(req.callback_url),
            response.model_dump(mode="json"),
        )
        response.callback_scheduled = True

    return response
