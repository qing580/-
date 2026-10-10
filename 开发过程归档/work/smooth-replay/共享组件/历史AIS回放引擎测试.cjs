const assert = require('node:assert/strict');
const Replay = require('./历史AIS回放引擎.js');

function point(time, lat, lon, sog = null, cog = null) {
  return { time, lat, lon, sog, cog };
}

function vessel(points) {
  return Replay.prepareVessel({ mmsi: '123456789', points });
}

const tests = [];
function test(name, fn) { tests.push({ name, fn }); }

test('prepare filters invalid rows, sorts and removes exact duplicates', () => {
  const prepared = vessel([
    point('2026-09-15T00:01:00Z', 1.1, 103.8),
    point('bad', 1.2, 103.9),
    point('2026-09-15T00:00:00Z', 1.0, 103.7),
    point('2026-09-15T00:01:00Z', 1.1, 103.8)
  ]);
  assert.equal(prepared.points.length, 2);
  assert.ok(prepared.points[0].timeMs < prepared.points[1].timeMs);
});

test('binary search returns surrounding observations', () => {
  const prepared = vessel([
    point('2026-09-15T00:00:00Z', 1, 103),
    point('2026-09-15T00:01:00Z', 2, 104)
  ]);
  const bracket = Replay.bracketAt(prepared, Date.parse('2026-09-15T00:00:30Z'));
  assert.equal(bracket.previousIndex, 0);
  assert.equal(bracket.nextIndex, 1);
});

test('course projection follows cardinal directions', () => {
  const base = Replay.normalizePoint(point('2026-09-15T00:00:00Z', 0, 0, 10, 0));
  const north = Replay.destination(base, 60000);
  assert.ok(north.lat > 0);
  assert.ok(Math.abs(north.lon) < 1e-6);
  base.cog = 90;
  const east = Replay.destination(base, 60000);
  assert.ok(east.lon > 0);
  assert.ok(Math.abs(east.lat) < 1e-6);
});

test('normal interval lands exactly on the next real observation', () => {
  const prepared = vessel([
    point('2026-09-15T00:00:00Z', 1, 103, 12, 90),
    point('2026-09-15T00:05:00Z', 1.02, 103.05, 12, 90)
  ]);
  const state = Replay.stateAt(prepared, Date.parse('2026-09-15T00:05:00Z'));
  assert.equal(state.displayPosition.lat, 1.02);
  assert.equal(state.displayPosition.lon, 103.05);
  assert.equal(state.estimated, false);
});

test('missing motion fields falls back to linear interpolation', () => {
  const prepared = vessel([
    point('2026-09-15T00:00:00Z', 1, 103),
    point('2026-09-15T00:02:00Z', 1.02, 103.04)
  ]);
  const state = Replay.stateAt(prepared, Date.parse('2026-09-15T00:01:00Z'));
  assert.ok(Math.abs(state.displayPosition.lat - 1.01) < 1e-9);
  assert.ok(Math.abs(state.displayPosition.lon - 103.02) < 1e-9);
});

test('long gap stops extrapolating after sixty seconds and becomes stale', () => {
  const prepared = vessel([
    point('2026-09-15T00:00:00Z', 1, 103, 10, 90),
    point('2026-09-15T00:30:00Z', 1.1, 103.3, 10, 90)
  ]);
  const afterMinute = Replay.stateAt(prepared, Date.parse('2026-09-15T00:01:00Z'));
  const afterTen = Replay.stateAt(prepared, Date.parse('2026-09-15T00:10:00Z'));
  assert.equal(afterMinute.stale, false);
  assert.equal(afterTen.stale, true);
  assert.ok(Math.abs(afterTen.displayPosition.lon - afterMinute.displayPosition.lon) < 1e-12);
});

test('end-of-track uses the same extrapolation cap', () => {
  const prepared = vessel([point('2026-09-15T00:00:00Z', 1, 103, 10, 180)]);
  const state = Replay.stateAt(prepared, Date.parse('2026-09-15T00:10:00Z'));
  assert.equal(state.status, 'stale-end');
  assert.equal(state.stale, true);
});

test('clock supports pause, speed, jump and end stop', () => {
  const clock = Replay.createClock(0, 600000, { baseHistorySecondsPerRealSecond: 60 });
  assert.equal(clock.advance(1000), 0);
  clock.play();
  clock.advance(1000);
  assert.equal(clock.timeMs, 15000); // real delta is capped at 250 ms
  clock.setSpeed(4);
  clock.advance(250);
  assert.equal(clock.timeMs, 75000);
  clock.jump(-30000);
  assert.equal(clock.timeMs, 45000);
  clock.seek(600000);
  clock.advance(16);
  assert.equal(clock.playing, false);
});

let failed = 0;
for (const { name, fn } of tests) {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    failed += 1;
    console.error(`FAIL ${name}`);
    console.error(error.stack || error);
  }
}
console.log(`${tests.length - failed}/${tests.length} tests passed`);
if (failed) process.exit(1);
