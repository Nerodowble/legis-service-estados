"""
Adapter MA — Assembleia Legislativa do Maranhão (ALEMA).

Sistema: WordPress com REST API nativa pública.
LIST: GET https://www.al.ma.leg.br/sitealema/wp-json/wp/v2/ordem
  Retorna JSON; mas content.rendered é HTML com PLs estruturados (parser secundário).

CPTs disponíveis (publicos):
  /wp/v2/ordem       (253 ordens do dia)
  /wp/v2/diario      (572 diários)
  /wp/v2/deputado    (134 perfis)
  /wp/v2/posts       (search funciona — "PL 269/2024" retorna resultados)

Headers úteis:
  X-WP-Total — total absoluto
  X-WP-TotalPages — total de páginas
"""

from __future__ import annotations

import re

import httpx

from src.adapters.base import AdapterBase, FiltrosBusca
from src.adapters.filtros import filtrar_local
from src.config import settings
from src.errors import ALIndisponivelError
from src.parsers import normalizar_texto, parse_html
from src.schemas import (
    Autor,
    DadosAdicionais,
    ProposicaoNormalizadaRaw,
    ResponseEnvelope,
    TotalsByNivel,
)

BASE_URL = "https://www.al.ma.leg.br/sitealema/wp-json/wp/v2"


