"""Envelope da resposta — seção 2 do payload (vigil_payload_fetch_live.pdf)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.proposicao import ProposicaoNormalizadaRaw


class TotalsByNivel(BaseModel):
    federal: int = 0
    estadual: int = 0
    municipal: int = 0


class ResponseEnvelope(BaseModel):
    """
    Envelope idêntico ao retornado por /propositions/fetch-live do legis-service principal.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "data": [
                        {
                            "id_proposicao_origem": "108457",
                            "casa_origem": "Assembleia Legislativa do Estado do Amapá",
                            "sigla_tipo": "MOC",
                            "numero": "317",
                            "ano": 2026,
                            "ementa": "Moção de Aplauso aos profissionais.",
                            "data_apresentacao": "2026-05-19",
                            "status": "Enviado para Diretoria Legislativa",
                            "url_inteiro_teor": "https://elegis.al.ap.leg.br/portal/proposicao/108457",
                            "autores": [
                                {"nome": "Deputado Rodolfo Vale", "partido": "UNIÃO BRASIL",
                                 "uf": "AP", "tipo": "Deputado"}
                            ],
                            "tramitacoes": [],
                            "dados_adicionais": {
                                "casaIdentificadora": "ALAP",
                                "enteIdentificador": "AP",
                                "tipoConteudo": "Proposição",
                                "tipoDocumento": "MOC",
                            },
                            "monitor": False,
                            "nivel_federativo": "estadual",
                        }
                    ],
                    "total": 35,
                    "total_pages": 12,
                    "totals_by_nivel": {"federal": 0, "estadual": 35, "municipal": 0},
                }
            ]
        }
    )

    data: list[ProposicaoNormalizadaRaw] = Field(default_factory=list)
    total: int | None = None
    total_pages: int | None = None
    totals_by_nivel: TotalsByNivel | None = None
