const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const encounter = require('./船舶邻近计算.js');
const management = require('./管理端数据逻辑.js');

let checks = 0;
function test(name, fn) {
  fn();
  checks += 1;
  console.log(`PASS ${name}`);
}

const time = Date.parse('2026-09-08T06:00:00Z');
const point = (lat, lon, cog, sog, offset = 0) => ({
  lat, lon, cog, sog, heading: cog, time: new Date(time + offset).toISOString()
});
const vessel = (mmsi, name, points, category = '货船') => ({ mmsi, name, points, category });

test('future head-on encounter becomes an event', () => {
  const data = [
    vessel('111111111', 'OWN', [point(0, 0, 90, 10)]),
    vessel('222222222', 'TARGET', [point(0, 0.1, 270, 10)])
  ];
  const result = management.buildEvents(data, time, encounter);
  assert.ok(['高风险会遇', '会遇风险初筛'].includes(result.events[0].kind));
  assert.ok(result.events[0].cpa.tcpa >= 0);
  assert.ok(result.events[0].score >= 35);
});

test('encounter event IDs retain full MMSIs', () => {
  const data = [
    vessel('111116000', 'OWN', [point(0, 0, 90, 10)]),
    vessel('222226000', 'TARGET', [point(0, 0.1, 270, 10)])
  ];
  const event = management.buildEvents(data, time, encounter).events[0];
  assert.match(event.id, /111116000/);
  assert.match(event.id, /222226000/);
});

test('passed encounter is not emitted as future collision risk', () => {
  const data = [
    vessel('111111111', 'OWN', [point(0, 0, 270, 10)]),
    vessel('222222222', 'TARGET', [point(0, 0.1, 90, 10)])
  ];
  assert.equal(management.buildEvents(data, time, encounter).events.length, 0);
});

test('stale positions are excluded from encounter events', () => {
  const old = -6 * 60000;
  const data = [
    vessel('111111111', 'OWN', [point(0, 0, 90, 10, old)]),
    vessel('222222222', 'TARGET', [point(0, 0.1, 270, 10, old)])
  ];
  assert.equal(management.buildEvents(data, time, encounter).events.length, 0);
});

test('large short-term course change creates a review event', () => {
  const data = [vessel('333333333', 'TURNER', [
    point(1, 103, 10, 8, -60000),
    point(1.001, 103.001, 100, 8)
  ])];
  const events = management.buildEvents(data, time, encounter).events;
  assert.ok(events.some(event => event.kind === '异常转向初筛'));
  assert.ok(events.every(event => /初筛|会遇/.test(event.kind)));
});

test('sharp speed drop creates a review event', () => {
  const data = [vessel('444444444', 'SLOWER', [
    point(1, 103, 20, 14, -60000),
    point(1.001, 103.001, 22, 4)
  ])];
  assert.ok(management.buildEvents(data, time, encounter).events.some(event => event.kind === '异常减速初筛'));
});

test('data quality separates position validity and motion coverage', () => {
  const data = [vessel('555555555', 'QUALITY', [
    point(1, 103, 20, 8),
    { lat: 1, lon: 103, time: new Date(time).toISOString(), sog: null, cog: null }
  ], '未知')];
  const quality = management.dataQuality(data);
  assert.equal(quality.positionValidity, 1);
  assert.equal(quality.motionCoverage, 0.5);
  assert.equal(quality.classificationCoverage, 0);
});

test('management HTML and assets are wired', () => {
  const html = fs.readFileSync(path.join(__dirname, '管理端海事业务台.html'), 'utf8');
  for (const name of ['管理端界面.css', '管理端数据逻辑.js', '管理端界面.js']) {
    assert.ok(fs.existsSync(path.join(__dirname, name)));
    assert.match(html, new RegExp(name.replace('.', '\\.')));
  }
  for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
    if (match[1].trim()) new vm.Script(match[1]);
  }
  new vm.Script(fs.readFileSync(path.join(__dirname, '管理端界面.js'), 'utf8'));
});

test('real six-hour dataset produces a valid management snapshot', () => {
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'malacca_enhanced_ais_6h_demo_data.json'), 'utf8'));
  const times = data.vessels.flatMap(item => item.points.map(p => Date.parse(p.time))).filter(Number.isFinite).sort((a, b) => a - b);
  const sampleTime = times[Math.floor(times.length * 0.58)];
  const result = management.buildEvents(data.vessels, sampleTime, encounter);
  assert.ok(result.snapshots.length > 0);
  assert.ok(Array.isArray(result.events));
  assert.ok(result.events.every((event, index, list) => index === 0 || list[index - 1].score >= event.score));
});

console.log(`${checks} management checks passed.`);
