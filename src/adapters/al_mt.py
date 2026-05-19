"""
Adapter MT — Assembleia Legislativa do Mato Grosso (ALMT).

Sistema: HermesLegis (Symfony), instituído pela Lei estadual nº 9.159/2009.
Endpoint: GET https://www.al.mt.gov.br/proposicao/cpdoc/{ID}/visualizar
Padrão técnico: HTML estruturado. O <title> já contém tipo + número/ano + autor + status.

Tipos validados no portal (select tipoPropositura):
  1=PL, 2=PLC, 3=PDL, 4=PR, 5=Veto, 6=IND, 7=REQ, 8/9/10=Mocoes, 11=PEC, 15=Oficio,
  16=MoLouvor, 19=MoRepudio, 20=MoSolidariedade.

Anos cobertos: 1899-2026 (128 anos).

Esta é a implementação de REFERÊNCIA — usar como exemplo para os demais adapters.
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

BASE_URL = "https://www.al.mt.gov.br"

# Mapeamento tipo (sigla) -> id no form Symfony
TIPO_PARA_ID = {
    "PL": 1,
    "PLC": 2,
    "PDL": 3,
    "PR": 4,
    "VET": 5,
    "IND": 6,
    "REQ": 7,
    "PEC": 11,
    "OFI": 15,
}

# Mapeamento reverso (texto longo do portal -> sigla normalizada)
TEXTO_TIPO_PARA_SIGLA = {
    "projeto de lei": "PL",
    "projeto de lei complementar": "PLC",
    "projeto de decreto legislativo": "PDL",
    "projeto de resolução": "PR",
    "veto": "VET",
    "indicação": "IND",
    "requerimento": "REQ",
    "moção de aplausos": "MOC",
    "moção de congratulação": "MOC",
    "moção de pesar": "MOC",
    "proposta de emenda à constituição": "PEC",
    "ofício": "OFI",
    "moção de louvor": "MOC",
    "moção de repúdio": "MOC",
    "moção de solidariedade": "MOC",
}


class AdapterMT(AdapterBase):
    UF = "MT"
    NOME_CASA = "Assembleia Legislativa do Estado de Mato Grosso"
    SOURCE_ID = "al_mt"
    HOST_PRINCIPAL = BASE_URL

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        params: dict[str, str] = {}
        if filtros.ano:
            params["ano"] = str(filtros.ano)
        if filtros.tipo and filtros.tipo.upper() in TIPO_PARA_ID:
            params["tipoPropositura"] = str(TIPO_PARA_ID[filtros.tipo.upper()])
        if filtros.numero:
            params["numero"] = filtros.numero
        if filtros.autor:
            params["autor"] = filtros.autor
        if filtros.keyword:
            params["buscaTextual"] = filtros.keyword
        if filtros.data_inicio:
            params["dataPublicacaoInicio"] = self._formatar_data_br(filtros.data_inicio)
        if filtros.data_fim:
            params["dataPublicacaoFim"] = self._formatar_data_br(filtros.data_fim)

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(f"{BASE_URL}/proposicao", params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("MT", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("MT", None, str(e)) from e

            html = decode_response(response)

        return self._parsear_listagem(html, filtros)

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """GET direto na URL canônica /proposicao/cpdoc/{ID}/visualizar."""
        url = f"{BASE_URL}/proposicao/cpdoc/{id_proposicao}/visualizar"

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("MT", e.response.status_code, str(e)) from e

            html = decode_response(response)

        prop = self._parsear_detalhe(html, id_proposicao, url)
        return ResponseEnvelope(
            data=[prop] if prop else [],
            total=1 if prop else 0,
            total_pages=1,
            totals_by_nivel=TotalsByNivel(estadual=1 if prop else 0),
        )

    # ─────────────────────────────────────────────────────────
    # Parsers privados
    # ─────────────────────────────────────────────────────────

    def _parsear_listagem(self, html: str, filtros: FiltrosBusca) -> ResponseEnvelope:
        """
        Estrutura real do HermesLegis ALMT (validada ao vivo 2026-05-19):

          <h3 class="fs-16">VETO PARCIAL APOSTO AO PROJETO DE LEI Nº 864/2023,
            QUE DISPÕE SOBRE ... AUTORES: DEPUTADO DIEGO GUIMARÃES E
            DEPUTADO EDUARDO BOTELHO</h3>
          <div class="text-muted mb-2">
            Veto n° 1/2026 Mensagem n° 170/2025 - Protocolo n° 871/2026
          </div>
          <div id="collapse-group-172857">
            <turbo-frame src="/proposicao/172857/tramitacoes"></turbo-frame>
            ...
          </div>

        O ID está no `collapse-group-N`. <h3> tem ementa completa + autores
        nominais. <div class="text-muted"> tem tipo/número/ano de cada
        peça (Veto, Mensagem, Protocolo, Processo).
        """
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []
        vistos: set[str] = set()

        # Cada proposição vem num bloco com id="collapse-group-N"
        for grupo in tree.css('div[id^="collapse-group-"]'):
            grupo_id = grupo.attributes.get("id") or ""
            m_id = re.search(r"collapse-group-(\d+)", grupo_id)
            if not m_id:
                continue
            cpdoc_id = m_id.group(1)
            if cpdoc_id in vistos:
                continue
            vistos.add(cpdoc_id)

            # h3 e .text-muted estão como IRMÃOS do collapse-group (não dentro)
            # Buscamos no container que envolve ambos
            container = grupo.parent
            if not container:
                continue

            h3 = container.css_first("h3.fs-16") or container.css_first("h3")
            text_muted = container.css_first("div.text-muted")
            ementa_raw = normalizar_texto(h3.text(strip=True)) if h3 else ""
            meta_raw = normalizar_texto(text_muted.text(strip=True)) if text_muted else ""

            # Extrair sigla+número+ano do .text-muted (primeira peça)
            # Padrão: "Veto n° 1/2026 Mensagem n° 170/2025 - ..."
            sigla, numero, ano = self._extrair_tipo_numero_ano(meta_raw or ementa_raw)

            # Extrair autores do h3 (após "AUTOR:" ou "AUTORES:")
            autores = self._extrair_autores_h3(ementa_raw)

            # Limpar AUTORES: do texto da ementa
            ementa_limpa = re.split(r"\s*AUTOR(?:ES)?:\s*", ementa_raw, maxsplit=1)[0].strip()
            ementa = ementa_limpa or None

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=cpdoc_id,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=numero,
                    ano=ano,
                    ementa=ementa,
                    ementa_detalhada=meta_raw if meta_raw and meta_raw != ementa else None,
                    data_apresentacao=None,
                    status=None,
                    url_inteiro_teor=f"{BASE_URL}/proposicao/cpdoc/{cpdoc_id}/visualizar",
                    autores=autores,
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        codigoMateria=cpdoc_id,
                        casaIdentificadora="ALMT",
                        enteIdentificador="MT",
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

    def _extrair_autores_h3(self, h3_texto: str) -> list[Autor]:
        """
        Extrai lista de autores do <h3>. Padrões observados:
          "... AUTOR: DEPUTADO X"
          "... AUTORES: DEPUTADO X E DEPUTADO Y"
          "... AUTORES: DEPUTADO X, DEPUTADO Y E DEPUTADO Z"
        """
        m = re.search(r"AUTOR(?:ES)?:\s*(.+?)$", h3_texto or "", re.IGNORECASE | re.DOTALL)
        if not m:
            return []
        bloco = m.group(1).strip()
        # Separar por E/vírgula
        nomes_brutos = re.split(r"\s*(?:,|\s+E\s+)\s*", bloco)
        autores: list[Autor] = []
        for nome in nomes_brutos:
            nome = nome.strip().rstrip(".")
            if not nome:
                continue
            # Remover prefixo "DEPUTADO/DEPUTADA"
            tipo = "Deputado"
            m_dep = re.match(r"DEPUTAD[OA]\s+(.+)", nome, re.IGNORECASE)
            if m_dep:
                nome_limpo = m_dep.group(1).strip()
                nome = f"Deputado {nome_limpo}"
            autores.append(Autor(nome=nome, uf="MT", tipo=tipo))
        return autores

    def _parsear_detalhe(
        self, html: str, id_proposicao: str, url: str
    ) -> ProposicaoNormalizadaRaw | None:
        tree = parse_html(html)

        # MT entrega tudo no <title>: "Projeto de lei nº 1/2026 Dep. Eduardo Botelho - Projeto em Tramitação"
        title_node = tree.css_first("title")
        if not title_node:
            raise ParserFalhouError("MT", "<title> não encontrado")
        title = normalizar_texto(title_node.text(strip=True)) or ""

        sigla, numero, ano, autor_nome, status = self._parsear_title(title)

        # Tentar pegar ementa do corpo (selector pode variar; ajustar conforme HTML real)
        ementa = None
        for h_tag in ("h2", "h3", "p"):
            n = tree.css_first(h_tag)
            if n:
                txt = normalizar_texto(n.text(strip=True))
                if txt and len(txt) > 30:
                    ementa = txt
                    break

        autores = [Autor(nome=autor_nome, uf="MT", tipo="Deputado")] if autor_nome else []

        return ProposicaoNormalizadaRaw(
            id_proposicao_origem=id_proposicao,
            casa_origem=self.NOME_CASA,
            sigla_tipo=sigla,
            numero=numero,
            ano=ano,
            ementa=ementa,
            data_apresentacao=None,
            status=status,
            url_inteiro_teor=url,
            autores=autores,
            tramitacoes=[],
            dados_adicionais=DadosAdicionais(
                casaIdentificadora="ALMT",
                enteIdentificador="MT",
                tipoConteudo="Proposição",
                tipoDocumento=sigla,
            ),
            monitor=False,
            nivel_federativo="estadual",
        )

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────

    def _parsear_title(
        self, title: str
    ) -> tuple[str | None, str | None, int | None, str | None, str | None]:
        """
        Title MT padrão:
          "Projeto de lei nº 1/2026 Dep. Eduardo Botelho - Projeto em Tramitação"
        """
        m = re.match(
            r"^(?P<tipo>.+?)\s+n[º°]\s*(?P<num>\d+)/(?P<ano>\d+)\s+"
            r"(?:Dep\.?\s+)?(?P<autor>.+?)\s+-\s+(?P<status>.+)$",
            title,
            re.IGNORECASE,
        )
        if not m:
            return None, None, None, None, title

        tipo_texto = m.group("tipo").strip().lower()
        sigla = TEXTO_TIPO_PARA_SIGLA.get(tipo_texto, tipo_texto[:3].upper())

        try:
            ano = int(m.group("ano"))
        except (TypeError, ValueError):
            ano = None

        return sigla, m.group("num"), ano, m.group("autor").strip(), m.group("status").strip()

    def _extrair_tipo_numero_ano(
        self, texto: str
    ) -> tuple[str | None, str | None, int | None]:
        """
        Extrai sigla+numero+ano de strings como:
          "Projeto de lei complementar nº 1/2026"
          "Proposta de emenda à Constituição nº 1/2026"
          "Veto nº 1/2026 Mensagem nº 170/2025 - ..."
          "PL 42/2026"

        Captura até 5 palavras antes do "nº" e procura match longo→curto
        no TEXTO_TIPO_PARA_SIGLA.
        """
        if not texto:
            return None, None, None
        m = re.search(
            r"((?:[\wáéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]+\s+){0,5}[\wáéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]+)"
            r"\s+n?[º°]?\s*(\d+)\s*/\s*(\d{2,4})",
            texto,
        )
        if not m:
            return None, None, None
        prefixo = m.group(1).strip().lower()

        # Tentar match longo→curto no dicionário
        sigla: str | None = None
        for chave_long, sig in sorted(
            TEXTO_TIPO_PARA_SIGLA.items(), key=lambda kv: -len(kv[0])
        ):
            if chave_long in prefixo:
                sigla = sig
                break
        if not sigla:
            # Fallback: 3 primeiras letras da última palavra do prefixo
            ultima_palavra = prefixo.split()[-1] if prefixo.split() else prefixo
            sigla = ultima_palavra.upper()[:3]

        try:
            ano = int(m.group(3))
            if ano < 100:
                ano += 2000
        except (TypeError, ValueError):
            ano = None
        return sigla, m.group(2), ano

    def _formatar_data_br(self, iso: str) -> str:
        """YYYY-MM-DD -> DD/MM/YYYY (formato esperado pelo Symfony)."""
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso)
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else iso
