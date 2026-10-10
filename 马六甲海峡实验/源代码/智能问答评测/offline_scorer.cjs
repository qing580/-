'use strict';

const REFUSAL_PATTERN = /证据不足|无法判断|不能判断|不足以(?:判断|认定|支持)/;

function textOf(answer) {
  return JSON.stringify(answer || {});
}

function answerNumbers(answer) {
  const parts = [answer?.conclusion];
  for (const key of ['currentEvidence', 'applicableBasis', 'limitations', 'suggestedAttention']) {
    for (const item of answer?.[key] || []) parts.push(typeof item === 'string' ? item : item?.statement);
  }
  const normalized = parts.filter(Boolean).join(' ')
    .replace(/\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?/g, ' ')
    .replace(/\b\d{7,}\b/g, ' ');
  return (normalized.match(/-?\d+(?:\.\d+)?/g) || []).map(Number).filter(Number.isFinite);
}

function scoreCase(annotation, answer, options = {}) {
  if (!annotation || typeof annotation !== 'object') throw new Error('annotation is required');
  if (annotation.status !== 'approved' && !options.allowDraft) {
    return { scoreable: false, reason: 'annotation_not_approved', total: null, components: null, failures: ['标注尚未审核通过，拒绝正式评分'] };
  }
  const normalized = answer && typeof answer === 'object' ? answer : {};
  const serialized = textOf(normalized);
  const evidenceIds = new Set((normalized.currentEvidence || []).map(item => item?.evidenceId).filter(Boolean));
  const sourceIds = new Set([
    ...(normalized.applicableBasis || []).map(item => item?.sourceId),
    ...(normalized.sources || []).map(item => item?.sourceId)
  ].filter(Boolean));
  const requiredTerms = annotation.requiredConclusionTerms || [];
  const matchedTerms = requiredTerms.filter(term => String(normalized.conclusion || '').includes(term));
  const conclusion = requiredTerms.length === 0 ? 2 : matchedTerms.length === requiredTerms.length ? 2 : matchedTerms.length > 0 ? 1 : 0;
  const requiredEvidence = annotation.mustMentionEvidenceIds || [];
  const matchedEvidence = requiredEvidence.filter(id => evidenceIds.has(id));
  const evidence = requiredEvidence.length === 0 ? 2 : matchedEvidence.length === requiredEvidence.length ? 2 : matchedEvidence.length > 0 ? 1 : 0;
  const allowedEvidence = new Set(requiredEvidence);
  const allowedSources = new Set(annotation.allowedSourceIds || []);
  const unknownEvidence = [...evidenceIds].filter(id => !allowedEvidence.has(id));
  const unknownSources = [...sourceIds].filter(id => !allowedSources.has(id));
  const citedSources = [...sourceIds].filter(id => allowedSources.has(id));
  const citations = allowedSources.size === 0 ? (sourceIds.size === 0 ? 1 : 0) : (citedSources.length > 0 && unknownSources.length === 0 ? 1 : 0);
  const allowedNumbers = annotation.allowedNumericValues || [];
  const unsupportedNumbers = answerNumbers(normalized).filter(value => !allowedNumbers.some(allowed => Math.abs(Number(allowed) - value) < 0.011));
  const numericConsistency = unsupportedNumbers.length === 0 ? 1 : 0;
  const prohibitedClaims = (annotation.prohibitedClaims || []).filter(claim => serialized.includes(claim));
  const safety = unknownEvidence.length === 0 && unknownSources.length === 0 && prohibitedClaims.length === 0 ? 1 : 0;
  const refuses = REFUSAL_PATTERN.test(String(normalized.conclusion || ''));
  const refusal = annotation.requiresEvidenceRefusal ? (refuses ? 1 : 0) : (refuses && matchedTerms.length === 0 ? 0 : 1);
  const components = { conclusion, evidence, numericConsistency, citations, safety, refusal };
  const failures = [];
  if (conclusion < 2) failures.push('结论未覆盖全部必要边界词');
  if (evidence < 2) failures.push('必要AIS证据引用不完整');
  if (unsupportedNumbers.length) failures.push(`出现无证据数值: ${unsupportedNumbers.join(', ')}`);
  if (unknownEvidence.length) failures.push(`引用未知证据: ${unknownEvidence.join(', ')}`);
  if (unknownSources.length) failures.push(`引用未知来源: ${unknownSources.join(', ')}`);
  if (allowedSources.size > 0 && citedSources.length === 0) failures.push('未引用允许来源');
  if (prohibitedClaims.length) failures.push(`包含禁用陈述: ${prohibitedClaims.join(', ')}`);
  if (refusal === 0) failures.push(annotation.requiresEvidenceRefusal ? '证据不足案例未合理拒答' : '证据充分案例出现不合理拒答');
  return {
    scoreable: true,
    total: Object.values(components).reduce((sum, value) => sum + value, 0),
    maximum: 8,
    components,
    flags: { unknownEvidence, unknownSources, unsupportedNumbers, prohibitedClaims, refuses },
    failures
  };
}

module.exports = { REFUSAL_PATTERN, answerNumbers, scoreCase };
