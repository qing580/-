'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadConfig } = require('../config.cjs');
const { createAisTools } = require('../ais_tools.cjs');
const { createRetriever } = require('../retrieval.cjs');
const { createKnowledgeGraph } = require('../knowledge_graph.cjs');
const { createAnswerService } = require('../answer_service.cjs');
const { createAuditLogger } = require('../audit_log.cjs');

function dependencies(config, modelClient) {
  return {
    aisTools: createAisTools(config),
    retriever: createRetriever(config),
    knowledgeGraph: createKnowledgeGraph(config),
    modelClient,
    auditLogger: createAuditLogger(fs.mkdtempSync(path.join(os.tmpdir(), 'maritime-answer-audit-')))
  };
}

const input = { question: '解释当前会遇异常及证据', mmsi: '563021070', time: '2026-09-08T08:04:30Z' };

test('offline mode returns evidence packet without invoking model', async () => {
  const config = loadConfig({ port: 0, env: {} });
  let called = false;
  const service = createAnswerService(config, { ...dependencies(config, { complete: async () => { called = true; } }), env: {} });
  const result = await service.ask(input);
  assert.equal(result.status, 'local_evidence_only');
  assert.equal(called, false);
  assert.ok(result.evidencePacket.graphTrace.paths.length > 0);
});

test('online mode accepts a fully traceable simulated response', async () => {
  const env = { DEEPSEEK_API_KEY: 'test-key', MARITIME_AGENT_ONLINE: '1' };
  const config = loadConfig({ port: 0, env });
  const modelClient = {
    complete: async messages => {
      const packet = JSON.parse(messages[1].content).evidencePacket;
      const evidenceId = packet.graphTrace.evidence[0].id;
      const sourceId = packet.graphTrace.paths[0].claim.source.id;
      return {
        model: 'deepseek-flash', finishReason: 'stop', usage: { prompt_tokens: 10, completion_tokens: 10 }, latencyMs: 5,
        cost: { currency: 'USD', estimatedCost: 0.00001 },
        content: JSON.stringify({
          conclusion: '当前证据支持辅助研判。',
          currentEvidence: [{ evidenceId, statement: '已取得当前真实AIS观测。' }],
          applicableBasis: [{ sourceId, statement: 'AIS只用于辅助研判。' }],
          limitations: ['仍需其他航海信息复核。'],
          suggestedAttention: ['核对雷达、目视与VTS信息。'],
          sources: [{ sourceId, title: '已审核来源' }]
        })
      };
    }
  };
  const service = createAnswerService(config, { ...dependencies(config, modelClient), env });
  const result = await service.ask(input);
  assert.equal(result.status, 'success');
  assert.equal(result.model, 'deepseek-flash');
  assert.match(result.auditId, /^AQ-/);
});

test('guard blocks simulated hallucinated evidence', async () => {
  const env = { DEEPSEEK_API_KEY: 'test-key', MARITIME_AGENT_ONLINE: '1' };
  const config = loadConfig({ port: 0, env });
  const modelClient = {
    complete: async () => ({
      model: 'deepseek-flash', finishReason: 'stop', usage: {}, latencyMs: 1, cost: null,
      content: JSON.stringify({
        conclusion: '错误引用。', currentEvidence: [{ evidenceId: 'OBS-NOT-REAL', statement: '无来源证据。' }],
        applicableBasis: [], limitations: [], suggestedAttention: [], sources: []
      })
    })
  };
  const service = createAnswerService(config, { ...dependencies(config, modelClient), env });
  const result = await service.ask(input);
  assert.equal(result.status, 'blocked_by_guard');
  assert.equal(result.error, 'answer_unknown_evidence');
  assert.equal(result.answer, null);
});
