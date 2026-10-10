const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const user = fs.readFileSync(path.join(root, '用户端航行助手版', '用户端界面.js'), 'utf8');
const admin = fs.readFileSync(path.join(root, '管理端海事业务台版', '管理端界面.js'), 'utf8');

for (const id of ['cuEncounterViz', 'cuRouteViz', 'cuEnvironmentViz', 'cuEvidenceViz']) {
  assert.match(user, new RegExp(id), `user page visualization missing: ${id}`);
}
for (const method of ['relativeMotion', 'routePlot', 'statusMatrix', 'evidenceChain']) {
  assert.match(user, new RegExp(`AisVisuals\\.${method}`), `user visualization method missing: ${method}`);
}

for (const id of ['mgEventTimelineViz', 'mgEnvironmentViz']) {
  assert.match(admin, new RegExp(id), `management page visualization missing: ${id}`);
}
for (const method of ['timeline', 'relativeMotion', 'trackPlot', 'lineChart', 'statusMatrix', 'barChart']) {
  assert.match(admin, new RegExp(`AisVisuals\\.${method}`), `management visualization method missing: ${method}`);
}

assert.match(user, /cutoffMs:\s*currentTime\(\)/, 'user tracks must follow replay time');
assert.match(admin, /cutoffMs:\s*currentTime\(\)/, 'management tracks must follow replay time');
assert.match(admin, /准确率展示[\s\S]*暂不展示/, 'model page must not invent accuracy');
assert.match(user, /环境数据未接入不等于环境安全/, 'user environment page must preserve data boundary');

console.log('18/18 dual-portal subpage visualization checks passed');
