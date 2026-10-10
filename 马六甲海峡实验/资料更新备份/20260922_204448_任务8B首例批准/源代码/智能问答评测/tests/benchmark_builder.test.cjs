'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { buildBenchmark } = require('../benchmark_builder.cjs');

const projectRoot = path.resolve(__dirname, '..', '..', '..');
const generatedAt = '2026-09-22T00:00:00.000Z';

function build() {
  const outputRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'malacca-benchmark-'));
  return buildBenchmark({ projectRoot, outputRoot, generatedAt });
}

function read(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }

test('builder creates the fixed twelve-case quota as drafts outside the knowledge base', () => {
  const result = build();
  assert.equal(result.manifest.cases.length, 12);
  const counts = result.manifest.cases.reduce((map, item) => map.set(item.family, (map.get(item.family) || 0) + 1), new Map());
  assert.deepEqual(Object.fromEntries(counts), { normal: 2, encounter: 4, behavior: 2, insufficient: 3, knowledge: 1 });
  assert.ok(result.manifest.cases.every(item => item.annotationStatus === 'draft'));
  assert.doesNotMatch(result.outputRoot, /知识库资料/);
  const summary = fs.readFileSync(path.join(result.outputRoot, 'candidate_review_summary.md'), 'utf8');
  assert.match(summary, /CASE-ENCOUNTER-001/);
  assert.match(summary, /DCPA/);
  assert.match(summary, /不是人工金标准/);
  const mmsiCounts = result.manifest.cases.flatMap(item => item.involvedMmsis).reduce((map, mmsi) => map.set(mmsi, (map.get(mmsi) || 0) + 1), new Map());
  assert.ok([...mmsiCounts.values()].every(count => count <= 2));
  for (const item of result.manifest.cases) {
    const annotation = read(path.join(result.outputRoot, 'cases', item.caseId, 'annotation.json'));
    assert.equal(annotation.status, 'draft');
  }
});

test('same input produces stable case identity, replay time, evidence and zero-valued whitelist', () => {
  const first = build();
  const second = build();
  const identity = result => result.manifest.cases.map(item => ({ caseId: item.caseId, mmsi: item.mmsi, replayTime: item.replayTime, eventId: item.eventId }));
  assert.deepEqual(identity(first), identity(second));
  for (const item of first.manifest.cases) {
    const firstPacket = read(path.join(first.outputRoot, 'cases', item.caseId, 'evidence_packet.json'));
    const secondPacket = read(path.join(second.outputRoot, 'cases', item.caseId, 'evidence_packet.json'));
    assert.deepEqual(firstPacket, secondPacket);
  }
  const annotations = first.manifest.cases.map(item => read(path.join(first.outputRoot, 'cases', item.caseId, 'annotation.json')));
  assert.ok(annotations.some(item => item.allowedNumericValues.includes(0)));
  const turn = read(path.join(first.outputRoot, 'cases', 'CASE-BEHAVIOR-001', 'annotation.json'));
  const slowdown = read(path.join(first.outputRoot, 'cases', 'CASE-BEHAVIOR-002', 'annotation.json'));
  assert.ok(turn.allowedNumericValues.includes(108) && turn.allowedNumericValues.includes(4.7));
  assert.ok(slowdown.allowedNumericValues.includes(22.7) && slowdown.allowedNumericValues.includes(0.4));
});

test('AIS packets never contain observations or event times after replay time', () => {
  const result = build();
  for (const item of result.manifest.cases.filter(item => item.replayTime)) {
    const replay = Date.parse(item.replayTime);
    const packet = read(path.join(result.outputRoot, 'cases', item.caseId, 'evidence_packet.json'));
    for (const point of packet.aisContext?.trajectory || []) assert.ok(Date.parse(point.observedAt) <= replay, `${item.caseId} has future trajectory`);
    const current = packet.aisContext?.currentObservation;
    if (current) assert.ok(Date.parse(current.observedAt) <= replay, `${item.caseId} has future current observation`);
    for (const observation of packet.caseEvidence?.involvedObservations || []) {
      assert.ok(Date.parse(observation.observedAt) <= replay, `${item.caseId} has future involved observation`);
    }
    for (const event of packet.aisContext?.events || []) {
      const time = Date.parse(event.time || event.observedAt || item.replayTime);
      if (Number.isFinite(time)) assert.ok(time <= replay, `${item.caseId} has future event`);
    }
  }
});

test('encounter cases freeze both vessel states and only whitelist selected-event numbers', () => {
  const result = build();
  for (const item of result.manifest.cases.filter(row => row.family === 'encounter')) {
    const packet = read(path.join(result.outputRoot, 'cases', item.caseId, 'evidence_packet.json'));
    const annotation = read(path.join(result.outputRoot, 'cases', item.caseId, 'annotation.json'));
    assert.equal(packet.caseEvidence.selectedEventId, item.eventId);
    assert.equal(packet.caseEvidence.involvedObservations.length, 2);
    assert.deepEqual(packet.caseEvidence.involvedObservations.map(row => row.mmsi).sort(), item.involvedMmsis.slice().sort());
    assert.ok(packet.caseEvidence.involvedObservations.every(row => annotation.mustMentionEvidenceIds.includes(row.id)));
    assert.equal(annotation.mustMentionEvidenceIds.length, 5);
    assert.ok(!annotation.mustMentionEvidenceIds.some(id => id.startsWith('OBS-')));
    assert.equal(annotation.expectedEvidenceSummary.method, 'constant_velocity_linear_extrapolation');
  }
  const first = read(path.join(result.outputRoot, 'cases', 'CASE-ENCOUNTER-001', 'annotation.json'));
  assert.ok(first.allowedNumericValues.includes(0.524842));
  assert.ok(first.allowedNumericValues.includes(7.1));
  assert.ok(!first.allowedNumericValues.includes(13.161814));
  assert.ok(!first.allowedNumericValues.includes(2026));
  assert.ok(!first.allowedNumericValues.includes(-352003176));
  assert.ok(first.requiredLimitations.some(item => item.includes('SOG低于1节')));
  assert.ok(first.requiredLimitations.some(item => item.includes('少于2个观测点')));
});

test('insufficient evidence cases cover all three planned failure modes', () => {
  const result = build();
  const subtypes = result.manifest.cases.filter(item => item.family === 'insufficient').map(item => item.subtype).sort();
  assert.deepEqual(subtypes, ['回放时刻前无有效观测', '观测超过5分钟', '运动字段缺失'].sort());
});
