# Adapters por Estado — lógica e particularidades

Este documento descreve, para cada uma das 11 ALs cobertas, o **padrão técnico upstream**, a **lógica de extração**, os **campos retornados** e as **particularidades observadas**.

Para a matriz consolidada de capacidade (executável):
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_completude_por_al.py::test_imprimir_matriz_capacidade -s
```

---

## 🟢 al_ap — Amapá (ALAP)

**Casa**: Assembleia Legislativa do Estado do Amapá
**Sistema upstream**: eLegis Laravel SSR
**Detalhe implementado**: ✅ SIM (mais rico de todos)

### Endpoints upstream
| Operação | URL |
|---|---|
| LIST | `GET https://elegis.al.ap.leg.br/portal/proposicoes?ano=YYYY&tipo_proposicao=N` |
| DETAIL | `GET https://elegis.al.ap.leg.br/portal/proposicao/{ID}` |
| Parlamentares | `GET https://al.ap.leg.br/pagina.php?pg=exibir_legislatura` |

### Lógica
1. **Listagem**: parseia `<tbody><tr>` com 5 cells: data, tipo+número, autor, ementa, link.
2. **Detalhe**: parseia `<h1>` para tipo+número+ano, `<p><strong>Origem/Ementa/Data/Texto Original/Observações</strong>...</p>`, e tabela `<h2>Movimentos</h2> + <table>` para tramitações.
3. **Enriquecimento de autor**: fetch único da página de parlamentares cacheado em memória; tooltip `onmouseover` de cada deputado tem `<b>Partido:</b> X` e `<b>Profissão:</b> Y`.

### TIPO_PARA_ID
| Sigla | ID upstream |
|---|---|
| PLO / PL | 1 |
| PLC | 2 |
| REQ | 3 |
| PEC | 4 |
| MOC | 5 |
| IND | 8 |
| PR | 9 |
| PDL | 10 |

### Campos extraídos
✅ id, sigla, número, ano, ementa, data, **autor com partido**, status (última tramitação), url, tramitações (no detalhe), legislatura (em `dados_adicionais.objetivo`), codigoMateria

### Exemplo
```bash
curl 'http://localhost:8081/propositions/fetch-live/al_ap/108457'
```

### Particularidades
- 27 cards por página, paginação client-side (fonte devolve tudo)
- Heurística de órgão: "Enviado para Diretoria Legislativa" → `orgao=DLE`, `nome_orgao=Diretoria Legislativa`, `tipo_tramitacao=Enviado`
- `robots.txt`: subdomínio `al.ap.leg.br` proíbe `/pagina.php` mas `elegis.al.ap.leg.br` é liberado

---

## 🟢 al_ba — Bahia (ALBA)

**Casa**: Assembleia Legislativa do Estado da Bahia
**Sistema upstream**: Portal ALBA "atividade-legislativa-nova"
**Detalhe implementado**: ✅ SIM

### Endpoints upstream
| Operação | URL |
|---|---|
| LIST | `GET https://www.al.ba.gov.br/atividade-legislativa-nova/proposicoes?dataInicio=DD/MM/YYYY&dataFim=DD/MM/YYYY&palavra=X&numero=N` |
| DETAIL | `GET https://www.al.ba.gov.br/atividade-legislativa-nova/proposicao/{TIPO}-{NUM}-{ANO}` |

### Lógica
1. **Listagem**: extrai slugs canônicos `TIPO-NUM-ANO` (ex: `REQ-10650-2025`) de cada `<a href="/atividade-legislativa-nova/proposicao/...">`.
2. **Detalhe**: GET direto na URL canônica; parseia HTML para ementa, autor, tramitações.

### Campos extraídos
✅ id (slug), sigla, número, ano, url

### Particularidades
- **Pegadinha histórica**: o path antigo `/atividade-legislativa/` retorna sempre os mesmos 20 OF/REQ de 2020-2021 (lista hardcoded). Use **`atividade-legislativa-nova`**.
- Aceita formatos com ponto: `REQ-9.698-2021` (parseado pelo `_parsear_slug`)
- Filtros nativos: `dataInicio`, `dataFim`, `palavra`, `numero`, `tipoProposicao`
- ⚠️ Achado de segurança (não-exploitado): Spring Boot Actuator parcialmente exposto. Reportado responsavelmente; não usar para fingerprinting.

---

## 🟡 al_ce — Ceará (ALECE)

**Casa**: Assembleia Legislativa do Estado do Ceará
**Sistema upstream**: PHP legado dos anos 2000, **ISO-8859-1**
**Detalhe implementado**: ❌ não (default da base)

