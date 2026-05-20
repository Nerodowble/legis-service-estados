# Guia de Integração — para o backend LegalBot

Este documento mostra como o `legis-service` principal (e qualquer outro consumidor) integra com o `legis-service-estados`.

## Premissa

O contrato é **idêntico** ao que o backend já usa para Câmara/Senado/ALMG. Você não precisa criar tipos novos — `ProposicaoNormalizadaRaw` é o mesmo schema.

Existem **duas estratégias** de integração:

1. **Proxy direto** (recomendado): o `legis-service` recebe `?source=al_xx` e proxia para este microserviço, mantendo o frontend ignorante da divisão.
2. **Cliente paralelo**: frontend chama diretamente os dois serviços via API Gateway.

Recomendamos a **opção 1** porque preserva auth, scoring VIGIL e cache no `legis-service` principal.

---

## Estratégia 1 — Proxy direto no legis-service

### Arquitetura

```
┌─────────┐    /propositions/fetch-live?source=al_pe
│ Frontend │─────────────────────────────────────────┐
└─────────┘                                          ▼
                              ┌──────────────────────────────────┐
                              │  legis-service (LegalBot)        │
                              │   ┌─────────────────────────┐    │
                              │   │ if source.startswith("al_")    │
                              │   │   → proxy estados        │    │
                              │   │ if source in (camara,...)    │
                              │   │   → handler atual        │    │
                              │   └─────────────────────────┘    │
                              └──────────────────────────────────┘
                                            │ proxy
                                            ▼
                          ┌──────────────────────────────────┐
                          │  legis-service-estados (este)    │
                          └──────────────────────────────────┘
```

### Implementação Python (FastAPI no legis-service)

```python
# legis-service/app/routes/propositions.py

from enum import Enum
from typing import Annotated
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.schemas import ResponseEnvelope


class SourceEnum(str, Enum):
    camara = "camara"
    senado = "senado"
    almg = "almg"
    camara_sp = "camara_sp"
    # NOVOS (vão para o microserviço de estados):
    al_ap = "al_ap"
    al_ba = "al_ba"
    al_ce = "al_ce"
    al_df = "al_df"
    al_ma = "al_ma"
    al_mt = "al_mt"
    al_pa = "al_pa"
    al_pe = "al_pe"
    al_rj = "al_rj"
    al_sc = "al_sc"
    al_sp = "al_sp"
    al_estados = "al_estados"  # agregado
    all = "all"


router = APIRouter(prefix="/propositions", tags=["propositions"])


@router.get("/fetch-live", response_model=ResponseEnvelope)
async def fetch_live(
    source: SourceEnum,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ano: int | None = None,
    keyword: str | None = None,
    autor: str | None = None,
    numero: str | None = None,
    tipo: str | None = None,
    tema: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
):
    # Roteamento estadual → microserviço externo
    if source.value.startswith("al_") or source.value == "al_estados":
        return await _proxy_estados(source.value, locals())

    # Roteamento existente (Câmara, Senado, ALMG, etc.)
    if source == SourceEnum.camara:
        return await fetch_camara(...)
    # ... outros handlers já existentes
    ...


async def _proxy_estados(source: str, params: dict) -> ResponseEnvelope:
    """Encaminha para legis-service-estados com timeout e tratamento de erro."""
    upstream_params = {
        k: v for k, v in params.items()
        if v is not None and k != "self"
    }
    upstream_params["source"] = source

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.get(
                f"{settings.LEGIS_ESTADOS_URL}/propositions/fetch-live",
                params=upstream_params,
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Propaga o status code do microserviço (503, 451, etc.)
            raise HTTPException(
                status_code=e.response.status_code,
                detail=e.response.json() if e.response.content else str(e),
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"legis-estados off: {e}")

        return ResponseEnvelope(**r.json())
```

### Detalhe (proxy de path-param)

```python
@router.get("/fetch-live/{source}/{id_proposicao}")
async def fetch_detalhe(source: SourceEnum, id_proposicao: str):
    if source.value.startswith("al_"):
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{settings.LEGIS_ESTADOS_URL}"
                f"/propositions/fetch-live/{source.value}/{id_proposicao}"
            )
            r.raise_for_status()
            return r.json()
    # ... lógica existente para outras sources
```

### Configuração

