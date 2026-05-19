"""
Adapter RJ — Assembleia Legislativa do Estado do Rio de Janeiro (ALERJ).

Sistema: IBM Lotus Notes / Domino (legado anos 90).
ATENÇÃO: HTTP (não HTTPS). Sistema estável há 20+ anos.

LIST: GET http://alerjln1.alerj.rj.gov.br/{base}.nsf/{view}?ReadViewEntries&Start=N&Count=M

Bases (.nsf):
  scpro2327.nsf — legislatura corrente (2023-2027)
  scpro.nsf      — histórico (2.563 leis)
  contlei.nsf    — legislação consolidada

Views: vlei, vleicomp, vMensagem, vindicacao, vemenda, vdecreto, vveto, vresolucao

Parser específico em src/parsers/lotus.py
"""

from __future__ import annotations

import httpx

from src.adapters.base import AdapterBase, FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.config import settings
from src.errors import ALIndisponivelError, ParserFalhouError
from src.parsers.lotus import parse_view_entries
from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)

# HTTP (NÃO HTTPS) — sistema legado
BASE_URL = "http://alerjln1.alerj.rj.gov.br"

TIPO_PARA_VIEW = {
    "PL": "vlei",
    "PLC": "vleicomp",
    "MSG": "vMensagem",
    "IND": "vindicacao",
    "PEC": "vemenda",
    "PDL": "vdecreto",
    "VET": "vveto",
    "PR": "vresolucao",
}


class AdapterRJ(AdapterBase):
    UF = "RJ"
    NOME_CASA = "Assembleia Legislativa do Estado do Rio de Janeiro"
    SOURCE_ID = "al_rj"
    HOST_PRINCIPAL = BASE_URL

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        # Selecionar base por ano
        base = "scpro2327" if (filtros.ano or 2024) >= 2023 else "scpro"
        view = TIPO_PARA_VIEW.get((filtros.tipo or "PL").upper(), "vlei")
        sigla = (filtros.tipo or "PL").upper()

        start = (filtros.page - 1) * filtros.per_page + 1

        url = f"{BASE_URL}/{base}.nsf/{view}"
        params = {
            "ReadViewEntries": "",
            "Start": str(start),
            "Count": str(filtros.per_page),
        }

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("RJ", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                raise ALIndisponivelError("RJ", None, str(e)) from e

            xml_str = response.text

        try:
            total, entries = parse_view_entries(xml_str, view)
        except Exception as e:
            raise ParserFalhouError("RJ", f"parse Lotus falhou: {e}") from e

        items: list[ProposicaoNormalizadaRaw] = []
        for e in entries:
            unid = e.get("_unid") or ""
            numero_raw = e.get("numero") or ""
            # Lotus retorna "PL 1234/2024" — extrair numero e ano
            num, ano = self._parsear_numero_lotus(numero_raw)

            autor_nome = e.get("autor")
            ementa = e.get("ementa")
            data = e.get("data_apresentacao")
            situacao = e.get("situacao")

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=unid,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=num,
                    ano=ano,
                    ementa=ementa,
                    data_apresentacao=data,
                    status=situacao,
                    url_inteiro_teor=f"{BASE_URL}/{base}.nsf/{unid}?OpenDocument" if unid else None,
                    autores=[Autor(nome=autor_nome, uf="RJ", tipo="Deputado")] if autor_nome else [],
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        casaIdentificadora="ALERJ",
                        enteIdentificador="RJ",
                        tipoConteudo="Proposição",
                        tipoDocumento=sigla,
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        total_pages = (total // filtros.per_page) + 1 if filtros.per_page else 1

        items = filtrar_local(items, filtros)
        return ResponseEnvelope(
            data=items,
            total=total,
            total_pages=total_pages,
            totals_by_nivel=TotalsByNivel(estadual=len(items)),
        )

    def _parsear_numero_lotus(self, s: str) -> tuple[str | None, int | None]:
        import re

        m = re.search(r"(\d+)/(\d{2,4})", s or "")
        if not m:
            return None, None
        ano_raw = int(m.group(2))
        ano = ano_raw if ano_raw > 100 else 2000 + ano_raw
        return m.group(1), ano
