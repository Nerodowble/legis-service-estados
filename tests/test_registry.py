"""Testes do registry — todos os 11 adapters devem estar registrados."""

from src.orquestrador.registry import get_adapter, listar_sources_disponiveis


def test_registry_tem_11_adapters():
    sources = listar_sources_disponiveis()
    assert len(sources) == 11
    esperados = {
        "al_ap", "al_ba", "al_ce", "al_df", "al_ma", "al_mt",
        "al_pa", "al_pe", "al_rj", "al_sc", "al_sp",
    }
    assert set(sources) == esperados


def test_get_adapter_retorna_singleton():
    a1 = get_adapter("al_mt")
    a2 = get_adapter("al_mt")
    assert a1 is a2


def test_get_adapter_invalido_levanta_keyerror():
    import pytest
    with pytest.raises(KeyError):
        get_adapter("al_xx_inexistente")


def test_todos_adapters_tem_metadados_obrigatorios():
    for source_id in listar_sources_disponiveis():
        adapter = get_adapter(source_id)
        assert adapter.UF, f"{source_id} sem UF"
        assert adapter.NOME_CASA, f"{source_id} sem NOME_CASA"
        assert adapter.SOURCE_ID == source_id, f"{source_id} SOURCE_ID inconsistente"
        assert adapter.HOST_PRINCIPAL.startswith("http"), f"{source_id} HOST_PRINCIPAL invalido"
