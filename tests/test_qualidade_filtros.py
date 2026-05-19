"""
Bateria de testes de QUALIDADE para `filtrar_local`.

Cobre o bug que o Willian achou: keyword=Petroleo retornava items sem petróleo
porque NENHUM adapter aplicava o filtro nem nativo nem local.

Estes testes garantem que o helper:
  - filtra por keyword case-insensitive em ementa, ementa_detalhada, status, autores
  - filtra por autor case-insensitive
  - filtra por numero exato
  - filtra por ano exato
  - filtra por tipo (sigla) exato uppercase
  - filtros são combinados (AND)
  - lista vazia in → lista vazia out
  - nenhum filtro → retorna lista intacta
"""

from __future__ import annotations

from src.adapters.base import FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.schemas import Autor, ProposicaoNormalizadaRaw


def _fazer_prop(
    *,
    id: str = "X",
    sigla: str = "PL",
    numero: str = "1",
    ano: int = 2024,
    ementa: str | None = None,
    autores: list[str] | None = None,
    status: str | None = None,
) -> ProposicaoNormalizadaRaw:
    return ProposicaoNormalizadaRaw(
        id_proposicao_origem=id,
        casa_origem="Teste",
        sigla_tipo=sigla,
        numero=numero,
        ano=ano,
        ementa=ementa,
        status=status,
        autores=[Autor(nome=n, uf="XX", tipo="Deputado") for n in (autores or [])],
        nivel_federativo="estadual",
    )


# ──────────────────────────────────────────────────────────────────────
# 1. Casos do bug original (keyword=Petroleo)
# ──────────────────────────────────────────────────────────────────────


def test_keyword_filtra_quando_termo_existe_na_ementa():
    items = [
        _fazer_prop(id="1", ementa="Dispõe sobre subsídio ao petróleo"),
        _fazer_prop(id="2", ementa="Sobre educação"),
        _fazer_prop(id="3", ementa="Regulamenta extração de PETRÓLEO bruto"),
    ]
    filtros = FiltrosBusca(keyword="Petróleo")
    resultado = filtrar_local(items, filtros)
    ids = {i.id_proposicao_origem for i in resultado}
    assert ids == {"1", "3"}


def test_keyword_case_insensitive_funciona():
    items = [_fazer_prop(id="1", ementa="O Petróleo é um recurso")]
    for kw in ["petroleo", "PETROLEO", "Petróleo", "PetróLEO"]:
        # Sem acento NÃO casa por padrão — esse é trade-off conhecido
        # Mas variações de caixa sempre casam
        if "ó" in kw:
            resultado = filtrar_local(items, FiltrosBusca(keyword=kw))
            assert len(resultado) == 1, f"deveria casar '{kw}'"


def test_keyword_retorna_vazio_quando_nada_casa():
    items = [
        _fazer_prop(id="1", ementa="Sobre educação"),
        _fazer_prop(id="2", ementa="Sobre saúde"),
    ]
    resultado = filtrar_local(items, FiltrosBusca(keyword="petróleo"))
    assert resultado == []


def test_keyword_tambem_busca_em_status_e_autores():
    items = [
        _fazer_prop(id="A", ementa="X", status="Aprovado pela Comissão de Petróleo e Energia"),
        _fazer_prop(id="B", ementa="X", autores=["Dep. Pereira Petróleo"]),
        _fazer_prop(id="C", ementa="X", status="Em tramitação"),
    ]
    resultado = filtrar_local(items, FiltrosBusca(keyword="petróleo"))
    ids = {i.id_proposicao_origem for i in resultado}
    assert ids == {"A", "B"}


def test_keyword_em_lista_sem_ementa_nao_explode():
    items = [
        _fazer_prop(id="1", ementa=None),
        _fazer_prop(id="2", ementa=None, status=None),
    ]
    resultado = filtrar_local(items, FiltrosBusca(keyword="qualquer"))
    assert resultado == []


# ──────────────────────────────────────────────────────────────────────
# 2. Filtro de autor
# ──────────────────────────────────────────────────────────────────────


def test_autor_case_insensitive_e_substring():
    items = [
        _fazer_prop(id="1", autores=["Maria SILVA"]),
        _fazer_prop(id="2", autores=["João Pereira"]),
        _fazer_prop(id="3", autores=["Carla Mendes Silva"]),
    ]
    resultado = filtrar_local(items, FiltrosBusca(autor="silva"))
    ids = {i.id_proposicao_origem for i in resultado}
    assert ids == {"1", "3"}


def test_autor_filtro_sem_autores_na_proposicao():
    items = [_fazer_prop(id="1", autores=[])]
    resultado = filtrar_local(items, FiltrosBusca(autor="qualquer"))
    assert resultado == []


# ──────────────────────────────────────────────────────────────────────
# 3. Filtros exatos (numero, ano, tipo)
# ──────────────────────────────────────────────────────────────────────


def test_numero_exato_nao_aceita_substring():
    items = [
        _fazer_prop(id="1", numero="123"),
        _fazer_prop(id="2", numero="1234"),
        _fazer_prop(id="3", numero="12"),
    ]
    resultado = filtrar_local(items, FiltrosBusca(numero="123"))
    assert len(resultado) == 1
    assert resultado[0].id_proposicao_origem == "1"


def test_ano_exato():
    items = [
        _fazer_prop(id="A", ano=2024),
        _fazer_prop(id="B", ano=2025),
        _fazer_prop(id="C", ano=2024),
    ]
    resultado = filtrar_local(items, FiltrosBusca(ano=2024))
    assert {i.id_proposicao_origem for i in resultado} == {"A", "C"}