```env
# .env do legis-service
LEGIS_ESTADOS_URL=http://legis-service-estados:8081
# ou em dev local:
# LEGIS_ESTADOS_URL=http://host.docker.internal:8081
# em prod (k8s):
# LEGIS_ESTADOS_URL=http://legis-service-estados.legalbot.svc.cluster.local:8081
```

### Aplicação de scoring VIGIL após o proxy

O `legis-service-estados` devolve `termometro`, `score_risco`, `indicador_alta_prob` sempre `null` — esses campos são responsabilidade do `legis-service` principal:

```python
async def _proxy_estados(source: str, params: dict) -> ResponseEnvelope:
    envelope = await _fetch_upstream(source, params)

    # Aplicar scoring VIGIL nos items retornados
    for item in envelope.data:
        item.termometro = vigil_scorer.termometro(item)
        item.score_risco = vigil_scorer.risco(item)
        item.indicador_alta_prob = vigil_scorer.alta_prob(item)

    return envelope
```

---

## Estratégia 2 — Cliente direto via API Gateway

Se a LegalBot tem um Gateway (ex: Kong, Traefik, AWS API Gateway), pode-se rotear `?source=al_*` direto para o microserviço de estados:

```yaml
# Exemplo Kong/Traefik
routes:
  - path: /propositions/fetch-live
    when: "query.source matches '^al_'"
    upstream: http://legis-service-estados:8081
  - path: /propositions/fetch-live
    when: default
    upstream: http://legis-service:8000
```

**Desvantagens** dessa abordagem:
- Frontend precisa saber que existem 2 serviços (auth duplicada)
- Scoring VIGIL não é aplicado nas proposições estaduais
- Cache/rate-limit do `legis-service` não cobre os estaduais

---

## Snippets para outros stacks

### Node.js (axios)

```javascript
import axios from 'axios';

const ESTADOS_URL = process.env.LEGIS_ESTADOS_URL || 'http://localhost:8081';

async function fetchEstaduais({ source, ano, keyword, page = 1, per_page = 20 }) {
  const { data } = await axios.get(`${ESTADOS_URL}/propositions/fetch-live`, {
    params: { source, ano, keyword, page, per_page },
    timeout: 30000,
  });
  return data; // ResponseEnvelope
}

// Uso:
const envelope = await fetchEstaduais({
  source: 'al_pe',
  ano: 2024,
  keyword: 'petroleo',
});
console.log(`${envelope.total} proposições encontradas`);
```

### Go (net/http)

```go
package estados

import (
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "net/url"
)

type Envelope struct {
    Data       []Proposicao `json:"data"`
    Total      int          `json:"total"`
    TotalPages int          `json:"total_pages"`
}

func FetchLive(ctx context.Context, source string, params map[string]string) (*Envelope, error) {
    u, _ := url.Parse(fmt.Sprintf("%s/propositions/fetch-live", estadosURL))
    q := u.Query()
    q.Set("source", source)
    for k, v := range params { q.Set(k, v) }
    u.RawQuery = q.Encode()

    req, _ := http.NewRequestWithContext(ctx, "GET", u.String(), nil)
    resp, err := http.DefaultClient.Do(req)
    if err != nil { return nil, err }
    defer resp.Body.Close()

    var env Envelope
    if err := json.NewDecoder(resp.Body).Decode(&env); err != nil {
        return nil, err
    }
    return &env, nil
}
```

### TypeScript (frontend, via legis-service)

```typescript
// Frontend NÃO chama legis-service-estados diretamente.
// Chama o legis-service que faz proxy transparente.

import { httpClient } from '@/lib/api';

interface FetchLiveParams {
  source: string;   // pode ser 'al_pe', 'al_ap', 'al_estados', 'camara', etc.
  page?: number;
  per_page?: number;
  ano?: number;
  keyword?: string;
}

async function fetchProposicoes(params: FetchLiveParams) {
  return httpClient.get<ResponseEnvelope>('/propositions/fetch-live', {
    params,
  });
}

// Frontend não sabe que existem 2 serviços — só envia source
const resp = await fetchProposicoes({ source: 'al_pe', ano: 2024 });
```

---

## Deploy

### Docker Compose (dev)

