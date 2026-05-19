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
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                raise ALIndisponivelError("CE", None, str(e)) from e

            html = decode_response(response)  # ISO-8859-1 detectado automaticamente

        return self._parsear_listagem(html, filtros)

    def _parsear_listagem(self, html: str, filtros: FiltrosBusca) -> ResponseEnvelope:
        # Estrutura PHP legado: cada PL é um bloco com "N° do Proj.: X/AA"
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []

        # TODO (dev): refinar selectores conforme HTML real do PHP legado.
        # Padrão observado: cada PL em uma <tr> com campos consecutivos.
        bloco_texto = tree.body.text() if tree.body else ""

        # Regex no texto puro funciona porque o HTML é gerado por PHP simples.
        # Em modo DOTALL, ".+?" casa newlines — não usar [^\n].
        padrao = re.compile(
            r"N[º°]?\s*do\s*Proj\.?\s*:?\s*(\d+)\s*/\s*(\d{2,4})"
            r"\s*Autor\s*:?\s*(.+?)"
            r"\s*Entrada\s*:?\s*(\d{2}\.\d{2}\.\d{2,4})"
            r"\s*Ementa\s*:?\s*(.+?)(?=N[º°]?\s*do\s*Proj|$)",
            re.IGNORECASE | re.DOTALL,
        )

        for m in padrao.finditer(bloco_texto):
            numero = m.group(1)
            ano_curto = int(m.group(2))
            ano = ano_curto if ano_curto > 100 else 2000 + ano_curto
            autor = normalizar_texto(m.group(3))
            entrada = m.group(4)
            ementa = normalizar_texto(m.group(5))

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=f"PL-{numero}-{ano}",
                    casa_origem=self.NOME_CASA,
                    sigla_tipo="PL",
                    numero=numero,
                    ano=ano,
                    ementa=ementa,
                    data_apresentacao=self._converter_data(entrada),
                    url_inteiro_teor=(
                        f"{BASE_URL}/legislativo/proposicoes/numero.php"
                        f"?nome=31_legislatura&tabela=projeto_lei"
                    ),
                    autores=[Autor(nome=autor, uf="CE", tipo="Deputado")] if autor else [],
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        casaIdentificadora="ALECE",
                        enteIdentificador="CE",
                        tipoConteudo="Proposição",
                        tipoDocumento="PL",
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        items = filtrar_local(items, filtros)
        return ResponseEnvelope(
            data=items,
            total=len(items),
            total_pages=63,  # CE: 31ª legislatura tem 63 páginas conhecidas
            totals_by_nivel=TotalsByNivel(estadual=len(items)),
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
