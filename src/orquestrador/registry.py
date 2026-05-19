"""
Registry de adapters — mapeia ?source=al_xx para a classe do adapter correspondente.

Para adicionar um novo estado:
  1. Criar src/adapters/al_xx.py implementando AdapterBase
  2. Adicionar entrada no dict _ADAPTERS abaixo
"""

from __future__ import annotations

from src.adapters.al_ap import AdapterAP
from src.adapters.al_ba import AdapterBA
from src.adapters.al_ce import AdapterCE
from src.adapters.al_df import AdapterDF
from src.adapters.al_ma import AdapterMA
from src.adapters.al_mt import AdapterMT
from src.adapters.al_pa import AdapterPA
from src.adapters.al_pe import AdapterPE
from src.adapters.al_rj import AdapterRJ
from src.adapters.al_sc import AdapterSC
from src.adapters.al_sp import AdapterSP
from src.adapters.base import AdapterBase

_ADAPTERS: dict[str, type[AdapterBase]] = {
    "al_ap": AdapterAP,
    "al_ba": AdapterBA,
    "al_ce": AdapterCE,
    "al_df": AdapterDF,
    "al_ma": AdapterMA,
    "al_mt": AdapterMT,
    "al_pa": AdapterPA,
    "al_pe": AdapterPE,
    "al_rj": AdapterRJ,
    "al_sc": AdapterSC,
    "al_sp": AdapterSP,
}

# Singletons — adapter é stateless, podemos reusar a instância
_INSTANCIAS: dict[str, AdapterBase] = {}


def get_adapter(source_id: str) -> AdapterBase:
    """Retorna a instância do adapter para o source informado."""
    if source_id not in _ADAPTERS:
        raise KeyError(f"Source desconhecido: {source_id}")
    if source_id not in _INSTANCIAS:
        _INSTANCIAS[source_id] = _ADAPTERS[source_id]()
    return _INSTANCIAS[source_id]


def listar_sources_disponiveis() -> list[str]:
    return list(_ADAPTERS.keys())
