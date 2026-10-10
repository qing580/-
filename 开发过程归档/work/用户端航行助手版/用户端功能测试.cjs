const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const client = require('./用户端数据逻辑.js');
const management = require('./管理端数据逻辑.js');

let checks = 0;
function test(name, fn) { fn(); checks += 1; console.log(`PASS ${name}`); }
const vessel = mmsi => ({ mmsi, name: `SHIP-${mmsi}` });
const event = (score, ids, lat = 1.2, lon = 103.8) => ({
  id: `E-${score}`, score, level: score >= 75 ? '高风险' : '中高风险', confidence: '中',
  location: { lat, lon }, vessels: ids.map(vessel), cpa: { dcpa: 0.4, tcpa: 6 }, encounterShape: '交叉形态'
});

test('related events only include own ship and keep Top 5', () => {
  const events = [90, 80, 70, 60, 50, 40].map((score, index) => event(score, index === 5 ? ['9', '8'] : ['1', String(index + 2)]));
  const result = client.relatedEvents(events, '1');
  assert.equal(result.length, 5);
  assert.deepEqual(result.map(item => item.score), [90, 80, 70, 60, 50]);
});

test('single-vessel behavior events are excluded from encounter list', () => {
  const behavior = { ...event(70, ['1']), cpa: null };
  assert.equal(client.relatedEvents([behavior], '1').length, 0);
});

test('attention band uses user-facing language', () => {
  assert.equal(client.attentionBand([event(80, ['1', '2'])]).level, '需立即关注');
  assert.equal(client.attentionBand([]).level, '当前未见突出会遇风险');
});

test('point on route corridor has zero distance', () => {
  const distance = client.pointToSegmentNm({ lat: 1, lon: 103.5 }, { lat: 1, lon: 103 }, { lat: 1, lon: 104 });
  assert.ok(distance < 0.001);
});

test('route assessment keeps nearby events', () => {
  const result = client.routeAssessment({ lat: 1, lon: 103 }, { lat: 1, lon: 104 }, [
    event(80, ['1', '2'], 1.01, 103.5), event(70, ['1', '3'], 2, 103.5)
  ], 3);
  assert.equal(result.available, true);
  assert.equal(result.events.length, 1);
  assert.equal(result.highest, 80);
});

test('answer includes required evidence fields', () => {
  const answer = client.answerCard('nearby', { events: [event(80, ['1', '2'])], ownMmsi: '1', time: '2026-09-08T00:00:00Z' });
  for (const field of ['conclusion', 'evidence', 'confidence', 'uncertainty', 'action', 'time']) assert.ok(answer[field]);
});

test('focused trajectory uses only the preceding 30 minutes', () => {
  const cutoff = Date.parse('2026-09-08T06:00:00Z');
  const track = management.recentTrack({ points: [
    { time: '2026-09-08T05:29:59Z', lat: 1, lon: 103 },
    { time: '2026-09-08T05:30:00Z', lat: 1.01, lon: 103.01 },
    { time: '2026-09-08T05:55:00Z', lat: 1.02, lon: 103.02 },
    { time: '2026-09-08T06:01:00Z', lat: 1.03, lon: 103.03 }
  ] }, cutoff, 30);
  assert.equal(track.length, 2);
});

test('client HTML and scripts are wired and parse', () => {
  const html = fs.readFileSync(path.join(__dirname, '用户端航行助手.html'), 'utf8');
  for (const file of ['用户端界面.css', '用户端界面.js', '用户端数据逻辑.js']) assert.match(html, new RegExp(file.replace('.', '\\.')));
  new vm.Script(fs.readFileSync(path.join(__dirname, '用户端数据逻辑.js'), 'utf8'));
  new vm.Script(fs.readFileSync(path.join(__dirname, '用户端界面.js'), 'utf8'));
});

console.log(`${checks} client checks passed.`);
