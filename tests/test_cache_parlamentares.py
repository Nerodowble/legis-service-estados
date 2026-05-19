"""
Testes do helper CacheParlamentares.

Cobre:
  - cache vazio inicialmente
  - warm() popula via fetcher
  - lookup case-insensitive
  - lookup tolerante a prefixo "Deputado/Dep."
  - TTL expira e força rebuild
  - fetcher que lança exception → cache vazio (não propaga)
  - invalidar() força rebuild
"""

from __future__ import annotations

import time

import pytest

from src.orquestrador.cache_parlamentares import (
    CacheParlamentares,
    _normalizar_nome,
)


def test_normalizar_remove_prefixo_deputado():
    assert _normalizar_nome("Deputado João da Silva") == "joão da silva"
    assert _normalizar_nome("Deputada Maria Souza") == "maria souza"
    assert _normalizar_nome("Dep. Carlos") == "carlos"
    assert _normalizar_nome("João") == "joão"


def test_normalizar_colapsa_espacos():
    assert _normalizar_nome("  João   da   Silva  ") == "joão da silva"


@pytest.mark.asyncio
async def test_warm_popula_e_lookup_funciona():
    cache = CacheParlamentares("al_test_1", ttl=60)
    cache.invalidar()

    async def fetcher():
        return {
            "Maria Silva": {"partido": "PT", "id": "1"},
            "João Pereira": {"partido": "PP", "id": "2"},
        }

    await cache.warm(fetcher)
    assert cache.size() == 2
    assert cache.partido_de("Maria Silva") == "PT"
    assert cache.partido_de("MARIA SILVA") == "PT"  # case-insensitive
    assert cache.partido_de("Deputada Maria Silva") == "PT"  # prefixo
    assert cache.id_de("João Pereira") == "2"


@pytest.mark.asyncio
async def test_lookup_inexistente_retorna_none():
    cache = CacheParlamentares("al_test_2")
    cache.invalidar()

    async def fetcher():
        return {"X": {"partido": "Y"}}

    await cache.warm(fetcher)
    assert cache.partido_de("Inexistente") is None
    assert cache.lookup("Inexistente") == {}


@pytest.mark.asyncio
async def test_fetcher_exception_resulta_cache_vazio():
    cache = CacheParlamentares("al_test_3")
    cache.invalidar()

    async def fetcher_quebrado():
        raise RuntimeError("upstream offline")

    await cache.warm(fetcher_quebrado)
    assert cache.size() == 0
    assert cache.partido_de("Qualquer") is None


@pytest.mark.asyncio
async def test_ttl_expira_e_re_fetcha():
    cache = CacheParlamentares("al_test_4", ttl=0.1)
    cache.invalidar()

    chamadas = {"count": 0}

    async def fetcher():
        chamadas["count"] += 1
        return {"X": {"partido": f"v{chamadas['count']}"}}

    await cache.warm(fetcher)
    assert chamadas["count"] == 1
    assert cache.partido_de("X") == "v1"

    # Segunda chamada dentro do TTL: não rebuilds
    await cache.warm(fetcher)
    assert chamadas["count"] == 1

    # Aguardar expiração
    time.sleep(0.15)
    await cache.warm(fetcher)
    assert chamadas["count"] == 2
    assert cache.partido_de("X") == "v2"


@pytest.mark.asyncio
async def test_caches_de_sources_diferentes_sao_independentes():
    cache_a = CacheParlamentares("al_test_a")
    cache_b = CacheParlamentares("al_test_b")
    cache_a.invalidar()
    cache_b.invalidar()

    async def f_a():
        return {"Alice": {"partido": "AAA"}}

    async def f_b():
        return {"Bob": {"partido": "BBB"}}

    await cache_a.warm(f_a)
    await cache_b.warm(f_b)

    assert cache_a.partido_de("Alice") == "AAA"
    assert cache_a.partido_de("Bob") is None
    assert cache_b.partido_de("Bob") == "BBB"
    assert cache_b.partido_de("Alice") is None
