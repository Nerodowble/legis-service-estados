# API Reference — legis-service-estados

Base URL local: `http://127.0.0.1:8081`

## Sumário de endpoints

| Método | Path | Descrição |
|---|---|---|
| GET | `/` | Banner com metadados do serviço |
| GET | `/health` | Liveness (sempre 200 se app responde) |
| GET | `/health/ready` | Readiness |
| GET | `/health/sources` | Estado dos circuit breakers das 11 ALs |
| GET | `/health/sources/check` | **Probe ATIVO** das 11 ALs em paralelo (latência + up/down) |
| GET | `/health/sources/{source}` | Probe ATIVO de uma AL específica |
| GET | `/propositions/fetch-live` | **Listagem** de proposições por AL (ou agregado) |
| GET | `/propositions/fetch-live/{source}/{id_proposicao}` | **Detalhe** de uma proposição específica |
| POST | `/webhooks/check` | **Diff** de um snapshot vs estado atual (+ callback opcional) |
| GET | `/metrics` | Métricas Prometheus (com ETag/304) |
| GET | `/docs` | Swagger UI interativo |
| GET | `/redoc` | ReDoc |
| GET | `/openapi.json` | OpenAPI 3.1 (para importar no Postman/Insomnia) |

---

## 1. `GET /propositions/fetch-live`

Listagem de proposições. **Contrato 100% compatível** com o endpoint análogo do `legis-service` principal.

### Query parameters

| Param | Tipo | Obrigatório | Default | Descrição |
|---|---|---|---|---|
| `source` | enum | **sim** | — | `al_ap`, `al_ba`, `al_ce`, `al_df`, `al_ma`, `al_mt`, `al_pa`, `al_pe`, `al_rj`, `al_sc`, `al_sp`, `al_estados` (agregado) |
| `page` | int ≥ 1 | não | `1` | Página (1-indexed) |
| `per_page` | int 1–100 | não | `20` | Tamanho da página |
| `ano` | int | não | — | Ano da proposição |
| `keyword` | str | não | — | Texto a buscar em ementa/status/autores (case-insensitive) |
| `autor` | str | não | — | Substring do nome do autor (case-insensitive) |
| `numero` | str | não | — | Número exato da proposição |
| `tipo` | str | não | — | Sigla: `PL`, `PEC`, `PDL`, `PLC`, `REQ`, `IND`, `MOC`, `PR`... |
| `tema` | str | não | — | Tema/assunto (algumas ALs suportam) |
| `data_inicio` | str (YYYY-MM-DD) | não | — | Data inicial do filtro temporal |
| `data_fim` | str (YYYY-MM-DD) | não | — | Data final do filtro temporal |

### Códigos de status

| Código | Quando ocorre |
|---|---|
| `200` | Sucesso (mesmo se `data: []`) |
| `404` | `source` inválido ou `id_proposicao` não encontrada |
| `422` | Validação de query (ex: `per_page=999`, `page=0`, `source` fora do enum) |
| `451` | AL bloqueada institucionalmente (ex: ACL restritivo) |
| `502` | Parser falhou (HTML/XML mudou estrutura) |
| `503` | AL upstream indisponível (DNS, timeout, 5xx) |
| `500` | Erro inesperado (vai pro log com traceback) |

### Body de erro

Todos os erros retornam JSON estruturado:

```json
{
  "uf": "PE",
  "status": 503,
  "motivo": "[Errno 11002] getaddrinfo failed",
  "tipo": "AL_INDISPONIVEL"
}
```

Tipos de erro:

| `tipo` | HTTP | Significado |
|---|---|---|
| `AL_INDISPONIVEL` | 503 | Fonte upstream falhou (DNS, timeout, 5xx) |
| `AL_BLOQUEADA` | 451 | AL não pode ser acessada por motivo legal/institucional |
| `PARSER_FALHOU` | 502 | Fetch ok, mas HTML/XML mudou estrutura |
| `PROPOSICAO_NAO_ENCONTRADA` | 404 | Detalhe com ID inexistente |

### Schema de resposta (`ResponseEnvelope`)

```json
{
  "data": [ /* lista de ProposicaoNormalizadaRaw */ ],
  "total": 945,
  "total_pages": 48,
  "totals_by_nivel": {
    "federal": 0,
    "estadual": 945,
    "municipal": 0
  }
}
```

