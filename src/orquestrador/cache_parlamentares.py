"""
Cache compartilhado de mapping {nome → {partido, id}} por AL.

Cada adapter implementa uma função `fetcher` que retorna o mapping atualizado
da sua AL (formato livre). O cache:
  - guarda em memória do processo (singleton)
  - aplica TTL (default 6h — mandato raramente muda intra-dia)
  - faz lookup case-insensitive + tolerante a prefixo "Deputado/Dep."

Zero persistência em disco (mantém princípio stateless do serviço).
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable

# Lock por source para evitar N fetches simultâneos do mesmo upstream
_locks: dict[str, asyncio.Lock] = {}
_caches: dict[str, dict[str, dict[str, str]]] = {}
_timestamps: dict[str, float] = {}

# TTL padrão (seg)
TTL_DEFAULT = 6 * 3600


def _normalizar_nome(nome: str) -> str:
    """Lowercase + remove prefixo Deputado/Dep./Deputada + colapsa espaços."""
    s = (nome or "").strip()
    s = re.sub(r"^Deputad[oa]\.?\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^Dep\.?\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


class CacheParlamentares:
    """
    Singleton de cache por `source_id` com TTL.

    Uso:
        cache = CacheParlamentares("al_pe")
        await cache.warm(fetcher=AdapterPE._fetch_parlamentares)
        info = cache.lookup("Junior Matuto")
        # info = {"partido": "Republicanos", "id": "..."} ou {}
    """

    def __init__(self, source_id: str, ttl: float = TTL_DEFAULT):
        self.source_id = source_id
        self.ttl = ttl
        _locks.setdefault(source_id, asyncio.Lock())

    async def warm(self, fetcher: Callable[[], Awaitable[dict[str, dict[str, str]]]]) -> None:
        """
        Garante cache fresco. Se expirado, chama `fetcher` (com lock).
        Falhas de fetcher tornam o cache um dict vazio até o próximo TTL.
        """
        agora = time.time()
        ts = _timestamps.get(self.source_id, 0)
        if self.source_id in _caches and (agora - ts) < self.ttl:
            return

        async with _locks[self.source_id]:
            # double-check (outra coroutine pode ter populado enquanto esperávamos)
            ts = _timestamps.get(self.source_id, 0)
            if self.source_id in _caches and (agora - ts) < self.ttl:
                return
            try:
                novo = await fetcher()
                if not isinstance(novo, dict):
                    novo = {}
            except Exception:
                novo = {}
            # Normalizar keys
            normalizado: dict[str, dict[str, str]] = {}
            for nome, atributos in novo.items():
                nome_norm = _normalizar_nome(nome)
                if nome_norm:
                    normalizado[nome_norm] = atributos or {}
            _caches[self.source_id] = normalizado
            _timestamps[self.source_id] = time.time()

    def lookup(self, nome: str) -> dict[str, str]:
        """
        Retorna dict de atributos (partido, id, etc.) para o nome dado.
        Match case-insensitive + tolerante a prefixos Deputado/Dep.
        Retorna {} se não encontrar.
        """
        cache = _caches.get(self.source_id, {})
        return cache.get(_normalizar_nome(nome), {})

    def partido_de(self, nome: str) -> str | None:
        info = self.lookup(nome)
        return info.get("partido") or None

    def id_de(self, nome: str) -> str | None:
        info = self.lookup(nome)
        return info.get("id") or None

    def size(self) -> int:
        return len(_caches.get(self.source_id, {}))

    def idade_seg(self) -> float:
        ts = _timestamps.get(self.source_id, 0)
        return time.time() - ts if ts else float("inf")

    def invalidar(self) -> None:
        """Força rebuild no próximo warm()."""
        _caches.pop(self.source_id, None)
        _timestamps.pop(self.source_id, None)