class AdapterMA(AdapterBase):
    UF = "MA"
    NOME_CASA = "Assembleia Legislativa do Estado do Maranhão"
    SOURCE_ID = "al_ma"
    HOST_PRINCIPAL = "https://www.al.ma.leg.br"

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        """
        Estratégia: listar as ordens do dia recentes e extrair PLs estruturados
        de cada content.rendered (HTML embutido).
        """
        params: dict[str, str] = {
            "per_page": str(min(filtros.per_page, 100)),
            "page": str(filtros.page),
        }
        if filtros.ano:
            params["after"] = f"{filtros.ano}-01-01T00:00:00"
            params["before"] = f"{filtros.ano}-12-31T23:59:59"
        if filtros.keyword:
            params["search"] = filtros.keyword

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(f"{BASE_URL}/ordem", params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("MA", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("MA", None, str(e)) from e

            total = int(response.headers.get("X-WP-Total", "0"))
            total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
            ordens = response.json()

        items: list[ProposicaoNormalizadaRaw] = []
        for ordem in ordens:
            html_content = ordem.get("content", {}).get("rendered", "")
            items.extend(self._extrair_pls_de_ordem(html_content, ordem))

        items = filtrar_local(items, filtros)
        return ResponseEnvelope(
            data=items,
            total=total,
            total_pages=total_pages,
            totals_by_nivel=TotalsByNivel(estadual=len(items)),
        )

    def _extrair_pls_de_ordem(
        self, html_content: str, ordem: dict
    ) -> list[ProposicaoNormalizadaRaw]:
        """Parse secundário do HTML embarcado para extrair PLs individuais."""
        if not html_content:
            return []

        tree = parse_html(html_content)
        texto = normalizar_texto(tree.text() or "") or ""

        # Padrão: "PROJETO DE LEI ORDINÁRIA Nº 030/2020, DE AUTORIA DO DEPUTADO X
        #          QUE dispõe sobre criação de programa estadual."
        # Notas:
        #  - autor: aceita letras/acentos/espaços até o "QUE" da ementa
        #  - ementa: aceita até o próximo PROJETO/PEC/etc ou ponto final
        # Autor pode ser: DEPUTADO X, DEPUTADA Y, PODER EXECUTIVO, MESA DIRETORA,
        # COMISSÃO Z, BANCADA W, etc.
        padrao = re.compile(
            r"(?P<tipo>PROJETO DE LEI(?:\s+ORDIN[ÁA]RIA|\s+COMPLEMENTAR)?|PEC|PDL|REQUERIMENTO|INDICA[ÇC][ÃA]O|MO[ÇC][ÃA]O)"
            r"\s+N[º°]\s*(?P<num>\d+)\s*/\s*(?P<ano>\d{4})"
            r"(?:[\s,]*DE\s+AUTORIA\s+(?:DO|DA|DOS|DAS)?\s*"
            r"(?P<tipo_autor>DEPUTAD[OA]|PODER\s+EXECUTIVO|MESA\s+DIRETORA|COMISS[ÃA]O|BANCADA|PODER\s+JUDICI[ÁA]RIO|MINIST[ÉE]RIO\s+P[ÚU]BLICO|TRIBUNAL\s+DE\s+CONTAS)?"
            r"\s*(?P<autor>[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇa-zçáéíóú\s\.]+?))?"
            r"(?:[\s,]+QUE\s+(?P<ementa>.+?))?"
            r"(?=\s+(?:PROJETO|PEC|PDL|REQUERIMENTO|INDICA[ÇC][ÃA]O|MO[ÇC][ÃA]O)\s+N|\s*$|\.\s*$)",
            re.IGNORECASE | re.DOTALL,
        )

        items: list[ProposicaoNormalizadaRaw] = []
        vistos: set[tuple[str, str, int]] = set()

        for m in padrao.finditer(texto):
            sigla = self._normalizar_sigla(m.group("tipo"))
            numero = m.group("num").lstrip("0") or "0"
            try:
                ano = int(m.group("ano"))
            except (TypeError, ValueError):
                continue

            chave = (sigla, numero, ano)
            if chave in vistos:
                continue
            vistos.add(chave)

            autor = normalizar_texto(m.group("autor"))
            tipo_autor_bruto = (m.group("tipo_autor") or "").upper()
            ementa = normalizar_texto(m.group("ementa"))

            # Classificar tipo do autor
            if "DEPUTAD" in tipo_autor_bruto:
                tipo_autor = "Deputado"
                nome_autor = f"Deputado {autor}" if autor else None
            elif "EXECUTIVO" in tipo_autor_bruto:
                tipo_autor = "Executivo"
                nome_autor = "Poder Executivo"
            elif "MESA" in tipo_autor_bruto:
                tipo_autor = "Comissao"
                nome_autor = "Mesa Diretora"
            elif "COMISS" in tipo_autor_bruto:
                tipo_autor = "Comissao"
                nome_autor = f"Comissão {autor}" if autor else "Comissão"
            elif "BANCADA" in tipo_autor_bruto:
                tipo_autor = "Comissao"
                nome_autor = f"Bancada {autor}" if autor else "Bancada"
            elif tipo_autor_bruto:
                tipo_autor = "Outro"
                nome_autor = f"{tipo_autor_bruto.title()} {autor or ''}".strip()
            else:
                tipo_autor = "Outro"
                nome_autor = autor

            autores_list = [Autor(nome=nome_autor, uf="MA", tipo=tipo_autor)] if nome_autor else []

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=f"{sigla}-{numero}-{ano}",
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=numero,
                    ano=ano,
                    ementa=ementa,
                    data_apresentacao=(ordem.get("date") or "")[:10],
                    url_inteiro_teor=ordem.get("link"),
                    autores=autores_list,
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        casaIdentificadora="ALEMA",
                        enteIdentificador="MA",
                        tipoConteudo="Proposição",
                        tipoDocumento=sigla,
                    ),
                    monitor=False,
                    nivel_federativo="estadual",
                )
            )

        return items

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """
        Detalhe ALEMA: id é o slug "{SIGLA}-{NUM}-{ANO}" gerado pelo adapter.
        Como cada PL vem embarcado em uma "Ordem do Dia" no WordPress REST,
        e o WP-JSON não expõe filtro direto, percorremos várias ordens
        recentes do ano alvo e devolvemos a primeira que casar.
        """
        from src.errors import ProposicaoNaoEncontradaError

        m = re.match(r"([A-Z]+)-(\d+)-(\d{4})", id_proposicao)
        if not m:
            raise ProposicaoNaoEncontradaError("MA", id_proposicao)
        sigla_alvo = m.group(1)
        numero_alvo = m.group(2)
        ano_alvo = int(m.group(3))

        # Buscar até 50 ordens do ano (geralmente cobre tudo)
        try:
            envelope = await self.listar(
                FiltrosBusca(page=1, per_page=50, ano=ano_alvo, tipo=sigla_alvo, numero=numero_alvo)
            )
        except Exception as e:
            raise ALIndisponivelError("MA", None, str(e)) from e

        for item in envelope.data:
            if (
                item.sigla_tipo == sigla_alvo
                and item.numero == numero_alvo
                and item.ano == ano_alvo
            ):
                return ResponseEnvelope(
                    data=[item],
                    total=1,
                    total_pages=1,
                    totals_by_nivel=TotalsByNivel(estadual=1),
                )

        raise ProposicaoNaoEncontradaError("MA", id_proposicao)

    def _normalizar_sigla(self, texto: str) -> str:
        t = texto.upper().strip()
        if "PROJETO DE LEI COMPLEMENTAR" in t:
            return "PLC"
        if "PROJETO DE LEI" in t:
            return "PL"
        if "EMENDA À CONSTITUIÇÃO" in t or t == "PEC":
            return "PEC"
        if "DECRETO LEGISLATIVO" in t or t == "PDL":
            return "PDL"
        if "REQUERIMENTO" in t:
            return "REQ"
        if "INDICAÇÃO" in t or "INDICACAO" in t:
            return "IND"
        if "MOÇÃO" in t or "MOCAO" in t:
            return "MOC"
        return t[:3]