### Schema `ProposicaoNormalizadaRaw`

Compatível campo a campo com o contrato `vigil_payload_fetch_live` da LegalBot.

```json
{
  "id_proposicao_origem": "108457",
  "casa_origem": "Assembleia Legislativa do Estado do Amapá",
  "sigla_tipo": "MOC",
  "numero": "317",
  "ano": 2026,
  "ementa": "Moção de Aplauso aos profissionais listados...",
  "ementa_detalhada": null,
  "data_apresentacao": "2026-05-19",
  "status": "Enviado para Diretoria Legislativa",
  "url_inteiro_teor": "https://elegis.al.ap.leg.br/portal/proposicao/108457",
  "autores": [
    {
      "id_autor_origem": "95",
      "nome": "Deputado Rodolfo Vale",
      "partido": "UNIÃO BRASIL",
      "uf": "AP",
      "tipo": "Deputado"
    }
  ],
  "tramitacoes": [
    {
      "data": "2026-05-19",
      "orgao": "DLE",
      "nome_orgao": "Diretoria Legislativa",
      "descricao": "Enviado para Diretoria Legislativa",
      "despacho": null,
      "tipo_tramitacao": "Enviado",
      "regime": null,
      "apreciacao": null,
      "ambito": null,
      "sequencia": 1,
      "url_documento": null
    }
  ],
  "dados_adicionais": {
    "codigoMateria": "108457",
    "objetivo": "IX Legislatura - 2023 / 2027 - 3ª sessão Legislativa",
    "casaIdentificadora": "ALAP",
    "enteIdentificador": "AP",
    "tipoConteudo": "Proposição",
    "tipoDocumento": "MOC"
  },
  "monitor": false,
  "termometro": null,
  "score_risco": null,
  "nivel_federativo": "estadual",
  "indicador_alta_prob": null
}
```

#### Campos de identificação

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `id_proposicao_origem` | str | sim | ID nativo da AL (numérico, slug ou hash dependendo da fonte) |
| `casa_origem` | str | sim | Nome completo da casa legislativa |
| `sigla_tipo` | str | não* | `PL`, `PEC`, `MOC`, `IND`, `REQ`, `PDL`, `PLC`, `PR` |
| `numero` | str | não* | Número da proposição |
| `ano` | int | não* | Ano da proposição |

*Alguns adapters preenchem só na resposta de detalhe (ex: `al_mt` enriquece pelo `<title>`).

#### Campos de conteúdo

| Campo | Tipo | Descrição |
|---|---|---|
| `ementa` | str | Ementa principal |
| `ementa_detalhada` | str | Observações/justificativa quando disponível |
| `data_apresentacao` | str | `YYYY-MM-DD` (sempre ISO, mesmo se a fonte mandar `DD/MM/YYYY`) |
| `status` | str | Situação atual (texto livre) |
| `url_inteiro_teor` | str | URL canônica ou link para PDF |

#### Autores (array)

| Campo | Tipo | Descrição |
|---|---|---|
| `id_autor_origem` | str | ID nativo do deputado quando o portal expõe |
| `nome` | str | Nome completo (preserva prefixo "Deputado/Deputada") |
| `partido` | str | Sigla do partido (extraída quando disponível) |
| `uf` | str | UF do adapter (2 letras) |
| `tipo` | str | `Deputado`, `Comissao`, `Executivo`, `Popular`, `Outro` |

#### Tramitações (array, mais recente primeiro)

| Campo | Tipo | Descrição |
|---|---|---|
| `data` | str | `YYYY-MM-DD` |
| `orgao` | str | Sigla do órgão (`DLE`, `PLEN`, `CCJ`, ...) |
| `nome_orgao` | str | Nome legível do órgão |
| `descricao` | str | Texto da tramitação |
| `despacho` | str | Despacho associado |
| `tipo_tramitacao` | str | Verbo: `Enviado`, `Incluído`, `Aprovado`, `Arquivado`... |
| `sequencia` | int | Ordem (1 = mais recente) |
| `url_documento` | str | Link para documento da tramitação |

#### Dados adicionais

