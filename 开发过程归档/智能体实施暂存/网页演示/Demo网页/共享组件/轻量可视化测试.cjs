const assert = require('node:assert/strict');
const Viz = require('./轻量可视化.js');

const p = (time, lat, lon, sog = null, cog = null) => ({ time, lat, lon, sog, cog });

const points = [
  p('2026-09-17T00:00:00Z', 1, 103, 8, 90),
  p('2026-09-17T00:01:00Z', 1.01, 103.01, 9, 92),
  p('2026-09-17T00:05:00Z', 1.05, 103.05, null, null),
  p('2026-09-17T00:06:00Z', 1.06, 103.06, 7, 88)
];

const segments = Viz.trackSegments(points, { cutoffMs: Date.parse('2026-09-17T00:07:00Z') });
assert.equal(segments.length, 2, 'long AIS gaps must split true tracks');
assert.deepEqual(segments.map(segment => segment.length), [2, 2]);

const track = Viz.trackPlot(points, { cutoffMs: Date.parse('2026-09-17T00:07:00Z'), title: '真实轨迹' });
assert.match(track, /<svg/);
assert.match(track, /真实轨迹/);
assert.doesNotMatch(track, /NaN|Infinity/);

const line = Viz.lineChart([
  { label: 'SOG', color: '#168c91', points: points.map(item => ({ time: item.time, value: item.sog })) }
], { title: '航速趋势', unit: 'kt' });
assert.match(line, /航速趋势/);
assert.doesNotMatch(line, /NaN|Infinity/);
assert.equal((line.match(/class="ais-viz-series"/g) || []).length, 2, 'long AIS gaps must split trend lines');

const emptyLine = Viz.lineChart([{ label: 'COG', points: [{ time: 'bad', value: null }] }], { title: '航向趋势' });
assert.match(emptyLine, /暂无可绘制的真实数据/);

const matrix = Viz.statusMatrix([
  { label: '台风路径', status: '未接入', tone: 'missing', detail: '需要正式数据源' }
]);
assert.match(matrix, /台风路径/);
assert.match(matrix, /未接入/);

const route = Viz.routePlot({
  start: { lat: 1.2, lon: 103.7 },
  end: { lat: 1.3, lon: 104.0 },
  events: [{ label: 'ENC-1', lat: 1.25, lon: 103.85, tone: 'critical' }],
  corridorNm: 3
});
assert.match(route, /筛查走廊/);
assert.doesNotMatch(route, /NaN|Infinity/);

console.log('8/8 lightweight visualization checks passed');
