'use strict';

const fs = require('node:fs');
const path = require('node:path');

const VALID_STATUSES = new Set(['local_evidence_only', 'success', 'blocked_by_guard', 'model_error']);
const VALID_MODES = new Set(['local_evidence', 'deepseek_online']);
const MAX_RESULTS = 200;

class AuditQueryError extends Error {
  constructor(code, message, statusCode = 400) {
    super(message);
    this.name = 'AuditQueryError';
    this.code = code;
    this.statusCode = statusCode;
  }
}

function cleanText(value, maximum = 1000) {
  if (value === null || value === undefined) return null;
  return String(value)
    .replace(/\b(?:sk-[a-z0-9_-]{8,}|bearer\s+[a-z0-9._-]{8,})\b/gi, '[已脱敏密钥]')
    .replace(/\b[A-Za-z]:\\[^\s"']+/g, '[已脱敏路径]')
    .replace(/\/(?:Users|home|tmp|var)\/[^\s"']+/g, '[已脱敏路径]')
    .slice(0, maximum);
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function stringArray(value, maximumItems = 100) {
  if (!Array.isArray(value)) return [];
  return value.slice(0, maximumItems).map(item => cleanText(item, 300)).filter(Boolean);
}

function normalizeUsage(value) {
  if (!value || typeof value !== 'object') return null;
  const usage = {
    promptTokens: finiteNumber(value.prompt_tokens),
    cacheHitTokens: finiteNumber(value.prompt_cache_hit_tokens ?? value.prompt_tokens_details?.cached_tokens),
    cacheMissTokens: finiteNumber(value.prompt_cache_miss_tokens),
    completionTokens: finiteNumber(value.completion_tokens),
    totalTokens: finiteNumber(value.total_tokens)
  };
  return Object.values(usage).some(item => item !== null) ? usage : null;
}

function normalizeCost(value) {
  if (!value || typeof value !== 'object') return null;
  const estimatedCost = finiteNumber(value.estimatedCost);
  if (estimatedCost === null) return null;
  return {
    currency: cleanText(value.currency, 8) || 'USD',
    pricingCheckedAt: cleanText(value.pricingCheckedAt, 20),
    band: cleanText(value.band, 20),
    estimatedCost
  };
}

function normalizeAnswer(value) {
  if (!value || typeof value !== 'object') return null;
  const evidence = Array.isArray(value.currentEvidence) ? value.currentEvidence.slice(0, 100).map(item => ({
    evidenceId: cleanText(item?.evidenceId, 160),
    statement: cleanText(item?.statement, 1000)
  })).filter(item => item.evidenceId || item.statement) : [];
  const basis = Array.isArray(value.applicableBasis) ? value.applicableBasis.slice(0, 100).map(item => ({
    sourceId: cleanText(item?.sourceId, 160),
    statement: cleanText(item?.statement, 1000)
  })).filter(item => item.sourceId || item.statement) : [];
  const sources = Array.isArray(value.sources) ? value.sources.slice(0, 100).map(item => ({
    sourceId: cleanText(item?.sourceId, 160),
    title: cleanText(item?.title, 500),
    institution: cleanText(item?.institution, 200),
    version: cleanText(item?.version, 160),
    locator: cleanText(item?.locator, 500),
    sourceUrl: /^https?:\/\//i.test(String(item?.sourceUrl || '')) ? cleanText(item.sourceUrl, 1000) : null
  })).filter(item => item.sourceId || item.title) : [];
  return {
    conclusion: cleanText(value.conclusion, 2000),
    currentEvidence: evidence,
    applicableBasis: basis,
    limitations: stringArray(value.limitations),
    suggestedAttention: stringArray(value.suggestedAttention),
    sources
  };
}

function normalizeRecord(record) {
  if (!record || typeof record !== 'object' || !record.auditId) return null;
  return {
    auditId: cleanText(record.auditId, 160),
    createdAt: cleanText(record.createdAt, 64),
    question: cleanText(record.question, 2000),
    mode: VALID_MODES.has(record.mode) ? record.mode : 'unknown',
    status: VALID_STATUSES.has(record.status) ? record.status : 'unknown',
    mmsi: /^\d{7,10}$/.test(String(record.mmsi || '')) ? String(record.mmsi) : null,
    replayTime: cleanText(record.replayTime, 64),
    evidenceIds: stringArray(record.evidenceIds),
    sourceIds: stringArray(record.sourceIds),
    reason: cleanText(record.reason, 160),
    errorCode: cleanText(record.errorCode, 160),
    model: cleanText(record.model, 160),
    finishReason: cleanText(record.finishReason, 160),
    usage: normalizeUsage(record.usage),
    cost: normalizeCost(record.cost),
    latencyMs: finiteNumber(record.latencyMs),
    answer: normalizeAnswer(record.answer)
  };
}

function summaryOf(record) {
  return {
    auditId: record.auditId,
    createdAt: record.createdAt,
    questionPreview: cleanText(record.question, 120),
    mode: record.mode,
    status: record.status,
    mmsi: record.mmsi,
    replayTime: record.replayTime,
    model: record.model,
    usage: record.usage,
    cost: record.cost,
    latencyMs: record.latencyMs
  };
}

function parseFilters(input = {}) {
  const status = String(input.status || '').trim();
  const mode = String(input.mode || '').trim();
  const q = String(input.q || '').trim();
  if (status && !VALID_STATUSES.has(status)) throw new AuditQueryError('invalid_audit_status', '不支持的审计状态');
  if (mode && !VALID_MODES.has(mode)) throw new AuditQueryError('invalid_audit_mode', '不支持的运行模式');
  if (q.length > 100) throw new AuditQueryError('invalid_audit_query', '审计搜索关键词不能超过100字符');
  return { status, mode, q: q.toLocaleLowerCase('zh-CN') };
}

function createAuditStore(root) {
  const auditRoot = path.resolve(root);

  function readAll() {
    if (!fs.existsSync(auditRoot)) return { state: 'not_initialized', records: [], skippedInvalidRows: 0 };
    const files = fs.readdirSync(auditRoot).filter(name => name.endsWith('.jsonl')).sort().reverse();
    const records = [];
    let skippedInvalidRows = 0;
    for (const file of files) {
      const lines = fs.readFileSync(path.join(auditRoot, file), 'utf8').split(/\r?\n/).filter(Boolean);
      for (const line of lines) {
        try {
          const normalized = normalizeRecord(JSON.parse(line));
          if (normalized) records.push(normalized);
          else skippedInvalidRows += 1;
        } catch (_error) {
          skippedInvalidRows += 1;
        }
      }
    }
    records.sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')));
    const unique = [];
    const seen = new Set();
    for (const record of records) {
      if (seen.has(record.auditId)) continue;
      seen.add(record.auditId);
      unique.push(record);
    }
    return { state: files.length ? 'ready' : 'not_initialized', records: unique, skippedInvalidRows };
  }

  function filtered(filters = {}) {
    const parsed = parseFilters(filters);
    const snapshot = readAll();
    const records = snapshot.records.filter(record => {
      if (parsed.status && record.status !== parsed.status) return false;
      if (parsed.mode && record.mode !== parsed.mode) return false;
      if (!parsed.q) return true;
      return [record.auditId, record.question, record.mmsi].some(value => String(value || '').toLocaleLowerCase('zh-CN').includes(parsed.q));
    });
    return { ...snapshot, records, totalMatched: records.length };
  }

  function list(filters = {}) {
    const snapshot = filtered(filters);
    const limited = snapshot.records.slice(0, MAX_RESULTS);
    const counts = { total: snapshot.records.length, success: 0, localEvidence: 0, blockedOrError: 0 };
    snapshot.records.forEach(record => {
      if (record.status === 'success') counts.success += 1;
      if (record.status === 'local_evidence_only') counts.localEvidence += 1;
      if (record.status === 'blocked_by_guard' || record.status === 'model_error') counts.blockedOrError += 1;
    });
    return {
      state: snapshot.state,
      limit: MAX_RESULTS,
      totalMatched: snapshot.totalMatched,
      skippedInvalidRows: snapshot.skippedInvalidRows,
      counts,
      records: limited.map(summaryOf)
    };
  }

  function detail(auditId) {
    const id = String(auditId || '').trim();
    if (!/^AQ-[A-Za-z0-9-]{8,80}$/.test(id)) throw new AuditQueryError('invalid_audit_id', '审计编号格式无效');
    const record = readAll().records.find(item => item.auditId === id);
    if (!record) throw new AuditQueryError('audit_not_found', '没有找到该审计记录', 404);
    return record;
  }

  function exportRecords(filters = {}) {
    const snapshot = filtered(filters);
    return {
      exportedAt: new Date().toISOString(),
      state: snapshot.state,
      skippedInvalidRows: snapshot.skippedInvalidRows,
      totalMatched: snapshot.totalMatched,
      records: snapshot.records.slice(0, MAX_RESULTS)
    };
  }

  return { list, detail, exportRecords };
}

module.exports = { AuditQueryError, MAX_RESULTS, cleanText, normalizeRecord, parseFilters, createAuditStore };