| Campo | Tipo | Descrição |
|---|---|---|
| `codigoMateria` | str/int | Identificador interno (fallback = `id_proposicao_origem`) |
| `objetivo` | str | Contexto (ex: "IX Legislatura - 2023 / 2027") |
| `casaIdentificadora` | str | Sigla da casa (`ALAP`, `ALEPE`, `CLDF`, ...) |
| `enteIdentificador` | str | UF (2 letras) |
| `tipoConteudo` | str | Sempre `"Proposição"` (com Ç e ã) |
| `tipoDocumento` | str | = `sigla_tipo` |

#### Campos VIGIL (scoring — sempre null aqui)

| Campo | Tipo | Por que vem null |
|---|---|---|
| `termometro` | float (0-100) | Calculado pelo `legis-service` principal (não responsabilidade deste microserviço) |
| `score_risco` | enum | idem |
| `indicador_alta_prob` | bool | idem |
| `nivel_federativo` | enum | **Sempre `"estadual"`** neste serviço |
| `monitor` | bool | **Sempre `false`** (estado por usuário fica no `legis-service`) |

### Exemplos cURL

#### Listagem simples

```bash
curl 'http://localhost:8081/propositions/fetch-live?source=al_pe&ano=2024&per_page=10'
```

#### Com filtros combinados (keyword + autor + tipo)

```bash
curl 'http://localhost:8081/propositions/fetch-live?source=al_ap&ano=2026&tipo=MOC&keyword=Aplauso&per_page=20'
```

#### Agregado em todas as 11 ALs (fan-out paralelo)

```bash
curl 'http://localhost:8081/propositions/fetch-live?source=al_estados&ano=2024&per_page=5'
```

> **Tempo médio**: 5–15s (depende da AL mais lenta). Falhas individuais NÃO derrubam o agregado — fontes off são puladas com warning no log.

#### Paginação

```bash
# Página 1
curl 'http://localhost:8081/propositions/fetch-live?source=al_pe&ano=2024&page=1&per_page=20'

# Página 2
curl 'http://localhost:8081/propositions/fetch-live?source=al_pe&ano=2024&page=2&per_page=20'
```

---

## 2. `GET /propositions/fetch-live/{source}/{id_proposicao}`

Detalhe de uma proposição específica. Use o `id_proposicao_origem` retornado na listagem.

### Path parameters

| Param | Tipo | Descrição |
|---|---|---|
| `source` | enum | Igual ao do endpoint de listagem (exceto `al_estados`) |
| `id_proposicao` | str | ID nativo retornado em `id_proposicao_origem` |

### Comportamento por AL

- **`al_ap`, `al_mt`**: faz GET na URL canônica e parseia HTML enriquecido (tramitações, partido do autor, legislatura)
- **`al_ba`, `al_df`, `al_sc`**: detalhe enriquece sigla/número/ano + ementa
- **Outras**: usa default da `AdapterBase` que filtra a listagem por `numero` (limitado)

### Exemplo

```bash
curl 'http://localhost:8081/propositions/fetch-live/al_ap/108457'
```

Resposta:
```json
{
  "data": [{ /* ProposicaoNormalizadaRaw com 20+ campos preenchidos */ }],
  "total": 1,
  "total_pages": 1,
  "totals_by_nivel": {"federal": 0, "estadual": 1, "municipal": 0}
}
```

---

## 3. `POST /webhooks/check`

Diff de um snapshot do cliente contra o estado atual das fontes. Útil para o
`legis-service` principal detectar mudanças nas proposições que cada usuário
monitora — sem manter polling síncrono.

### Princípio

O microserviço é **stateless**: quem mantém estado é o cliente. O cliente
envia `[{source, id_proposicao_origem, content_hash}]`, e respondemos com
quais mudaram. Opcionalmente disparamos POST async para `callback_url`.

### Request body

