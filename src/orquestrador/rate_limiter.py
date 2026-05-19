"""
Rate limiter por origem (AL).

Cada AL tem seu próprio limit independente. Um usuário consultando SE
não pode afetar outro consultando BA. Limites baseados na robustez
observada de cada fonte.
"""

from __future__ import annotations

from aiolimiter import AsyncLimiter

from src.config import settings

# Limites em requests por segundo, por AL
# Ajustado pelo multiplicador global settings.RATE_LIMIT_FATOR
_LIMITES_BASE: dict[str, float] = {
    # APIs robustas + HTML SSR modernos
    "al_ap": 2.0,
    "al_ba": 1.5,
    "al_df": 2.0,
    "al_ma": 2.0,
    "al_mt": 2.0,
    "al_pe": 2.0,
    "al_sc": 1.5,
    "al_sp": 0.5,  # dumps grandes — bem conservador

    # Legados antigos — mais conservador
    "al_ce": 0.5,  # PHP anos 2000
    "al_rj": 0.5,  # Lotus Notes anos 90
    "al_pa": 1.0,  # ASP.NET com postback
}


class RateLimiters:
    """Mantém um AsyncLimiter por source_id."""

    def __init__(self):
        self._limiters: dict[str, AsyncLimiter] = {}
        for source, rps in _LIMITES_BASE.items():
            rps_efetivo = max(rps * settings.RATE_LIMIT_FATOR, 0.1)
            # AsyncLimiter(max_rate, time_period) -> N requests per time_period seconds
            self._limiters[source] = AsyncLimiter(max_rate=rps_efetivo * 10, time_period=10)

    def get(self, source_id: str) -> AsyncLimiter:
        if source_id not in self._limiters:
            # default conservador
            self._limiters[source_id] = AsyncLimiter(max_rate=5, time_period=10)
        return self._limiters[source_id]


rate_limiters = RateLimiters()
