'use strict';

const fs = require('node:fs');
const path = require('node:path');

const REGISTRY_PATH = path.join('00_资料目录与来源登记', '资料来源登记.json');

function tokens(text) {
  const normalized = String(text || '').toLowerCase();
  const latin = normalized.match(/[a-z0-9][a-z0-9._/-]*/g) || [];
  const chinese = (normalized.match(/[\u3400-\u9fff]+/g) || []).flatMap(group => {
    if (group.length === 1) return [group];
    return Array.from({ length: group.length - 1 }, (_, index) => group.slice(index, index + 2));
  });
  return [...new Set([...latin, ...chinese])];
}

function markdownChunks(text) {
  const chunks = [];
  let heading = '正文';
  let lines = [];
  const flush = () => {
    const content = lines.join('\n').trim();
    if (content) chunks.push({ heading, content });
    lines = [];
  };
  String(text || '').split(/\r?\n/).forEach(line => {
    const match = line.match(/^#{1,4}\s+(.+)$/);
    if (match) {
      flush();
      heading = match[1].trim();
    } else {
      lines.push(line);
    }
  });
  flush();
  return chunks;
}

function createRetriever(config) {
  let cache = null;

  function buildIndex() {
    const registryFile = path.join(config.knowledgeBaseRoot, REGISTRY_PATH);
    if (!fs.existsSync(registryFile)) return { registryFile, records: [], chunks: [] };
    const records = JSON.parse(fs.readFileSync(registryFile, 'utf8'));
    if (!Array.isArray(records)) throw new Error('资料来源登记.json必须是数组');
    const approved = records.filter(record => record.reviewStatus === '已审核');
    const chunks = [];
    approved.forEach(record => {
      const contentFile = path.resolve(config.knowledgeBaseRoot, record.contentFile || '');
      const rootPrefix = `${path.resolve(config.knowledgeBaseRoot)}${path.sep}`;
      if (!contentFile.startsWith(rootPrefix) || !fs.existsSync(contentFile)) return;
      markdownChunks(fs.readFileSync(contentFile, 'utf8')).forEach((chunk, index) => {
        const searchable = `${record.title} ${record.institution} ${record.keywords || ''} ${chunk.heading} ${chunk.content}`;
        chunks.push({ record, index, ...chunk, tokenSet: new Set(tokens(searchable)) });
      });
    });
    return { registryFile, records, chunks };
  }

  function index() {
    if (!cache) cache = buildIndex();
    return cache;
  }

  function refresh() {
    cache = buildIndex();
    return status();
  }

  function status() {
    const state = index();
    return {
      state: state.chunks.length ? 'ready' : 'not_initialized',
      registeredSources: state.records.length,
      approvedSources: state.records.filter(record => record.reviewStatus === '已审核').length,
      searchableChunks: state.chunks.length
    };
  }

  function search(query, options = {}) {
    const queryText = String(query || '').trim();
    if (queryText.length < 2 || queryText.length > 300) throw new Error('检索问题长度必须在2至300字符之间');
    const queryTokens = tokens(queryText);
    const limit = Math.max(1, Math.min(8, Number(options.limit) || 5));
    const results = index().chunks.map(chunk => {
      const overlap = queryTokens.reduce((sum, token) => sum + (chunk.tokenSet.has(token) ? 1 : 0), 0);
      const exact = chunk.content.toLowerCase().includes(queryText.toLowerCase()) ? 4 : 0;
      const titleMatch = tokens(chunk.record.title).some(token => queryTokens.includes(token)) ? 1.5 : 0;
      return { chunk, score: overlap + exact + titleMatch };
    }).filter(item => item.score > 0)
      .sort((first, second) => second.score - first.score || first.chunk.record.id.localeCompare(second.chunk.record.id) || first.chunk.index - second.chunk.index)
      .slice(0, limit);
    return results.map(item => ({
      sourceId: item.chunk.record.id,
      title: item.chunk.record.title,
      institution: item.chunk.record.institution,
      sourceType: item.chunk.record.sourceType,
      sourceUrl: item.chunk.record.sourceUrl,
      version: item.chunk.record.version,
      region: item.chunk.record.region,
      reviewStatus: item.chunk.record.reviewStatus,
      locator: item.chunk.heading,
      excerpt: item.chunk.content.slice(0, 900),
      retrievalScore: item.score
    }));
  }

  return { refresh, search, status };
}

module.exports = { REGISTRY_PATH, createRetriever, markdownChunks, tokens };
