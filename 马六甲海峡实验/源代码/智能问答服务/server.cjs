'use strict';

const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { loadConfig } = require('./config.cjs');
const { AisToolError, createAisTools } = require('./ais_tools.cjs');
const { createRetriever } = require('./retrieval.cjs');
const { createKnowledgeGraph, KnowledgeGraphError } = require('./knowledge_graph.cjs');
const { createAnswerService } = require('./answer_service.cjs');
const { AuditQueryError, createAuditStore } = require('./audit_store.cjs');

const MIME_TYPES = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2'
};

function sendJson(response, statusCode, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': body.length,
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff'
  });
  response.end(body);
}

function sendJsonDownload(response, filename, payload) {
  const body = Buffer.from(JSON.stringify(payload, null, 2));
  response.writeHead(200, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': body.length,
    'Content-Disposition': `attachment; filename="${filename}"`,
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff'
  });
  response.end(body);
}

function readJsonBody(request, maximumBytes = 65536) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    request.on('data', chunk => {
      size += chunk.length;
      if (size > maximumBytes) {
        reject(Object.assign(new Error('请求体超过64KB'), { code: 'request_too_large', statusCode: 413 }));
        request.destroy();
        return;
      }
      chunks.push(chunk);
    });
    request.on('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}')); }
      catch (_error) { reject(Object.assign(new Error('请求体必须是有效JSON'), { code: 'invalid_json', statusCode: 400 })); }
    });
    request.on('error', reject);
  });
}

function safeStaticPath(demoRoot, requestPath, entryFile) {
  let decoded;
  try {
    decoded = decodeURIComponent(requestPath);
  } catch (_error) {
    return null;
  }
  const relative = decoded === '/' ? entryFile : decoded.replace(/^\/+/, '');
  const target = path.resolve(demoRoot, relative);
  const rootPrefix = `${path.resolve(demoRoot)}${path.sep}`;
  return target === path.resolve(demoRoot) || target.startsWith(rootPrefix) ? target : null;
}

