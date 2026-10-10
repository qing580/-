'use strict';

const path = require('node:path');

const SERVICE_VERSION = '0.1.0';

function parsePort(argv = process.argv.slice(2), env = process.env) {
  const index = argv.indexOf('--port');
  const raw = index >= 0 ? argv[index + 1] : env.MARITIME_AGENT_PORT;
  const port = Number(raw || 8765);
  if (!Number.isInteger(port) || port < 0 || port > 65535) {
    throw new Error(`Invalid port: ${raw}`);
  }
  return port;
}

function loadConfig(options = {}) {
  const serviceDir = options.serviceDir || __dirname;
  return {
    serviceVersion: SERVICE_VERSION,
    host: '127.0.0.1',
    port: options.port ?? parsePort(options.argv, options.env),
    demoRoot: path.resolve(options.demoRoot || path.join(serviceDir, '..', '..', '网页演示', 'Demo网页')),
    entryFile: '海上异常监测智能体.html',
    deepseekConfigured: Boolean((options.env || process.env).DEEPSEEK_API_KEY),
    knowledgeBaseState: 'not_initialized'
  };
}

module.exports = { SERVICE_VERSION, parsePort, loadConfig };
