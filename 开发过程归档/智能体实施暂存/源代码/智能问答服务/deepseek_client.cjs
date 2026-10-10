'use strict';

const OFFICIAL_BASE_URL = 'https://api.deepseek.com';
const DEFAULT_MODEL = 'deepseek-flash';
const PRICING_SNAPSHOT = {
  checkedAt: '2026-09-21',
  currency: 'USD',
  perMillionTokens: {
    'deepseek-flash': {
      offPeak: { cacheHitInput: 0.003, cacheMissInput: 0.15, output: 0.6 },
      peak: { cacheHitInput: 0.006, cacheMissInput: 0.3, output: 1.2 }
    },
    'deepseek-v4-pro': {
      offPeak: { cacheHitInput: 0.022, cacheMissInput: 0.66, output: 1.98 },
      peak: { cacheHitInput: 0.044, cacheMissInput: 1.32, output: 3.96 }
    }
  }
};

class DeepSeekError extends Error {
  constructor(code, message, statusCode = 502) {
    super(message);
    this.name = 'DeepSeekError';
    this.code = code;
    this.statusCode = statusCode;
  }
}

function isPeakTime(dateValue = new Date()) {
  const date = new Date(dateValue);
  const day = date.getUTCDay();
  const hour = date.getUTCHours();
  return day >= 1 && day <= 5 && ((hour >= 1 && hour < 4) || (hour >= 6 && hour < 10));
}

function estimateCost(model, usage = {}, dateValue = new Date()) {
  const table = PRICING_SNAPSHOT.perMillionTokens[model];
  if (!table) return null;
  const band = isPeakTime(dateValue) ? 'peak' : 'offPeak';
  const rates = table[band];
  const hit = Number(usage.prompt_cache_hit_tokens ?? usage.prompt_tokens_details?.cached_tokens ?? 0) || 0;
  const prompt = Number(usage.prompt_tokens) || 0;
  const miss = Number(usage.prompt_cache_miss_tokens ?? Math.max(0, prompt - hit)) || 0;
  const output = Number(usage.completion_tokens) || 0;
  return {
    currency: 'USD',
    pricingCheckedAt: PRICING_SNAPSHOT.checkedAt,
    band,
    estimatedCost: (hit * rates.cacheHitInput + miss * rates.cacheMissInput + output * rates.output) / 1_000_000
  };
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function createDeepSeekClient(options = {}) {
  const apiKey = String(options.apiKey || '').trim();
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  const model = options.model || DEFAULT_MODEL;
  const timeoutMs = Math.max(1000, Math.min(60000, Number(options.timeoutMs) || 20000));
  const retries = Math.max(0, Math.min(1, Number(options.retries) || 0));
  if (!fetchImpl) throw new Error('当前Node环境不支持fetch');
  if (!PRICING_SNAPSHOT.perMillionTokens[model]) throw new Error(`不支持的DeepSeek模型: ${model}`);

  async function complete(messages) {
    if (!apiKey) throw new DeepSeekError('deepseek_key_missing', '未配置DeepSeek API Key', 503);
    const body = {
      model,
      messages,
      thinking: { type: 'disabled' },
      response_format: { type: 'json_object' },
      max_tokens: 1200,
      stream: false
    };
    let lastError;
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      const startedAt = Date.now();
      try {
        const response = await fetchImpl(`${OFFICIAL_BASE_URL}/chat/completions`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal
        });
        const text = await response.text();
        let payload;
        try { payload = JSON.parse(text); } catch (_error) { throw new DeepSeekError('deepseek_invalid_json', 'DeepSeek返回了无法解析的响应'); }
        if (!response.ok) {
          const retryable = response.status === 429 || response.status >= 500;
          const error = new DeepSeekError('deepseek_http_error', `DeepSeek请求失败（HTTP ${response.status}）`, response.status);
          if (!retryable || attempt >= retries) throw error;
          lastError = error;
          await wait(250 * (attempt + 1));
          continue;
        }
        const choice = payload.choices?.[0];
        if (!choice || typeof choice.message?.content !== 'string') throw new DeepSeekError('deepseek_response_invalid', 'DeepSeek响应缺少回答内容');
        return {
          model: payload.model || model,
          finishReason: choice.finish_reason || null,
          content: choice.message.content,
          usage: payload.usage || {},
          latencyMs: Date.now() - startedAt,
          cost: estimateCost(model, payload.usage || {})
        };
      } catch (error) {
        if (error.name === 'AbortError') lastError = new DeepSeekError('deepseek_timeout', `DeepSeek请求超过${timeoutMs}毫秒`, 504);
        else lastError = error instanceof DeepSeekError ? error : new DeepSeekError('deepseek_network_error', 'DeepSeek网络请求失败');
        if (attempt >= retries || !['deepseek_timeout', 'deepseek_network_error'].includes(lastError.code)) throw lastError;
        await wait(250 * (attempt + 1));
      } finally {
        clearTimeout(timer);
      }
    }
    throw lastError;
  }

  return { complete, model, timeoutMs, retries };
}

module.exports = { DEFAULT_MODEL, DeepSeekError, OFFICIAL_BASE_URL, PRICING_SNAPSHOT, createDeepSeekClient, estimateCost, isPeakTime };
