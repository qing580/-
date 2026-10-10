(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.UnifiedPortalLogic = api;
})(typeof self !== 'undefined' ? self : this, function () {
  const ROLES = ['user', 'admin'];

  function normalizeRole(value) {
    const role = String(value || '').replace(/^#/, '').toLowerCase();
    return ROLES.includes(role) ? role : 'user';
  }

  function hashForRole(role) {
    return `#${normalizeRole(role)}`;
  }

  function loadSummary(statuses) {
    const values = ROLES.map(role => statuses[role]);
    if (values.every(value => value === 'ready')) return { kind: 'ready', text: '两端已就绪' };
    if (values.some(value => value === 'error')) return { kind: 'partial', text: '部分视角异常' };
    return { kind: 'loading', text: '正在加载两端' };
  }

  return { ROLES, normalizeRole, hashForRole, loadSummary };
});
