# legis-service-estados

Microserviço Python+FastAPI **stateless** que cobre as **11 Assembleias Legislativas estaduais** sem API REST pública. Expõe os dados no contrato unificado `ProposicaoNormalizadaRaw` consumido pelo `legis-service` da LegalBot.

```
┌──────────────────┐    GET /propositions/fetch-live?source=al_xx
│  legis-service   │────────────────────────────────────────────────┐
│    (LegalBot)    │                                                 │
└──────────────────┘                                                 ▼
                                              ┌──────────────────────────────┐
                                              │  legis-service-estados       │
                                              │  Route → RateLimit → Breaker │
                                              │       → Adapter → Filtros    │
                                              └──────────────────────────────┘
                                                            │
                       ┌────────────────────────────────────┼───────────────────┐
                       ▼                                    ▼                   ▼
                ┌──────────────┐                     ┌──────────────┐    ┌──────────────┐
                │ ALAP eLegis  │ ...11 adapters...   │ ALEPE XML    │    │ ALESP dump   │
                │ HTML SSR     │                     │ dadosabertos │    │ ZIP/XML 150M │
                └──────────────┘                     └──────────────┘    └──────────────┘
```

## Documentação completa

| Arquivo | O que tem |
|---|---|
| [docs/api-reference.md](docs/api-reference.md) | Referência de endpoints, query params, schema completo de response, exemplos cURL, códigos de erro |
| [docs/integracao.md](docs/integracao.md) | Como o backend LegalBot integra/proxia para esta API + snippets prontos em Python, Node, Go |
| [docs/adapters-por-estado.md](docs/adapters-por-estado.md) | Estado por estado: URL upstream, padrão técnico, campos extraídos, particularidades, exemplos |
| [docs/levantamento_assembleias.md](../docs/levantamento_assembleias.md) | Levantamento técnico exaustivo das 27 ALs do Brasil (2700+ linhas) |

## Princípios arquiteturais

- **Stateless**: zero DB, zero Redis, zero disco. Cada request bate na fonte ao vivo.
- **Modular**: 1 adapter por AL. Adicionar/remover AL não impacta outros.
- **Contrato unificado**: toda resposta é `ProposicaoNormalizadaRaw` (mesmo do `legis-service`).
- **Resiliente**: rate limiter, circuit breaker e retry por origem.
- **Defensivo**: filtro local de `keyword`/`autor` aplicado pós-fetch para garantir comportamento mesmo quando a fonte não suporta busca nativa.
- **Observável**: logs estruturados, métricas/traces OpenTelemetry opcionais.

## Sources expostos

| Source | Estado / Casa | Padrão técnico upstream |
|---|---|---|
| `al_ap` | Amapá (ALAP) | eLegis Laravel SSR + tooltip de parlamentares |
| `al_ba` | Bahia (ALBA) | HTML semântico + slug canônico `TIPO-NUM-ANO` |
| `al_ce` | Ceará (ALECE) | PHP legado ISO-8859-1, regex no body |
| `al_df` | Distrito Federal (CLDF) | Liferay; slug `TIPO_NUM_ANO` |
| `al_ma` | Maranhão (ALEMA) | WordPress REST + HTML embarcado em Ordens do Dia |
| `al_mt` | Mato Grosso (ALMT) | HermesLegis Symfony; `<title>` parser |
| `al_pa` | Pará (ALEPA) | DevExpress callback `.card-proposicao` |
| `al_pe` | Pernambuco (ALEPE) | XML público com atributos no `<projeto>` |
| `al_rj` | Rio de Janeiro (ALERJ) | IBM Lotus Notes; XML `?ReadViewEntries` |
| `al_sc` | Santa Catarina (ALESC) | eLegis CakePHP + htmx; hash curto base36 |
| `al_sp` | São Paulo (ALESP) | Dumps ZIP/XML públicos (streaming-parse) |
| `al_estados` | **agregado paralelo** | fan-out nas 11 ALs com fault isolation |

