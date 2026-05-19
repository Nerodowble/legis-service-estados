"""
Adapter BA — Assembleia Legislativa da Bahia (ALBA).

Sistema: portal próprio Java (webjars + Bootstrap).
LIST funcional: GET https://www.al.ba.gov.br/atividade-legislativa-nova/proposicoes
  ?dataInicio=DD/MM/YYYY&dataFim=DD/MM/YYYY&palavra=X&numero=N
DETAIL: GET https://www.al.ba.gov.br/atividade-legislativa-nova/proposicao/{TIPO}-{NUM_COM_PONTO}-{ANO}
  ex: REQ-10650-2025

ATENÇÃO: path /atividade-legislativa/ (sem -nova) retorna sempre lista hardcoded de 2020-2021.
Usar SEMPRE /atividade-legislativa-nova/.

ACHADO DE SEGURANÇA (para reporte responsável):
  /actuator/env e /actuator/mappings retornam HTTP 500 (endpoints existem; config padrão exporia dados sensíveis).
"""

from __future__ import annotations

import re

import httpx

from src.adapters.base import AdapterBase, FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.config import settings
from src.errors import ALIndisponivelError
from src.orquestrador.cache_parlamentares import CacheParlamentares
from src.parsers import normalizar_texto, parse_html
from src.parsers.encoding import decode_response
from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)

BASE_URL = "https://www.al.ba.gov.br"


