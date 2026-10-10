'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { buildAnswerView, createClient, evidenceItem } = require('./智能体客户端.js');

const packet = {
  aisContext: { evidenceGate: { boundary: '只使用真实AIS观测。', missingReasons: [] } },
  retrieval: [{ sourceId: 'KB-0001', title: 'IMO AIS指南', institution: 'IMO', version: 'A.1106(29)', locator: 'AIS 与避碰决策', sourceUrl: 'https://example.test/imo' }],
  graphTrace: {
    event: { id: 'ENC-1', kind: '高风险会遇' },
    boundary: '不认定违法。',
    evidence: [
      { id: 'OBS-1', type: 'AIS_REAL_OBSERVATION', facts: { sogKt: 8.2, cogDeg: 90, ageMinutes: 1 } },
      { id: 'CPA-1', type: 'CPA_TCPA_DERIVATION', available: true, facts: { dcpaNm: 0.2, tcpaMinutes: 3, relativeSpeedKt: 10 } }
    ],
    paths: [{ claim: { statement: 'AIS不能作为唯一避碰依据。', boundary: '需要其他航海信息。', source: { id: 'KB-0001', title: 'IMO AIS指南', institution: 'IMO', version: 'A.1106(29)', locator: 'AIS 与避碰决策', sourceUrl: 'https://example.test/imo' } } }]
  }
};

test('local evidence response becomes a traceable display model', () => {
  const view = buildAnswerView({ status: 'local_evidence_only', evidencePacket: packet });
  assert.equal(view.mode, 'local_evidence');
  assert.match(view.conclusion, /尚未调用在线大模型/);
  assert.ok(view.currentEvidence.some(item => item.evidenceId === 'CPA-1'));
  assert.equal(view.sources[0].sourceId, 'KB-0001');
  assert.equal(view.sources.length, 1, '同一审核资料只应在来源列表出现一次');
});

test('online response preserves guarded answer sections', () => {
  const answer = {
    conclusion: '辅助研判结论。',
    currentEvidence: [{ evidenceId: 'OBS-1', statement: 'AIS观测存在。' }],
    applicableBasis: [{ sourceId: 'KB-0001', statement: '适用依据。' }],
    limitations: ['仍需复核。'], suggestedAttention: ['保持瞭望。'],
    sources: [{ sourceId: 'KB-0001', title: 'IMO AIS指南' }]
  };
  const view = buildAnswerView({ status: 'success', answer });
  assert.equal(view.mode, 'online');
  assert.equal(view.currentEvidence[0].evidenceId, 'OBS-1');
});

test('blocked model response falls back to local evidence', () => {
  const view = buildAnswerView({ status: 'blocked_by_guard', evidencePacket: packet });
  assert.equal(view.mode, 'blocked');
  assert.match(view.conclusion, /未通过证据校验/);
  assert.equal(view.sources[0].sourceId, 'KB-0001');
});

test('client posts only the supplied context payload', async () => {
  let request;
  const client = createClient(async (url, options) => {
    request = { url, options, body: JSON.parse(options.body) };
    return new Response(JSON.stringify({ status: 'local_evidence_only', evidencePacket: packet }), { status: 200 });
  });
  await client.ask({ question: '当前异常是什么？', mmsi: '563021070', time: '2026-09-08T08:04:30Z' });
  assert.equal(request.url, '/api/ask');
  assert.deepEqual(Object.keys(request.body).sort(), ['mmsi', 'question', 'time']);
});

test('evidence formatter never invents unavailable CPA values', () => {
  const item = evidenceItem({ id: 'CPA-X', type: 'CPA_TCPA_DERIVATION', available: false, facts: {} });
  assert.match(item.statement, /无法形成有效推算/);
  assert.doesNotMatch(item.statement, /0\.00/);
});
