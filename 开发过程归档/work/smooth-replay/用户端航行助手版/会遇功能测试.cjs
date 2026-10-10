const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const m = require('./船舶邻近计算.js');
const t = Date.parse('2026-09-05T10:00:00Z');
const p = (lat, lon, extra = {}) => ({ lat, lon, time: new Date(t).toISOString(), sog: 8, cog: 359, ...extra });
let checks = 0;
function test(name, fn) { fn(); checks++; console.log('PASS ' + name); }
test('same-position distance', () => assert.equal(m.distance(p(1,103),p(1,103)),0));
test('one equatorial degree is about 60 nautical miles', () => assert.ok(Math.abs(m.distance(p(0,0),p(0,1))-60.04)<.1));
test('wrap-around COG angle', () => assert.equal(m.course(p(1,103),p(1,103,{cog:1}),t).delta,2));
test('missing COG is not zero degrees', () => assert.equal(m.course(p(1,103),p(1,103,{cog:null}),t).delta,null));
test('low speed guarded', () => assert.equal(m.course(p(1,103),p(1,103,{sog:.2}),t).delta,null));
test('old position guarded', () => assert.equal(m.course(p(1,103),p(1,103),t+301000).delta,null));
test('future records excluded and latest sorted correctly', () => {
  const v={points:[p(1,103),p(4,104,{time:new Date(t+1000).toISOString()}),p(0,102,{time:new Date(t-1000).toISOString()})]};
  assert.equal(m.latest(v,t).lat,1);
});
test('invalid coordinates excluded', () => assert.equal(m.latest({points:[p(null,103),p(91,103)]},t),null));
test('own ship excluded and neighbors sorted', () => {
  const rows=m.neighbors([{mmsi:1,points:[p(1,103)]},{mmsi:2,points:[p(1,104)]},{mmsi:3,points:[p(1,103.1)]}], '1', t).rows;
  assert.deepEqual(rows.map(r=>r.vessel.mmsi),[3,2]);
});
test('risk ranking prefers closer crossing target', () => {
  const own={mmsi:1,points:[p(1,103,{cog:0,sog:12})]};
  const nearCross={mmsi:2,points:[p(1.01,103,{cog:90,sog:12})]};
  const farParallel={mmsi:3,points:[p(1,103.8,{cog:2,sog:12})]};
  const rows=m.neighbors([own, farParallel, nearCross], '1', t).rows;
  const ranked=m.rank(rows, 2);
  assert.equal(ranked[0].vessel.mmsi,2);
  assert.ok(ranked[0].risk.score > ranked[1].risk.score);
});
test('CPA/TCPA computes future head-on encounter', () => {
  const own=p(0,0,{cog:90,sog:10});
  const target=p(0,1,{cog:270,sog:10});
  const cpa=m.cpa(own,target,t);
  assert.equal(cpa.available,true);
  assert.ok(Math.abs(cpa.tcpa-180.1)<1);
  assert.ok(cpa.dcpa<0.01);
});
test('CPA/TCPA marks passed encounter', () => {
  const own=p(0,0,{cog:270,sog:10});
  const target=p(0,1,{cog:90,sog:10});
  const cpa=m.cpa(own,target,t);
  assert.equal(cpa.available,true);
  assert.ok(cpa.tcpa<0);
  assert.match(cpa.label,/过去/);
});
test('empty own position handled', () => assert.deepEqual(m.neighbors([], '1',t),{point:null,rows:[]}));
const htmlEntry = fs.existsSync(path.join(__dirname, '用户端航行助手.html'))
  ? '用户端航行助手.html'
  : fs.existsSync(path.join(__dirname, '管理端海事业务台.html'))
    ? '管理端海事业务台.html'
    : '会遇情景演示版.html';
const html = fs.readFileSync(path.join(__dirname, htmlEntry), 'utf8');
test('inline JavaScript parses', () => {
  for (const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) if (match[1].trim()) new vm.Script(match[1]);
});
test('external assets and extension syntax', () => {
  for (const name of ['会遇情景.css','船舶邻近计算.js','会遇情景.js']) assert.ok(fs.existsSync(path.join(__dirname,name)));
  new vm.Script(fs.readFileSync(path.join(__dirname,'会遇情景.js'),'utf8'));
});
console.log(`${checks} checks passed. Browser visual tests are separate.`);
