"""
Schema ProposicaoNormalizadaRaw compatível com legis-service principal.

Referência: vigil_payload_fetch_live.pdf — contrato de dados acordado com o backend.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Autor(BaseModel):
    """Objeto Autor (seção 4 do payload)."""

    id_autor_origem: str | None = None
    nome: str
    partido: str | None = None
    uf: str | None = None
    tipo: str | None = None  # "Deputado", "Comissao", "Executivo", "Popular", "Outro"


class Tramitacao(BaseModel):
    """Objeto Tramitacao (seção 5 do payload)."""

    data: str | None = None  # ISO 8601 (YYYY-MM-DD) ou DD/MM/YYYY
    orgao: str | None = None
    nome_orgao: str | None = None
    descricao: str | None = None
    despacho: str | None = None
    tipo_tramitacao: str | None = None
    regime: str | None = None
    apreciacao: str | None = None
    ambito: str | None = None
    sequencia: int | None = None
    url_documento: str | None = None


class DadosAdicionais(BaseModel):
    """Objeto dados_adicionais (seção 6 do payload)."""

    codigoMateria: int | str | None = None
    objetivo: str | None = None
    casaIdentificadora: str | None = None  # "CD", "SF", "ALMG", "ALBA", etc.
    enteIdentificador: str | None = None  # "BR", "MG", "BA", etc.
    tipoConteudo: str | None = None  # "Proposição"
    tipoDocumento: str | None = None  # "PL", "PEC", "REQ", etc.


class ProposicaoNormalizadaRaw(BaseModel):
    """
    Item da lista — schema unificado consumido pelo legis-service.

    Campos obrigatórios: id_proposicao_origem, casa_origem.
    Demais são opcionais conforme a fonte (seção 10 do payload).
    """

    # Identificação (obrigatórios)
    id_proposicao_origem: str
    casa_origem: str

    # Identidade legislativa
    sigla_tipo: str | None = None
    numero: str | None = None
    ano: int | None = None

    # Conteúdo
    ementa: str | None = None
    ementa_detalhada: str | None = None
    data_apresentacao: str | None = None  # YYYY-MM-DD preferencial
    status: str | None = None
    url_inteiro_teor: str | None = None

    # Relacionamentos
    autores: list[Autor] = Field(default_factory=list)
    tramitacoes: list[Tramitacao] = Field(default_factory=list)
    dados_adicionais: DadosAdicionais | None = None

    # Flags
    monitor: bool | None = False

    # Campos VIGIL (seção 7) — scoring opcional
    termometro: float | None = None
    score_risco: Literal["CRITICO", "ALTO", "MEDIO", "BAIXO"] | None = None
    nivel_federativo: Literal["federal", "estadual", "municipal"] | None = None
    indicador_alta_prob: bool | None = None