### Endpoint
```
GET https://www2.al.ce.gov.br/legislativo/proposicoes/numero.php
  ?nome=31_legislatura
  &tabela=projeto_lei
  &opcao={D|T|A|R|J|G|P|I|S|E|V}
  &absolutepage=N
```

### Opções (param `opcao`)
| Code | Significado |
|---|---|
| D | Deliberados |
| T | Todos |
| A | Aprovados |
| R | Retirados |
| J | Prejudicados |
| G | Diligência |
| P | Prazo |
| I | Visto |
| S | Sobrestado |
| E | Veto |
| V | Vetado |

### Lógica
1. Fetch da página (encoding **ISO-8859-1** detectado automaticamente)
2. Regex no `body.text()` para extrair blocos `Nº do Proj.: X/YY  Autor: X  Entrada: DD.MM.YY  Ementa: X`
3. Conversão de data `DD.MM.YY` → `YYYY-MM-DD`

### Campos extraídos
✅ id, sigla=PL, número, ano, ementa, data, autor

### Particularidades
- Paginação por `absolutepage` (não `page`)
- 63 páginas conhecidas na 31ª legislatura (~2.353 PLs)
- `robots.txt`: VAZIO (sem restrição)
- Ementa pode ser MUITO grande (parser usa `(?=N[º°]?\s*do\s*Proj|$)` como look-ahead)

---

## 🟢 al_df — Distrito Federal (CLDF)

**Casa**: Câmara Legislativa do Distrito Federal
**Sistema upstream**: Liferay portal
**Detalhe implementado**: ✅ SIM

### Endpoints upstream
| Operação | URL |
|---|---|
| LIST | `GET https://www.cl.df.gov.br/pt/web/guest/projetos?delta=30&start=N` |
| DETAIL | `GET https://www.cl.df.gov.br/proposicao/-/documentos/{TIPO}_{NUM}_{ANO}` |
| JSON discovery | `GET https://www.cl.df.gov.br/api/jsonws?discover` (838 serviços) |

### Lógica
1. **Listagem**: extrai slugs `TIPO_NUM_ANO` (ex: `PL_1495_2025`, `IND_10447_2026`, `MO_746_2024`) dos `<a href="/proposicao/-/documentos/...">`
2. **Detalhe**: GET na URL canônica; parseia Liferay HTML para ementa via heurística `<p>...ementa...</p>`

### Campos extraídos
✅ id (slug), sigla, número, ano, url; ementa só no detalhe (parser defensivo)

### Particularidades
- Paginação por `start=1, 31, 61, ...` (não `page`)
- ~170 páginas (~5.120 proposições no total)
- Tipos vistos: PL, MO (Moção), IND
- DCL (Diário): `GET /pt/buscar-dcl` (PDF público)

---

## 🟡 al_ma — Maranhão (ALEMA)

**Casa**: Assembleia Legislativa do Estado do Maranhão
**Sistema upstream**: WordPress com REST API nativa
**Detalhe implementado**: ❌ não

### Endpoint
```
GET https://www.al.ma.leg.br/sitealema/wp-json/wp/v2/ordem
  ?after=YYYY-01-01T00:00:00
  &before=YYYY-12-31T23:59:59
  &search=X
```

### Lógica
1. Fetch das **Ordens do Dia** (CPT `/ordem` do WordPress)
2. Para cada ordem, parseia `content.rendered` (HTML embarcado) extraindo blocos:
   - `PROJETO DE LEI ORDINÁRIA Nº 030/2024, DE AUTORIA DO DEPUTADO X QUE Y`

### Campos extraídos
✅ id (`{SIGLA}-{NUM}-{ANO}`), sigla, número, ano, ementa, data, url (link da ordem)

### CPTs descobertos
| CPT | Conteúdo | Volume |
|---|---|---|
| `/wp/v2/ordem` | Ordens do dia | 253 |
| `/wp/v2/diario` | Diários | 572 |
| `/wp/v2/deputado` | Perfis | 134 |
| `/wp/v2/posts` | Notícias (`search` funciona) | — |

### Headers úteis
- `X-WP-Total`: total absoluto
- `X-WP-TotalPages`: total de páginas

### Particularidades
- Autores aparecem no texto mas **não-estruturados** (parser deixa `autores=[]`)
- Encoding UTF-8 padrão WordPress

---

## 🟢 al_mt — Mato Grosso (ALMT)

**Casa**: Assembleia Legislativa do Estado de Mato Grosso
**Sistema upstream**: HermesLegis (Symfony)
**Detalhe implementado**: ✅ SIM (essencial para ALMT)