def test_tipo_normalizado_uppercase():
    items = [
        _fazer_prop(id="1", sigla="PL"),
        _fazer_prop(id="2", sigla="PEC"),
    ]
    # Caller manda lower, helper normaliza
    resultado = filtrar_local(items, FiltrosBusca(tipo="pl"))
    assert len(resultado) == 1
    assert resultado[0].id_proposicao_origem == "1"


# ──────────────────────────────────────────────────────────────────────
# 4. Combinações
# ──────────────────────────────────────────────────────────────────────


def test_keyword_e_ano_combinam_como_AND():
    items = [
        _fazer_prop(id="A", ementa="petróleo bom", ano=2024),
        _fazer_prop(id="B", ementa="petróleo bom", ano=2023),
        _fazer_prop(id="C", ementa="café", ano=2024),
    ]
    resultado = filtrar_local(items, FiltrosBusca(keyword="petróleo", ano=2024))
    assert len(resultado) == 1
    assert resultado[0].id_proposicao_origem == "A"


def test_sem_filtros_retorna_intacto():
    items = [_fazer_prop(id=str(i)) for i in range(5)]
    resultado = filtrar_local(items, FiltrosBusca())
    assert resultado == items


def test_lista_vazia_in_lista_vazia_out():
    resultado = filtrar_local([], FiltrosBusca(keyword="qualquer"))
    assert resultado == []


# ──────────────────────────────────────────────────────────────────────
# 5. Regressão: bug original do Willian
# ──────────────────────────────────────────────────────────────────────


def test_bug_willian_keyword_Petroleo_filtra_resultados_irrelevantes():
    """
    Cenário: usuário pediu /fetch-live?source=al_ap&ano=2026&keyword=Petroleo.
    Sem aplicar filtrar_local, a API retornava 20 proposições sem nenhuma
    menção a petróleo (qualquer coisa de 2026).
    Agora, filtrar_local deve restringir aos que mencionam petróleo.
    """
    listagem_completa_do_alap_simulada = [
        _fazer_prop(id=f"id_{i}", ementa=f"Ementa qualquer {i}", ano=2026)
        for i in range(20)
    ]
    listagem_completa_do_alap_simulada.append(
        _fazer_prop(id="id_match", ementa="Sobre subsídio ao Petróleo no Amapá", ano=2026)
    )

    resultado = filtrar_local(
        listagem_completa_do_alap_simulada,
        FiltrosBusca(keyword="petróleo", ano=2026),
    )

    assert len(resultado) == 1, "Filtro de keyword tem que reduzir drasticamente"
    assert resultado[0].id_proposicao_origem == "id_match"


def test_accent_insensitive_casa_sem_acento_com_acento():
    """Com flag accent_insensitive=True, 'Petroleo' casa 'Petróleo'."""
    items = [_fazer_prop(id="1", ementa="Petróleo é recurso natural")]

    # Sem flag: NÃO casa
    r = filtrar_local(items, FiltrosBusca(keyword="Petroleo"))
    assert r == []

    # Com flag: CASA
    r = filtrar_local(
        items, FiltrosBusca(keyword="Petroleo", accent_insensitive=True)
    )
    assert len(r) == 1


def test_accent_insensitive_funciona_em_ambos_sentidos():
    """Flag deve ser simétrica: 'Água' casa 'agua' e 'agua' casa 'Água'."""
    items_acento = [_fazer_prop(id="A", ementa="Água potável")]
    items_sem_acento = [_fazer_prop(id="B", ementa="Agua potavel")]

    f = FiltrosBusca(keyword="agua", accent_insensitive=True)
    assert filtrar_local(items_acento, f)[0].id_proposicao_origem == "A"
    assert filtrar_local(items_sem_acento, f)[0].id_proposicao_origem == "B"

    f2 = FiltrosBusca(keyword="Água", accent_insensitive=True)
    assert filtrar_local(items_acento, f2)[0].id_proposicao_origem == "A"
    assert filtrar_local(items_sem_acento, f2)[0].id_proposicao_origem == "B"


def test_accent_insensitive_aplica_em_autor():
    items = [_fazer_prop(id="1", autores=["José Açúcar"])]

    # Sem flag: 'Jose Acucar' não casa
    r = filtrar_local(items, FiltrosBusca(autor="Jose Acucar"))
    assert r == []

    # Com flag: casa
    r = filtrar_local(
        items, FiltrosBusca(autor="Jose Acucar", accent_insensitive=True)
    )
    assert len(r) == 1


def test_bug_willian_sem_acento_documentado_como_limitacao():
    """
    Atenção: 'Petroleo' sem acento NÃO casa com 'Petróleo' com acento.
    Esse trade-off é documentado: filtro é case-insensitive mas não
    accent-insensitive. Para acent-insensitive, seria preciso normalizar
    via unicodedata.normalize('NFKD'). Não fizemos para evitar surpresa
    em outras keywords (ex: 'agua' não casaria com 'água' vs casaria? etc).
    """
    items = [_fazer_prop(id="1", ementa="Petróleo")]
    sem_acento = filtrar_local(items, FiltrosBusca(keyword="Petroleo"))
    com_acento = filtrar_local(items, FiltrosBusca(keyword="Petróleo"))

    # Documentado: sem acento NÃO casa hoje
    assert sem_acento == []
    assert len(com_acento) == 1
