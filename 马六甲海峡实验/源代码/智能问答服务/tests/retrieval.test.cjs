'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { createRetriever, markdownChunks, tokens } = require('../retrieval.cjs');

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'maritime-kb-'));
  fs.mkdirSync(path.join(root, '00_资料目录与来源登记'), { recursive: true });
  fs.mkdirSync(path.join(root, '01_资料'), { recursive: true });
  fs.writeFileSync(path.join(root, '01_资料', 'approved.md'), '# AIS限制\n\nAIS信息用于辅助态势感知，不能替代人工瞭望。', 'utf8');
  fs.writeFileSync(path.join(root, '01_资料', 'pending.md'), '# 未审核结论\n\n秘密测试材料不得被检索。', 'utf8');
  fs.writeFileSync(path.join(root, '00_资料目录与来源登记', '资料来源登记.json'), JSON.stringify([
    { id: 'KB-1', title: 'AIS指南', institution: '官方机构', reviewStatus: '已审核', sourceType: '官方指南', sourceUrl: 'https://example.test/1', version: '1', region: '国际', contentFile: '01_资料/approved.md' },
    { id: 'KB-2', title: '待核实资料', institution: '未知', reviewStatus: '待审核', sourceType: '网页', sourceUrl: 'https://example.test/2', version: '未知', region: '未知', contentFile: '01_资料/pending.md' }
  ], null, 2), 'utf8');
  return root;
}

test('tokenizer keeps latin terms and Chinese bigrams', () => {
  assert.ok(tokens('AIS 数据质量').includes('ais'));
  assert.ok(tokens('AIS 数据质量').includes('数据'));
});

test('markdown is split at headings with locators', () => {
  const chunks = markdownChunks('# A\nfirst\n## B\nsecond');
  assert.deepEqual(chunks.map(chunk => chunk.heading), ['A', 'B']);
});

test('only approved sources are indexed and returned', () => {
  const retriever = createRetriever({ knowledgeBaseRoot: fixture() });
  assert.deepEqual(retriever.status(), { state: 'ready', registeredSources: 2, approvedSources: 1, searchableChunks: 1 });
  const results = retriever.search('AIS能否替代人工瞭望');
  assert.equal(results[0].sourceId, 'KB-1');
  assert.equal(results.some(result => result.sourceId === 'KB-2'), false);
});

test('empty or oversized queries are rejected', () => {
  const retriever = createRetriever({ knowledgeBaseRoot: fixture() });
  assert.throws(() => retriever.search('a'));
  assert.throws(() => retriever.search('问'.repeat(301)));
});

test('project knowledge base returns reviewed official and experiment sources', () => {
  const knowledgeBaseRoot = path.resolve(__dirname, '..', '..', '..', '知识库资料');
  const retriever = createRetriever({ knowledgeBaseRoot });
  const status = retriever.status();
  assert.equal(status.state, 'ready');
  assert.equal(status.registeredSources, 7);
  assert.equal(status.approvedSources, 4);

  const collision = retriever.search('AIS能不能作为唯一避碰依据');
  assert.equal(collision[0].sourceId, 'KB-0001');
  assert.equal(collision[0].locator, 'AIS 与避碰决策');

  const straitrep = retriever.search('哪些船需要参加STRAITREP');
  assert.equal(straitrep[0].sourceId, 'KB-0003');
  assert.equal(straitrep[0].locator, '哪些船舶需要报告');

  const classification = retriever.search('目前船舶分类准确率怎么样');
  assert.equal(classification[0].sourceId, 'KB-0005');
  assert.equal(classification[0].locator, '独立日期分类检查');

  const allResults = [collision, straitrep, classification].flat();
  assert.equal(allResults.some(result => result.sourceId === 'KB-0004'), false);
});