### Endpoints upstream
| Operação | URL |
|---|---|
| LIST | `GET https://www.al.mt.gov.br/proposicao?ano=YYYY&tipo=N` |
| DETAIL | `GET https://www.al.mt.gov.br/proposicao/cpdoc/{ID}/visualizar` |

### Lógica
1. **Listagem**: só extrai IDs nativos dos hrefs `/proposicao/cpdoc/{ID}/visualizar`
2. **Detalhe**: parseia o `<title>` que tem formato `"Projeto de lei nº 42/2026 Dep. Eduardo Botelho - Projeto em Tramitação"`

### Campos extraídos
- **Listagem**: id, url (apenas)
- **Detalhe**: sigla, número, ano, autor, status

### Particularidades
- Listagem é **leve** (só IDs) — detalhe é **obrigatório** para qualquer dado útil
- Para pré-popular dados na listagem, faria sentido lançar N fetches paralelos de detalhe — atualmente isso não é feito (trade-off de performance)
- 100+ IDs por página

---

## 🟢 al_pa — Pará (ALEPA)

**Casa**: Assembleia Legislativa do Estado do Pará
**Sistema upstream**: ASP.NET WebForms com DevExpress
**Detalhe implementado**: ❌ não (mas listagem é rica)

### Endpoints upstream
| Operação | URL |
|---|---|
| LIST (fast) | `GET https://www.alepa.pa.gov.br/Legislativo/CallbackPanelProposicoes?tipo=N&ano=YYYY` |
| Tipos | `GET https://www.alepa.pa.gov.br/Legislativo/GetTipoProposicoes` |
| Autores | `GET https://www.alepa.pa.gov.br/Legislativo/GetTipoAutores` |
| LIST (full postback) | `POST https://www.alepa.pa.gov.br/Legislativo/CallbackPanelProposicoes` com `__VIEWSTATE`+`__EVENTVALIDATION` |
| DETAIL upstream | `GET https://www.alepa.pa.gov.br/Legislativo/DetalhesProposicao?IdProposicao=N` |

### Lógica
1. GET com `?tipo=N&ano=YYYY` retorna HTML estruturado (~16KB) sem precisar de postback
2. Headers obrigatórios: `Referer: /Legislativo/CardViewProposicoes`
3. Parser de `.card-proposicao` com:
   - `<h3>` = autor
   - `<span>` = tipo+número+data
   - `<p>` = ementa
   - `onclick='onCardClick("...?IdProposicao=N")'` = id

### TIPO_PARA_ID
| Sigla | ID upstream |
|---|---|
| PDL | 1 |
| PEC | 2 |
| PL | 3 |
| PLC | 4 |
| PR | 5 |

### Campos extraídos
✅ id, sigla, número, ano, ementa, data, autor, status (sempre "Em tramitação" no CallbackPanel), url

### Particularidades
- 2.433 itens em 244 páginas no ano 2024
- Paginação real exige postback DevExpress completo (atualmente não implementada — só primeira página)
- Status é fixo (`"Em tramitação"`) porque o CallbackPanel só lista vigentes

---

## 🟢 al_pe — Pernambuco (ALEPE)

**Casa**: Assembleia Legislativa do Estado de Pernambuco
**Sistema upstream**: API XML pública (dados abertos)
**Detalhe implementado**: ❌ não

### Endpoints upstream
| Operação | URL |
|---|---|
| LIST projetos | `GET https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/projetos/?ano=YYYY` |
| LIST indicações | `GET https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/indicacoes/?ano=YYYY` |
| LIST requerimentos | `GET https://dadosabertos.alepe.pe.gov.br/api/v1/proposicoes/requerimentos/?ano=YYYY` |

### Lógica
1. Fetch do XML público
2. Parse via `lxml` — estrutura é **atributos no elemento `<projeto>`**, NÃO tags filhas:

```xml
<projetos>
  <projeto docid="13539" numero="3" ano="2024"
           tipo="PROJETO DE LEI ORDINARIA"
           ementa="Susta o Decreto..."
           dataPublicacao="14/06/2024">
    <autores>
      <autor nome="Coronel Alberto Feitosa" tipo="DEPUTADO"/>
    </autores>
  </projeto>
</projetos>
```

3. Mapeamento `tipo` → sigla: "PROJETO DE LEI ORDINARIA" → `PL`, "PROJETO DE LEI COMPLEMENTAR" → `PLC`, "PROJETO DE DECRETO LEGISLATIVO" → `PDL`, "PROPOSTA DE EMENDA A CONSTITUIÇÃO" → `PEC`, etc.