class AdapterBA(AdapterBase):
    UF = "BA"
    NOME_CASA = "Assembleia Legislativa do Estado da Bahia"
    SOURCE_ID = "al_ba"
    HOST_PRINCIPAL = BASE_URL

    # Cache compartilhado de parlamentares (singleton + TTL 6h)
    _cache = CacheParlamentares("al_ba")

    async def _fetch_parlamentares(self) -> dict[str, dict[str, str]]:
        """
        Faz 1 fetch de /deputados/deputados-estaduais e parseia 63 cards.
        Estrutura: <a class="deputado-nome">Adolfo Menezes</a> + sigla partido
        adjacente no DOM (texto concatenado: "Adolfo MenezesPSD").
        """
        url = f"{BASE_URL}/deputados/deputados-estaduais"
        try:
            async with httpx.AsyncClient(
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                headers={"User-Agent": settings.USER_AGENT},
                follow_redirects=True,
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
                html = decode_response(r)
        except Exception:
            return {}

        tree = parse_html(html)
        cache: dict[str, dict[str, str]] = {}

        # Cada deputado tem <a class="deputado-nome">NOME</a>. Procurar o
        # texto do container pai (geralmente "NOMEPARTIDO" colado).
        siglas_validas = {
            "PT", "PP", "PSD", "PL", "PDT", "PV", "PSB", "PSDB", "MDB",
            "PSOL", "REDE", "REPUBLICANOS", "PODE", "PODEMOS", "AVANTE",
            "NOVO", "PATRIOTA", "PROS", "PSC", "PCDOB", "CIDADANIA",
            "SOLIDARIEDADE", "UNIÃO", "UNIAO", "UB",
        }
        for el in tree.css(".deputado-nome"):
            nome = (el.text(strip=True) or "").strip()
            if not nome:
                continue
            # Pai costuma ter "NOMEPARTIDO" colado
            pai = el.parent
            if not pai:
                continue
            t_pai = (pai.text(strip=True) or "").strip()
            # Remover o nome do início para isolar o resto
            resto = t_pai[len(nome):].strip()
            # Match a primeira sigla válida que aparece
            partido = None
            for sigla in sorted(siglas_validas, key=lambda s: -len(s)):
                if resto.upper().startswith(sigla):
                    partido = sigla
                    break
            if partido:
                cache[nome] = {"partido": partido}
        return cache

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        # Warm-up do cache de parlamentares (silencioso se falhar)
        await self._cache.warm(self._fetch_parlamentares)

        params: dict[str, str] = {}
        if filtros.data_inicio:
            params["dataInicio"] = self._iso_para_br(filtros.data_inicio)
        if filtros.data_fim:
            params["dataFim"] = self._iso_para_br(filtros.data_fim)
        elif filtros.ano:
            params["dataInicio"] = f"01/01/{filtros.ano}"
            params["dataFim"] = f"31/12/{filtros.ano}"
        if filtros.numero:
            params["numero"] = filtros.numero
        if filtros.keyword:
            params["palavra"] = filtros.keyword

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/atividade-legislativa-nova/proposicoes", params=params
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("BA", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("BA", None, str(e)) from e

            html = decode_response(response)

        return self._parsear_listagem(html, filtros)

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """GET na URL canônica /atividade-legislativa-nova/proposicao/{slug}."""
        url = f"{BASE_URL}/atividade-legislativa-nova/proposicao/{id_proposicao}"

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("BA", e.response.status_code, str(e)) from e

            html = decode_response(response)

        prop = self._parsear_detalhe(html, id_proposicao, url)
        return ResponseEnvelope(
            data=[prop] if prop else [],
            total=1 if prop else 0,
            total_pages=1,
            totals_by_nivel=TotalsByNivel(estadual=1 if prop else 0),
        )

    def _parsear_listagem(self, html: str, filtros: FiltrosBusca) -> ResponseEnvelope:
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []

        # Estrutura real (validada ao vivo):
        #   <tr class="table-itens">
        #     <td class="mapa"><a href="/atividade-legislativa-nova/proposicao/REQ-10402-2024">...REQ/10402/2024...</a></td>
        #     <td><span class="fe-html-ativ">Ementa aqui</span></td>
        #     <td><a href="...pdf">Texto Original</a></td>
        #   </tr>
        for tr in tree.css("tr.table-itens"):
            a = tr.css_first('a[href*="/atividade-legislativa-nova/proposicao/"]')
            if not a:
                continue
            href = a.attributes.get("href") or ""
            m = re.search(r"/atividade-legislativa-nova/proposicao/([A-Z]+-?[\d.]+-\d{4})", href)
            if not m:
                continue
            slug = m.group(1)
            sigla, numero, ano = self._parsear_slug(slug)

            # Ementa: <span class="fe-html-ativ"> dentro da 2ª <td>
            ementa = None
            ementa_el = tr.css_first("span.fe-html-ativ")
            if ementa_el:
                ementa = (ementa_el.text(strip=True) or "").lstrip("\xa0 ").strip() or None

            # URL do PDF de texto original (3ª <td>)
            url_pdf = None
            for link in tr.css("a[href]"):
                href_link = link.attributes.get("href") or ""
                if href_link.lower().endswith(".pdf") or "texto" in (link.text() or "").lower():
                    url_pdf = href_link if href_link.startswith("http") else f"{BASE_URL}{href_link}"
                    break

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=slug,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=numero,
                    ano=ano,
                    ementa=ementa,
                    url_inteiro_teor=url_pdf
                    or f"{BASE_URL}/atividade-legislativa-nova/proposicao/{slug}",
                    dados_adicionais=DadosAdicionais(
                        codigoMateria=slug,
                        casaIdentificadora="ALBA",
                        enteIdentificador="BA",
                        tipoConteudo="Proposição",
                        tipoDocumento=sigla,
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        items = filtrar_local(items, filtros)
        total = len(items)
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

    def _parsear_detalhe(
        self, html: str, slug: str, url: str
    ) -> ProposicaoNormalizadaRaw | None:
        tree = parse_html(html)

        sigla, numero, ano = self._parsear_slug(slug)
        autor = self._extrair_campo(tree, "Autor")
        origem = self._extrair_campo(tree, "Origem")
        data_entrada = self._extrair_campo(tree, "Data de Entrada")
        regime = self._extrair_campo(tree, "Regime")
        ementa = self._extrair_campo(tree, "Ementa")

        autores = [
            Autor(
                nome=autor,
                uf="BA",
                tipo="Deputado",
                partido=self._cache.partido_de(autor),
            )
        ] if autor else []

        return ProposicaoNormalizadaRaw(
            id_proposicao_origem=slug,
            casa_origem=self.NOME_CASA,
            sigla_tipo=sigla,
            numero=numero,
            ano=ano,
            ementa=ementa,
            data_apresentacao=self._iso_data(data_entrada),
            status=regime,
            url_inteiro_teor=url,
            autores=autores,
            tramitacoes=[],
            dados_adicionais=DadosAdicionais(
                casaIdentificadora="ALBA",
                enteIdentificador="BA",
                tipoConteudo="Proposição",
                tipoDocumento=sigla,
                objetivo=origem,
            ),
            monitor=False,
            nivel_federativo="estadual",
        )

    def _extrair_campo(self, tree, label: str) -> str | None:
        """Helper: encontra <dt>Label:</dt><dd>Valor</dd> ou similar."""
        for dt in tree.css("dt"):
            if label.lower() in (dt.text(strip=True) or "").lower():
                dd = dt.next
                while dd is not None and dd.tag != "dd":
                    dd = dd.next
                if dd is not None:
                    return normalizar_texto(dd.text(strip=True))
        return None

    def _parsear_slug(self, slug: str) -> tuple[str | None, str | None, int | None]:
        # ex: "REQ-10650-2025" ou "REQ-9.698-2021"
        m = re.match(r"^([A-Z]+)\-?([\d.]+)\-(\d{4})$", slug)
        if not m:
            return None, None, None
        sigla = m.group(1)
        numero = m.group(2).replace(".", "")
        try:
            ano = int(m.group(3))
        except ValueError:
            ano = None
        return sigla, numero, ano

    def _iso_para_br(self, iso: str) -> str:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso)
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else iso

    def _iso_data(self, br: str | None) -> str | None:
        if not br:
            return None
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", br)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else br
