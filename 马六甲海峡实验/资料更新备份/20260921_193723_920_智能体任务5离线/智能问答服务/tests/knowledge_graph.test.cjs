'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { createKnowledgeGraph } = require('../knowledge_graph.cjs');
const { loadConfig } = require('../config.cjs');
const { createAisTools } = require('../ais_tools.cjs');

function fixture(sourceStatus = '已审核') {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'maritime-graph-'));
  fs.mkdirSync(path.join(root, '00_资料目录与来源登记'), { recursive: true });
  fs.mkdirSync(path.join(root, '96_图谱审核数据'), { recursive: true });
  fs.writeFileSync(path.join(root, '00_资料目录与来源登记', '资料来源登记.json'), JSON.stringify([
    { id: 'KB-1', title: '来源', institution: '官方', version: '1', sourceUrl: 'https://example.test', reviewStatus: sourceStatus }
  ]), 'utf8');
  fs.writeFileSync(path.join(root, '96_图谱审核数据', 'approved_graph.json'), JSON.stringify({ claims: [
    { id: 'KG-1', title: '已审核声明', statement: '说明', boundary: '边界', appliesToKinds: ['高风险会遇'], topics: ['collision'], sourceId: 'KB-1', locator: '第1节', reviewStatus: '已审核' },
    { id: 'KG-2', title: '候选声明', statement: '不得返回', boundary: '边界', appliesToKinds: ['*'], topics: ['collision'], sourceId: 'KB-1', locator: '未知', reviewStatus: '待审核' }
  ] }), 'utf8');
  return root;
}

function sampleContext() {
  return {
    query: { mmsi: '123456789', replayTime: '2026-09-08T08:00:00.000Z' },
    vessel: { mmsi: '123456789', name: 'TEST' },
    currentObservation: { observedAt: '2026-09-08T07:59:00.000Z', lat: 1.2, lon: 103.8, sogKt: 8, cogDeg: 90, ageMinutes: 1 },
    events: [{ id: 'ENC-1', kind: '高风险会遇', distanceNm: 0.2, cpa: { available: true, dcpaNm: 0.1, tcpaMinutes: 3, relativeSpeedKt: 10, method: 'constant_velocity_linear_extrapolation' } }],
    evidenceGate: { sufficientForCurrentMotion: true, missingReasons: [], boundary: '测试边界' }
  };
}

test('only reviewed claims backed by an approved source are active', () => {
  const graph = createKnowledgeGraph({ knowledgeBaseRoot: fixture() });
  assert.deepEqual(graph.status(), { state: 'ready', registeredClaims: 2, activeClaims: 1, approvedSources: 1 });
  assert.deepEqual(graph.topic('collision').claims.map(item => item.id), ['KG-1']);
});

test('disabling a source invalidates dependent graph paths', () => {
  const graph = createKnowledgeGraph({ knowledgeBaseRoot: fixture('待审核') });
  assert.equal(graph.status().activeClaims, 0);
  assert.equal(graph.trace(sampleContext(), 'ENC-1').status, 'no_approved_path');
});

test('event trace links actual evidence to reviewed claims without violation language', () => {
  const graph = createKnowledgeGraph({ knowledgeBaseRoot: fixture() });
  const trace = graph.trace(sampleContext(), 'ENC-1');
  assert.equal(trace.status, 'ready');
  assert.equal(trace.paths[0].claim.source.id, 'KB-1');
  assert.ok(trace.evidence.some(item => item.type === 'CPA_TCPA_DERIVATION'));
  assert.doesNotMatch(JSON.stringify(trace), /已违法|必须转向/);
});

test('invalid and missing event identifiers are rejected', () => {
  const graph = createKnowledgeGraph({ knowledgeBaseRoot: fixture() });
  assert.throws(() => graph.trace(sampleContext(), '../event'));
  assert.throws(() => graph.trace(sampleContext(), 'ENC-404'));
});

test('formal graph traces a real replay event to IMO evidence boundaries', () => {
  const config = loadConfig({ port: 0 });
  const tools = createAisTools(config);
  const graph = createKnowledgeGraph(config);
  const context = tools.context('563021070', '2026-09-08T08:04:30Z');
  const trace = graph.trace(context, context.events[0].id);
  assert.equal(trace.status, 'ready');
  assert.ok(trace.paths.some(item => item.claim.id === 'KG-C002' && item.claim.source.id === 'KB-0001'));
  assert.doesNotMatch(JSON.stringify(trace), /"score"|风险值/);
});
