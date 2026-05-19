# Lazy re-exports: importar via `from src.orquestrador.registry import ...`
# evita inicializar registry (que carrega 11 adapters) só por importar um
# submódulo "leve" como cache_parlamentares.
__all__ = ["get_adapter", "listar_sources_disponiveis"]


def __getattr__(nome: str):
    # PEP 562: lazy module attribute lookup
    if nome in ("get_adapter", "listar_sources_disponiveis"):
        from src.orquestrador import registry

        return getattr(registry, nome)
    raise AttributeError(f"module 'src.orquestrador' has no attribute {nome!r}")