function createRequestHandler(config, services = {}) {
  const aisTools = services.aisTools || createAisTools(config);
  const retriever = services.retriever || createRetriever(config);
  const knowledgeGraph = services.knowledgeGraph || createKnowledgeGraph(config);
  const answerService = services.answerService || createAnswerService(config, {
    aisTools,
    retriever,
    knowledgeGraph,
    env: services.env || process.env,
    modelClient: services.modelClient,
    auditLogger: services.auditLogger
  });
  const auditStore = services.auditStore || createAuditStore(config.auditRoot);
  return async function requestHandler(request, response) {
    const requestUrl = new URL(request.url, `http://${config.host}`);
    if (requestUrl.pathname === '/api/health') {
      if (request.method !== 'GET') {
        sendJson(response, 405, { error: 'method_not_allowed' });
        return;
      }
      sendJson(response, 200, {
        status: 'ok',
        serviceVersion: config.serviceVersion,
        mode: config.deepseekConfigured ? (config.onlineEnabled ? 'online_ready' : 'online_locked') : 'local_evidence',
        deepseekConfigured: config.deepseekConfigured,
        onlineEnabled: config.onlineEnabled,
        deepseekModel: config.deepseekModel,
        knowledgeBaseState: retriever.status().state,
        knowledgeGraphState: knowledgeGraph.status().state
      });
      return;
    }

    if (requestUrl.pathname === '/api/ais/metadata') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        sendJson(response, 200, aisTools.metadata());
      } catch (error) {
        sendJson(response, error.statusCode || 500, { error: error.code || 'ais_tool_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname === '/api/ais/context') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        const payload = aisTools.context(requestUrl.searchParams.get('mmsi'), requestUrl.searchParams.get('time'), {
          windowMinutes: requestUrl.searchParams.get('windowMinutes')
        });
        sendJson(response, 200, payload);
      } catch (error) {
        const statusCode = error instanceof AisToolError ? error.statusCode : 500;
        sendJson(response, statusCode, { error: error.code || 'ais_tool_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname === '/api/kb/status') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      sendJson(response, 200, retriever.status());
      return;
    }

    if (requestUrl.pathname === '/api/kb/search') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        sendJson(response, 200, { query: requestUrl.searchParams.get('q') || '', results: retriever.search(requestUrl.searchParams.get('q')) });
      } catch (error) {
        sendJson(response, 400, { error: 'invalid_query', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname === '/api/graph/status') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      sendJson(response, 200, knowledgeGraph.status());
      return;
    }

    if (requestUrl.pathname === '/api/graph/topic') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        sendJson(response, 200, knowledgeGraph.topic(requestUrl.searchParams.get('topic')));
      } catch (error) {
        const statusCode = error instanceof KnowledgeGraphError ? error.statusCode : 500;
        sendJson(response, statusCode, { error: error.code || 'knowledge_graph_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname === '/api/graph/trace') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        const context = aisTools.context(requestUrl.searchParams.get('mmsi'), requestUrl.searchParams.get('time'), {
          windowMinutes: requestUrl.searchParams.get('windowMinutes')
        });
        sendJson(response, 200, knowledgeGraph.trace(context, requestUrl.searchParams.get('eventId')));
      } catch (error) {
        const statusCode = error instanceof AisToolError || error instanceof KnowledgeGraphError ? error.statusCode : 500;
        sendJson(response, statusCode, { error: error.code || 'knowledge_graph_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname === '/api/ask') {
      if (request.method !== 'POST') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        const input = await readJsonBody(request);
        sendJson(response, 200, await answerService.ask(input));
      } catch (error) {
        sendJson(response, error.statusCode || 500, { error: error.code || 'answer_service_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname === '/api/audits') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        sendJson(response, 200, auditStore.list({
          status: requestUrl.searchParams.get('status'),
          mode: requestUrl.searchParams.get('mode'),
          q: requestUrl.searchParams.get('q')
        }));
      } catch (error) {
        const statusCode = error instanceof AuditQueryError ? error.statusCode : 500;
        sendJson(response, statusCode, { error: error.code || 'audit_query_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname === '/api/audits/export') {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        const payload = auditStore.exportRecords({
          status: requestUrl.searchParams.get('status'),
          mode: requestUrl.searchParams.get('mode'),
          q: requestUrl.searchParams.get('q')
        });
        sendJsonDownload(response, `maritime-agent-audits-${new Date().toISOString().slice(0, 10)}.json`, payload);
      } catch (error) {
        const statusCode = error instanceof AuditQueryError ? error.statusCode : 500;
        sendJson(response, statusCode, { error: error.code || 'audit_export_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname.startsWith('/api/audits/')) {
      if (request.method !== 'GET') return sendJson(response, 405, { error: 'method_not_allowed' });
      try {
        const encodedId = requestUrl.pathname.slice('/api/audits/'.length);
        const auditId = decodeURIComponent(encodedId);
        sendJson(response, 200, auditStore.detail(auditId));
      } catch (error) {
        const statusCode = error instanceof AuditQueryError || error instanceof URIError ? (error.statusCode || 400) : 500;
        sendJson(response, statusCode, { error: error.code || 'audit_query_error', message: error.message });
      }
      return;
    }

    if (requestUrl.pathname.startsWith('/api/')) {
      sendJson(response, 404, { error: 'api_not_found' });
      return;
    }

    if (!['GET', 'HEAD'].includes(request.method)) {
      sendJson(response, 405, { error: 'method_not_allowed' });
      return;
    }

    const target = safeStaticPath(config.demoRoot, requestUrl.pathname, config.entryFile);
    if (!target) {
      sendJson(response, 403, { error: 'forbidden_path' });
      return;
    }

    fs.stat(target, (statError, stats) => {
      if (statError || !stats.isFile()) {
        sendJson(response, 404, { error: 'file_not_found' });
        return;
      }
      response.writeHead(200, {
        'Content-Type': MIME_TYPES[path.extname(target).toLowerCase()] || 'application/octet-stream',
        'Content-Length': stats.size,
        'Cache-Control': 'no-cache',
        'X-Content-Type-Options': 'nosniff'
      });
      if (request.method === 'HEAD') {
        response.end();
        return;
      }
      fs.createReadStream(target).pipe(response);
    });
  };
}

function createAppServer(options = {}) {
  const config = loadConfig(options);
  return { config, server: http.createServer(createRequestHandler(config, { ...(options.services || {}), env: options.env || process.env })) };
}

function startFromCommandLine() {
  const { config, server } = createAppServer();
  server.listen(config.port, config.host, () => {
    const address = server.address();
    process.stdout.write(`Maritime agent local service listening on http://${config.host}:${address.port}\n`);
  });
  const shutdown = () => server.close(() => process.exit(0));
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);
}

if (require.main === module) startFromCommandLine();

module.exports = { createAppServer, createRequestHandler, readJsonBody, safeStaticPath, sendJsonDownload };