### TIPO_PARA_ENDPOINT
| Sigla | endpoint |
|---|---|
| PL (default) | `projetos` |
| IND | `indicacoes` |
| REQ | `requerimentos` |

### Campos extraídos
✅ id (docid), sigla, número, ano, ementa, data (convertida pra ISO), autor com tipo

### Particularidades
- 945 PDLs em 2024 (confirmado ao vivo)
- Paginação client-side (XML devolve tudo)
- DNS pode falhar transitoriamente (já visto) → adapter mapeia para `ALIndisponivelError`

---

## 🟡 al_rj — Rio de Janeiro (ALERJ)

**Casa**: Assembleia Legislativa do Estado do Rio de Janeiro
**Sistema upstream**: **IBM Lotus Notes / Domino** (legado dos anos 90)
**Detalhe implementado**: ❌ não
**HTTPS**: ❌ NÃO (HTTP only, documentado)

### Endpoint
```
GET http://alerjln1.alerj.rj.gov.br/{base}.nsf/{view}
  ?ReadViewEntries&Start=N&Count=M
```

### Bases .nsf descobertas
| Base | Conteúdo | Volume |
|---|---|---|
| `scpro2327.nsf` | Legislatura corrente (2023-2027) | — |
| `scpro.nsf` | Histórico | 2.563 leis |
| `contlei.nsf` | Legislação consolidada | — |

### Views
| View | Tipo |
|---|---|
| `vlei` | PL |
| `vleicomp` | PLC |
| `vMensagem` | MSG |
| `vindicacao` | IND |
| `vemenda` | PEC |
| `vdecreto` | PDL |
| `vveto` | VET |
| `vresolucao` | PR |

### Lógica
1. Lotus Notes responde XML com `<viewentries>` e `<viewentry position="N" unid="HEX">`
2. Cada `<viewentry>` tem múltiplos `<entrydata columnnumber="X">` que dependem da view
3. Parser específico em `src/parsers/lotus.py` com `COLUNAS_POR_VIEW` mapeando cada view para os índices de coluna esperados
4. Datetime Lotus tem formato próprio (`20240315T100000,00-03`) — converter para ISO

### Seleção de base por ano
```python
base = "scpro2327" if (filtros.ano or 2024) >= 2023 else "scpro"
```

### URL canônica de cada documento
```
http://alerjln1.alerj.rj.gov.br/{base}.nsf/{UNID}?OpenDocument
```

### Particularidades
- ⚠️ **HTTP NÃO HTTPS** — exceção documentada; ALERJ não tem TLS no Lotus
- 20+ anos sem migração — provavelmente estável por mais 20
- Encoding pode variar — usar `decode_response()` do `parsers/encoding.py`
- Search disponível: `?SearchView&Query=saude&Count=50`
- Pode demorar (legado) — rate limit conservador 0.5 req/s

---

## 🟢 al_sc — Santa Catarina (ALESC)

**Casa**: Assembleia Legislativa do Estado de Santa Catarina
**Sistema upstream**: eLegis (CakePHP + htmx)
**Detalhe implementado**: ✅ SIM

### Endpoints upstream
| Operação | URL |
|---|---|
| LIST | `GET https://portalelegis.alesc.sc.gov.br/proposicoes/processo-legislativo?ano=YYYY&tipoPropositura=N&page=N` |
| DETAIL | `GET https://portalelegis.alesc.sc.gov.br/proposicoes/{HASH}/tramitacoes` |

### Lógica
1. **Listagem**: extrai `<a href="/proposicoes/{HASH}/tramitacoes">PL./0216/2024</a>`
   - HASH é base36 de ~5 chars (ex: `N0MQP`, `5Z1Q7`, `X3KT9`)
   - Texto do link tem formato `PL./{numero}/{ano}` ou `PEC/{numero}/{ano}`
2. **Detalhe**: parseia `<title>` que tem formato `"Tramitações / PL./0216/2024 / Proposições / e-Legis / ALESC"`

### SIGLA_PARA_TIPO (param `tipoPropositura`)
| Sigla | ID upstream |
|---|---|
| PL | 1 |
| PLC | 2 |
| PEC | 3 |
| IND | 4 |
| REQ | 5 |
| MOC | 6 |

### Campos extraídos
- **Listagem**: id (hash), sigla, número, ano, url
- **Detalhe**: + ementa, autor, data (busca defensiva em `<dt>/<th>/<strong>`)

