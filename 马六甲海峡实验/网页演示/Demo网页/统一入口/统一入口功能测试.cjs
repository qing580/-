const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const logic = require('./统一入口逻辑.js');

let checks = 0;
function test(name, fn) { fn(); checks += 1; console.log(`PASS ${name}`); }

const portalDir = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(portalDir, '海上异常监测智能体.html'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '统一入口.css'), 'utf8');
const script = fs.readFileSync(path.join(__dirname, '统一入口.js'), 'utf8');
const launcher = fs.readFileSync(path.join(portalDir, 'start_navigation_assistant.ps1'), 'utf8');

test('invalid and empty roles default to user', () => {
  assert.equal(logic.normalizeRole(''), 'user');
  assert.equal(logic.normalizeRole('#unknown'), 'user');
});

test('valid role hashes round-trip', () => {
  assert.equal(logic.normalizeRole('#admin'), 'admin');
  assert.equal(logic.hashForRole('admin'), '#admin');
  assert.equal(logic.hashForRole('user'), '#user');
});

test('load summary distinguishes ready, loading and partial states', () => {
  assert.deepEqual(logic.loadSummary({ user: 'ready', admin: 'ready' }), { kind: 'ready', text: '两端已就绪' });
  assert.equal(logic.loadSummary({ user: 'ready', admin: 'loading' }).kind, 'loading');
  assert.equal(logic.loadSummary({ user: 'ready', admin: 'error' }).kind, 'partial');
});

test('portal contains persistent user and admin frames', () => {
  assert.match(html, /id="userFrame"[^>]+用户端航行助手版\/用户端航行助手\.html/);
  assert.match(html, /id="adminFrame"[^>]+管理端海事业务台版\/管理端海事业务台\.html/);
  assert.match(css, /\.portal-pane\s*\{[^}]*visibility:\s*hidden/s);
  assert.match(css, /\.portal-pane\.is-active\s*\{[^}]*visibility:\s*visible/s);
});

test('switching updates hash without navigating or replacing frame sources', () => {
  assert.match(script, /history\.replaceState/);
  assert.match(script, /classList\.toggle\('is-active'/);
  assert.doesNotMatch(script, /frames\[[^\]]+\]\.src\s*=/);
});

test('launcher opens the stable unified entry', () => {
  assert.match(launcher, /海上异常监测智能体\.html/);
  assert.doesNotMatch(launcher, /用户端航行助手版.*用户端航行助手\.html/);
});

console.log(`${checks} unified portal checks passed.`);
