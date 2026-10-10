const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const engine = fs.readFileSync(path.join(__dirname, '历史AIS回放引擎.js'), 'utf8');
assert.match(engine, /maxInterpolationGapMs:\s*2\s*\*\s*60\s*\*\s*1000/, 'engine must cap interpolation at two minutes');
assert.match(engine, /trackWindowMs:\s*10\s*\*\s*60\s*\*\s*1000/, 'engine must keep a ten-minute true trail window');
assert.match(engine, /recentTrackSegments/, 'engine must expose gap-aware true trail segments');
assert.doesNotMatch(engine, /estimated-gap|estimated-end/, 'engine must not extrapolate across gaps or beyond track end');
const pages = [
  ['用户端', path.join(root, '用户端航行助手版', '用户端航行助手.html'), path.join(root, '用户端航行助手版', '用户端界面.js')],
  ['管理端', path.join(root, '管理端海事业务台版', '管理端海事业务台.html'), path.join(root, '管理端海事业务台版', '管理端界面.js')]
];

for (const [name, htmlPath, extensionPath] of pages) {
  const html = fs.readFileSync(htmlPath, 'utf8');
  const extension = fs.readFileSync(extensionPath, 'utf8');
  assert.match(html, /\.\.\/共享组件\/历史AIS回放引擎\.js/, `${name} must load the shared engine`);
  assert.match(html, /\.\.\/共享组件\/轻量可视化\.js/, `${name} must load shared visualization code`);
  assert.match(html, /\.\.\/共享组件\/轻量可视化\.css/, `${name} must load shared visualization styles`);
  assert.match(html, /requestAnimationFrame\(replayLoop\)/, `${name} must use animation frames`);
  assert.doesNotMatch(html, /setInterval\(nextFrame/, `${name} must not use the old jump timer`);
  assert.match(html, /id="speedSelect"/, `${name} must expose speed control`);
  assert.match(html, /markerCache = new Map\(\)/, `${name} must cache markers`);
  assert.match(extension, /replayFrameHooks\.push/, `${name} extension must join the continuous frame loop`);
  assert.match(extension, /HistoricalAisReplay\.stateAt/, `${name} extension must use shared interpolation`);
  assert.match(extension, /HistoricalAisReplay\.recentTrackSegments/, `${name} extension must use shared gap-aware trails`);
  assert.match(extension, /MarkerCache = new Map\(\)/i, `${name} extension must reuse markers`);
  assert.match(extension, /TrailCache = new Map\(\)/i, `${name} extension must reuse trail layers`);
  console.log(`PASS ${name} smooth replay integration`);
}

console.log('2/2 page integrations passed');