```yaml
# docker-compose.yml (na raiz do mono-repo LegalBot)
services:
  legis-service:
    build: ./legis-service
    environment:
      LEGIS_ESTADOS_URL: http://legis-service-estados:8081
    depends_on:
      - legis-service-estados
    ports:
      - "8000:8000"

  legis-service-estados:
    build: ./legis-service-estados
    ports:
      - "8081:8081"
    environment:
      APP_ENV: production
      LOG_LEVEL: info
      RATE_LIMIT_FATOR: 1.0
```

### Kubernetes

```yaml
# legis-service-estados.deploy.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legis-service-estados
spec:
  replicas: 2  # stateless → pode escalar horizontalmente
  selector:
    matchLabels:
      app: legis-service-estados
  template:
    metadata:
      labels:
        app: legis-service-estados
    spec:
      containers:
      - name: app
        image: legalbot/legis-service-estados:latest
        ports:
        - containerPort: 8081
        env:
        - name: APP_ENV
          value: production
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: http://otel-collector.observability:4318
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /health
            port: 8081
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8081
          initialDelaySeconds: 5
          periodSeconds: 10

---
apiVersion: v1
kind: Service
metadata:
  name: legis-service-estados
spec:
  selector:
    app: legis-service-estados
  ports:
  - port: 8081
    targetPort: 8081
```

### Escalabilidade

Como é **stateless**, basta aumentar `replicas`. O rate limit e o circuit breaker são **por-pod** — múltiplas instâncias multiplicam efetivamente o teto de req/s no upstream (cuidado: pode estressar a AL alvo se subir 10+ pods).

> Para evitar overload nas ALs, prefira escalar para **2-3 pods** e ajustar `RATE_LIMIT_FATOR` para `0.5` (corta o teto pela metade por pod).

---

## Migração gradual (recomendado)

Se o `legis-service` hoje retorna 404 para `source=al_pe`, faça o roll-out em fases:

### Fase 1 — Sombra (sem expor)
- Deploy do `legis-service-estados` sem rotear nada
- Acessar `/health/sources` para validar
- Testar manualmente via cURL

### Fase 2 — Feature flag
```python
if settings.ENABLE_AL_ESTADOS and source.value.startswith("al_"):
    return await _proxy_estados(source.value, params)
# Sem flag: retorna 501 Not Implemented (comportamento atual)
```

### Fase 3 — Gradual por AL
```python
ALS_HABILITADAS = set(settings.ALS_HABILITADAS.split(","))
# .env: ALS_HABILITADAS=al_pe,al_ap,al_mt

if source.value in ALS_HABILITADAS:
    return await _proxy_estados(source.value, params)
```

### Fase 4 — Full
Remover flag, todos os 11 al_xx + `al_estados` ativos.

---

## Detectando mudanças nas proposições (webhook/diff)

O endpoint `POST /webhooks/check` permite que o `legis-service` principal
detecte quais proposições monitoradas pelos usuários LegalBot **mudaram**
desde a última verificação — sem precisar refazer fetch de todas elas.

### Caso de uso típico

A LegalBot tem N usuários, cada um monitorando M proposições estaduais
(`monitor=true` no contexto deles). Periodicamente (cron de 5min, p.ex.),
o `legis-service` quer saber **quais mudaram**.

Em vez de chamar `/propositions/fetch-live/al_xx/{id}` N×M vezes
(latência alta + estresse no upstream), envia 1 POST com até 100 items:

```python
# legis-service/jobs/detectar_mudancas.py
import asyncio
import hashlib
import json
import httpx
from app.db import session
from app.models import ProposicaoMonitorada

ESTADOS_URL = settings.LEGIS_ESTADOS_URL


def _hash_canonico(proposicao_json: dict) -> str:
    """Mesma fórmula do serviço para garantir compatibilidade."""
    excluir = {"monitor", "termometro", "score_risco", "indicador_alta_prob"}
    payload = {k: v for k, v in proposicao_json.items() if k not in excluir}
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


async def detectar_mudancas_estaduais():
    """Roda a cada 5 minutos."""
    monitoradas = session.query(ProposicaoMonitorada).filter(
        ProposicaoMonitorada.source.startswith("al_")
    ).limit(100).all()

    snapshot = [
        {
            "source": p.source,
            "id_proposicao_origem": p.id_origem,
            "content_hash": p.content_hash,  # gravado na última verificação
        }
        for p in monitoradas
    ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{ESTADOS_URL}/webhooks/check",
            json={
                "snapshot": snapshot,
                # callback opcional — se quiser receber via webhook em vez de
                # processar a resposta síncrona:
                # "callback_url": "https://api.legalbot.com/webhooks/proposicoes-mudaram",
            },
        )
        r.raise_for_status()
        diff = r.json()

    # Processar mudanças
    for change in diff["changes"]:
        if change["status_diff"] == "changed":
            # Atualizar registro local + notificar usuários do monitoramento
            atualizar_proposicao(change["proposicao"])
            notificar_usuarios(change["source"], change["id_proposicao_origem"])
        elif change["status_diff"] == "not_found":
            # Proposição arquivada/removida na fonte
            marcar_como_arquivada(change["source"], change["id_proposicao_origem"])
        # unchanged não vem no response (default)

    return diff["summary"]  # ex: {"new": 0, "changed": 3, "not_found": 1, "unchanged": 96}
```

