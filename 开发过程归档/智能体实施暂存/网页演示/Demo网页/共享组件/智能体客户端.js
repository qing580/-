(function (root) {
  'use strict';

  function unique(items, key) {
    const seen = new Set();
    return items.filter(item => {
      const value = key(item);
      if (!value || seen.has(value)) return false;
      seen.add(value);
      return true;
    });
  }

  function finite(value, digits, suffix) {
    const number = Number(value);
    return Number.isFinite(number) ? `${number.toFixed(digits)}${suffix}` : '不可用';
  }

  function evidenceItem(item) {
    if (item.type === 'AIS_REAL_OBSERVATION') {
      return {
        evidenceId: item.id,
        label: 'AIS真实观测',
        statement: `航速 ${finite(item.facts?.sogKt, 1, ' kt')}，航向 ${finite(item.facts?.cogDeg, 1, '°')}，数据年龄 ${finite(item.facts?.ageMinutes, 1, ' min')}`
      };
    }
    if (item.type === 'RELATIVE_DISTANCE') return { evidenceId: item.id, label: '当前距离', statement: finite(item.value, 2, ' nm') };
    if (item.type === 'CPA_TCPA_DERIVATION') {
      return {
        evidenceId: item.id,
        label: 'CPA/TCPA推算',
        statement: item.available
          ? `DCPA ${finite(item.facts?.dcpaNm, 2, ' nm')}，TCPA ${finite(item.facts?.tcpaMinutes, 1, ' min')}，相对速度 ${finite(item.facts?.relativeSpeedKt, 1, ' kt')}`
          : '当前运动字段不足，无法形成有效推算'
      };
    }
    if (item.type === 'BEHAVIOR_SCREENING_METRIC') return { evidenceId: item.id, label: '行为筛查指标', statement: String(item.value || '不可用') };
    if (item.type === 'DATA_QUALITY_GATE') {
      return {
        evidenceId: item.id,
        label: '数据质量门槛',
        statement: item.sufficientForCurrentMotion ? '当前运动证据满足初步分析条件' : `证据不足：${(item.missingReasons || []).join('；') || '运动字段不完整'}`
      };
    }
    return { evidenceId: item.id, label: '证据', statement: '已记录可追溯证据' };
  }

  function localEvidenceView(response) {
    const packet = response.evidencePacket || {};
    const trace = packet.graphTrace || {};
    const event = trace.event;
    const paths = trace.paths || [];
    const retrieval = packet.retrieval || [];
    const sources = unique([
      ...paths.map(path => path.claim?.source).filter(Boolean).map(source => ({
        sourceId: source.id, title: source.title, institution: source.institution,
        version: source.version, locator: source.locator, sourceUrl: source.sourceUrl
      })),
      ...retrieval.map(result => ({
        sourceId: result.sourceId, title: result.title, institution: result.institution,
        version: result.version, locator: result.locator, sourceUrl: result.sourceUrl
      }))
    ], source => source.sourceId || source.title);
    const limitations = unique([
      trace.boundary,
      packet.aisContext?.evidenceGate?.boundary,
      ...(packet.aisContext?.evidenceGate?.missingReasons || []),
      ...paths.map(path => path.claim?.boundary)
    ].filter(Boolean).map(text => ({ text })), item => item.text).map(item => item.text);
    return {
      mode: 'local_evidence',
      statusLabel: '本地证据模式',
      conclusion: event
        ? `当前回放证据链包含“${event.kind}”。系统已整理观测、推算与审核依据，但尚未调用在线大模型。`
        : '当前回放时刻未形成可追溯异常事件，已返回现有数据质量与审核资料。',
      currentEvidence: (trace.evidence || []).map(evidenceItem),
      applicableBasis: paths.map(path => ({
        sourceId: path.claim.source.id,
        locator: path.claim.source.locator,
        statement: path.claim.statement
      })),
      limitations,
      suggestedAttention: ['结合雷达、人工瞭望、VTS与最新航海资料复核。', '回放时间或关注船变化后重新生成证据。'],
      sources,
      packet
    };
  }

  function onlineView(response) {
    const answer = response.answer;
    return {
      mode: 'online',
      statusLabel: 'DeepSeek + 本地证据',
      conclusion: answer.conclusion,
      currentEvidence: answer.currentEvidence.map(item => ({ ...item, label: '当前证据' })),
      applicableBasis: answer.applicableBasis,
      limitations: answer.limitations,
      suggestedAttention: answer.suggestedAttention,
      sources: answer.sources,
      packet: null
    };
  }

  function buildAnswerView(response) {
    if (response?.status === 'success' && response.answer) return onlineView(response);
    const local = localEvidenceView(response || {});
    if (response?.status === 'blocked_by_guard') {
      local.mode = 'blocked';
      local.statusLabel = '回答已被证据守卫拦截';
      local.conclusion = '在线回答未通过证据校验，以下仅保留本地可追溯证据。';
    }
    if (response?.status === 'model_error') {
      local.mode = 'degraded';
      local.statusLabel = '在线服务已降级';
      local.conclusion = '在线模型暂不可用，以下仅保留本地可追溯证据。';
    }
    return local;
  }

  function createClient(fetchImpl) {
    const request = fetchImpl || root.fetch.bind(root);
    async function health(signal) {
      const response = await request('/api/health', { signal, cache: 'no-store' });
      if (!response.ok) throw new Error(`健康检查失败（HTTP ${response.status}）`);
      return response.json();
    }
    async function ask(payload, signal) {
      const response = await request('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.message || `问答请求失败（HTTP ${response.status}）`);
      return body;
    }
    return { ask, health };
  }

  const api = { buildAnswerView, createClient, evidenceItem, localEvidenceView };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.MaritimeAgentClient = api;
})(typeof window !== 'undefined' ? window : globalThis);
