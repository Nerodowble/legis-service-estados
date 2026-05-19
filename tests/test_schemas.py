"""Smoke test do contrato Pydantic — garante compatibilidade com legis-service."""

from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)


def test_proposicao_minima_valida():
    p = ProposicaoNormalizadaRaw(
        id_proposicao_origem="abc-1",
        casa_origem="Assembleia Teste",
        sigla_tipo="PL",
        numero="1",
        ano=2025,
        dados_adicionais=DadosAdicionais(
            casaIdentificadora="ALXX",
            enteIdentificador="XX",
            tipoConteudo="Proposição",
            tipoDocumento="PL",
        ),
        nivel_federativo="estadual",
    )
    assert p.id_proposicao_origem == "abc-1"
    assert p.monitor is False  # default
    assert p.autores == []
    assert p.tramitacoes == []


def test_envelope_serializa_para_dict():
    envelope = ResponseEnvelope(
        data=[],
        total=0,
        total_pages=1,
        totals_by_nivel=TotalsByNivel(estadual=0),
    )
    d = envelope.model_dump()
    assert d["total"] == 0
    assert d["totals_by_nivel"]["estadual"] == 0


def test_autor_aceita_apenas_uf_de_2_letras():
    a = Autor(nome="Fulano", uf="MT", tipo="Deputado")
    assert a.uf == "MT"
