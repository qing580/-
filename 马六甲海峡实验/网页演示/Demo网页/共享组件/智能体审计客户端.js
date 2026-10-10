(function (root) {
  'use strict';

  const STATUS_META = {
    success: { label: '在线回答成功', tone: 'success' },
    local_evidence_only: { label: '本地证据', tone: 'local' },
    blocked_by_guard: { label: '证据守卫拦截', tone: 'blocked' },
    model_error: { label: '在线服务降级', tone: 'error' },
    unknown: { label: '未知状态', tone: 'unknown' }
  };

  const MODE_META = {
    local_evidence: { label: '本地证据模式', online: false },
    deepseek_online: { label: 'DeepSeek在线模式', online: true },
    unknown: { label: '未知模式', online: false }
  };

  function queryString(filters = {}) {
    const params = new URLSearchParams();
    ['status', 'mode', 'q'].forEach(key => {
      const value = String(filters[key] || '').trim();
      if (value) params.set(key, value);
    });
    const text = params.toString();
    return text ? `?${text}` : '';
  }

  function createClient(fetchImpl) {
    const request = fetchImpl || root.fetch.bind(root);
    async function json(url, options = {}) {
      const response = await request(url, { cache: 'no-store', ...options });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw Object.assign(new Error(payload.message || `审计服务请求失败（HTTP ${response.status}）`), { status: response.status, code: payload.error });
      return payload;
    }
    return {
      list(filters, signal) { return json(`/api/audits${queryString(filters)}`, { signal }); },
      detail(auditId, signal) { return json(`/api/audits/${encodeURIComponent(auditId)}`, { signal }); },
      exportUrl(filters) { return `/api/audits/export${queryString(filters)}`; }
    };
  }

  function statusMeta(status) {
    return STATUS_META[status] || STATUS_META.unknown;
  }

  function modeMeta(mode) {
    return MODE_META[mode] || MODE_META.unknown;
  }

  const api = { createClient, queryString, statusMeta, modeMeta };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.MaritimeAuditClient = api;
})(typeof window !== 'undefined' ? window : globalThis);