> **Não cobertos** (ação institucional pendente): `al_rn` (PDF inviável), `al_mg` (ACL deliberada — `legis-service` principal já trata ALMG por API própria).

## Setup local

```powershell
# 1. Criar venv (requer Python 3.11+)
py -3 -m venv .venv

# 2. Instalar
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 3. (opcional) configurar
copy .env.example .env

# 4. Subir API
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8081
```

URLs disponíveis:
- http://127.0.0.1:8081/docs - **Swagger UI interativo**
- http://127.0.0.1:8081/redoc - ReDoc
- http://127.0.0.1:8081/openapi.json - OpenAPI 3.1 (importar no Postman)
- http://127.0.0.1:8081/health - liveness
- http://127.0.0.1:8081/health/sources - estado dos circuit breakers

## Exemplo rápido

```bash
# Listagem
curl 'http://localhost:8081/propositions/fetch-live?source=al_pe&ano=2024&keyword=petroleo'

# Detalhe (ID nativo da AL) — traz tramitações + autor com partido quando disponível
curl 'http://localhost:8081/propositions/fetch-live/al_ap/108457'

# Agregado de todas as 11 ALs em paralelo
curl 'http://localhost:8081/propositions/fetch-live?source=al_estados&ano=2024&per_page=10'

# Filtro accent-insensitive (Petroleo ≡ Petróleo)
curl 'http://localhost:8081/propositions/fetch-live?source=al_pe&keyword=Petroleo&accent_insensitive=true'

# Diff: detectar mudanças em proposições conhecidas (até 100 por request)
curl -X POST 'http://localhost:8081/webhooks/check' \
  -H 'Content-Type: application/json' \
  -d '{"snapshot":[{"source":"al_pe","id_proposicao_origem":"16370","content_hash":"abc..."}]}'

# Probe ATIVO de saúde das 11 ALs (latência + status em paralelo)
curl 'http://localhost:8081/health/sources/check'

# Métricas Prometheus (com ETag/304 — economiza scrape)
curl -i 'http://localhost:8081/metrics'
```

## Endpoints

| Método | Path | O que faz |
|---|---|---|
| GET | `/propositions/fetch-live` | Listagem com filtros (ano/tipo/keyword/autor/numero) |
| GET | `/propositions/fetch-live/{source}/{id}` | Detalhe enriquecido (tramitações, autor com partido) |
| POST | `/webhooks/check` | Diff snapshot vs estado atual + callback opcional |
| GET | `/health/sources/check` | Probe ATIVO paralelo das 11 ALs |
| GET | `/health/sources/{source}` | Probe ATIVO individual |
| GET | `/metrics` | Prometheus scrape (com ETag) |
| GET | `/docs` | Swagger UI interativo com examples |

Detalhes em [docs/api-reference.md](docs/api-reference.md).

## Rodar testes

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Bateria completa: **61 testes** cobrindo schema, registry, filtros (com regressão do bug "keyword=Petroleo"), contrato, API end-to-end, e **completude por AL** (uma fixture realista por estado).

## Estrutura do projeto

```
legis-service-estados/
├── README.md                    ← este arquivo
├── pyproject.toml               ← deps + ruff + mypy
├── Dockerfile / docker-compose.yml
├── docs/
│   ├── api-reference.md         ← spec dos endpoints
│   ├── integracao.md            ← guia para o dev backend
│   └── adapters-por-estado.md   ← lógica AL por AL
├── src/
│   ├── main.py                  ← FastAPI app + handlers globais
│   ├── config.py                ← Settings via env
│   ├── schemas/                 ← Pydantic v2 (ProposicaoNormalizadaRaw)
│   ├── routes/                  ← /propositions, /health
│   ├── adapters/                ← base + 11 al_xx.py + filtros
│   ├── orquestrador/            ← rate_limiter, circuit_breaker, retry, registry
│   ├── parsers/                 ← html_utils, xml_utils, lotus, encoding
│   ├── errors/                  ← exceptions custom
│   └── observability/           ← logger structlog, OTEL setup
└── tests/                       ← 61 testes (pytest + respx)
```

## Licença

Interno LegalBot.
