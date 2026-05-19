"""
Adapter PA — Assembleia Legislativa do Estado do Pará (ALEPA).

Sistema: ASP.NET WebForms com DevExpress (Padrão B híbrido: JSON helpers + HTML callback).

Endpoints descobertos:
  - JSON: GET /Legislativo/GetTipoProposicoes  → catálogo de tipos
  - JSON: GET /Legislativo/GetTipoAutores      → catálogo de autores
  - HTML: GET /Legislativo/CallbackPanelProposicoes?tipo=N&ano=YYYY
          (fast path — funciona com GET puro)
  - HTML: GET /Legislativo/CardViewProposicoes (página com __VIEWSTATE)
          + POST /Legislativo/CallbackPanelProposicoes (fluxo completo
          com Referer + X-Requested-With para casos avançados)

Listagem em cards `.dxcvCard` com header (tipo+número), body (ementa),
footer (autor, data). ~2.433 itens em 244 páginas no ano de 2024.

Catálogo TIPO (do helper /GetTipoProposicoes):
  1 = PROJETO DE DECRETO LEGISLATIVO
  2 = PROJETO DE EMENDA CONSTITUCIONAL
  3 = PROJETO DE LEI ORDINÁRIA      ← padrão
  4 = PROJETO DE LEI COMPLEMENTAR
  5 = PROJETO DE RESOLUÇÃO

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

BASE_URL = "https://www.alepa.pa.gov.br"

# Mapeamento sigla → código do catálogo ALEPA (confirmado via /GetTipoProposicoes)
SIGLA_PARA_TIPO_ID = {
    "PDL": 1,
    "PEC": 2,
    "PL": 3,
    "PLC": 4,
    "PR": 5,
}


class AdapterPA(AdapterBase):
    UF = "PA"
    NOME_CASA = "Assembleia Legislativa do Estado do Pará"
    SOURCE_ID = "al_pa"
    HOST_PRINCIPAL = BASE_URL

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        sigla = (filtros.tipo or "PL").upper()
        tipo_id = SIGLA_PARA_TIPO_ID.get(sigla, 3)  # default: PL ordinário

        params: dict[str, str] = {"tipo": str(tipo_id)}
        if filtros.ano:
            params["ano"] = str(filtros.ano)
        if filtros.numero:
            params["numero"] = filtros.numero

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={
                "User-Agent": settings.USER_AGENT,
                "Referer": f"{BASE_URL}/Legislativo/CardViewProposicoes",
            },
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/Legislativo/CallbackPanelProposicoes", params=params
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("PA", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("PA", None, str(e)) from e

            html = decode_response(response)

        try:
            return self._parsear_listagem(html, filtros, sigla)
        except Exception as e:
            raise ParserFalhouError("PA", f"parse DevExpress cards: {e}") from e

    def _parsear_listagem(
        self, html: str, filtros: FiltrosBusca, sigla_default: str
    ) -> ResponseEnvelope:
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []

        # Estrutura real observada em CallbackPanelProposicoes:
        #   <div class="card-proposicao" onclick='onCardClick("/Legislativo/DetalhesProposicao?IdProposicao=N&...")'>
        #     <h3>DEP. LÍVIA DUARTE</h3>
        #     <span>INDICAÇÃO Nº 142/2024, DE 18/12/2024</span>
        #     <p>{ementa}</p>
        #   </div>
        for card in tree.css(".card-proposicao"):
            onclick = card.attributes.get("onclick") or ""
            id_match = re.search(r"IdProposicao=(\d+)", onclick)
            tipo_match = re.search(r"tipo=([^&]+)", onclick)
            id_origem = id_match.group(1) if id_match else ""
            tipo_url = tipo_match.group(1).replace("%20", " ") if tipo_match else None

            h3 = card.css_first("h3")
            span = card.css_first("span")
            p = card.css_first("p")

            autor_nome = normalizar_texto(h3.text(strip=True)) if h3 else None
            cabecalho = normalizar_texto(span.text(strip=True)) if span else ""
            ementa = normalizar_texto(p.text(strip=True)) if p else None

            sigla, numero, ano, data_apresentacao = self._parsear_cabecalho(
                cabecalho, sigla_default, tipo_url
            )

            url_doc = (
                f"{BASE_URL}/Legislativo/DetalhesProposicao?IdProposicao={id_origem}"
                if id_origem
                else None
            )

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=id_origem,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=numero,
                    ano=ano,
                    ementa=ementa,
                    data_apresentacao=data_apresentacao,
                    status="Em tramitação",
                    url_inteiro_teor=url_doc,
                    autores=[Autor(nome=autor_nome, uf="PA", tipo="Deputado")] if autor_nome else [],
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        casaIdentificadora="ALEPA",
                        enteIdentificador="PA",
                        tipoConteudo="Proposição",
                        tipoDocumento=sigla,
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        # Aplicar filtros locais (keyword, autor, etc) que o ALEPA não suporta upstream
        items = filtrar_local(items, filtros)

        # Total: se houve filtro local, total reflete o filtrado; senão, usa rodapé do portal
        tem_filtro_local = any([filtros.keyword, filtros.autor, filtros.numero])
        total = len(items) if tem_filtro_local else (self._extrair_total(tree) or len(items))
        per_page = max(filtros.per_page, 1)
        total_pages = (total // per_page) + (1 if total % per_page else 0)

        return ResponseEnvelope(
            data=items[: filtros.per_page],  # ALEPA devolve a página inteira; recorta
            total=total,
            total_pages=max(total_pages, 1),
            totals_by_nivel=TotalsByNivel(estadual=min(len(items), filtros.per_page)),
        )

    def _extrair_total(self, tree) -> int | None:
        # "Página 1 de 244 (2433 itens)" no rodapé/cabeçalho
        for el in tree.css(".dxp-summary, .dxcvTitlePanel_Office365 p, p"):
            txt = el.text() or ""
            m = re.search(r"\((\d+)\s+itens?\)", txt)
            if m:
                return int(m.group(1))
            m = re.search(r"(\d+)\s+Resultados?", txt, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    def _parsear_cabecalho(
        self, s: str, sigla_default: str, tipo_url: str | None
    ) -> tuple[str, str | None, int | None, str | None]:
        # "INDICAÇÃO Nº 142/2024, DE 18/12/2024"
        # "PROJETO DE LEI ORDINÁRIA Nº 123/2024, DE 10/03/2024"
        m_data = re.search(r"DE\s+(\d{2}/\d{2}/\d{4})", s, re.IGNORECASE)
        data = self._converter_data_br(m_data.group(1)) if m_data else None

        m = re.search(
            r"(PROJETO DE LEI(?:\s+ORDIN[ÁA]RIA|\s+COMPLEMENTAR)?|"
            r"PROJETO DE DECRETO LEGISLATIVO|"
            r"PROJETO DE EMENDA(?:\s+CONSTITUCIONAL)?|PEC|PDL|PR|"
            r"INDICA[ÇC][ÃA]O|REQUERIMENTO|MO[ÇC][ÃA]O)"
            r"\s*N?[º°]?\s*(\d+)\s*/\s*(\d{2,4})",
            s,
            re.IGNORECASE,
        )
        if not m:
            return self._sigla_de_url(tipo_url) or sigla_default, None, None, data

        bruto = m.group(1).upper()
        if "COMPLEMENTAR" in bruto:
            sigla = "PLC"
        elif "DECRETO LEGISLATIVO" in bruto:
            sigla = "PDL"
        elif "EMENDA" in bruto or bruto == "PEC":
            sigla = "PEC"
        elif "PROJETO DE LEI" in bruto:
            sigla = "PL"
        elif "INDICA" in bruto:
            sigla = "IND"
        elif "REQUERIMENTO" in bruto:
            sigla = "REQ"
        elif bruto.startswith("MO"):
            sigla = "MOC"
        elif bruto == "PR":
            sigla = "PR"
        else:
            sigla = self._sigla_de_url(tipo_url) or sigla_default

        numero = m.group(2)
        ano_raw = int(m.group(3))
        ano = ano_raw if ano_raw > 100 else 2000 + ano_raw
        return sigla, numero, ano, data

    def _sigla_de_url(self, tipo_url: str | None) -> str | None:
        if not tipo_url:
            return None
        t = tipo_url.upper()
        if "COMPLEMENTAR" in t:
            return "PLC"
        if "DECRETO" in t:
            return "PDL"
        if "EMENDA" in t:
            return "PEC"
        if "INDICA" in t:
            return "IND"
        if "REQUERIMENTO" in t:
            return "REQ"
        if "LEI" in t:
            return "PL"
        return None

    def _converter_data_br(self, s: str | None) -> str | None:
        if not s:
            return None
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", s)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
