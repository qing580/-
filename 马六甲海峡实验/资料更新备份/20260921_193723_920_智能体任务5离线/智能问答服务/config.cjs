'use strict';

const path = require('node:path');

const SERVICE_VERSION = '0.2.0';

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
  const projectRoot = path.resolve(options.projectRoot || path.join(serviceDir, '..', '..'));
  const demoRoot = path.resolve(options.demoRoot || path.join(projectRoot, '网页演示', 'Demo网页'));
  return {
    serviceVersion: SERVICE_VERSION,
    host: '127.0.0.1',
    port: options.port ?? parsePort(options.argv, options.env),
    projectRoot,
    demoRoot,
    entryFile: '海上异常监测智能体.html',
    aisModuleDir: path.join(demoRoot, '用户端航行助手版'),
    aisDataFile: path.join(demoRoot, '用户端航行助手版', 'malacca_enhanced_ais_6h_demo_data.json'),
    knowledgeBaseRoot: path.resolve(options.knowledgeBaseRoot || path.join(projectRoot, '知识库资料')),
    deepseekConfigured: Boolean((options.env || process.env).DEEPSEEK_API_KEY),
    knowledgeBaseState: 'not_initialized'
  };
}

module.exports = { SERVICE_VERSION, parsePort, loadConfig };
