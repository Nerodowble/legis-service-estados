"""
Schema ProposicaoNormalizadaRaw compatível com legis-service principal.

Referência: vigil_payload_fetch_live.pdf — contrato de dados acordado com o backend.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Autor(BaseModel):
    """Objeto Autor (seção 4 do payload)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id_autor_origem": "95",
                    "nome": "Deputado Rodolfo Vale",
                    "partido": "UNIÃO BRASIL",
                    "uf": "AP",
                    "tipo": "Deputado",
                }
            ]
        }
    )

    id_autor_origem: str | None = Field(
        None, description="ID nativo do parlamentar na fonte (quando o portal expõe)."
    )
    nome: str = Field(..., description="Nome do autor. Pode incluir prefixo 'Deputado'/'Dep.'")
    partido: str | None = Field(
        None,
        description="Sigla do partido (enriquecida quando o adapter suporta).",
        examples=["PT", "PP", "UNIÃO BRASIL", "Republicanos"],
    )
    uf: str | None = Field(None, description="UF (2 letras) — bate com a UF do adapter.")
    tipo: str | None = Field(
        None,
        description="Tipo do autor.",
        examples=["Deputado", "Comissao", "Executivo", "Popular", "Outro"],
    )


class Tramitacao(BaseModel):
    """Objeto Tramitacao (seção 5 do payload)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "data": "2026-05-19",
                    "orgao": "DLE",
                    "nome_orgao": "Diretoria Legislativa",
                    "descricao": "Enviado para Diretoria Legislativa",
                    "despacho": None,
                    "tipo_tramitacao": "Enviado",
                    "regime": None,
                    "apreciacao": None,
                    "ambito": None,
                    "sequencia": 1,
                    "url_documento": None,
                }
            ]
        }
    )

    data: str | None = Field(
        None,
        description="Data ISO 8601 (YYYY-MM-DD). Adapters convertem formatos BR antes de devolver.",
    )
    orgao: str | None = Field(None, description="Sigla do órgão (DLE, PLEN, CCJ, ...).")
    nome_orgao: str | None = Field(None, description="Nome legível do órgão.")
    descricao: str | None = Field(None, description="Texto livre da tramitação.")
    despacho: str | None = Field(None, description="Despacho associado (raramente disponível).")
    tipo_tramitacao: str | None = Field(
        None,
        description="Verbo da movimentação.",
        examples=["Enviado", "Incluído", "Aprovado", "Arquivado"],
    )
    regime: str | None = None
    apreciacao: str | None = None
    ambito: str | None = None
    sequencia: int | None = Field(None, description="Ordem (1 = mais recente).")
    url_documento: str | None = None


class DadosAdicionais(BaseModel):
    """Objeto dados_adicionais (seção 6 do payload)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "codigoMateria": "108457",
                    "objetivo": "IX Legislatura - 2023 / 2027",
                    "casaIdentificadora": "ALAP",
                    "enteIdentificador": "AP",
                    "tipoConteudo": "Proposição",
                    "tipoDocumento": "MOC",
                }
            ]
        }
    )

    codigoMateria: int | str | None = Field(
        None, description="Identificador interno (fallback = id_proposicao_origem)."
    )
    objetivo: str | None = Field(None, description="Contexto livre (ex: legislatura).")
    casaIdentificadora: str | None = Field(
        None,
        description="Sigla da casa.",
        examples=["ALAP", "ALEPE", "CLDF", "ALMT"],
    )
    enteIdentificador: str | None = Field(
        None, description="UF (2 letras).", examples=["AP", "PE", "DF", "MT"]
    )
    tipoConteudo: str | None = Field(
        None,
        description="Sempre 'Proposição' (com acentos).",
        examples=["Proposição"],
    )
    tipoDocumento: str | None = Field(
        None, description="= sigla_tipo.", examples=["PL", "PEC", "MOC", "IND", "REQ"]
    )