```json
{
  "snapshot": [
    {
      "source": "al_pe",
      "id_proposicao_origem": "16370",
      "content_hash": "989a61f9bd6c254c…"
    },
    {
      "source": "al_mt",
      "id_proposicao_origem": "172857",
      "content_hash": null
    }
  ],
  "callback_url": "https://legalbot.com/api/webhooks/proposicoes",
  "incluir_unchanged": false
}
```

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `snapshot` | array | sim | Lista de até 100 items conhecidos pelo cliente |
| `snapshot[].source` | str | sim | `al_ap`, `al_pe`, etc. |
| `snapshot[].id_proposicao_origem` | str | sim | ID nativo retornado pela listagem |
| `snapshot[].content_hash` | str ou null | não | sha256 do JSON canônico anterior. Se null, item é tratado como `new` |
| `callback_url` | URL | não | POST async com o mesmo payload de response (BackgroundTasks) |
| `incluir_unchanged` | bool | não | Default false. Quando true, response também inclui items que não mudaram |

### Como gerar `content_hash` no cliente

Hash sha256 do JSON canônico da proposição, **excluindo** campos voláteis
(`monitor`, `termometro`, `score_risco`, `indicador_alta_prob`).

```python
# Python: replicar o hashing do serviço
import hashlib, json
def hash_proposicao(p: dict) -> str:
    p2 = {k: v for k, v in p.items()
          if k not in {"monitor", "termometro", "score_risco", "indicador_alta_prob"}}
    canonico = json.dumps(p2, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
```

### Response body

```json
{
  "checked": 2,
  "changes": [
    {
      "source": "al_pe",
      "id_proposicao_origem": "16370",
      "status_diff": "changed",
      "content_hash": "989a61f9bd6c254c…",
      "proposicao": { /* ProposicaoNormalizadaRaw completa */ },
      "erro": null
    },
    {
      "source": "al_mt",
      "id_proposicao_origem": "172857",
      "status_diff": "new",
      "content_hash": "a1b2c3d4e5f6…",
      "proposicao": { /* ... */ }
    }
  ],
  "summary": {"new": 1, "changed": 1},
  "callback_scheduled": true
}
```

### Valores de `status_diff`

| Valor | Significado |
|---|---|
| `new` | snapshot tinha `content_hash: null` — item nunca visto |
| `changed` | hash do snapshot ≠ hash atual; campo `proposicao` traz estado novo |
| `unchanged` | hash bate; `proposicao` omitido (só na response se `incluir_unchanged=true`) |
| `not_found` | upstream não acha mais essa proposição (arquivada/removida) |
| `error` | falha técnica; veja campo `erro` |

### Callback assíncrono

Se `callback_url` for fornecida:
1. Response síncrono volta normalmente (com `callback_scheduled: true`)
2. Em background (FastAPI BackgroundTasks), fazemos POST com `Content-Type: application/json` e body idêntico ao response
3. Falhas no callback são apenas logadas — não afetam a chamada original

### Exemplo cURL

```bash
curl -X POST http://localhost:8081/webhooks/check \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot": [
      {"source": "al_pe", "id_proposicao_origem": "16370"}
    ]
  }'
```

### Códigos

| Código | Quando |
|---|---|
| `200` | Diff calculado (mesmo com erros individuais nos items — eles vão no campo `erro` da entrada) |
| `422` | source desconhecido, snapshot > 100 items, ou callback_url inválida |

---

## 4. `GET /health/sources`

Estado dos circuit breakers por AL — útil para monitoramento e debug.

```bash
curl 'http://localhost:8081/health/sources'
```

```json
{
  "sources_disponiveis": ["al_ap", "al_ba", "al_ce", "al_df", "al_ma", "al_mt", "al_pa", "al_pe", "al_rj", "al_sc", "al_sp"],
  "breakers": {
    "al_pe": "closed",
    "al_mt": "closed",
    "al_rj": "open"
  }
}
```

Estados:
- `closed`: normal, requests passam
- `open`: AL falhou 5x seguidas → bloqueado por 60s
- `half-open`: testando se voltou ao ar (1 request de teste)

---

## 4. Rate limits e circuit breaker

### Rate limit por origem

| AL | Limite (req/s) | Razão |
|---|---|---|
| al_ap, al_df, al_ma, al_mt, al_pe | 2.0 | APIs modernas robustas |
| al_ba, al_sc | 1.5 | HTML SSR moderno |
| al_pa | 1.0 | DevExpress ASP.NET (postback caro) |
| al_ce, al_rj | 0.5 | Sistemas legados anos 2000/90 |
| al_sp | 0.5 | Dumps de 150MB |

Ajustável globalmente via `RATE_LIMIT_FATOR` no `.env` (multiplicador).

