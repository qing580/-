'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { createAuditStore, normalizeRecord, parseFilters } = require('../audit_store.cjs');

function fixtureRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'maritime-audit-store-'));
  const records = [
    { auditId: 'AQ-20260921120000000-aaaaaaaa', createdAt: '2026-09-21T12:00:00Z', question: '当前异常是什么？', mode: 'local_evidence', status: 'local_evidence_only', mmsi: '563021070', replayTime: '2026-09-08T08:04:30Z', evidenceIds: ['OBS-1'], sourceIds: ['KB-0001'] },
    { auditId: 'AQ-20260921120100000-bbbbbbbb', createdAt: '2026-09-21T12:01:00Z', question: 'AIS证据可靠吗？', mode: 'deepseek_online', status: 'success', mmsi: '563021070', model: 'deepseek-flash', usage: { prompt_tokens: 10, completion_tokens: 4 }, cost: { currency: 'USD', estimatedCost: 0.00001 }, latencyMs: 120, answer: { conclusion: '需要复核。', currentEvidence: [{ evidenceId: 'OBS-1', statement: '存在AIS观测。' }], applicableBasis: [], limitations: [], suggestedAttention: [], sources: [] } }
  ];
  fs.writeFileSync(path.join(root, '2026-09-21.jsonl'), `${records.map(item => JSON.stringify(item)).join('\n')}\n{bad json}\n`, 'utf8');
  return root;
}

test('list returns newest first, counts states and skips damaged lines', () => {
  const store = createAuditStore(fixtureRoot());
  const result = store.list();
  assert.equal(result.state, 'ready');
  assert.equal(result.records[0].status, 'success');
  assert.equal(result.counts.localEvidence, 1);
  assert.equal(result.skippedInvalidRows, 1);
});

test('filters by status, mode, audit id, question and mmsi', () => {
  const store = createAuditStore(fixtureRoot());
  assert.equal(store.list({ status: 'success' }).records.length, 1);
  assert.equal(store.list({ mode: 'local_evidence' }).records.length, 1);
  assert.equal(store.list({ q: 'bbbbbbbb' }).records.length, 1);
  assert.equal(store.list({ q: '当前异常' }).records.length, 1);
  assert.equal(store.list({ q: '563021070' }).records.length, 2);
});

test('detail returns one record and missing id is 404', () => {
  const store = createAuditStore(fixtureRoot());
  const record = store.detail('AQ-20260921120000000-aaaaaaaa');
  assert.deepEqual(record.evidenceIds, ['OBS-1']);
  assert.throws(() => store.detail('AQ-20260921120000000-cccccccc'), error => error.statusCode === 404);
});

test('empty directory reports not initialized', () => {
  const root = path.join(os.tmpdir(), `missing-audits-${Date.now()}`);
  assert.equal(createAuditStore(root).list().state, 'not_initialized');
});

test('normalizer redacts secrets and absolute paths and ignores unknown fields', () => {
  const record = normalizeRecord({
    auditId: 'AQ-20260921120000000-aaaaaaaa', createdAt: '2026-09-21T12:00:00Z',
    question: '读取 C:\\Users\\person\\secret.txt 和 sk-abcdefghijk', mode: 'local_evidence', status: 'local_evidence_only',
    environment: { DEEPSEEK_API_KEY: 'secret' }, stack: 'C:\\Users\\person\\app.js:1'
  });
  const text = JSON.stringify(record);
  assert.match(text, /已脱敏/);
  assert.doesNotMatch(text, /C:\\\\Users|sk-abcdefghijk|DEEPSEEK_API_KEY|stack/);
});

test('invalid and oversized filters are rejected', () => {
  assert.throws(() => parseFilters({ status: 'not-real' }), /不支持的审计状态/);
  assert.throws(() => parseFilters({ mode: 'not-real' }), /不支持的运行模式/);
  assert.throws(() => parseFilters({ q: 'x'.repeat(101) }), /不能超过100字符/);
});