### Particularidades
- 310 páginas × 20 = ~6.200 proposições
- htmx requer Accept específico — adapter envia `Accept: text/html,application/xhtml+xml` para receber HTML completo (não fragmento)
- Listagem **filtra paths reservados** (`processo-legislativo`, `feed`, `buscar`) ao extrair hashes

---

## 🟢 al_sp — São Paulo (ALESP)

**Casa**: Assembleia Legislativa do Estado de São Paulo
**Sistema upstream**: Dumps XML públicos em ZIP
**Detalhe implementado**: ❌ não (default da base)

### Endpoints upstream
```
GET https://www.al.sp.gov.br/repositorioDados/processo_legislativo/proposituras.zip
GET https://www.al.sp.gov.br/repositorioDados/processo_legislativo/tramitacoes.zip
GET https://www.al.sp.gov.br/repositorioDados/processo_legislativo/autores.zip
```

### Lógica
1. **Download** do ZIP (~50MB) com timeout estendido (60s connect)
2. **Streaming-parse** em memória via `lxml.etree.iterparse` (tag `propositura`) — itera elemento-a-elemento limpando memória, **sem nunca carregar o XML completo de 150MB descompactado**
3. **Filtros aplicados durante iteração**: `ano`, `tipo`, `numero`, `keyword` — abortagem cedo após pagar
4. **Paginação client-side** via `inicio:fim`

### Estrutura do XML
```xml
<proposituras>
  <propositura>
    <id>9999</id>
    <siglaTipo>PL</siglaTipo>
    <numero>1</numero>
    <anoLegislativo>2024</anoLegislativo>
    <ementa>...</ementa>
    <dataEntrada>2024-03-15</dataEntrada>
    <nomeAutor>...</nomeAutor>
  </propositura>
</proposituras>
```

### Campos extraídos
✅ id, sigla, número, ano, ementa, data (ISO), autor, url

### Particularidades
- Download de 50MB **por request** é caro — recomenda-se cache HTTP no consumidor (TanStack Query, ServiceWorker, ETag)
- Stateless preservado: **zero disco**, **zero DB** — ZIP fica só em memória durante o request
- Rate limit muito conservador: 0.5 req/s (cuidar dos dumps grandes)
- Ordem nativa do XML é cronológica reversa (mais recente primeiro)

---

## Resumo de capacidade por AL

| Source | id | sigla | num | ano | ementa | data | autor | partido | url | status | tramita | det |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| al_ap | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | det | det | ✅ |
| al_ba | ✅ | ✅ | ✅ | ✅ | det | — | — | — | ✅ | — | — | ✅ |
| al_ce | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | — | — |
| al_df | ✅ | ✅ | ✅ | ✅ | det | — | — | — | ✅ | — | — | ✅ |
| al_ma | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | — | — | — |
| al_mt | ✅ | det | det | det | — | — | det | — | ✅ | det | — | ✅ |
| al_pa | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | — |
| al_pe | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — |
| al_rj | ✅ | △ | △ | △ | △ | △ | △ | — | ✅ | △ | — | — |
| al_sc | ✅ | ✅ | ✅ | ✅ | det | det | det | — | ✅ | — | det | ✅ |
| al_sp | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | — | — |

Legenda:
- ✅ = sempre presente
- △ = depende do que o Lotus retorna para a `view` específica
- det = só disponível via `/fetch-live/{source}/{id}` (endpoint de detalhe)
- — = fonte upstream não expõe esse dado

---

## Roteiro para adicionar uma nova AL

1. Criar `src/adapters/al_xx.py` herdando de `AdapterBase`
   - Definir `UF`, `NOME_CASA`, `SOURCE_ID`, `HOST_PRINCIPAL`
   - Implementar `listar(filtros)` retornando `ResponseEnvelope`
   - (Opcional) implementar `detalhe(id_proposicao)`
2. Registrar em `src/orquestrador/registry.py`:
   ```python
   from src.adapters.al_xx import AdapterXX
   _ADAPTERS["al_xx"] = AdapterXX
   ```
3. Adicionar rate limit em `src/orquestrador/rate_limiter.py`:
   ```python
   _LIMITES_BASE["al_xx"] = 1.5  # req/s
   ```
4. Adicionar entrada no `SourceLiteral` em `src/routes/propositions.py`
5. Adicionar entrada no `CAPACIDADES` em `tests/capacidade_por_al.py`
6. Criar fixture em `tests/fixtures_por_al.py`
7. Adicionar `test_completude_al_xx` em `tests/test_completude_por_al.py`
8. Documentar nesta página
