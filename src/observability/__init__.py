from src.observability.logger import logger
from src.observability.metrics import setup_metrics
from src.observability.prometheus_metrics import (
    atualizar_gauges_breakers,
    medir_upstream,
)

__all__ = ["atualizar_gauges_breakers", "logger", "medir_upstream", "setup_metrics"]
