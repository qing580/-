'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { createAppServer, safeStaticPath } = require('../server.cjs');

const demoRoot = path.resolve(__dirname, '..', '..', '..', '网页演示', 'Demo网页');

async function withServer(env, callback) {
  const auditRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'maritime-server-audit-'));
  const app = createAppServer({ port: 0, demoRoot, env, auditRoot });
  await new Promise(resolve => app.server.listen(0, '127.0.0.1', resolve));
  try {
    const port = app.server.address().port;
    await callback(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise(resolve => app.server.close(resolve));
  }
}

function rawRequest(port, requestPath) {
  return new Promise((resolve, reject) => {
    const request = http.request({ host: '127.0.0.1', port, path: requestPath }, response => {
      response.resume();
      response.on('end', () => resolve(response));
    });
    request.on('error', reject);
    request.end();
  });
}

test('health reports local evidence mode without exposing secrets', async () => {
  await withServer({}, async baseUrl => {
    const response = await fetch(`${baseUrl}/api/health`);
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.equal(body.status, 'ok');
    assert.equal(body.serviceVersion, '0.3.0');
    assert.equal(body.mode, 'local_evidence');
    assert.equal(body.deepseekConfigured, false);
    assert.equal(body.onlineEnabled, false);
    assert.equal(body.knowledgeGraphState, 'ready');
    assert.doesNotMatch(JSON.stringify(body), /api[_-]?key/i);
  });
});

test('health only reports whether DeepSeek is configured and explicitly enabled', async () => {
  const secret = 'test-secret-must-not-leak';
  await withServer({ DEEPSEEK_API_KEY: secret, MARITIME_AGENT_ONLINE: '1' }, async baseUrl => {
    const body = await (await fetch(`${baseUrl}/api/health`)).json();
    assert.equal(body.mode, 'online_ready');
    assert.equal(body.deepseekConfigured, true);
    assert.equal(body.onlineEnabled, true);
    assert.doesNotMatch(JSON.stringify(body), new RegExp(secret));
  });
});

test('configured key remains locked without explicit online switch', async () => {
  await withServer({ DEEPSEEK_API_KEY: 'locked-secret' }, async baseUrl => {
    const body = await (await fetch(`${baseUrl}/api/health`)).json();
    assert.equal(body.mode, 'online_locked');
    assert.equal(body.onlineEnabled, false);
  });
});

test('root serves the stable unified entry', async () => {
  await withServer({}, async baseUrl => {
    const response = await fetch(`${baseUrl}/`);
    const html = await response.text();
    assert.equal(response.status, 200);
    assert.match(html, /海上异常监测智能体/);
  });
});

test('static path resolution rejects traversal', () => {
  assert.equal(safeStaticPath(demoRoot, '/..%2F..%2Fsecret.txt', 'index.html'), null);
  assert.ok(safeStaticPath(demoRoot, '/统一入口/统一入口.js', 'index.html').startsWith(demoRoot));
});

test('unknown APIs return JSON 404', async () => {
  await withServer({}, async baseUrl => {
    const response = await fetch(`${baseUrl}/api/not-real`);
    assert.equal(response.status, 404);
    assert.deepEqual(await response.json(), { error: 'api_not_found' });
  });
});

test('AIS metadata and context APIs use the formal dataset', async () => {
  await withServer({}, async baseUrl => {
    const metadata = await (await fetch(`${baseUrl}/api/ais/metadata`)).json();
    assert.equal(metadata.vesselCount, 581);
    const response = await fetch(`${baseUrl}/api/ais/context?mmsi=563021070&time=${encodeURIComponent('2026-09-08T08:04:30Z')}`);
    const context = await response.json();
    assert.equal(response.status, 200);
    assert.equal(context.vessel.mmsi, '563021070');
    assert.doesNotMatch(JSON.stringify(context), /"score"|风险值/);
  });
});

test('AIS context API rejects path-like identifiers', async () => {
  await withServer({}, async baseUrl => {
    const response = await fetch(`${baseUrl}/api/ais/context?mmsi=..%2Fsecret&time=${encodeURIComponent('2026-09-08T08:04:30Z')}`);
    assert.equal(response.status, 400);
    assert.equal((await response.json()).error, 'invalid_mmsi');
  });
});

test('knowledge graph traces a replay event to approved sources', async () => {
  await withServer({}, async baseUrl => {
    const params = new URLSearchParams({ mmsi: '563021070', time: '2026-09-08T08:04:30Z' });
    const response = await fetch(`${baseUrl}/api/graph/trace?${params}`);
    const trace = await response.json();
    assert.equal(response.status, 200);
    assert.equal(trace.status, 'ready');
    assert.ok(trace.paths.some(item => item.claim.source.id === 'KB-0001'));
    assert.doesNotMatch(JSON.stringify(trace), /"score"|风险值|已违法/);
  });
});

test('knowledge graph topic endpoint validates topic identifiers', async () => {
  await withServer({}, async baseUrl => {
    const valid = await (await fetch(`${baseUrl}/api/graph/topic?topic=straitrep`)).json();
    assert.ok(valid.claims.some(item => item.id === 'KG-C003'));
    const invalid = await fetch(`${baseUrl}/api/graph/topic?topic=..%2Fsecret`);
    assert.equal(invalid.status, 400);
  });
});

test('ask endpoint defaults to local evidence and never calls a model', async () => {
  await withServer({}, async baseUrl => {
    const response = await fetch(`${baseUrl}/api/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: 'AIS能不能作为唯一避碰依据', mmsi: '563021070', time: '2026-09-08T08:04:30Z' })
    });
    const body = await response.json();
    assert.equal(response.status, 200);
    assert.equal(body.status, 'local_evidence_only');
    assert.equal(body.answer, null);
    assert.equal(body.evidencePacket.retrieval[0].sourceId, 'KB-0001');
  });
});
