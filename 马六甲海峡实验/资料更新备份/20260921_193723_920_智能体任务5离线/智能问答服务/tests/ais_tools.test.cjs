'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const { loadConfig } = require('../config.cjs');
const { AisToolError, createAisTools } = require('../ais_tools.cjs');

const projectRoot = path.resolve(__dirname, '..', '..', '..');
const config = loadConfig({ projectRoot, port: 0, env: {} });
const tools = createAisTools(config);

test('metadata describes the formal historical dataset without local source paths', () => {
  const metadata = tools.metadata();
  assert.equal(metadata.vesselCount, 581);
  assert.equal(metadata.pointCount, 15414);
  assert.match(metadata.dataset, /malacca_enhanced_ais_6h_demo_data\.json$/);
  assert.doesNotMatch(JSON.stringify(metadata), /C:\\/);
});

test('context uses only observations at or before replay time and exposes no risk score', () => {
  const replayTime = '2026-09-08T08:04:30.000Z';
  const result = tools.context('563021070', replayTime);
  assert.equal(result.vessel.mmsi, '563021070');
  assert.ok(result.currentObservation);
  assert.ok(result.trajectory.length > 0);
  assert.ok(result.trajectory.every(point => Date.parse(point.observedAt) <= Date.parse(replayTime)));
  assert.doesNotMatch(JSON.stringify(result), /"score"|riskScore|风险值/);
  assert.match(result.evidenceGate.boundary, /真实AIS观测/);
});

test('context rejects path-like MMSI and out-of-range time', () => {
  assert.throws(() => tools.context('../secret', '2026-09-08T08:04:30Z'), error => error instanceof AisToolError && error.code === 'invalid_mmsi');
  assert.throws(() => tools.context('563021070', '2030-01-01T00:00:00Z'), error => error instanceof AisToolError && error.code === 'time_out_of_range');
});

test('trajectory window is capped at sixty minutes', () => {
  const result = tools.context('563021070', '2026-09-08T08:04:30Z', { windowMinutes: 999 });
  assert.equal(result.query.trajectoryWindowMinutes, 60);
  const start = Date.parse(result.query.replayTime) - 60 * 60000;
  assert.ok(result.trajectory.every(point => Date.parse(point.observedAt) >= start));
});