class ProposicaoNormalizadaRaw(BaseModel):
    """
    Item da lista — schema unificado consumido pelo legis-service.

    Campos obrigatórios: id_proposicao_origem, casa_origem.
    Demais são opcionais conforme a fonte (seção 10 do payload).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id_proposicao_origem": "108457",
                    "casa_origem": "Assembleia Legislativa do Estado do Amapá",
                    "sigla_tipo": "MOC",
                    "numero": "317",
                    "ano": 2026,
                    "ementa": "Moção de Aplauso aos profissionais da Educação.",
                    "ementa_detalhada": None,
                    "data_apresentacao": "2026-05-19",
                    "status": "Enviado para Diretoria Legislativa",
                    "url_inteiro_teor": "https://elegis.al.ap.leg.br/portal/proposicao/108457",
                    "autores": [
                        {
                            "id_autor_origem": "95",
                            "nome": "Deputado Rodolfo Vale",
                            "partido": "UNIÃO BRASIL",
                            "uf": "AP",
                            "tipo": "Deputado",
                        }
                    ],
                    "tramitacoes": [
                        {
                            "data": "2026-05-19",
                            "orgao": "DLE",
                            "nome_orgao": "Diretoria Legislativa",
                            "descricao": "Enviado para Diretoria Legislativa",
                            "tipo_tramitacao": "Enviado",
                            "sequencia": 1,
                        }
                    ],
                    "dados_adicionais": {
                        "codigoMateria": "108457",
                        "objetivo": "IX Legislatura - 2023 / 2027",
                        "casaIdentificadora": "ALAP",
                        "enteIdentificador": "AP",
                        "tipoConteudo": "Proposição",
                        "tipoDocumento": "MOC",
                    },
                    "monitor": False,
                    "termometro": None,
                    "score_risco": None,
                    "nivel_federativo": "estadual",
                    "indicador_alta_prob": None,
                }
            ]
        }
    )

    # Identificação (obrigatórios)
    id_proposicao_origem: str = Field(
        ...,
        description="ID nativo da AL (numérico, slug ou hash dependendo da fonte).",
        examples=["108457", "REQ-10650-2025", "PL_1495_2025", "5Z1Q7"],
    )
    casa_origem: str = Field(
        ...,
        description="Nome completo da casa legislativa.",
        examples=["Assembleia Legislativa do Estado do Amapá"],
    )

    # Identidade legislativa
    sigla_tipo: str | None = Field(
        None,
        description="Sigla do tipo de proposição (UPPERCASE).",
        examples=["PL", "PEC", "PDL", "PLC", "MOC", "IND", "REQ", "PR"],
    )
    numero: str | None = Field(None, description="Número da proposição.", examples=["317", "1234"])
    ano: int | None = Field(None, description="Ano da proposição.", examples=[2024, 2025, 2026])

    # Conteúdo
    ementa: str | None = Field(None, description="Ementa principal.")
    ementa_detalhada: str | None = Field(None, description="Observações/justificativa.")
    data_apresentacao: str | None = Field(
        None,
        description="Data ISO YYYY-MM-DD.",
        examples=["2026-05-19"],
    )
    status: str | None = Field(None, description="Situação atual (texto livre).")
    url_inteiro_teor: str | None = Field(
        None, description="URL canônica ou link direto para PDF."
    )

    # Relacionamentos
    autores: list[Autor] = Field(default_factory=list)
    tramitacoes: list[Tramitacao] = Field(default_factory=list)
    dados_adicionais: DadosAdicionais | None = None

    # Flags
    monitor: bool | None = Field(
        False,
        description="Sempre False neste serviço (estado por-usuário é do legis-service principal).",
    )

    # Campos VIGIL (seção 7) — scoring opcional
    termometro: float | None = Field(
        None,
        description="Score VIGIL 0-100. Sempre null aqui — calculado pelo legis-service principal.",
        ge=0,
        le=100,
    )
    score_risco: Literal["CRITICO", "ALTO", "MEDIO", "BAIXO"] | None = Field(
        None,
        description="Categoria VIGIL. Sempre null aqui.",
    )
    nivel_federativo: Literal["federal", "estadual", "municipal"] | None = Field(
        None,
        description="Sempre 'estadual' neste serviço.",
    )
    indicador_alta_prob: bool | None = Field(
        None,
        description="Flag VIGIL. Sempre null aqui.",
    )
