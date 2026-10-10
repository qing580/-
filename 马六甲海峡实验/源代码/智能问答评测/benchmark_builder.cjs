'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { loadConfig } = require('../智能问答服务/config.cjs');
const { createAisTools } = require('../智能问答服务/ais_tools.cjs');
const { createRetriever } = require('../智能问答服务/retrieval.cjs');
const { createKnowledgeGraph } = require('../智能问答服务/knowledge_graph.cjs');

const GENERATOR_VERSION = '1.0.0';
const FIVE_MINUTES = 5 * 60 * 1000;
const TWENTY_MINUTES = 20 * 60 * 1000;

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

const REVIEW_CORE_FIELDS = [
  'expectedConclusionBoundary', 'expectedEvidenceSummary', 'requiredConclusionTerms',
  'mustMentionEvidenceIds', 'allowedSourceIds', 'allowedNumericValues',
  'requiresEvidenceRefusal', 'prohibitedClaims', 'requiredLimitations'
];

function reviewCore(annotation) {
  return Object.fromEntries(REVIEW_CORE_FIELDS.map(key => [key, annotation?.[key] ?? null]));
}

function writeAnnotation(file, draft) {
  if (fs.existsSync(file)) {
    const existing = readJson(file);
    if (['approved', 'rejected'].includes(existing.status)) {
      if (JSON.stringify(reviewCore(existing)) !== JSON.stringify(reviewCore(draft))) {
        throw new Error(`已审核标注与新证据不一致，拒绝覆盖: ${file}`);
      }
      writeJson(file, existing);
      return existing;
    }
  }
  writeJson(file, draft);
  return draft;
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function pointTime(point) {
  const value = Date.parse(point?.time);
  return Number.isFinite(value) ? value : null;
}

function finiteMotion(point) {
  const sog = Number(point?.sog);
  const cog = Number(point?.cog);
  return point?.sog !== null && point?.sog !== '' && Number.isFinite(sog) && sog >= 0 && sog < 102.3 &&
    point?.cog !== null && point?.cog !== '' && Number.isFinite(cog) && cog >= 0 && cog < 360;
}

function mmsisOf(event) {
  return event.vessels.map(vessel => String(vessel.mmsi)).sort();
}

function candidateKey(event) {
  if (event.kind.includes('会遇')) return `encounter:${mmsisOf(event).join('-')}`;
  return `${event.kind}:${mmsisOf(event)[0]}`;
}

function eventCandidates(data, management, encounter) {
  const allTimes = data.vessels.flatMap(vessel => vessel.points.map(pointTime)).filter(Number.isFinite).sort((a, b) => a - b);
  const start = allTimes[0];
  const end = allTimes[allTimes.length - 1];
  const candidates = [];
  const lastSeen = new Map();
  for (let time = start; time <= end; time += FIVE_MINUTES) {
    const built = management.buildEvents(data.vessels, time, encounter);
    for (const event of built.events) {
      const key = candidateKey(event);
      const previous = lastSeen.get(key);
      if (previous !== undefined && time - previous < TWENTY_MINUTES) continue;
      lastSeen.set(key, time);
      candidates.push({
        family: event.kind.includes('会遇') ? 'encounter' : 'behavior',
        subtype: event.kind,
        time: new Date(time).toISOString(),
        timeMs: time,
        eventId: event.id,
        level: event.level,
        mmsis: mmsisOf(event),
        vesselNames: event.vessels.map(vessel => vessel.name || '未获取船名'),
        metric: event.metric || null,
        dcpaNm: Number.isFinite(event.cpa?.dcpa) ? event.cpa.dcpa : null,
        tcpaMinutes: Number.isFinite(event.cpa?.tcpa) ? event.cpa.tcpa : null
      });
    }
  }
  return { start, end, candidates };
}

function canUse(candidate, counts, limit = 2) {
  return candidate.mmsis.every(mmsi => (counts.get(mmsi) || 0) < limit);
}

function markUsed(candidate, counts) {
  candidate.mmsis.forEach(mmsi => counts.set(mmsi, (counts.get(mmsi) || 0) + 1));
}

function takeFirst(pool, predicate, counts) {
  const found = pool.find(candidate => predicate(candidate) && canUse(candidate, counts));
  if (!found) throw new Error('现有数据无法满足任务8A案例配额与去重约束');
  markUsed(found, counts);
  return found;
}

function chooseEventCases(candidates) {
  const counts = new Map();
  const encounters = candidates.filter(item => item.family === 'encounter').sort((a, b) => a.timeMs - b.timeMs || a.eventId.localeCompare(b.eventId));
  const behavior = candidates.filter(item => item.family === 'behavior').sort((a, b) => a.timeMs - b.timeMs || a.eventId.localeCompare(b.eventId));
  const selected = [];
  selected.push(takeFirst(encounters, item => item.level === '高风险', counts));
  selected.push(takeFirst(encounters, item => item.level === '高风险' && item.timeMs - selected[0].timeMs >= TWENTY_MINUTES, counts));
  selected.push(takeFirst(encounters, item => item.level === '中高风险', counts));
  selected.push(takeFirst(encounters, item => item.level === '中高风险' && item.timeMs - selected[2].timeMs >= TWENTY_MINUTES, counts));
  selected.push(takeFirst(behavior, item => item.subtype === '异常转向初筛', counts));
  selected.push(takeFirst(behavior, item => item.subtype === '异常减速初筛', counts));
  return { selected, counts };
}

function chooseNormalCases(data, management, encounter, start, end, counts) {
  const candidates = [];
  for (let time = start + 30 * 60 * 1000; time <= end - 30 * 60 * 1000; time += FIVE_MINUTES) {
    const built = management.buildEvents(data.vessels, time, encounter);
    const eventMmsis = new Set(built.events.flatMap(mmsisOf));
    for (const row of built.snapshots) {
      const mmsi = String(row.vessel.mmsi);
      if (row.ageMinutes > 5 || !finiteMotion(row.point) || eventMmsis.has(mmsi) || (counts.get(mmsi) || 0) >= 2) continue;
      candidates.push({ family: 'normal', subtype: '无当前关联事件', time: new Date(time).toISOString(), timeMs: time, eventId: null, level: '未形成事件', mmsis: [mmsi], vesselNames: [row.vessel.name || '未获取船名'] });
    }
  }
  if (!candidates.length) throw new Error('没有找到满足证据门槛的正常案例');
  const first = candidates[0];
  markUsed(first, counts);
  const second = candidates.find(item => item.timeMs - first.timeMs >= 60 * 60 * 1000 && canUse(item, counts));
  if (!second) throw new Error('没有找到时间分离的第二个正常案例');
  markUsed(second, counts);
  return [first, second];
}

function sortedPoints(vessel) {
  return vessel.points.map(point => ({ point, timeMs: pointTime(point) })).filter(item => item.timeMs !== null).sort((a, b) => a.timeMs - b.timeMs);
}

function chooseInsufficientCases(data, start, end, counts) {
  const pools = { missingMotion: [], stale: [], noPrior: [] };
  const vessels = [...data.vessels].sort((a, b) => String(a.mmsi).localeCompare(String(b.mmsi)));
  for (const vessel of vessels) {
    const mmsi = String(vessel.mmsi);
    if ((counts.get(mmsi) || 0) >= 2) continue;
    const points = sortedPoints(vessel);
    const item = points.find(row => !finiteMotion(row.point));
    if (item) pools.missingMotion.push({ family: 'insufficient', subtype: '运动字段缺失', time: new Date(item.timeMs).toISOString(), timeMs: item.timeMs, eventId: null, level: '证据不足', mmsis: [mmsi], vesselNames: [vessel.name || '未获取船名'] });
    for (let index = 1; index < points.length; index += 1) {
      if (points[index].timeMs - points[index - 1].timeMs > 12 * 60 * 1000) {
        const timeMs = points[index - 1].timeMs + 6 * 60 * 1000;
        if (timeMs >= start && timeMs <= end) {
          pools.stale.push({ family: 'insufficient', subtype: '观测超过5分钟', time: new Date(timeMs).toISOString(), timeMs, eventId: null, level: '证据不足', mmsis: [mmsi], vesselNames: [vessel.name || '未获取船名'] });
          break;
        }
      }
    }
    if (points[0]?.timeMs - start > 2 * 60 * 1000) {
      const timeMs = points[0].timeMs - 60 * 1000;
      pools.noPrior.push({ family: 'insufficient', subtype: '回放时刻前无有效观测', time: new Date(timeMs).toISOString(), timeMs, eventId: null, level: '证据不足', mmsis: [mmsi], vesselNames: [vessel.name || '未获取船名'] });
    }
  }
  const selected = [];
  for (const key of ['missingMotion', 'stale', 'noPrior']) {
    const item = pools[key].find(candidate => canUse(candidate, counts));
    if (!item) throw new Error('证据不足案例类型不完整或MMSI复用超过上限');
    selected.push(item);
    markUsed(item, counts);
  }
  return selected;
}

function caseQuestion(candidate) {
  if (candidate.family === 'encounter') return '请解释当前关注船附近的主要会遇异常及其AIS证据。';
  if (candidate.subtype === '异常转向初筛') return '当前船舶是否出现需要复核的异常转向，证据和局限性是什么？';
  if (candidate.subtype === '异常减速初筛') return '当前船舶是否出现需要复核的异常减速，证据和局限性是什么？';
  if (candidate.family === 'normal') return '当前回放时刻是否存在与关注船相关的明确异常事件？';
  return '当前AIS证据是否足以判断船舶运动或异常状态？';
}

function observationAtOrBefore(data, mmsi, replayTimeMs) {
  const vessel = data.vessels.find(item => String(item.mmsi) === String(mmsi));
  if (!vessel) return null;
  const rows = sortedPoints(vessel).filter(item => item.timeMs <= replayTimeMs);
  const latest = rows[rows.length - 1];
  if (!latest) return null;
  const heading = Number(latest.point.heading);
  return {
    id: `CASEOBS-${mmsi}-${new Date(latest.timeMs).toISOString()}`,
    mmsi: String(mmsi),
    vesselName: vessel.name || '未获取船名',
    observedAt: new Date(latest.timeMs).toISOString(),
    lat: latest.point.lat ?? null,
    lon: latest.point.lon ?? null,
    sogKt: latest.point.sog ?? null,
    cogDeg: latest.point.cog ?? null,
    trueHeadingDeg: latest.point.heading !== null && latest.point.heading !== '' && Number.isFinite(heading) && heading >= 0 && heading < 360 ? heading : null,
    sourceType: 'AIS_real_observation'
  };
}

function compactPacket(data, aisTools, retriever, graph, candidate) {
  const question = caseQuestion(candidate);
  const context = aisTools.context(candidate.mmsis[0], candidate.time, { windowMinutes: 30 });
  const retrieval = retriever.search(question, { limit: 4 });
  const graphTrace = graph.trace(context, candidate.eventId);
  const involvedObservations = candidate.family === 'encounter'
    ? candidate.mmsis.map(mmsi => observationAtOrBefore(data, mmsi, candidate.timeMs)).filter(Boolean)
    : [];
  const caseEvidence = involvedObservations.length
    ? { selectedEventId: candidate.eventId, involvedObservations }
    : null;
  return { question, aisContext: context, caseEvidence, retrieval, graphTrace };
}

function knowledgePacket(retriever) {
  const question = 'AIS能否作为唯一避碰依据？请说明限制和需要结合的信息。';
  return { question, aisContext: null, retrieval: retriever.search(question, { limit: 4 }), graphTrace: null };
}

function numbersFrom(value, output = []) {
  if (typeof value === 'number' && Number.isFinite(value)) output.push(value);
  else if (typeof value === 'string') {
    for (const match of value.matchAll(/-?\d+(?:\.\d+)?/g)) {
      const number = Number(match[0]);
      if (Number.isFinite(number)) output.push(number);
    }
  }
  else if (Array.isArray(value)) value.forEach(item => numbersFrom(item, output));
  else if (value && typeof value === 'object') Object.entries(value).forEach(([key, item]) => {
    if (!/id$|mmsi|time|date|observed|updated/i.test(key)) numbersFrom(item, output);
  });
  return output;
}

function unique(values) {
  return [...new Set(values.filter(value => value !== null && value !== undefined && value !== ''))];
}

function annotationFor(caseItem, packet) {
  const graphEvidence = packet.graphTrace?.evidence || [];
  const graphEvidenceIds = graphEvidence
    .filter(item => caseItem.family !== 'encounter' || item.type !== 'AIS_REAL_OBSERVATION')
    .map(item => item.id);
  const evidenceIds = unique([
    ...graphEvidenceIds,
    ...(packet.caseEvidence?.involvedObservations?.map(item => item.id) || [])
  ]);
  const sourceIds = unique([
    ...packet.retrieval.map(item => item.sourceId),
    ...(packet.graphTrace?.paths || []).map(item => item.claim?.source?.id)
  ]);
  const insufficient = caseItem.family === 'insufficient';
  const knowledge = caseItem.family === 'knowledge';
  const requiredLimitations = knowledge
    ? ['AIS不能替代雷达、人工瞭望或航海判断']
    : ['仅使用回放时刻及以前的AIS证据', '不替代人工航海判断'];
  if (caseItem.family === 'encounter') {
    const observations = packet.caseEvidence?.involvedObservations || [];
    if (observations.some(item => Number.isFinite(Number(item.sogKt)) && Number(item.sogKt) < 1)) {
      requiredLimitations.push('至少一船SOG低于1节，低速时COG与会遇形态解释需谨慎');
    }
    if ((packet.aisContext?.trajectory || []).length < 2) {
      requiredLimitations.push('关注船30分钟窗口少于2个观测点，不能验证轨迹变化稳定性');
    }
    if (observations.some(item => item.trueHeadingDeg === null)) {
      requiredLimitations.push('至少一船true_heading不可用，不得把缺失值解释为实际船艏向');
    }
    if (observations.some(item => item.vesselName === '未获取船名')) {
      requiredLimitations.push('至少一船名称未获取，不得对其身份或船型作确定表述');
    }
  }
  let requiredConclusionTerms = [];
  let expectedConclusionBoundary = '';
  if (insufficient) {
    requiredConclusionTerms = ['证据不足'];
    expectedConclusionBoundary = '必须明确当前AIS证据不足，不能判断船舶当前运动或异常状态。';
  } else if (knowledge) {
    requiredConclusionTerms = ['不能', '唯一'];
    expectedConclusionBoundary = '必须说明AIS不能作为唯一避碰依据，并要求结合雷达、瞭望、VTS或其他航海信息。';
  } else if (caseItem.family === 'normal') {
    requiredConclusionTerms = ['未形成事件', '绝对安全'];
    expectedConclusionBoundary = '可说明当前筛选器未形成关联事件，但不得表述为海上绝对安全。';
  } else {
    requiredConclusionTerms = caseItem.family === 'encounter' ? ['会遇', '人工复核'] : [caseItem.subtype.replace('初筛', ''), '人工复核'];
    expectedConclusionBoundary = '只能说明现有AIS与筛查规则形成需要关注或复核的证据，不认定违法、责任或主观意图。';
  }
  return {
    status: 'draft',
    reviewedBy: null,
    reviewedAt: null,
    expectedConclusionBoundary,
    expectedEvidenceSummary: caseItem.family === 'encounter' ? {
      selectedEventId: packet.caseEvidence?.selectedEventId || null,
      screeningLevel: packet.graphTrace?.event?.level || caseItem.screeningLevel,
      screeningConfidence: packet.graphTrace?.event?.confidence || null,
      distanceNm: packet.graphTrace?.event?.distanceNm ?? null,
      dcpaNm: packet.graphTrace?.event?.cpa?.dcpaNm ?? null,
      tcpaMinutes: packet.graphTrace?.event?.cpa?.tcpaMinutes ?? null,
      relativeSpeedKt: packet.graphTrace?.event?.cpa?.relativeSpeedKt ?? null,
      method: packet.graphTrace?.event?.cpa?.method || null,
      involvedObservations: packet.caseEvidence?.involvedObservations || []
    } : null,
    requiredConclusionTerms,
    mustMentionEvidenceIds: evidenceIds,
    allowedSourceIds: sourceIds,
    allowedNumericValues: unique(numbersFrom({ evidence: packet.graphTrace?.evidence || [], observation: packet.aisContext?.currentObservation || null, caseEvidence: packet.caseEvidence || null }).map(value => Number(value.toFixed(6)))),
    requiresEvidenceRefusal: insufficient,
    prohibitedClaims: ['已违法', '违反避碰规则', '应立即转向', '必须立即改向', '碰撞风险分'],
    requiredLimitations,
    reviewerNotes: '请逐项核对问题、证据ID、来源、数值、结论边界和拒答要求；确认后再将status改为approved。'
  };
}

function caseRecord(caseId, candidate, packet) {
  return {
    caseId,
    family: candidate.family,
    subtype: candidate.subtype,
    question: packet.question,
    mmsi: candidate.mmsis[0] || null,
    vesselName: candidate.vesselNames?.[0] || null,
    involvedMmsis: candidate.mmsis,
    replayTime: candidate.time || null,
    eventId: candidate.eventId || null,
    screeningLevel: candidate.level,
    screeningMetric: candidate.metric || null,
    dcpaNm: candidate.dcpaNm ?? null,
    tcpaMinutes: candidate.tcpaMinutes ?? null,
    annotationStatus: 'draft'
  };
}

function reviewChecklist(cases) {
  const rows = cases.map(item => {
    const checked = item.annotationStatus === 'approved' ? 'x' : ' ';
    const note = item.annotationStatus === 'approved' ? '已批准，审核详情见annotation.json。' : '';
    return `- [${checked}] ${item.caseId} | ${item.family}/${item.subtype} | ${item.mmsi || '无MMSI'} | ${item.replayTime || '无回放时间'}\n  - [${checked}] 问题与案例类型一致\n  - [${checked}] AIS证据与回放时间一致\n  - [${checked}] 允许来源与结论边界合理\n  - [${checked}] 拒答要求和禁用陈述完整\n  - 审核意见：${note}`;
  }).join('\n');
  const approved = cases.filter(item => item.annotationStatus === 'approved').length;
  const rejected = cases.filter(item => item.annotationStatus === 'rejected').length;
  const draft = cases.length - approved - rejected;
  return `# 任务8A第一版案例审核清单\n\n当前状态：已批准${approved}例、已否决${rejected}例、待审核${draft}例。请逐例核对，不要批量改为approved。\n\n${rows}\n`;
}

function datasetCard(manifest) {
  return `# 马六甲海峡智能问答评测基准集 v1\n\n- 状态：草稿，尚未形成金标准。\n- 数据区域：马六甲海峡东南段及新加坡海峡实验范围。\n- AIS时间范围：${manifest.dataset.timeRange.start} 至 ${manifest.dataset.timeRange.end}。\n- 案例数：${manifest.cases.length}。\n- 生成器版本：${manifest.generatorVersion}。\n- AIS数据SHA256：${manifest.dataset.sha256}。\n\n## 构造边界\n\n案例来自现有历史回放和既有筛查算法。事件候选不是违法或责任认定，正常候选也不等于海上绝对安全。所有标注必须经人工逐例确认后才能用于正式评测。\n\n## 隔离规则\n\n本目录位于运行结果，不得复制到知识库资料，不得被RAG索引，也不得作为模型输入的一部分。\n`;
}

function displayMetric(item) {
  if (item.family === 'encounter') return `DCPA ${Number(item.dcpaNm).toFixed(3)} nm；TCPA ${Number(item.tcpaMinutes).toFixed(1)} min`;
  if (item.family === 'behavior') return item.screeningMetric || item.subtype;
  if (item.family === 'insufficient') return `工具缺失原因：${item.subtype}`;
  if (item.family === 'normal') return '当前运动证据门槛通过；筛选器未形成关联事件';
  return '核对AIS不能作为唯一避碰依据及所需辅助信息';
}

function candidateReviewSummary(cases) {
  const statusText = status => ({ approved: '已批准', rejected: '已否决', draft: '待审核' }[status] || status);
  const rows = cases.map(item => `| ${item.caseId} | ${item.family}/${item.subtype} | ${item.vesselName || '不适用'} (${item.involvedMmsis.join('+') || '无MMSI'}) | ${item.replayTime || '不适用'} | ${displayMetric(item)} | ${statusText(item.annotationStatus)} |`).join('\n');
  return `# 任务8A候选案例审核摘要\n\n> 本页是程序生成的审核入口，不是模型结果，也不是人工金标准。12例的标注状态均为\`draft\`。\n\n| 案例 | 类型 | 船舶 | 回放时刻（UTC） | 关键候选依据 | 状态 |\n| --- | --- | --- | --- | --- | --- |\n${rows}\n\n## 审核方法\n\n1. 先核对本页的船舶、时刻和候选依据。\n2. 打开对应案例目录的\`evidence_packet.json\`，确认AIS观测、事件指标和来源只来自回放时刻及以前。\n3. 打开\`annotation.json\`，核对结论边界、必要证据ID、允许来源、数值白名单和禁用陈述。\n4. 在\`review_checklist.md\`记录意见。确认后才可把单例状态改为\`approved\`；不合格案例标为\`rejected\`并补选。\n\n## 解释边界\n\n- “高风险/中高风险”是现有筛查规则的候选等级，不是违法、责任或必然碰撞认定。\n- “未形成事件”只表示当前筛选器没有生成关联事件，不等于绝对安全。\n- 三个证据不足案例必须拒绝给出确定运动或异常结论。\n- 本轮没有调用DeepSeek，不存在模型准确率、RAG增益或图谱增益结果。\n`;
}

function buildBenchmark(options = {}) {
  const projectRoot = path.resolve(options.projectRoot || path.join(__dirname, '..', '..'));
  const config = loadConfig({ projectRoot });
  const data = readJson(config.aisDataFile);
  const management = require(path.join(config.aisModuleDir, '管理端数据逻辑.js'));
  const encounter = require(path.join(config.aisModuleDir, '船舶邻近计算.js'));
  const aisTools = createAisTools(config);
  const retriever = createRetriever(config);
  const graph = createKnowledgeGraph(config);
  const outputRoot = path.resolve(options.outputRoot || path.join(projectRoot, '运行结果', '智能问答第一版', '评测基准集_v1'));
  const scanned = eventCandidates(data, management, encounter);
  const eventSelection = chooseEventCases(scanned.candidates);
  const normal = chooseNormalCases(data, management, encounter, scanned.start, scanned.end, eventSelection.counts);
  const insufficient = chooseInsufficientCases(data, scanned.start, scanned.end, eventSelection.counts);
  const candidates = [...normal, ...eventSelection.selected.slice(0, 4), ...eventSelection.selected.slice(4), ...insufficient];
  const prefixes = { normal: 'NORMAL', encounter: 'ENCOUNTER', behavior: 'BEHAVIOR', insufficient: 'INSUFFICIENT' };
  const counters = new Map();
  const builtCases = [];
  for (const candidate of candidates) {
    const next = (counters.get(candidate.family) || 0) + 1;
    counters.set(candidate.family, next);
    const caseId = `CASE-${prefixes[candidate.family]}-${String(next).padStart(3, '0')}`;
    const packet = compactPacket(data, aisTools, retriever, graph, candidate);
    const record = caseRecord(caseId, candidate, packet);
    const annotation = annotationFor(record, packet);
    writeJson(path.join(outputRoot, 'cases', caseId, 'evidence_packet.json'), packet);
    const savedAnnotation = writeAnnotation(path.join(outputRoot, 'cases', caseId, 'annotation.json'), annotation);
    record.annotationStatus = savedAnnotation.status;
    builtCases.push(record);
  }
  const knowledgeCandidate = { family: 'knowledge', subtype: 'AIS使用限制', time: null, eventId: null, level: '专业知识', mmsis: [], vesselNames: [] };
  const knowledge = knowledgePacket(retriever);
  const knowledgeRecord = caseRecord('CASE-KNOWLEDGE-001', knowledgeCandidate, knowledge);
  writeJson(path.join(outputRoot, 'cases', knowledgeRecord.caseId, 'evidence_packet.json'), knowledge);
  const savedKnowledgeAnnotation = writeAnnotation(path.join(outputRoot, 'cases', knowledgeRecord.caseId, 'annotation.json'), annotationFor(knowledgeRecord, knowledge));
  knowledgeRecord.annotationStatus = savedKnowledgeAnnotation.status;
  builtCases.push(knowledgeRecord);
  const manifest = {
    benchmarkId: 'malacca-agent-benchmark-v1',
    generatorVersion: GENERATOR_VERSION,
    generatedAt: options.generatedAt || new Date().toISOString(),
    status: 'draft',
    dataset: { file: path.basename(config.aisDataFile), sha256: sha256(config.aisDataFile), timeRange: { start: new Date(scanned.start).toISOString(), end: new Date(scanned.end).toISOString() } },
    selectionSummary: {
      sampledEveryMinutes: 5,
      encounterOccurrences: scanned.candidates.filter(item => item.family === 'encounter').length,
      behaviorOccurrences: scanned.candidates.filter(item => item.family === 'behavior').length,
      note: '候选数已经按同一事件过程20分钟窗口去重，不能解释为真实异常发生率。'
    },
    cases: builtCases
  };
  writeJson(path.join(outputRoot, 'candidate_manifest.json'), manifest);
  fs.writeFileSync(path.join(outputRoot, 'review_checklist.md'), reviewChecklist(builtCases), 'utf8');
  fs.writeFileSync(path.join(outputRoot, 'candidate_review_summary.md'), candidateReviewSummary(builtCases), 'utf8');
  fs.writeFileSync(path.join(outputRoot, 'dataset_card.md'), datasetCard(manifest), 'utf8');
  return { outputRoot, manifest };
}

module.exports = { GENERATOR_VERSION, eventCandidates, chooseEventCases, chooseNormalCases, chooseInsufficientCases, annotationFor, writeAnnotation, buildBenchmark };
