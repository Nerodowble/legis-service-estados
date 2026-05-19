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

import httpx
from lxml import etree

from src.adapters.base import AdapterBase, FiltrosBusca
from src.config import settings
from src.errors import ALIndisponivelError, ParserFalhouError
from src.schemas import (
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
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
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

    # Mapeamento IdNatureza → sigla (estrutura ALESP validada ao vivo)
    # Fonte: proposituras.xml + cross-check com numero/ano em www.al.sp.gov.br
    _NATUREZA_PARA_SIGLA = {
        "1": "PL",    # Projeto de Lei
        "2": "PLC",   # Projeto de Lei Complementar
        "3": "PEC",   # Proposta de Emenda à Constituição
        "4": "PDL",   # Projeto de Decreto Legislativo
        "5": "PR",    # Projeto de Resolução
        "6": "MOC",   # Moção
        "7": "IND",   # Indicação
        "8": "REQ",   # Requerimento
    }

    # Mapeamento inverso para filtro upstream
    _SIGLA_PARA_NATUREZA = {v: k for k, v in _NATUREZA_PARA_SIGLA.items()}

    def _aplica_filtros(self, elem, filtros: FiltrosBusca) -> bool:
        if filtros.ano:
            ano = self._txt(elem, "AnoLegislativo")
            if ano and ano != str(filtros.ano):
                return False
        if filtros.tipo:
            id_nat = self._txt(elem, "IdNatureza") or ""
            sigla_alvo = filtros.tipo.upper()
            sigla_obtida = self._NATUREZA_PARA_SIGLA.get(id_nat, "")
            if sigla_obtida and sigla_obtida != sigla_alvo:
                return False
        if filtros.numero:
            numero = self._txt(elem, "NroLegislativo")
            if numero and numero != filtros.numero:
                return False
        if filtros.keyword:
            ementa = (self._txt(elem, "Ementa") or "").lower()
            if filtros.keyword.lower() not in ementa:
                return False
        return True

    def _normalizar(self, elem) -> ProposicaoNormalizadaRaw:
        """
        Estrutura real do <propositura> (validada ao vivo 2026-05-19):
          <AnoLegislativo>1996</AnoLegislativo>
          <CodOriginalidade>(spaces)</CodOriginalidade>
          <Ementa>...</Ementa>
          <DtEntradaSistema>2004-01-17T00:00:00-02:00</DtEntradaSistema>
          <DtPublicacao>1996-10-18T00:00:00-02:00</DtPublicacao>
          <IdDocumento>3238</IdDocumento>
          <IdNatureza>1</IdNatureza>
          <NroLegislativo>673</NroLegislativo>

        OBS: o dump proposituras.xml NÃO inclui autor; para autor, seria
        necessário cruzar com autores.zip (fora do escopo atual).
        """
        id_origem = self._txt(elem, "IdDocumento") or ""
        id_natureza = self._txt(elem, "IdNatureza") or ""
        sigla = self._NATUREZA_PARA_SIGLA.get(id_natureza, "PL")
        numero = self._txt(elem, "NroLegislativo")
        ano = self._int(elem, "AnoLegislativo")
        ementa = self._txt(elem, "Ementa")
        # DtPublicacao é a data oficial; DtEntradaSistema é quando o sistema cadastrou
        data = self._txt(elem, "DtPublicacao") or self._txt(elem, "DtEntradaSistema")
        cod_orig = (self._txt(elem, "CodOriginalidade") or "").strip()

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
            autores=[],  # ALESP: autor está em autores.zip (cross-reference futura)
            tramitacoes=[],
            dados_adicionais=DadosAdicionais(
                codigoMateria=id_origem or None,
                objetivo=cod_orig or None,
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
        # ALESP DtPublicacao: "1996-10-18T00:00:00-02:00" → "1996-10-18"
        if len(s) >= 10 and s[4] == "-":
            return s[:10]
        # Formato DD/MM/YYYY
        if len(s) == 10 and s[2] == "/":
            return f"{s[6:10]}-{s[3:5]}-{s[0:2]}"
        return s

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """
        Detalhe via filtro por IdDocumento no dump completo (streaming).

        ALESP não expõe endpoint single-item — baixa proposituras.zip e
        itera procurando o IdDocumento. Custo idêntico à listagem do ano
        completo (uma vez que o dump é único).
        """
        from src.errors import ProposicaoNaoEncontradaError

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
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("SP", None, str(e)) from e
            conteudo_zip = response.content

        with zipfile.ZipFile(io.BytesIO(conteudo_zip)) as zf:
            xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not xml_names:
                raise ParserFalhouError("SP", "ZIP sem .xml")
            with zf.open(xml_names[0]) as xml_stream:
                contexto = etree.iterparse(
                    xml_stream, events=("end",), tag="propositura", recover=True
                )
                for _, elem in contexto:
                    id_doc = self._txt(elem, "IdDocumento")
                    if id_doc == str(id_proposicao):
                        item = self._normalizar(elem)
                        return ResponseEnvelope(
                            data=[item],
                            total=1,
                            total_pages=1,
                            totals_by_nivel=TotalsByNivel(estadual=1),
                        )
                    elem.clear()
                    parent = elem.getparent()
                    if parent is not None:
                        while elem.getprevious() is not None:
                            del parent[0]

        raise ProposicaoNaoEncontradaError("SP", id_proposicao)