### Circuit breaker

- **fail_max**: 5 falhas consecutivas
- **reset_timeout**: 60s no estado `open`
- Cada AL tem seu próprio breaker (falha de uma não afeta outra)

### Retry

- 3 tentativas com backoff exponencial (1s, 2s, 4s)
- Aplicado apenas em erros transitórios: `TimeoutException`, `ConnectError`, `RemoteProtocolError`, HTTP `429/500/502/503/504`

---

## 5. `GET /metrics` (Prometheus + ETag)

Endpoint Prometheus em `text/plain` para scraping. Suporta cache HTTP via
ETag/If-None-Match.

### Headers de resposta

| Header | Valor |
|---|---|
| `ETag` | `W/"<sha256 truncado>"` (weak) |
| `Cache-Control` | `max-age=5` |
| `Content-Type` | `text/plain; version=0.0.4; charset=utf-8` |

### Comportamento 304

Cliente Prometheus pode mandar `If-None-Match` no scrape seguinte. Se o
payload **não mudou** desde o último, devolvemos `304 Not Modified` (sem body):

```bash
# Primeira coleta
curl -i http://localhost:8081/metrics
# < ETag: W/"abc123…"

# Coleta seguinte (3s depois)
curl -i http://localhost:8081/metrics -H 'If-None-Match: W/"abc123…"'
# > HTTP/1.1 304 Not Modified
```

### Métricas expostas

```
legis_estados_requests_total{source, operacao, outcome}        Counter
legis_estados_items_returned_total{source, operacao}           Counter
legis_estados_upstream_errors_total{source, tipo}              Counter
legis_estados_upstream_duration_seconds{source, operacao}      Histogram
legis_estados_circuit_breaker_state{source}                    Gauge (0=closed, 1=half, 2=open)
```

Queries Prometheus prontas para Grafana:

```promql
# req/s por source
rate(legis_estados_requests_total[5m])

# p95 de latência upstream por source
histogram_quantile(0.95, sum(rate(legis_estados_upstream_duration_seconds_bucket[5m])) by (source, le))

# alerta quando breaker abrir
legis_estados_circuit_breaker_state > 0
```

---

## 6. Observabilidade

### Logs estruturados (structlog)

Em dev: console colorido. Em prod: JSON.

```json
{
  "event": "al_indisponivel",
  "source": "al_pe",
  "status": null,
  "motivo": "[Errno 11002] getaddrinfo failed",
  "level": "warning",
  "timestamp": "2026-05-19T15:30:00Z"
}
```

> **NUNCA loga corpo de resposta** — só metadados e identificadores.

### Métricas / Traces (OpenTelemetry, opt-in)

Defina `OTEL_EXPORTER_OTLP_ENDPOINT` no `.env`:

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
OTEL_SERVICE_NAME=legis-service-estados
```

Instrumenta automaticamente:
- FastAPI (latência de cada endpoint)
- httpx (chamadas upstream para as ALs)

Sem o env, o setup é **no-op** (zero overhead).

---

## 7. Limitações conhecidas

| Limitação | Justificativa |
|---|---|
| Filtro `keyword` é case-insensitive mas **não** accent-insensitive por default | Use `?accent_insensitive=true` para casar `Petroleo` com `Petróleo` |
| Paginação client-side em ALs sem suporte nativo (al_ap, al_pe, al_ma, etc.) | Fonte upstream devolve página inteira; recortamos local |
| `tramitacoes[*].despacho/regime/apreciacao/ambito` quase sempre null | Portais estaduais raramente expõem esses campos |
| Campos VIGIL (`termometro`, `score_risco`) sempre null | Scoring é responsabilidade do `legis-service` principal |
| `al_rj` HTTP (não HTTPS) | Lotus Notes legado dos anos 90 — exceção documentada |
| `al_sp` baixa dump de ~16MB por request | Trade-off do dump público (HTTP Cache-Control no consumidor ajuda) |
| `al_sp` autores em listagem sempre vazios | `proposituras.xml` não inclui autor (`autores.zip` retorna 404). Detalhe ALESP enriquece via `/propositura/?id=N`. |
| `al_pa` paginação só primeira página | Postback DevExpress completo é instável; primeira página + filtros nativos cobrem 95% dos casos |
