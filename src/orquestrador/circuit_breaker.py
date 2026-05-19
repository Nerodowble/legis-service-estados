"""
Circuit breaker por origem (AL).

Se uma AL falhar N vezes em sequência, marca o breaker como "aberto"
e qualquer request seguinte retorna 503 imediatamente por X segundos
(sem nem tentar). Após o tempo, vai para "half-open" e tenta de novo.

pybreaker 1.4.1.call_async() depende do tornado (não usamos). Por isso
expomos `call_async_safe` que replica a lógica do breaker manualmente
para funções `async def`.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import pybreaker

from src.config import settings


class BreakerRegistry:
    """Um CircuitBreaker independente por source_id."""

    def __init__(self):
        self._breakers: dict[str, pybreaker.CircuitBreaker] = {}

    def get(self, source_id: str) -> pybreaker.CircuitBreaker:
        if source_id not in self._breakers:
            self._breakers[source_id] = pybreaker.CircuitBreaker(
                fail_max=settings.CB_FAIL_THRESHOLD,
                reset_timeout=settings.CB_RESET_TIMEOUT_SECONDS,
                name=f"breaker-{source_id}",
            )
        return self._breakers[source_id]

    def get_estado_resumido(self) -> dict[str, str]:
        """Snapshot dos estados — útil para /health/sources."""
        return {sid: br.current_state for sid, br in self._breakers.items()}


breakers = BreakerRegistry()


async def call_async_safe(
    breaker: pybreaker.CircuitBreaker,
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Executa uma corrotina sob o controle do circuit breaker, sem depender
    de tornado. Usa o `state` interno do pybreaker para checar/marcar
    sucessos e falhas — equivale ao que `call()` faz para funções síncronas.
    """
    state = breaker.state  # pybreaker.CircuitBreakerState atual
    state.before_call(func, *args, **kwargs)  # pode raise CircuitBreakerError
    try:
        ret = await func(*args, **kwargs)
    except BaseException as exc:
        # Repassa erro ao state (incrementa contador e abre se atingir limite)
        state._handle_error(exc, reraise=True)
        raise  # _handle_error já re-lança, mas garantimos
    state._handle_success()
    return ret