### Modo callback (assíncrono)

Se preferir receber via webhook (sem aguardar a resposta síncrona — útil
quando o snapshot é grande), forneça `callback_url`:

```python
await client.post(f"{ESTADOS_URL}/webhooks/check", json={
    "snapshot": [...],
    "callback_url": "https://api.legalbot.com/webhooks/proposicoes-mudaram",
})
# Response síncrono volta com callback_scheduled=true; o POST async chega depois
```

No seu webhook receiver:

```python
@router.post("/webhooks/proposicoes-mudaram")
async def receber_diff(payload: DiffResponse):
    for change in payload.changes:
        # mesma lógica de antes
        ...
    return {"ok": True}
```

### Gerando `content_hash` no cliente

Importante: **use a mesma fórmula do serviço** para hashes baterem. Hash
sha256 do JSON canônico (sort_keys=True), excluindo campos voláteis:

```python
EXCLUIR = {"monitor", "termometro", "score_risco", "indicador_alta_prob"}

def hash_proposicao(p: dict) -> str:
    payload = {k: v for k, v in p.items() if k not in EXCLUIR}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
            .encode("utf-8")
    ).hexdigest()
```

### Limites práticos

- **Snapshot máx**: 100 items por request (controle de fan-out)
- **Custo**: 1 fetch upstream por item (rate-limited por origem AL)
- **Tempo**: ~3-5s para 100 items distribuídos em várias ALs (paralelizado)
- **Não persistimos** o snapshot — cliente envia novamente a cada poll

---

## Troubleshooting

| Sintoma | Diagnóstico | Solução |
|---|---|---|
| HTTP 503 ao chamar `?source=al_pe` | Fonte upstream off ou DNS falhou | Conferir `/health/sources` — breaker pode estar `open`; aguardar 60s |
| HTTP 502 (PARSER_FALHOU) | A fonte mudou estrutura HTML/XML | Olhar `docs/adapters-por-estado.md` da AL afetada + ajustar parser |
| `data: []` mesmo sem filtros | Adapter pode ter parser quebrado silenciosamente | Rodar `pytest tests/test_completude_por_al.py::test_completude_al_<uf>` |
| Filtro `keyword` retorna 0 | Não é accent-insensitive — usar termo com acentos | Documentado em `api-reference.md` |
| `al_estados` timeout | Alguma AL está lenta | Tempo total = AL mais lenta; warmup do cache de parlamentares al_ap leva ~1s na 1ª chamada |
| OpenAPI vazio em `/openapi.json` | Pode estar usando version errada do FastAPI | `pip install -U "fastapi>=0.110"` |

---

## Checklist de validação após integração

- [ ] `GET /propositions/fetch-live?source=al_pe&ano=2024` retorna 200 com `data: [...]`
- [ ] `GET /propositions/fetch-live?source=al_estados&per_page=5` retorna 200 e mistura items de várias ALs
- [ ] `GET /propositions/fetch-live?source=al_ap_inexistente` retorna 422 (não 500)
- [ ] `GET /propositions/fetch-live/al_ap/108457` retorna 1 item com `tramitacoes` populadas
- [ ] Frontend recebe `tipoConteudo: "Proposição"` (com acentos)
- [ ] Logs do legis-service NÃO contêm corpos de proposição (apenas metadata)
- [ ] Métricas no Grafana mostram latência por `source`
