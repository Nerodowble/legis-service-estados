"""
Adapter SP — Assembleia Legislativa de São Paulo (ALESP).

Sistema: Dumps XML públicos em ZIP no repositório de dados abertos.
URLs (ALESP, dados abertos):
  https://www.al.sp.gov.br/repositorioDados/processo_legislativo/proposituras.zip
  https://www.al.sp.gov.br/repositorioDados/processo_legislativo/tramitacoes.zip
  https://www.al.sp.gov.br/repositorioDados/processo_legislativo/autores.zip

Cada ZIP contém um único XML grande (proposituras.xml, ~150 MB descompactado).
Esquema observado: <proposituras><propositura>...</propositura></proposituras>

ATENÇÃO — STATELESS:
  Estamos num serviço sem disco/DB. Não baixamos o ZIP a cada request.
  Estratégia: streaming-parse direto do ZIP em memória, filtrando enquanto
  itera. Iteração one-shot por request. Como o XML é grande, usamos
  iterparse e abortamos cedo após paginar/filtrar.

  Em produção real, esta fonte pode justificar cache leve por TTL no
  cliente (HTTP Cache-Control + ETag), MAS o serviço continua stateless.

NOTA: Como o filtro é client-side, "page=1, per_page=20" sempre retorna
  os 20 primeiros que combinam com filtros. Paginação eficiente requer
  ordenação determinística — usamos ordem nativa do XML.

Fallback: se o ZIP estiver inacessível, lança ALIndisponivelError.
"""

from __future__ import annotations

import io
import zipfile
from typing import Iterable

import httpx
from lxml import etree

from src.adapters.base import AdapterBase, FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.config import settings
from src.errors import ALIndisponivelError, ParserFalhouError
from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)

BASE_URL = "https://www.al.sp.gov.br"
URL_DUMP_PROPOSITURAS = f"{BASE_URL}/repositorioDados/processo_legislativo/proposituras.zip"


class AdapterSP(AdapterBase):
    UF = "SP"
    NOME_CASA = "Assembleia Legislativa do Estado de São Paulo"
    SOURCE_ID = "al_sp"
    HOST_PRINCIPAL = BASE_URL

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        # Download do ZIP (timeout maior — dump é grande)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(URL_DUMP_PROPOSITURAS)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("SP", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                raise ALIndisponivelError("SP", None, str(e)) from e

            conteudo_zip = response.content

        try:
            items, total = self._streaming_parse(conteudo_zip, filtros)
        except Exception as e:
            raise ParserFalhouError("SP", f"parse dump ZIP/XML: {e}") from e

        total_pages = (
            (total // filtros.per_page) + (1 if total % filtros.per_page else 0)
            if filtros.per_page
            else 1
        )

        return ResponseEnvelope(
            data=items,
            total=total,
            total_pages=max(total_pages, 1),
            totals_by_nivel=TotalsByNivel(estadual=len(items)),
        )

    def _streaming_parse(
        self, conteudo_zip: bytes, filtros: FiltrosBusca
    ) -> tuple[list[ProposicaoNormalizadaRaw], int]:
        """
        Abre o ZIP em memória, faz iterparse do XML e filtra/pagina sob demanda.
        """
        items: list[ProposicaoNormalizadaRaw] = []
        total_filtrado = 0

        # Janela de paginação
        inicio = (filtros.page - 1) * filtros.per_page
        fim = inicio + filtros.per_page

        with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_names:
                raise ValueError("ZIP não contém .xml")

            with zf.open(xml_names[0]) as xml_stream:
                contexto = etree.iterparse(
                    xml_stream, events=("end",), tag="propositura", recover=True
                )

                for _, elem in contexto:
                    if self._aplica_filtros(elem, filtros):
                        if inicio <= total_filtrado < fim:
                            items.append(self._normalizar(elem))
                        total_filtrado += 1

                    # Libera memória do elemento processado
                    elem.clear()
                    parent = elem.getparent()
                    if parent is not None:
                        while elem.getprevious() is not None:
                            del parent[0]

        return items, total_filtrado

    def _aplica_filtros(self, elem, filtros: FiltrosBusca) -> bool:
        if filtros.ano:
            ano = self._txt(elem, "anoLegislativo") or self._txt(elem, "ano")
            if ano and ano != str(filtros.ano):
                return False
        if filtros.tipo:
            sigla = (self._txt(elem, "siglaTipo") or "").upper()
            if sigla and sigla != filtros.tipo.upper():
                return False
        if filtros.numero:
            numero = self._txt(elem, "numero")
            if numero and numero != filtros.numero:
                return False
        if filtros.keyword:
            ementa = (self._txt(elem, "ementa") or "").lower()
            if filtros.keyword.lower() not in ementa:
                return False
        return True

    def _normalizar(self, elem) -> ProposicaoNormalizadaRaw:
        id_origem = self._txt(elem, "id") or self._txt(elem, "idDocumento") or ""
        sigla = (self._txt(elem, "siglaTipo") or "PL").upper()
        numero = self._txt(elem, "numero")
        ano = self._int(elem, "anoLegislativo") or self._int(elem, "ano")
        ementa = self._txt(elem, "ementa")
        data = self._txt(elem, "dataEntrada") or self._txt(elem, "dataApresentacao")
        autor_nome = self._txt(elem, "nomeAutor") or self._txt(elem, "autor")

        return ProposicaoNormalizadaRaw(
            id_proposicao_origem=str(id_origem),
            casa_origem=self.NOME_CASA,
            sigla_tipo=sigla,
            numero=numero,
            ano=ano,
            ementa=ementa,
            data_apresentacao=self._normalizar_data(data),
            url_inteiro_teor=(
                f"{BASE_URL}/propositura/?id={id_origem}" if id_origem else None
            ),
            autores=[Autor(nome=autor_nome, uf="SP", tipo="Deputado")] if autor_nome else [],
            tramitacoes=[],
            dados_adicionais=DadosAdicionais(
                casaIdentificadora="ALESP",
                enteIdentificador="SP",
                tipoConteudo="Proposição",
                tipoDocumento=sigla,
            ),
            monitor=False,
            nivel_federativo="estadual",
        )

    def _txt(self, elem, tag: str) -> str | None:
        # Procura tanto child direto quanto descendant (XML inconsistente)
        found = elem.find(tag) if elem is not None else None
        if found is None:
            found = elem.find(f".//{tag}") if elem is not None else None
        if found is None or found.text is None:
            return None
        return (found.text or "").strip() or None

    def _int(self, elem, tag: str) -> int | None:
        v = self._txt(elem, tag)
        try:
            return int(v) if v else None
        except ValueError:
            return None

    def _normalizar_data(self, s: str | None) -> str | None:
        if not s:
            return None
        # ALESP usa "DD/MM/YYYY" ou ISO; deixamos a string ISO passar
        if len(s) >= 10 and s[4] == "-":
            return s[:10]
        if len(s) == 10 and s[2] == "/":
            return f"{s[6:10]}-{s[3:5]}-{s[0:2]}"
        return s
