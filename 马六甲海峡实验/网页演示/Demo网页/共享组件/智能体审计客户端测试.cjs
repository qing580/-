'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { createClient, queryString, statusMeta, modeMeta } = require('./智能体审计客户端.js');

test('audit filters are encoded without empty parameters', () => {
  assert.equal(queryString({ status: 'success', q: 'AQ 1', mode: '' }), '?status=success&q=AQ+1');
});

test('client lists and retrieves audits through read-only endpoints', async () => {
  const calls = [];
  const client = createClient(async url => {
    calls.push(url);
    return new Response(JSON.stringify({ records: [] }), { status: 200 });
  });
  await client.list({ mode: 'local_evidence' });
  await client.detail('AQ-12345678');
  assert.deepEqual(calls, ['/api/audits?mode=local_evidence', '/api/audits/AQ-12345678']);
});

test('export uses the same filters as the list', () => {
  const client = createClient(async () => new Response('{}'));
  assert.equal(client.exportUrl({ status: 'model_error' }), '/api/audits/export?status=model_error');
});

test('status and mode labels distinguish local, online and blocked records', () => {
  assert.equal(statusMeta('local_evidence_only').tone, 'local');
  assert.equal(statusMeta('blocked_by_guard').tone, 'blocked');
  assert.equal(modeMeta('deepseek_online').online, true);
  assert.equal(modeMeta('local_evidence').online, false);
});
