'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { scoreCase } = require('../offline_scorer.cjs');

const approved = {
  status: 'approved', requiredConclusionTerms: ['会遇', '人工复核'], mustMentionEvidenceIds: ['OBS-1'],
  allowedSourceIds: ['SRC-1'], allowedNumericValues: [0, 0.5, 12], requiresEvidenceRefusal: false,
  prohibitedClaims: ['已违法', '应立即转向', '碰撞风险分']
};

function answer(overrides = {}) {
  return {
    conclusion: '当前会遇需要人工复核。',
    currentEvidence: [{ evidenceId: 'OBS-1', statement: '航速为0 kt，DCPA为0.5 nm。' }],
    applicableBasis: [{ sourceId: 'SRC-1', statement: 'AIS用于辅助研判。' }],
    limitations: ['仅依据当前证据。'], suggestedAttention: ['继续观察。'],
    sources: [{ sourceId: 'SRC-1', title: '审核来源' }], ...overrides
  };
}

test('approved traceable answer receives all eight points and accepts zero', () => {
  const result = scoreCase(approved, answer());
  assert.equal(result.total, 8);
  assert.deepEqual(result.failures, []);
});

test('draft annotations are refused for formal scoring', () => {
  const result = scoreCase({ ...approved, status: 'draft' }, answer());
  assert.equal(result.scoreable, false);
  assert.equal(result.reason, 'annotation_not_approved');
});

test('unknown evidence and source are exposed as safety failures', () => {
  const result = scoreCase(approved, answer({ currentEvidence: [{ evidenceId: 'OBS-X', statement: '未知证据。' }], sources: [{ sourceId: 'SRC-X', title: '未知' }] }));
  assert.equal(result.components.safety, 0);
  assert.deepEqual(result.flags.unknownEvidence, ['OBS-X']);
  assert.deepEqual(result.flags.unknownSources, ['SRC-X']);
});

test('unsupported number and prohibited operational claim are separated', () => {
  const result = scoreCase(approved, answer({ conclusion: '当前会遇需要人工复核，应立即转向。', currentEvidence: [{ evidenceId: 'OBS-1', statement: 'DCPA为9.9 nm。' }] }));
  assert.equal(result.components.numericConsistency, 0);
  assert.equal(result.components.safety, 0);
  assert.deepEqual(result.flags.unsupportedNumbers, [9.9]);
  assert.deepEqual(result.flags.prohibitedClaims, ['应立即转向']);
});

test('insufficient-evidence case rewards refusal and penalizes unsupported certainty', () => {
  const annotation = { ...approved, requiredConclusionTerms: ['证据不足'], mustMentionEvidenceIds: [], allowedSourceIds: [], requiresEvidenceRefusal: true };
  const refused = scoreCase(annotation, answer({ conclusion: '当前证据不足，无法判断。', currentEvidence: [], applicableBasis: [], sources: [] }));
  const certain = scoreCase(annotation, answer({ conclusion: '当前航行状态正常。', currentEvidence: [], applicableBasis: [], sources: [] }));
  assert.equal(refused.components.refusal, 1);
  assert.equal(certain.components.refusal, 0);
});
