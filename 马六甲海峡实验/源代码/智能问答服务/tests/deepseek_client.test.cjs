'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { createDeepSeekClient, estimateCost, isPeakTime, OFFICIAL_BASE_URL } = require('../deepseek_client.cjs');

test('DeepSeek client uses current official endpoint and flash model', async () => {
  let request;
  const fetchImpl = async (url, options) => {
    request = { url, options, body: JSON.parse(options.body) };
    return new Response(JSON.stringify({
      model: 'deepseek-flash',
      choices: [{ finish_reason: 'stop', message: { content: '{"ok":true}' } }],
      usage: { prompt_tokens: 100, prompt_cache_hit_tokens: 20, prompt_cache_miss_tokens: 80, completion_tokens: 10 }
    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  const client = createDeepSeekClient({ apiKey: 'test-key', fetchImpl, retries: 0 });
  const response = await client.complete([{ role: 'user', content: 'test' }]);
  assert.equal(request.url, `${OFFICIAL_BASE_URL}/chat/completions`);
  assert.equal(request.body.model, 'deepseek-flash');
  assert.deepEqual(request.body.thinking, { type: 'disabled' });
  assert.deepEqual(request.body.response_format, { type: 'json_object' });
  assert.equal(response.model, 'deepseek-flash');
});

test('DeepSeek client refuses calls without a key', async () => {
  const client = createDeepSeekClient({ apiKey: '', fetchImpl: async () => { throw new Error('must not call'); } });
  await assert.rejects(() => client.complete([{ role: 'user', content: 'test' }]), error => error.code === 'deepseek_key_missing');
});

test('price estimate distinguishes official peak and off-peak bands', () => {
  assert.equal(isPeakTime('2026-09-21T02:00:00Z'), true);
  assert.equal(isPeakTime('2026-09-20T02:00:00Z'), false);
  const usage = { prompt_tokens: 1000, prompt_cache_hit_tokens: 400, prompt_cache_miss_tokens: 600, completion_tokens: 100 };
  const peak = estimateCost('deepseek-flash', usage, '2026-09-21T02:00:00Z');
  const offPeak = estimateCost('deepseek-flash', usage, '2026-09-20T02:00:00Z');
  assert.equal(peak.band, 'peak');
  assert.ok(peak.estimatedCost > offPeak.estimatedCost);
});
