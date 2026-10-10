'use strict';

const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { loadConfig } = require('./config.cjs');
const { AisToolError, createAisTools } = require('./ais_tools.cjs');
const { createRetriever } = require('./retrieval.cjs');

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
  return function requestHandler(request, response) {
    const requestUrl = new URL(request.url, `http://${config.host}`);
    if (requestUrl.pathname === '/api/health') {
      if (request.method !== 'GET') {
        sendJson(response, 405, { error: 'method_not_allowed' });
        return;
      }
      sendJson(response, 200, {
        status: 'ok',
        serviceVersion: config.serviceVersion,
        mode: config.deepseekConfigured ? 'online_ready' : 'local_evidence',
        deepseekConfigured: config.deepseekConfigured,
        knowledgeBaseState: retriever.status().state
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
  return { config, server: http.createServer(createRequestHandler(config, options.services)) };
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

module.exports = { createAppServer, createRequestHandler, safeStaticPath };
