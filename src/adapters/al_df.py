"""
Adapter DF — Câmara Legislativa do Distrito Federal (CLDF).

Sistema: portal Liferay público.
URL canônica DETAIL: GET https://www.cl.df.gov.br/proposicao/-/documentos/{TIPO}_{NUM}_{ANO}
  ex: PL_1495_2025, IND_10447_2026, MO_746_2024
LIST paginada: GET https://www.cl.df.gov.br/pt/web/guest/projetos?delta=30&start=N
  Paginação start=1..~5120 (~170 páginas × 30 = ~5000 proposições)
Liferay JSON API discovery: GET https://www.cl.df.gov.br/api/jsonws?discover (838 serviços)

DCL (Diário): GET https://www.cl.df.gov.br/pt/buscar-dcl (PDF público)
"""

from __future__ import annotations

import re

import httpx

from src.adapters.base import AdapterBase, FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.config import settings
from src.errors import ALIndisponivelError
from src.parsers import normalizar_texto, parse_html
from src.parsers.encoding import decode_response
from src.schemas import (
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)

BASE_URL = "https://www.cl.df.gov.br"


class AdapterDF(AdapterBase):
    UF = "DF"
    NOME_CASA = "Câmara Legislativa do Distrito Federal"
    SOURCE_ID = "al_df"
    HOST_PRINCIPAL = BASE_URL

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        start = (filtros.page - 1) * filtros.per_page + 1
        params = {
            "delta": str(filtros.per_page),
            "start": str(start),
            "sort": "dataLeitura_Number_sortable-",
        }

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(f"{BASE_URL}/pt/web/guest/projetos", params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("DF", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("DF", None, str(e)) from e

            html = decode_response(response)

        return self._parsear_listagem(html, filtros)

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """ID no formato {TIPO}_{NUM}_{ANO} ex: PL_1495_2025."""
        url = f"{BASE_URL}/proposicao/-/documentos/{id_proposicao}"

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("DF", e.response.status_code, str(e)) from e

            html = decode_response(response)

        return self._parsear_detalhe(html, id_proposicao, url)

    def _parsear_listagem(self, html: str, filtros: FiltrosBusca) -> ResponseEnvelope:
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []

        # Cada PL tem link /proposicao/-/documentos/{TIPO}_{NUM}_{ANO}
        slugs_unicos: list[str] = []
        for a in tree.css('a[href*="/proposicao/-/documentos/"]'):
            href = a.attributes.get("href") or ""
            m = re.search(r"/proposicao/-/documentos/([A-Z]+_\d+_\d{4})", href)
            if m and m.group(1) not in slugs_unicos:
                slugs_unicos.append(m.group(1))

        for slug in slugs_unicos:
            sigla, numero, ano = self._parsear_slug(slug)
            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=slug,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=numero,
                    ano=ano,
                    url_inteiro_teor=f"{BASE_URL}/proposicao/-/documentos/{slug}",
                    dados_adicionais=DadosAdicionais(
                        casaIdentificadora="CLDF",
                        enteIdentificador="DF",
                        tipoConteudo="Proposição",
                        tipoDocumento=sigla,
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        items = filtrar_local(items, filtros)
        return ResponseEnvelope(
            data=items,
            total=len(items),
            total_pages=170,  # CLDF: ~170 páginas conhecidas
            totals_by_nivel=TotalsByNivel(estadual=len(items)),
        )

    def _parsear_detalhe(
        self, html: str, slug: str, url: str
    ) -> ResponseEnvelope:
        tree = parse_html(html)
        sigla, numero, ano = self._parsear_slug(slug)

        # Liferay tem rótulos consistentes. Refinar conforme HTML real.
        ementa = None
        for elem in tree.css("p, div"):
            txt = normalizar_texto(elem.text(strip=True))
            if txt and 30 < len(txt) < 600 and "ementa" in txt.lower():
                # Pegar o texto após "Ementa:"
                m = re.search(r"Ementa[:\s]*(.+)", txt, re.IGNORECASE)
                if m:
                    ementa = m.group(1).strip()
                    break

        item = ProposicaoNormalizadaRaw(
            id_proposicao_origem=slug,
            casa_origem=self.NOME_CASA,
            sigla_tipo=sigla,
            numero=numero,
            ano=ano,
            ementa=ementa,
            url_inteiro_teor=url,
            autores=[],
            tramitacoes=[],
            dados_adicionais=DadosAdicionais(
                casaIdentificadora="CLDF",
                enteIdentificador="DF",
                tipoConteudo="Proposição",
                tipoDocumento=sigla,
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

    def _parsear_slug(self, slug: str) -> tuple[str | None, str | None, int | None]:
        # PL_1495_2025
        m = re.match(r"^([A-Z]+)_(\d+)_(\d{4})$", slug)
        if not m:
            return None, None, None
        try:
            ano = int(m.group(3))
        except ValueError:
            ano = None
        return m.group(1), m.group(2), ano
