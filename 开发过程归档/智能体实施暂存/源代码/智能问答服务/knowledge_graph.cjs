'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { REGISTRY_PATH } = require('./retrieval.cjs');

const GRAPH_PATH = path.join('96_图谱审核数据', 'approved_graph.json');

class KnowledgeGraphError extends Error {
  constructor(code, message, statusCode = 400) {
    super(message);
    this.name = 'KnowledgeGraphError';
    this.code = code;
    this.statusCode = statusCode;
  }
}

function readJson(file, fallback) {
  if (!fs.existsSync(file)) return fallback;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function evidenceFor(context, event) {
  const evidence = [];
  if (context.currentObservation) {
    evidence.push({
      id: `OBS-${context.vessel.mmsi}-${context.currentObservation.observedAt}`,
      type: 'AIS_REAL_OBSERVATION',
      observedAt: context.currentObservation.observedAt,
      facts: {
        lat: context.currentObservation.lat,
        lon: context.currentObservation.lon,
        sogKt: context.currentObservation.sogKt,
        cogDeg: context.currentObservation.cogDeg,
        ageMinutes: context.currentObservation.ageMinutes
      }
    });
  }
  if (event?.distanceNm !== null && event?.distanceNm !== undefined) {
    evidence.push({ id: `DISTANCE-${event.id}`, type: 'RELATIVE_DISTANCE', unit: 'nautical_mile', value: event.distanceNm });
  }
  if (event?.cpa) {
    evidence.push({
      id: `CPA-${event.id}`,
      type: 'CPA_TCPA_DERIVATION',
      method: event.cpa.method,
      available: event.cpa.available,
      facts: { dcpaNm: event.cpa.dcpaNm, tcpaMinutes: event.cpa.tcpaMinutes, relativeSpeedKt: event.cpa.relativeSpeedKt }
    });
  }
  if (event?.metric) evidence.push({ id: `METRIC-${event.id}`, type: 'BEHAVIOR_SCREENING_METRIC', value: event.metric });
  evidence.push({
    id: `QUALITY-${context.vessel.mmsi}`,
    type: 'DATA_QUALITY_GATE',
    sufficientForCurrentMotion: context.evidenceGate.sufficientForCurrentMotion,
    missingReasons: context.evidenceGate.missingReasons,
    boundary: context.evidenceGate.boundary
  });
  return evidence;
}

function createKnowledgeGraph(config) {
  let cache = null;

  function build() {
    const registryFile = path.join(config.knowledgeBaseRoot, REGISTRY_PATH);
    const graphFile = path.join(config.knowledgeBaseRoot, GRAPH_PATH);
    const registry = readJson(registryFile, []);
    const graph = readJson(graphFile, { schemaVersion: '1.0', claims: [] });
    if (!Array.isArray(registry) || !Array.isArray(graph.claims)) throw new Error('知识图谱或来源登记格式无效');
    const approvedSources = new Map(registry.filter(item => item.reviewStatus === '已审核').map(item => [item.id, item]));
    const activeClaims = graph.claims.filter(claim => claim.reviewStatus === '已审核' && approvedSources.has(claim.sourceId));
    return { registryFile, graphFile, registry, graph, approvedSources, activeClaims };
  }

  function state() {
    if (!cache) cache = build();
    return cache;
  }

  function refresh() {
    cache = build();
    return status();
  }

  function status() {
    const current = state();
    return {
      state: current.activeClaims.length ? 'ready' : 'not_initialized',
      registeredClaims: current.graph.claims.length,
      activeClaims: current.activeClaims.length,
      approvedSources: current.approvedSources.size
    };
  }

  function publicClaim(claim) {
    const source = state().approvedSources.get(claim.sourceId);
    return {
      id: claim.id,
      title: claim.title,
      statement: claim.statement,
      boundary: claim.boundary,
      relation: 'MAY_INFORM_INTERPRETATION',
      source: {
        id: source.id,
        title: source.title,
        institution: source.institution,
        version: source.version,
        sourceUrl: source.sourceUrl,
        locator: claim.locator,
        reviewStatus: source.reviewStatus
      }
    };
  }

  function topic(topicValue) {
    const topicId = String(topicValue || '').trim().toLowerCase();
    if (!/^[a-z0-9_]{2,50}$/.test(topicId)) throw new KnowledgeGraphError('invalid_topic', '主题必须是2至50位小写字母、数字或下划线');
    const claims = state().activeClaims.filter(claim => Array.isArray(claim.topics) && claim.topics.includes(topicId));
    return { topic: topicId, relationBoundary: '仅返回已审核知识的可能相关关系，不构成违法认定或操船指令。', claims: claims.map(publicClaim) };
  }

  function trace(context, eventId) {
    if (!context || !context.vessel || !Array.isArray(context.events)) throw new KnowledgeGraphError('invalid_context', 'AIS上下文格式无效', 500);
    const requestedId = String(eventId || '').trim();
    if (requestedId && !/^[A-Za-z0-9_-]{1,100}$/.test(requestedId)) throw new KnowledgeGraphError('invalid_event_id', '事件ID格式无效');
    const event = requestedId ? context.events.find(item => item.id === requestedId) : context.events[0];
    if (requestedId && !event) throw new KnowledgeGraphError('event_not_found', '当前船舶和回放时刻没有该事件', 404);
    if (!event) {
      return {
        status: 'no_current_event',
        query: context.query,
        vessel: context.vessel,
        evidence: evidenceFor(context, null),
        paths: [],
        boundary: '当前筛选器没有生成事件；这不等于海上绝对安全，也不生成规则或违法结论。'
      };
    }
    const claims = state().activeClaims.filter(claim =>
      Array.isArray(claim.appliesToKinds) && (claim.appliesToKinds.includes('*') || claim.appliesToKinds.includes(event.kind)));
    const evidence = evidenceFor(context, event);
    return {
      status: claims.length ? 'ready' : 'no_approved_path',
      query: context.query,
      vessel: context.vessel,
      event,
      evidence,
      paths: claims.map(claim => ({
        eventId: event.id,
        evidenceIds: evidence.map(item => item.id),
        relation: 'MAY_BE_EXPLAINED_WITH',
        claim: publicClaim(claim)
      })),
      boundary: '图谱路径只说明当前事件、观测证据与已审核知识之间可能相关，不认定违法，不替代雷达、人工瞭望、VTS或值班人员判断。'
    };
  }

  return { refresh, status, topic, trace };
}

module.exports = { GRAPH_PATH, KnowledgeGraphError, createKnowledgeGraph, evidenceFor };
