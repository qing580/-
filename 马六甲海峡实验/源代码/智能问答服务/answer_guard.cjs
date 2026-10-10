'use strict';

class AnswerGuardError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'AnswerGuardError';
    this.code = code;
    this.statusCode = 422;
  }
}

const REQUIRED_ARRAYS = ['currentEvidence', 'applicableBasis', 'limitations', 'suggestedAttention', 'sources'];
const FORBIDDEN_PATTERNS = [/风险值/i, /风险分/i, /\d+(?:\.\d+)?\s*分(?:数)?/, /已经违法/, /构成违法/, /承担(?:主要|全部|碰撞)?责任/, /必须(?:左转|右转|转向|加速|减速)/];

function numbers(text) {
  return (String(text || '').match(/-?\d+(?:\.\d+)?/g) || []).map(Number).filter(Number.isFinite);
}

function referencedIds(packet) {
  const evidenceIds = new Set(packet.graphTrace?.evidence?.map(item => item.id) || []);
  const sourceIds = new Set([
    ...(packet.retrieval || []).map(item => item.sourceId),
    ...(packet.graphTrace?.paths || []).map(item => item.claim?.source?.id)
  ].filter(Boolean));
  return { evidenceIds, sourceIds };
}

function validateAnswer(rawContent, packet) {
  let answer;
  try { answer = typeof rawContent === 'string' ? JSON.parse(rawContent) : rawContent; }
  catch (_error) { throw new AnswerGuardError('answer_invalid_json', '模型回答不是有效JSON'); }
  if (!answer || typeof answer !== 'object' || Array.isArray(answer)) throw new AnswerGuardError('answer_invalid_shape', '模型回答必须是JSON对象');
  if (typeof answer.conclusion !== 'string' || !answer.conclusion.trim()) throw new AnswerGuardError('answer_missing_conclusion', '模型回答缺少结论');
  REQUIRED_ARRAYS.forEach(key => {
    if (!Array.isArray(answer[key])) throw new AnswerGuardError('answer_invalid_shape', `模型回答字段${key}必须是数组`);
    if (answer[key].length > 8) throw new AnswerGuardError('answer_too_long', `模型回答字段${key}超过8项`);
  });
  const serialized = JSON.stringify(answer);
  const forbidden = FORBIDDEN_PATTERNS.find(pattern => pattern.test(serialized));
  if (forbidden) throw new AnswerGuardError('answer_forbidden_claim', '模型回答包含风险分、违法责任或强制操船结论');

  const { evidenceIds, sourceIds } = referencedIds(packet);
  answer.currentEvidence.forEach(item => {
    if (!item || typeof item.evidenceId !== 'string' || !evidenceIds.has(item.evidenceId)) {
      throw new AnswerGuardError('answer_unknown_evidence', '模型回答引用了未提供的AIS证据');
    }
  });
  [...answer.applicableBasis, ...answer.sources].forEach(item => {
    if (!item || typeof item.sourceId !== 'string' || !sourceIds.has(item.sourceId)) {
      throw new AnswerGuardError('answer_unknown_source', '模型回答引用了未提供或未审核的来源');
    }
  });

  const allowedNumbers = numbers(JSON.stringify(packet));
  const unsupported = numbers(serialized).filter(value => !allowedNumbers.some(allowed => Math.abs(allowed - value) < 0.011));
  if (unsupported.length) throw new AnswerGuardError('answer_unsupported_number', `模型回答包含无证据数值: ${unsupported[0]}`);
  return answer;
}

module.exports = { AnswerGuardError, FORBIDDEN_PATTERNS, numbers, referencedIds, validateAnswer };
