"""
Adapter AP — Assembleia Legislativa do Amapá (ALAP).

Sistema: eLegis Laravel SSR.
Endpoint LIST: GET https://elegis.al.ap.leg.br/portal/proposicoes?ano=YYYY&tipo_proposicao=N
Endpoint DETAIL: GET https://elegis.al.ap.leg.br/portal/proposicao/{id}    (id sequencial 1..~92151)
Padrão técnico: HTML SSR.

Fonte secundária (Diário Eletrônico, Lei 1797/2014):
  ediario.al.ap.leg.br/diario/consulta/?data_de=...&data_ate=...&q=...

Tipos AP (select):
  1=PLO, 2=PLC, 3=REQ, 4=PEC, 5=MOC, 8=IND, 9=Projeto Resolução, 10=PDL, 11=Prestação Contas

robots.txt:
  al.ap.leg.br DISALLOW /pagina.php (sistema legado - NÃO USAR)
  elegis.al.ap.leg.br liberado
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

BASE_URL = "https://elegis.al.ap.leg.br"
URL_PORTAL_ALAP = "https://al.ap.leg.br"
URL_LISTA_PARLAMENTARES = f"{URL_PORTAL_ALAP}/pagina.php?pg=exibir_legislatura"

TIPO_PARA_ID = {"PLO": 1, "PL": 1, "PLC": 2, "REQ": 3, "PEC": 4, "MOC": 5, "IND": 8, "PR": 9, "PDL": 10}


class AdapterAP(AdapterBase):
    UF = "AP"
    NOME_CASA = "Assembleia Legislativa do Estado do Amapá"
    SOURCE_ID = "al_ap"
    HOST_PRINCIPAL = BASE_URL

    # Cache do mapping {nome_normalizado: (id_dep, partido)} construído sob
    # demanda no primeiro fetch que precise enriquecer autor. Singleton
    # dentro do processo (adapter é singleton); zero persistência em disco.
    # Expira após CACHE_TTL_SECONDS para refletir mudanças de partido/mandato.
    _cache_parlamentares: dict[str, tuple[str, str]] | None = None
    _cache_parlamentares_ts: float = 0.0
    CACHE_TTL_SECONDS: float = 6 * 3600  # 6 horas (mandato de deputado raramente muda)

    async def listar(self, filtros: FiltrosBusca) -> ResponseEnvelope:
        # Warm-up do cache de parlamentares (silencioso se falhar)
        await self._construir_cache_parlamentares()

        params: dict[str, str] = {}
        if filtros.ano:
            params["ano"] = str(filtros.ano)
        if filtros.tipo and filtros.tipo.upper() in TIPO_PARA_ID:
            params["tipo_proposicao"] = str(TIPO_PARA_ID[filtros.tipo.upper()])

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(f"{BASE_URL}/portal/proposicoes", params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("AP", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("AP", None, str(e)) from e

            html = decode_response(response)

        return self._parsear_listagem(html, filtros)

    def _parsear_listagem(self, html: str, filtros: FiltrosBusca) -> ResponseEnvelope:
        tree = parse_html(html)
        items: list[ProposicaoNormalizadaRaw] = []

        # Cada PL é uma <tr> na tabela; ajustar selector conforme HTML real
        for tr in tree.css("tr"):
            cells = tr.css("td")
            if len(cells) < 4:
                continue

            data = normalizar_texto(cells[0].text(strip=True))
            tipo_numero = normalizar_texto(cells[1].text(strip=True))
            autor = normalizar_texto(cells[2].text(strip=True))
            ementa = normalizar_texto(cells[3].text(strip=True))

            if not tipo_numero:
                continue

            sigla, numero, ano = self._extrair_tipo_numero_ano(tipo_numero)
            link = tr.css_first("a[href*='/portal/proposicao/']")
            url = link.attributes.get("href", "") if link else ""
            id_origem = ""
            if url:
                m = re.search(r"/portal/proposicao/(\d+)", url)
                if m:
                    id_origem = m.group(1)

            if not id_origem:
                continue

            items.append(
                ProposicaoNormalizadaRaw(
                    id_proposicao_origem=id_origem,
                    casa_origem=self.NOME_CASA,
                    sigla_tipo=sigla,
                    numero=numero,
                    ano=ano,
                    ementa=ementa,
                    data_apresentacao=self._formatar_data(data),
                    url_inteiro_teor=f"{BASE_URL}/portal/proposicao/{id_origem}",
                    autores=[self._enriquecer_autor(autor)] if autor else [],
                    tramitacoes=[],
                    dados_adicionais=DadosAdicionais(
                        codigoMateria=id_origem,
                        casaIdentificadora="ALAP",
                        enteIdentificador="AP",
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

    async def detalhe(self, id_proposicao: str) -> ResponseEnvelope:
        """
        Busca detalhe via /portal/proposicao/{id} no eLegis.
        ID é o sequencial 1..~120000 que aparece nos hrefs da listagem.
        """
        # Warm-up do cache de parlamentares (silencioso se falhar)
        await self._construir_cache_parlamentares()

        url = f"{BASE_URL}/portal/proposicao/{id_proposicao}"

        async with httpx.AsyncClient(
            timeout=settings.HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": settings.USER_AGENT},
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise ALIndisponivelError("AP", e.response.status_code, str(e)) from e
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError) as e:
                raise ALIndisponivelError("AP", None, str(e)) from e

            html = decode_response(response)

        return self._parsear_detalhe(html, id_proposicao, url)

    def _parsear_detalhe(
        self, html: str, id_origem: str, url: str
    ) -> ResponseEnvelope:
        """
        Estrutura observada no eLegis ALAP (id 108457 etc):
          <h1 class="mb-0">Moção nº 0317/26-AL</h1>
          <div class="card-body">
            <p><strong>Origem:</strong> Deputado Rodolfo Vale</p>
            <p><strong>Ementa:</strong> Moção de Aplauso...</p>
            <p><strong>Data de Protocolo:</strong> 19/05/2026</p>
            <p><strong>Texto Original:</strong> ...</p>
            <p><strong>Observações:</strong></p>
          </div>
        """
        tree = parse_html(html)

        # 1. Tipo/número/ano vindos do <h1>
        sigla, numero, ano = "PL", None, None
        h1 = tree.css_first("h1.mb-0") or tree.css_first("h1")
        if h1:
            t = normalizar_texto(h1.text(strip=True)) or ""
            m = re.search(r"(\w+(?:\s+\w+){0,3})\s*n[º°]?\s*(\d+)/(\d{2,4})", t)
            if m:
                sigla = self._normalizar_sigla_curta(m.group(1))
                numero = m.group(2).lstrip("0") or "0"
                a = int(m.group(3))
                ano = a if a > 100 else 2000 + a

        # 2. Campos dentro de <p><strong>Rótulo:</strong> Valor</p>
        campos: dict[str, str] = {}
        for p in tree.css("p"):
            strong = p.css_first("strong")
            if not strong:
                continue
            rotulo = (strong.text(strip=True) or "").rstrip(":").strip().lower()
            if not rotulo:
                continue
            texto_total = p.text(strip=True) or ""
            valor = texto_total
            rotulo_completo = strong.text(strip=True) or ""
            if rotulo_completo and valor.startswith(rotulo_completo):
                valor = valor[len(rotulo_completo):].strip()
            valor = normalizar_texto(valor)
            if valor:
                campos[rotulo] = valor

        autor_nome = campos.get("origem") or campos.get("autor") or campos.get("autoria")
        ementa = campos.get("ementa")
        data_protocolo = campos.get("data de protocolo") or campos.get("data de apresentação")
        observacoes = campos.get("observações") or campos.get("observacoes")

        # 3. URL canônica do PDF (quando "Texto Original" tem link)
        url_pdf: str | None = None
        for p in tree.css("p"):
            strong = p.css_first("strong")
            if not strong:
                continue
            rotulo = (strong.text(strip=True) or "").rstrip(":").strip().lower()
            if rotulo == "texto original":
                link = p.css_first("a[href]")
                if link:
                    href = link.attributes.get("href") or ""
                    if href and href.lower() != "não disponível":
                        url_pdf = href if href.startswith("http") else f"{BASE_URL}{href}"
                break

        # 4. Tramitações via tabela <h2>Movimentos</h2> + <table>
        tramitacoes = self._extrair_tramitacoes(tree)

        # 5. Status atual = última tramitação (mais recente)
        status: str | None = None
        if tramitacoes:
            status = tramitacoes[0].descricao or tramitacoes[0].despacho

        # 6. Legislatura como contexto (vai para dados_adicionais.objetivo
        # já que o schema não tem campo dedicado)
        legislatura = self._extrair_legislatura(tree)

        item = ProposicaoNormalizadaRaw(
            id_proposicao_origem=id_origem,
            casa_origem=self.NOME_CASA,
            sigla_tipo=sigla.upper(),
            numero=numero,
            ano=ano,
            ementa=ementa,
            ementa_detalhada=observacoes if observacoes else None,
            data_apresentacao=self._formatar_data(data_protocolo),
            status=status,
            url_inteiro_teor=url_pdf or url,
            autores=[self._enriquecer_autor(autor_nome)] if autor_nome else [],
            tramitacoes=tramitacoes,
            dados_adicionais=DadosAdicionais(
                codigoMateria=id_origem,
                casaIdentificadora="ALAP",
                enteIdentificador="AP",
                tipoConteudo="Proposição",
                tipoDocumento=sigla.upper(),
                objetivo=legislatura,
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

    async def _construir_cache_parlamentares(self) -> None:
        """
        Constrói mapping {nome_normalizado: (iddeputado, partido)} via 1 fetch:

        A página /pagina.php?pg=exibir_legislatura tem 24 cards, e CADA
        <a iddeputado=N> tem um atributo `onmouseover="Tip('<b>Dep.</b> Aldilene
        Souza<br><b>Nome Completo:</b> ALDILENE MATOS DE SOUZA<br><b>Partido:</b>
        PDT<br><b>Profissão:</b> Administradora', ...)"`.
        Parseamos esse tooltip para extrair Partido + Profissão por deputado.

        Cache TTL controlado: rebuilds após CACHE_TTL_SECONDS para refletir
        mudanças de mandato/filiação partidária. Falhas silenciosas.
        """
        import time

        agora = time.time()
        idade = agora - AdapterAP._cache_parlamentares_ts
        cache_ok = AdapterAP._cache_parlamentares is not None
        cache_fresco = idade < AdapterAP.CACHE_TTL_SECONDS

        if cache_ok and cache_fresco:
            return
        try:
            async with httpx.AsyncClient(
                timeout=settings.HTTP_TIMEOUT_SECONDS,
                headers={"User-Agent": settings.USER_AGENT},
                follow_redirects=True,
            ) as client:
                response = await client.get(URL_LISTA_PARLAMENTARES)
                response.raise_for_status()
                html_lista = decode_response(response)
        except Exception:
            AdapterAP._cache_parlamentares = {}
            AdapterAP._cache_parlamentares_ts = agora  # marca tentativa para não martelar
            return

        tree = parse_html(html_lista)
        cache: dict[str, tuple[str, str]] = {}

        for card in tree.css(".box-foto-deputados"):
            a = card.css_first('a[href*="iddeputado="]')
            if not a:
                continue
            href = a.attributes.get("href") or ""
            m_id = re.search(r"iddeputado=(\d+)", href)
            if not m_id:
                continue
            iddep = m_id.group(1)

            onmouseover = a.attributes.get("onmouseover") or ""
            # onmouseover="Tip('<b>Dep.</b> Aldilene Souza<br>
            #                  <b>Nome Completo:</b> ALDILENE MATOS DE SOUZA<br>
            #                  <b>Partido:</b> PDT<br>...', ...)"
            m_nome = re.search(r"<b>Dep\.</b>\s*([^<]+?)<br>", onmouseover)
            m_partido = re.search(r"<b>Partido:</b>\s*([^<]+?)<br>", onmouseover)
            if not m_nome:
                continue
            nome = self._normalizar_nome_dep(m_nome.group(1))
            partido = m_partido.group(1).strip() if m_partido else ""
            if nome:
                cache[nome] = (iddep, partido)

        AdapterAP._cache_parlamentares = cache
        AdapterAP._cache_parlamentares_ts = agora

    def _normalizar_nome_dep(self, nome: str) -> str:
        """Remove prefixos 'Deputado/Deputada/Dep.' e normaliza espaços."""
        s = nome.strip()
        s = re.sub(r"^Deputad[oa]\.?\s+", "", s, flags=re.IGNORECASE)
        s = re.sub(r"^Dep\.\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    def _enriquecer_autor(self, nome_bruto: str) -> Autor:
        """Constrói Autor com partido + id_autor_origem quando o cache permite."""
        nome_limpo = self._normalizar_nome_dep(nome_bruto)
        cache = AdapterAP._cache_parlamentares or {}
        info = cache.get(nome_limpo)
        if not info:
            # tenta match case-insensitive
            for k, v in cache.items():
                if k.lower() == nome_limpo.lower():
                    info = v
                    break
        id_dep, partido = info if info else ("", None)
        return Autor(
            id_autor_origem=id_dep or None,
            nome=nome_bruto,  # preserva o "Deputado X" para o consumidor
            partido=partido or None,
            uf="AP",
            tipo="Deputado",
        )

    def _extrair_tramitacoes(self, tree) -> list[Tramitacao]:
        """
        ALAP renderiza tramitações em uma tabela com cabeçalho Data/Status/Documento,
        usualmente após um <h2>Movimentos</h2>.
        Tramitações vêm em ordem cronológica do portal — invertemos para deixar a
        mais recente primeiro (convenção do contrato com o legis-service).
        """
        tramitacoes: list[Tramitacao] = []
        for tabela in tree.css("table"):
            cabecalho = tabela.css_first("tr")
            if not cabecalho:
                continue
            headers = [
                (th.text(strip=True) or "").lower()
                for th in cabecalho.css("th")
            ]
            # Tabela alvo: ["data", "status", "documento"]
            if not ({"data", "status"} <= set(headers)):
                continue

            idx_data = headers.index("data") if "data" in headers else 0
            idx_status = headers.index("status") if "status" in headers else 1
            idx_doc = headers.index("documento") if "documento" in headers else -1

            for sequencia, tr in enumerate(tabela.css("tr"), start=1):
                cells = tr.css("td")
                if len(cells) < 2:  # pular header
                    continue
                data_br = normalizar_texto(cells[idx_data].text(strip=True))
                status = normalizar_texto(cells[idx_status].text(strip=True))
                doc_url: str | None = None
                if 0 <= idx_doc < len(cells):
                    link = cells[idx_doc].css_first("a[href]")
                    if link:
                        href = link.attributes.get("href") or ""
                        if href:
                            doc_url = href if href.startswith("http") else f"{BASE_URL}{href}"

                orgao, nome_orgao, tipo_tramit = self._extrair_orgao_da_descricao(status or "")
                tramitacoes.append(
                    Tramitacao(
                        data=self._formatar_data(data_br),
                        orgao=orgao,
                        nome_orgao=nome_orgao,
                        descricao=status,
                        tipo_tramitacao=tipo_tramit,
                        sequencia=sequencia,
                        url_documento=doc_url,
                    )
                )
            break  # só processamos a primeira tabela compatível
        # Mais recentes primeiro
        tramitacoes.reverse()
        for i, t in enumerate(tramitacoes, start=1):
            t.sequencia = i
        return tramitacoes

    def _extrair_orgao_da_descricao(
        self, descricao: str
    ) -> tuple[str | None, str | None, str | None]:
        """
        Heurística: extrai órgão e tipo-de-movimento da descrição da tramitação.

        Exemplos observados em ALAP:
          "Enviado para Diretoria Legislativa"           → orgao=DLE, nome=Diretoria Legislativa, tipo=Encaminhamento
          "Incluído para leitura: 17ª Sessão Extraordinária" → orgao=PLEN, nome=17ª Sessão Extraordinária, tipo=Leitura
          "Aprovado em Comissão de Constituição e Justiça" → orgao=CCJ, nome=CCJ, tipo=Aprovação
        """
        d = (descricao or "").strip()
        if not d:
            return None, None, None

        # Tipo de movimento (verbo da frase)
        tipo: str | None = None
        m_tipo = re.match(
            r"(Enviad[oa]|Recebid[oa]|Inclu[íi]d[oa]|Aprovad[oa]|Rejeitad[oa]|"
            r"Arquivad[oa]|Devolvid[oa]|Publicad[oa]|Distribu[íi]d[oa]|Designad[oa]|"
            r"Apresentad[oa]|Protocolad[oa])",
            d,
            re.IGNORECASE,
        )
        if m_tipo:
            tipo = m_tipo.group(1).capitalize()

        # Nome do órgão: tudo após "para" ou após ":"
        nome_orgao: str | None = None
        m_para = re.search(r"\bpara\s+(.+?)(?:[.,;]|$)", d, re.IGNORECASE)
        if m_para:
            nome_orgao = m_para.group(1).strip()
        else:
            m_dpts = re.search(r":\s*(.+?)(?:[.,;]|$)", d)
            if m_dpts:
                nome_orgao = m_dpts.group(1).strip()

        # Sigla do órgão (mapping conhecido)
        orgao_map = {
            "Diretoria Legislativa": "DLE",
            "Plenário": "PLEN",
            "Mesa Diretora": "MESA",
            "Comissão de Constituição e Justiça": "CCJ",
            "Comissão de Constituição, Justiça e Redação": "CCJR",
        }
        orgao: str | None = None
        if nome_orgao:
            for nome_long, sigla in orgao_map.items():
                if nome_long.lower() in (nome_orgao or "").lower():
                    orgao = sigla
                    break
            if not orgao and "Sessão" in nome_orgao:
                orgao = "PLEN"

        return orgao, nome_orgao, tipo

    def _extrair_legislatura(self, tree) -> str | None:
        """
        Extrai 'IX Legislatura - 2023 / 2027 - 3ª sessão Legislativa' do <h1>
        secundário, guardado em dados_adicionais.objetivo para preservar contexto.
        """
        for h1 in tree.css("h1"):
            t = normalizar_texto(h1.text(strip=True)) or ""
            if "Legislatura" in t and re.search(r"\d{4}", t):
                return t
        return None

    def _normalizar_sigla_curta(self, texto: str) -> str:
        t = (texto or "").lower().strip()
        if "complementar" in t:
            return "PLC"
        if "moção" in t or "mocao" in t:
            return "MOC"
        if "indicação" in t or "indicacao" in t:
            return "IND"
        if "requerimento" in t:
            return "REQ"
        if "emenda" in t:
            return "PEC"
        if "decreto" in t:
            return "PDL"
        if "lei" in t:
            return "PL"
        if "resolução" in t or "resolucao" in t:
            return "PR"
        return t[:3].upper() or "PL"

    def _extrair_tipo_numero_ano(self, texto: str) -> tuple[str | None, str | None, int | None]:
        m = re.search(r"(\w+(?:\s+\w+){0,4})\s*n[º°]?\s*(\d+)/(\d{2,4})", texto, re.IGNORECASE)
        if not m:
            return None, None, None
        sigla_raw = m.group(1).strip().lower()
        sigla_map = {
            "projeto de lei ordinária": "PL",
            "projeto de lei complementar": "PLC",
            "requerimento": "REQ",
            "indicação": "IND",
            "moção": "MOC",
            "projeto de resolução": "PR",
            "proposta de emenda à constituição": "PEC",
        }
        sigla = next(
            (v for k, v in sigla_map.items() if k in sigla_raw),
            sigla_raw[:3].upper(),
        )
        try:
            ano = int(m.group(3))
            if ano < 100:
                ano += 2000
        except (TypeError, ValueError):
            ano = None
        return sigla, m.group(2), ano

    def _formatar_data(self, br: str | None) -> str | None:
        if not br:
            return None
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", br)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else br
