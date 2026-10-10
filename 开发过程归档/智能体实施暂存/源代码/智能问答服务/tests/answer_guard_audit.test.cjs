'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { validateAnswer } = require('../answer_guard.cjs');
const { createAuditLogger, safeRecord } = require('../audit_log.cjs');

const packet = {
  graphTrace: {
    evidence: [{ id: 'OBS-1', facts: { sogKt: 8.2 } }],
    paths: [{ claim: { source: { id: 'KB-0001' } } }]
  },
  retrieval: [{ sourceId: 'KB-0001', excerpt: 'AIS不能作为唯一依据。' }]
};

function validAnswer() {
  return {
    conclusion: '当前证据仅支持辅助研判。',
    currentEvidence: [{ evidenceId: 'OBS-1', statement: '存在当前AIS观测。' }],
    applicableBasis: [{ sourceId: 'KB-0001', statement: 'AIS不能作为唯一依据。' }],
    limitations: ['仍需结合雷达和人工瞭望。'],
    suggestedAttention: ['复核其他航海信息。'],
    sources: [{ sourceId: 'KB-0001', title: 'IMO AIS指南' }]
  };
}

test('answer guard accepts traceable structured output', () => {
  assert.equal(validateAnswer(JSON.stringify(validAnswer()), packet).conclusion, '当前证据仅支持辅助研判。');
});

test('answer guard blocks unknown evidence, sources, numbers and forbidden claims', () => {
  const unknownEvidence = validAnswer();
  unknownEvidence.currentEvidence[0].evidenceId = 'OBS-404';
  assert.throws(() => validateAnswer(unknownEvidence, packet), error => error.code === 'answer_unknown_evidence');
  const unsupportedNumber = validAnswer();
  unsupportedNumber.conclusion = '距离为999海里。';
  assert.throws(() => validateAnswer(unsupportedNumber, packet), error => error.code === 'answer_unsupported_number');
  const forbidden = validAnswer();
  forbidden.conclusion = '该船已经违法，风险值88分。';
  assert.throws(() => validateAnswer(forbidden, packet), error => error.code === 'answer_forbidden_claim');
});

test('audit logger writes JSONL and rejects possible secrets', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'maritime-audit-'));
  const logger = createAuditLogger(root);
  const result = logger.write({ status: 'success', sourceIds: ['KB-0001'] });
  assert.ok(fs.existsSync(result.file));
  assert.match(fs.readFileSync(result.file, 'utf8'), /KB-0001/);
  assert.throws(() => safeRecord({ DEEPSEEK_API_KEY: 'secret' }));
  assert.throws(() => safeRecord({ token: 'sk-1234567890abcdef' }));
});
