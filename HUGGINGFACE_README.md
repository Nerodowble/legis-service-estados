---
title: legis-service-estados
emoji: 🏛️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: API stateless para 11 Assembleias Legislativas brasileiras
---

# legis-service-estados — deploy Hugging Face Spaces

API FastAPI stateless que cobre 11 Assembleias Legislativas estaduais
brasileiras (AP, BA, CE, DF, MA, MT, PA, PE, RJ, SC, SP) e expõe os dados
no contrato `ProposicaoNormalizadaRaw`.

## Como usar este Space

Após o build (5-10 minutos na primeira vez), os endpoints ficam em:

- `https://NOME-DO-SEU-SPACE.hf.space/docs` — Swagger UI interativo
- `https://NOME-DO-SEU-SPACE.hf.space/health` — Liveness check
- `https://NOME-DO-SEU-SPACE.hf.space/propositions/fetch-live?source=al_pe&ano=2024` — listagem
- `https://NOME-DO-SEU-SPACE.hf.space/health/sources/check` — probe das 11 ALs

## Repositório original

https://github.com/Nerodowble/legis-service-estados

## Aviso

O Space dorme após 48h sem acesso. Primeiro request após o sono leva
~10-15s para acordar. Acessos subsequentes respondem em <500ms (latência
herdada da AL upstream).
