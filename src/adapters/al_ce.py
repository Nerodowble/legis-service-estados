"""
Adapter CE — Assembleia Legislativa do Ceará (ALECE).

Sistema: PHP legado dos anos 2000 (ISO-8859-1).
LIST: GET https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php
  ?nome={26-31}_legislatura&tabela=projeto_lei&opcao={D|T|A|R|J|G|P|I|S|E|V}
  &absolutepage=N
Paginação real: parâmetro `absolutepage` (não `page`).

Opção:
  D = Deliberados, T = Todos, A = Aprovados, R = Retirados, J = Prejudicados,
  G = Diligência, P = Prazo, I = Visto, S = Sobrestado, E = Veto, V = Vetado

robots.txt: VAZIO (Disallow:) — sem restrição.
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
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
    Tramitacao,
)

BASE_URL = "https://www2.al.ce.gov.br"


class AdapterCE(AdapterBase):
    UF = "CE"
    NOME_CASA = "Assembleia Legislativa do Estado do Ceará"
    SOURCE_ID = "al_ce"
    HOST_PRINCIPAL = BASE_URL

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        params = {
            "nome": "31_legislatura",
            "tabela": "projeto_lei",
            "opcao": "T",
            "absolutepage": str(filtros.page),
        }

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/legislativo/proposicoes/numero.php", params=params
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("CE", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("CE", None, str(e)) from e

            html = decode_response(response)  # ISO-8859-1 detectado automaticamente

        return self._parsear_listagem(html, filtros)

    def _parsear_listagem(self, html: str, filtros: FiltrosBusca) -> ResponseEnvelope:
        """
        Estrutura real (validada ao vivo 2026-05-19):
          TR_N:   "Nº do Proj.:1/23 Autor:RENATO ROSENO Entrada:02.02.23 Expediente:07.02.23"
          TR_N+1: idêntico ao N (PHP renderiza 2x)
          TR_N+2: "Ementa:ACRESCE DISPOSITIVO À LEI Nº 12.023..."
          TR_N+3: idêntico ao N+2
          TR_N+4: "Descrição:"
          TR_N+5: "Distribuição/Comissões:CCJR/CVTDU/CTASP Localização:CCJREm 02.02.23 - ..."
        Total reportado no header: "Exibindo registros 1 a 20 (de 2355)"
        """
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []

        # Extrair total absoluto e total de páginas do header da listagem
        texto_completo = tree.body.text() if tree.body else ""
        total_absoluto = 0
        total_pages_real = 63
        m_total = re.search(r"de\s+(\d+)\s*\)", texto_completo)
        if m_total:
            total_absoluto = int(m_total.group(1))
        m_pages = re.search(r"P[áa]gina\s+\d+\s+de\s+(\d+)", texto_completo)
        if m_pages:
            total_pages_real = int(m_pages.group(1))

        # Coletar todos os TRs com texto. Item ocupa múltiplos TRs adjacentes.
        trs = tree.css("tr")
        i = 0
        while i < len(trs):
            txt = re.sub(r"\s+", " ", trs[i].text(strip=True) or "")
            # Cabeçalho de item: "Nº do Proj.:X/AA Autor:Y Entrada:DD.MM.YY [Expediente:...]"
            m_cab = re.match(
                r"N[º°]?\s*do\s*Proj\.?:\s*(\d+)\s*/\s*(\d{2,4})"
                r"\s*Autor:\s*(.+?)"
                r"\s*Entrada:\s*(\d{2}\.\d{2}\.\d{2,4})"
                r"(?:\s*Expediente:\s*(\d{2}\.\d{2}\.\d{2,4}))?",
                txt,
                re.IGNORECASE,
            )
            if not m_cab:
                i += 1
                continue

            numero = m_cab.group(1)
            ano_curto = int(m_cab.group(2))
            ano = ano_curto if ano_curto > 100 else 2000 + ano_curto
            autor = normalizar_texto(m_cab.group(3))
            entrada = m_cab.group(4)

            # Procurar ementa nos próximos TRs adjacentes (até 6 TRs à frente)
            ementa = None
            distribuicao = None
            localizacao = None
            tramitacoes_raw: list[Tramitacao] = []
            for j in range(i + 1, min(i + 8, len(trs))):
                t_seguinte = re.sub(r"\s+", " ", trs[j].text(strip=True) or "")
                if not t_seguinte:
                    continue
                m_ementa = re.match(r"Ementa:\s*(.+?)(?:\s+Descri[çc][ãa]o:|$)", t_seguinte, re.IGNORECASE)
                if m_ementa and not ementa:
                    ementa = normalizar_texto(m_ementa.group(1))
                m_dist = re.search(r"Distribui[çc][ãa]o/Comiss[õo]es:(.+?)(?:Localiza[çc][ãa]o:|$)", t_seguinte, re.IGNORECASE)
                if m_dist and not distribuicao:
                    distribuicao = normalizar_texto(m_dist.group(1))
                m_loc = re.search(r"Localiza[çc][ãa]o:(.+?)Em\s+", t_seguinte, re.IGNORECASE)
                if m_loc and not localizacao:
                    localizacao = normalizar_texto(m_loc.group(1))
                # Tramitações: "Em DD.MM.YY - Descrição"
                for m_tram in re.finditer(r"Em\s+(\d{2}\.\d{2}\.\d{2,4})\s*-\s*([^|]+?)(?=Em\s+\d{2}\.|$)", t_seguinte):
                    tramitacoes_raw.append(
                        Tramitacao(
                            data=self._converter_data(m_tram.group(1)),
                            descricao=normalizar_texto(m_tram.group(2)),
                            sequencia=len(tramitacoes_raw) + 1,
                        )
                    )

            # Última tramitação como status atual
            status = tramitacoes_raw[-1].descricao if tramitacoes_raw else localizacao

            # Mais recente primeiro
            tramitacoes_raw.reverse()
            for idx_t, t in enumerate(tramitacoes_raw, start=1):
                t.sequencia = idx_t

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=f"PL-{numero}-{ano}",
                    casa_origem=self.NOME_CASA,
                    sigla_tipo="PL",
                    numero=numero,
                    ano=ano,
                    ementa=ementa,
                    data_apresentacao=self._converter_data(entrada),
                    status=status,
                    url_inteiro_teor=(
                        f"{BASE_URL}/legislativo/proposicoes/numero.php"
                        f"?nome=31_legislatura&tabela=projeto_lei&opcao=T"
                    ),
                    autores=[Autor(nome=autor, uf="CE", tipo="Deputado")] if autor else [],
                    tramitacoes=tramitacoes_raw,
                    dados_adicionais=DadosAdicionais(
                        codigoMateria=f"PL-{numero}-{ano}",
                        objetivo=distribuicao,
                        casaIdentificadora="ALECE",
                        enteIdentificador="CE",
                        tipoConteudo="Proposição",
                        tipoDocumento="PL",
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

            # Avançar i para pular os TRs já consumidos
            i += 6  # heurística: cada item ocupa ~6 TRs

        items = filtrar_local(items, filtros)
        total = total_absoluto if total_absoluto > 0 else len(items)
        per_page = max(filtros.per_page, 1)
        inicio = (filtros.page - 1) * per_page
        fim = inicio + per_page
        pagina = items[inicio:fim]
        total_pages = total_pages_real

        return ResponseEnvelope(
            data=pagina,
            total=total,
            total_pages=max(total_pages, 1),
            totals_by_nivel=TotalsByNivel(estadual=len(pagina)),
        )

    def _converter_data(self, br: str) -> str | None:
        # CE usa formato 02.02.23 (DD.MM.YY)
        m = re.match(r"(\d{2})\.(\d{2})\.(\d{2,4})", br or "")
        if not m:
            return None
        dia, mes, ano = m.group(1), m.group(2), m.group(3)
        if len(ano) == 2:
            ano = "20" + ano
        return f"{ano}-{mes}-{dia}"
