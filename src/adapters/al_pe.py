"""
Adapter PE — Assembleia Legislativa de Pernambuco (ALEPE).

Sistema: API XML pública (descoberta via JS bundle do portal).
LIST: GET https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/?ano=YYYY
  + análogas: /proposicoes/indicacoes/ e /proposicoes/requerimentos/

Resposta: XML — usar lxml.
"""

from __future__ import annotations

import httpx

from src.adapters.base import AdapterBase, FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.config import settings
from src.errors import ALIndisponivelError, ParserFalhouError
from src.parsers import parse_xml
from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)

BASE_URL = "https://dadosabertos.alepe.pe.gov.br"

TIPO_PARA_ENDPOINT = {
    "PL": "projetos",
    "IND": "indicacoes",
    "REQ": "requerimentos",
}


class AdapterPE(AdapterBase):
    UF = "PE"
    NOME_CASA = "Assembleia Legislativa do Estado de Pernambuco"
    SOURCE_ID = "al_pe"
    HOST_PRINCIPAL = BASE_URL

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        endpoint = TIPO_PARA_ENDPOINT.get((filtros.tipo or "PL").upper(), "projetos")
        sigla = (filtros.tipo or "PL").upper()
        params: dict[str, str] = {}
        if filtros.ano:
            params["ano"] = str(filtros.ano)

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={
                "User-Agent": settings.USER_AGENT,
                "Accept": "application/xml, text/xml",
            },
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/api/v1/proposicoes/{endpoint}/", params=params
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("PE", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("PE", None, str(e)) from e

            try:
                root = parse_xml(response.content)
            except Exception as e:
                raise ParserFalhouError("PE", f"XML inválido: {e}") from e

        items: list[ProposicaoNormalizadaRaw] = []
        # Estrutura real (descoberta ao vivo 2026-05-19):
        # <projetos>
        #   <projeto docid="13539" numero="3" ano="2024" tipo="..." ementa="..." dataPublicacao="14/06/2024">
        #     <autores><autor nome="..." tipo="DEPUTADO"/></autores>
        #   </projeto>
        # </projetos>
        # Adapter genérico funciona para projetos, indicacoes, requerimentos
        # (cada endpoint devolve elementos similares com nome diferente).
        elementos = root.findall("projeto") + root.findall("indicacao") + root.findall("requerimento")
        for prop in elementos:
            attrs = prop.attrib
            id_origem = attrs.get("docid") or attrs.get("id") or ""
            if not id_origem:
                continue

            sigla_real = self._mapear_sigla(attrs.get("tipo"), sigla)

            autores = []
            for autor_el in prop.findall(".//autor"):
                nome = autor_el.attrib.get("nome")
                tipo_autor = autor_el.attrib.get("tipo", "Deputado").title()
                if nome:
                    autores.append(Autor(nome=nome, uf="PE", tipo=tipo_autor))

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=id_origem,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla_real,
                    numero=attrs.get("numero"),
                    ano=int(attrs["ano"]) if attrs.get("ano", "").isdigit() else None,
                    ementa=attrs.get("ementa"),
                    data_apresentacao=self._converter_data_br(attrs.get("dataPublicacao")),
                    url_inteiro_teor=None,
                    autores=autores,
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        casaIdentificadora="ALEPE",
                        enteIdentificador="PE",
                        tipoConteudo="Proposição",
                        tipoDocumento=sigla_real,
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        items = filtrar_local(items, filtros)
        total = len(items)

        # ALEPE não suporta paginação upstream → paginação client-side
        per_page = max(filtros.per_page, 1)
        inicio = (filtros.page - 1) * per_page
        fim = inicio + per_page
        pagina = items[inicio:fim]
        total_pages = (total // per_page) + (1 if total % per_page else 0)

        return ResponseEnvelope(
            data=pagina,
            total=total,
            total_pages=max(total_pages, 1),
            totals_by_nivel=TotalsByNivel(estadual=len(pagina)),
        )

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """
        ALEPE não tem endpoint single-item — o XML público devolve a lista
        completa por endpoint (projetos/indicacoes/requerimentos). Detalhe:
        baixa os 3 endpoints, filtra pelo docid solicitado, devolve o item.

        Custo: 3 fetches XML (cada um cobre 1 categoria do ano corrente),
        mas operação one-shot por request. Sem cache (stateless).
        """
        from src.errors import ProposicaoNaoEncontradaError

        endpoints = ["projetos", "indicacoes", "requerimentos"]
        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={
                "User-Agent": settings.USER_AGENT,
                "Accept": "application/xml, text/xml",
            },
            follow_redirects=True,
        ) as client:
            for endpoint in endpoints:
                try:
                    response = await client.get(
                        f"{BASE_URL}/api/v1/proposicoes/{endpoint}/"
                    )
                    response.raise_for_status()
                    root = parse_xml(response.content)
                except (httpx.HTTPStatusError, httpx.TimeoutException,
                        httpx.ConnectError, httpx.RemoteProtocolError,
                        httpx.ReadError, httpx.WriteError):
                    continue
                except Exception:
                    continue

                # Procurar por docid (cobre projeto/indicacao/requerimento)
                for tag in ("projeto", "indicacao", "requerimento"):
                    for prop in root.findall(tag):
                        if prop.attrib.get("docid") == str(id_proposicao):
                            return self._envelope_de_um(prop)

        raise ProposicaoNaoEncontradaError("PE", id_proposicao)

    def _envelope_de_um(self, prop) -> ResponseEnvelope:
        """Constroi ResponseEnvelope com 1 item a partir do elemento XML."""
        attrs = prop.attrib
        id_origem = attrs.get("docid") or ""
        sigla_real = self._mapear_sigla(attrs.get("tipo"), "PL")

        autores = []
        for autor_el in prop.findall(".//autor"):
            nome = autor_el.attrib.get("nome")
            tipo_autor = autor_el.attrib.get("tipo", "Deputado").title()
            if nome:
                autores.append(Autor(nome=nome, uf="PE", tipo=tipo_autor))

        item = ProposicaoNormalizadaRaw(
            id_proposicao_origem=str(id_origem),
            casa_origem=self.NOME_CASA,
            sigla_tipo=sigla_real,
            numero=attrs.get("numero"),
            ano=int(attrs["ano"]) if attrs.get("ano", "").isdigit() else None,
            ementa=attrs.get("ementa"),
            data_apresentacao=self._converter_data_br(attrs.get("dataPublicacao")),
            url_inteiro_teor=f"https://www.alepe.pe.gov.br/proposicao/?docid={id_origem}",
            autores=autores,
            tramitacoes=[],
            dados_adicionais=DadosAdicionais(
                codigoMateria=id_origem,
                objetivo=attrs.get("legislatura"),
                casaIdentificadora="ALEPE",
                enteIdentificador="PE",
                tipoConteudo="Proposição",
                tipoDocumento=sigla_real,
            ),
            monitor=False,
            nivel_federativo="estadual",
        )

        return ResponseEnvelope(
            data=[item],
            total=1,
            total_pages=1,
            totals_by_nivel=TotalsByNivel(estadual=1),
        )

    def _mapear_sigla(self, tipo: str | None, default: str) -> str:
        if not tipo:
            return default
        t = tipo.upper()
        if "COMPLEMENTAR" in t:
            return "PLC"
        if "DECRETO LEGISLATIVO" in t:
            return "PDL"
        if "EMENDA" in t:
            return "PEC"
        if "INDICA" in t:
            return "IND"
        if "REQUERIMENTO" in t:
            return "REQ"
        if "RESOLU" in t:
            return "PR"
        if "PROJETO DE LEI" in t:
            return "PL"
        return default

    def _converter_data_br(self, s: str | None) -> str | None:
        if not s:
            return None
        import re
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else s
