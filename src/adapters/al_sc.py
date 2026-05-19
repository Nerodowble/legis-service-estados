"""
Adapter SC — Assembleia Legislativa de Santa Catarina (ALESC).

Sistema: Portal eLegis (CakePHP + htmx) com hash curto (5 chars) por proposição.

LIST: GET https://portalelegis.alesc.sc.gov.br/proposicoes/processo-legislativo
  ?ano=YYYY&tipoPropositura=N&page=N
  Resposta: HTML SSR; 310 páginas × 20 = ~6.200 proposições.

DETAIL: GET https://portalelegis.alesc.sc.gov.br/proposicoes/{HASH}/tramitacoes
  HASH curto base36 (~5 chars), ex: "N0MQP".
  `<title>`: "Tramitações / PL./0216/2024 / Proposições / e-Legis / ALESC"
  Conteúdo: tabela com tramitação detalhada (20+ etapas: data, origem, destino,
  ação, parecer).

robots.txt: vazio.
"""

from __future__ import annotations

import re

import httpx

from src.adapters.base import AdapterBase, FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.config import settings
from src.errors import ALIndisponivelError, ParserFalhouError
from src.parsers import normalizar_texto, parse_html
from src.parsers.encoding import decode_response
from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)

BASE_URL = "https://portalelegis.alesc.sc.gov.br"


