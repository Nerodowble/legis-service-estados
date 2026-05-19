"""
AdapterBase — interface comum a todos os adapters de AL.

Cada adapter (al_ap, al_ba, al_ce...) implementa esta interface e é
responsável por:
  1. Buscar os dados na fonte oficial (HTML / XML / JSON / postback)
  2. Parsear o conteúdo
  3. Normalizar para o schema ProposicaoNormalizadaRaw

A camada de orquestração aplica rate limiter + circuit breaker + retry
em torno dos métodos definidos aqui.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.schemas import ResponseEnvelope


@dataclass
class FiltrosBusca:
    """
    Filtros aceitos por /propositions/fetch-live.

    Mantém compatibilidade com legis-service principal (seção 9 do payload).
    Nem toda AL respeitará todos os filtros — adapter ignora os não suportados.
    """

    page: int = 1
    per_page: int = 20
    ano: int | None = None
    keyword: str | None = None
    autor: str | None = None
    numero: str | None = None
    tipo: str | None = None  # sigla, ex: "PL", "PEC"
    tema: str | None = None
    data_inicio: str | None = None  # YYYY-MM-DD
    data_fim: str | None = None  # YYYY-MM-DD
    accent_insensitive: bool = False  # quando True, normaliza Unicode antes de comparar keyword/autor

    def to_query_dict(self) -> dict[str, Any]:
        """Para uso em logs e telemetria (sem campos None)."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class AdapterBase(ABC):
    """
    Contrato que todo adapter de AL deve cumprir.

    Atributos de classe (definir na subclasse):
        UF: sigla do estado (ex: "MT")
        NOME_CASA: nome legível da casa (ex: "Assembleia Legislativa do Mato Grosso")
        SOURCE_ID: identificador do source na API (ex: "al_mt")
        HOST_PRINCIPAL: host base da fonte
    """

    UF: str
    NOME_CASA: str
    SOURCE_ID: str
    HOST_PRINCIPAL: str

    @abstractmethod
    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        """
        Busca paginada com filtros. Retorna envelope completo.

        Raises:
            ALIndisponivelError: fonte fora do ar
            ALBloqueadaError: fonte exige auth ou está em ACL fechada
            ParserFalhouError: resposta veio mas não foi possível parsear
        """
        raise NotImplementedError

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """
        Busca uma proposição específica por ID. Retorna envelope com 1 item.

        Implementação default: chama listar() e filtra. Adapter pode sobrescrever
        para fazer GET direto na URL canônica (mais eficiente).
        """
        envelope = await self.listar(FiltrosBusca(per_page=100, numero=id_proposicao))
        envelope.data = [d for d in envelope.data if d.id_proposicao_origem == id_proposicao]
        envelope.total = len(envelope.data)
        return envelope

    async def health_check(self) -> bool:
        """
        Verifica se a fonte está responsiva. Usado por /health/sources.

        Implementação default: tenta listar 1 item.
        Adapter pode sobrescrever para uma checagem mais leve (HEAD na home, etc).
        """
        try:
            await self.listar(FiltrosBusca(per_page=1))
            return True
        except Exception:
            return False
