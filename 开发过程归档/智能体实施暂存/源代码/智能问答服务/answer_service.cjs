'use strict';

const { createDeepSeekClient, DeepSeekError } = require('./deepseek_client.cjs');
const { validateAnswer, AnswerGuardError } = require('./answer_guard.cjs');
const { createAuditLogger } = require('./audit_log.cjs');

const SYSTEM_PROMPT = `你是海上异常监测证据解释助手。只能依据用户消息中的evidencePacket回答，不使用未提供的常识补齐事实。输出一个JSON对象，字段固定为conclusion字符串，以及currentEvidence、applicableBasis、limitations、suggestedAttention、sources五个数组。currentEvidence每项必须包含evidenceId和statement；applicableBasis与sources每项必须包含sourceId，来源必须来自数据包。不得输出碰撞风险数值分，不认定违法或责任，不下达强制操船指令。证据不足时在conclusion明确写“证据不足”，并在limitations列出缺失项。`;

function compactContext(context) {
  if (!context) return null;
  return {
    query: context.query,
    dataset: context.dataset,
    vessel: context.vessel,
    currentObservation: context.currentObservation,
    trajectory: context.trajectory.slice(-12),
    neighbors: context.neighbors.slice(0, 5),
    events: context.events.slice(0, 3),
    quality: context.quality,
    evidenceGate: context.evidenceGate
  };
}

function createAnswerService(config, dependencies = {}) {
  const aisTools = dependencies.aisTools;
  const retriever = dependencies.retriever;
  const knowledgeGraph = dependencies.knowledgeGraph;
  const env = dependencies.env || process.env;
  const modelClient = dependencies.modelClient || createDeepSeekClient({ apiKey: env.DEEPSEEK_API_KEY, retries: 1 });
  const auditLogger = dependencies.auditLogger || createAuditLogger(config.auditRoot);

  async function ask(input = {}) {
    const question = String(input.question || '').trim();
    if (question.length < 2 || question.length > 300) throw Object.assign(new Error('问题长度必须在2至300字符之间'), { code: 'invalid_question', statusCode: 400 });
    const hasContext = input.mmsi !== undefined || input.time !== undefined;
    if (hasContext && (!input.mmsi || !input.time)) throw Object.assign(new Error('回放问答必须同时提供MMSI和时间'), { code: 'incomplete_context', statusCode: 400 });
    const context = hasContext ? aisTools.context(input.mmsi, input.time, { windowMinutes: input.windowMinutes }) : null;
    const retrieval = retriever.search(question, { limit: 4 });
    const graphTrace = context ? knowledgeGraph.trace(context, input.eventId) : null;
    const packet = { question, aisContext: compactContext(context), retrieval, graphTrace };
    const baseAudit = {
      createdAt: new Date().toISOString(),
      question,
      mode: config.onlineEnabled && config.deepseekConfigured ? 'deepseek_online' : 'local_evidence',
      mmsi: context?.vessel?.mmsi || null,
      replayTime: context?.query?.replayTime || null,
      evidenceIds: graphTrace?.evidence?.map(item => item.id) || [],
      sourceIds: [...new Set([...retrieval.map(item => item.sourceId), ...(graphTrace?.paths || []).map(item => item.claim.source.id)])]
    };
    if (!config.onlineEnabled || !config.deepseekConfigured) {
      const reason = !config.deepseekConfigured ? 'deepseek_key_not_configured' : 'online_mode_not_enabled';
      const audit = auditLogger.write({ ...baseAudit, status: 'local_evidence_only', reason });
      return { status: 'local_evidence_only', reason, auditId: audit.auditId, answer: null, evidencePacket: packet };
    }
    try {
      const response = await modelClient.complete([
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: JSON.stringify({ instruction: '请用中文解释问题并严格输出JSON。', evidencePacket: packet }) }
      ]);
      const answer = validateAnswer(response.content, packet);
      const audit = auditLogger.write({
        ...baseAudit,
        status: 'success',
        model: response.model,
        finishReason: response.finishReason,
        usage: response.usage,
        cost: response.cost,
        latencyMs: response.latencyMs,
        answer
      });
      return { status: 'success', auditId: audit.auditId, answer, model: response.model, usage: response.usage, cost: response.cost };
    } catch (error) {
      const status = error instanceof AnswerGuardError ? 'blocked_by_guard' : 'model_error';
      const audit = auditLogger.write({ ...baseAudit, status, errorCode: error.code || 'unknown_error' });
      if (error instanceof AnswerGuardError || error instanceof DeepSeekError) {
        return { status, auditId: audit.auditId, error: error.code, message: error.message, answer: null, evidencePacket: packet };
      }
      throw error;
    }
  }

  return { ask };
}

module.exports = { SYSTEM_PROMPT, compactContext, createAnswerService };