class AdapterSC(AdapterBase):
    UF = "SC"
    NOME_CASA = "Assembleia Legislativa do Estado de Santa Catarina"
    SOURCE_ID = "al_sc"
    HOST_PRINCIPAL = BASE_URL

    # Mapeamento de siglas → tipoPropositura do eLegis (catálogo do portal)
    SIGLA_PARA_TIPO = {
        "PL": 1,    # Projeto de Lei
        "PLC": 2,   # Projeto de Lei Complementar
        "PEC": 3,   # Proposta de Emenda à Constituição
        "IND": 4,   # Indicação
        "REQ": 5,   # Requerimento
        "MOC": 6,   # Moção
    }

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        params: dict[str, str] = {"page": str(filtros.page)}
        if filtros.ano:
            params["ano"] = str(filtros.ano)
        if filtros.tipo:
            tipo_id = self.SIGLA_PARA_TIPO.get(filtros.tipo.upper())
            if tipo_id:
                params["tipoPropositura"] = str(tipo_id)
        if filtros.keyword:
            params["q"] = filtros.keyword

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={
                "User-Agent": settings.USER_AGENT,
                # htmx checa Accept; queremos HTML completo, não fragmento
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/proposicoes/processo-legislativo", params=params
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("SC", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                raise ALIndisponivelError("SC", None, str(e)) from e

            html = decode_response(response)

        try:
            return self._parsear_listagem(html, filtros)
        except Exception as e:
            raise ParserFalhouError("SC", f"parse eLegis SC: {e}") from e

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """ID = hash curto eLegis (ex: 'N0MQP'). Endpoint: /proposicoes/{HASH}/tramitacoes."""
        url = f"{BASE_URL}/proposicoes/{id_proposicao}/tramitacoes"

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("SC", e.response.status_code, str(e)) from e

            html = decode_response(response)

        return self._parsear_detalhe(html, id_proposicao, url)

    def _parsear_listagem(self, html: str, filtros: FiltrosBusca) -> ResponseEnvelope:
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []

        # Listagem real do eLegis: links no padrão /proposicoes/{HASH}/tramitacoes
        # ou /proposicoes/{HASH}/{secao}. Hash é base36 de ~5 chars.
        hashes_vistos: set[str] = set()
        for a in tree.css('a[href*="/proposicoes/"]'):
            href = a.attributes.get("href") or ""
            m = re.search(r"/proposicoes/([A-Z0-9]{4,8})(?:/|$)", href)
            if not m:
                continue
            hash_id = m.group(1)
            # Ignorar paths reservados (não-hash)
            if hash_id.lower() in {"processo-legislativo", "feed", "buscar"}:
                continue
            if hash_id in hashes_vistos:
                continue
            hashes_vistos.add(hash_id)

            # Texto do link costuma ser "PL./0216/2024" ou similar
            titulo_link = normalizar_texto(a.text(strip=True))
            sigla, numero, ano = self._parsear_titulo_link(titulo_link or "")
            if not ano:
                ano = filtros.ano

            titulo = titulo_link

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=hash_id,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=numero,
                    ano=ano,
                    ementa=titulo if titulo and len(titulo) > 10 else None,
                    url_inteiro_teor=f"{BASE_URL}/proposicoes/{hash_id}/tramitacoes",
                    autores=[],
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        casaIdentificadora="ALESC",
                        enteIdentificador="SC",
                        tipoConteudo="Proposição",
                        tipoDocumento=sigla,
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        total = self._extrair_total(tree) or len(items)
        total_pages = (
            (total // filtros.per_page) + (1 if total % filtros.per_page else 0)
            if filtros.per_page
            else 1
        )

        items = filtrar_local(items, filtros)
        return ResponseEnvelope(
            data=items,
            total=total,
            total_pages=max(total_pages, 1),
            totals_by_nivel=TotalsByNivel(estadual=len(items)),
        )

    def _parsear_detalhe(self, html: str, hash_id: str, url: str) -> ResponseEnvelope:
        tree = parse_html(html)

        # <title> documentado: "Tramitações / PL./0216/2024 / Proposições / e-Legis / ALESC"
        sigla, numero, ano = "PL", None, None
        title_elem = tree.css_first("title")
        if title_elem:
            t = title_elem.text() or ""
            m = re.search(r"([A-Z]{2,4})\.?/?\s*(\d+)\s*/\s*(\d{4})", t)
            if m:
                sigla = m.group(1)
                numero = m.group(2).lstrip("0") or "0"
                ano = int(m.group(3))

        # Ementa, autor e data ficam em campos rotulados — busca defensiva
        def _campo(label: str) -> str | None:
            for elem in tree.css("dt, th, strong, label"):
                txt = (elem.text(strip=True) or "").lower().rstrip(":")
                if txt.startswith(label.lower()):
                    nxt = elem.next
                    if nxt:
                        return normalizar_texto(nxt.text(strip=True))
            return None

        ementa = _campo("ementa")
        autor_nome = _campo("autor")
        data = _campo("apresentação") or _campo("apresentacao")

        item = ProposicaoNormalizadaRaw(
            id_proposicao_origem=hash_id,
            casa_origem=self.NOME_CASA,
            sigla_tipo=sigla.upper(),
            numero=numero,
            ano=ano,
            ementa=ementa,
            data_apresentacao=data,
            url_inteiro_teor=url,
            autores=[Autor(nome=autor_nome, uf="SC", tipo="Deputado")] if autor_nome else [],
            tramitacoes=[],
            dados_adicionais=DadosAdicionais(
                casaIdentificadora="ALESC",
                enteIdentificador="SC",
                tipoConteudo="Proposição",
                tipoDocumento=sigla.upper(),
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

    def _extrair_total(self, tree) -> int | None:
        contador = tree.css_first('[data-total], .total-resultados, .pagination-info')
        if not contador:
            return None
        attr = contador.attributes.get("data-total")
        if attr and attr.isdigit():
            return int(attr)
        m = re.search(r"(\d+)", contador.text() or "")
        return int(m.group(1)) if m else None

    def _parsear_titulo_link(self, s: str) -> tuple[str, str | None, int | None]:
        # Padrão observado: "PL./0216/2024", "PEC/05/2023", "REQ./345/2024"
        m = re.match(r"([A-Z]{2,4})\.?/?\s*(\d+)\s*/\s*(\d{4})", s.strip())
        if not m:
            return "PL", None, None
        return m.group(1), m.group(2).lstrip("0") or "0", int(m.group(3))
