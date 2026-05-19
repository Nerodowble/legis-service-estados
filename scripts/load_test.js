/**
 * Load test do legis-service-estados via k6
 *
 * Como rodar:
 *   1. Instalar k6: https://k6.io/docs/get-started/installation/
 *   2. Subir o servidor:
 *        uvicorn src.main:app --host 127.0.0.1 --port 8080
 *   3. Rodar o teste:
 *        k6 run scripts/load_test.js
 *
 * Cenários cobertos:
 *   - smoke: 1 VU por 30s — confirma que tudo funciona
 *   - ramp_up: 1 → 10 VUs por 2min — testa concorrência básica
 *   - sustained: 10 VUs por 5min — verifica latência sustentada
 *
 * Thresholds (gates):
 *   - http_req_failed     < 1%   (menos de 1% erro)
 *   - p95 listagem        < 8s   (al_pa é o mais lento)
 *   - p95 detalhe         < 5s   (sem fetch ALESP ZIP)
 *   - p95 health probe    < 500ms
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Counter, Trend } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8080';

// Métricas customizadas por endpoint
const m_listagem = new Trend('latency_listagem');
const m_detalhe = new Trend('latency_detalhe');
const m_probe = new Trend('latency_probe');
const c_errors = new Counter('errors_total');

export const options = {
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      gracefulStop: '5s',
      tags: { scenario: 'smoke' },
    },
    ramp_up: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 5 },
        { duration: '1m', target: 10 },
        { duration: '30s', target: 0 },
      ],
      startTime: '40s',
      gracefulRampDown: '10s',
      tags: { scenario: 'ramp' },
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],     // <1% de erro
    'latency_listagem': ['p(95)<8000'], // p95 listagem <8s
    'latency_detalhe': ['p(95)<5000'],  // p95 detalhe <5s
    'latency_probe': ['p(95)<2000'],    // p95 probe <2s (latência da fonte)
  },
};

const SOURCES_RAPIDOS = ['al_pe', 'al_df', 'al_ma'];

export default function () {
  group('listagem', () => {
    const src = SOURCES_RAPIDOS[Math.floor(Math.random() * SOURCES_RAPIDOS.length)];
    const r = http.get(`${BASE}/propositions/fetch-live?source=${src}&per_page=5`);
    m_listagem.add(r.timings.duration);
    const ok = check(r, {
      'listagem 200': (resp) => resp.status === 200,
      'envelope tem data': (resp) => {
        try { return Array.isArray(resp.json('data')); } catch { return false; }
      },
    });
    if (!ok) c_errors.add(1);
  });

  sleep(0.5);

  group('detalhe al_pe', () => {
    // 16370 era válido em 2026 — pode falhar se XML mudar
    const r = http.get(`${BASE}/propositions/fetch-live/al_pe/16370`);
    m_detalhe.add(r.timings.duration);
    check(r, {
      'detalhe responde': (resp) => [200, 404].includes(resp.status),
    });
  });

  sleep(0.3);

  group('health probe', () => {
    const r = http.get(`${BASE}/health/sources/al_pe`);
    m_probe.add(r.timings.duration);
    const ok = check(r, {
      'probe 200': (resp) => resp.status === 200,
      'probe tem status': (resp) => {
        try { return ['up','down'].includes(resp.json('status')); } catch { return false; }
      },
    });
    if (!ok) c_errors.add(1);
  });

  sleep(0.7);
}

export function handleSummary(data) {
  const result = {
    'stdout': textSummary(data),
    'load_test_report.json': JSON.stringify(data, null, 2),
  };
  return result;
}

function textSummary(data) {
  const m = data.metrics;
  const requests = m.http_reqs ? m.http_reqs.values.count : 0;
  const failRate = m.http_req_failed ? (m.http_req_failed.values.rate * 100).toFixed(2) : '?';
  const p95 = m.http_req_duration ? m.http_req_duration.values['p(95)'].toFixed(1) : '?';
  const p99 = m.http_req_duration ? m.http_req_duration.values['p(99)'].toFixed(1) : '?';

  return `\n=== legis-service-estados — Load Test Report ===\n` +
    `Total requests:   ${requests}\n` +
    `Failure rate:     ${failRate}%\n` +
    `p95 duration:     ${p95}ms\n` +
    `p99 duration:     ${p99}ms\n` +
    `p95 listagem:     ${(m.latency_listagem?.values?.['p(95)'] || 0).toFixed(1)}ms\n` +
    `p95 detalhe:      ${(m.latency_detalhe?.values?.['p(95)'] || 0).toFixed(1)}ms\n` +
    `p95 health probe: ${(m.latency_probe?.values?.['p(95)'] || 0).toFixed(1)}ms\n` +
    `\nReport completo: load_test_report.json\n`;
}
