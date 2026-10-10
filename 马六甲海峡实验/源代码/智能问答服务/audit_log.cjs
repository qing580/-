'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function safeRecord(record) {
  const clone = JSON.parse(JSON.stringify(record));
  const serialized = JSON.stringify(clone);
  if (/sk-[a-z0-9_-]{8,}/i.test(serialized) || /authorization/i.test(serialized) || /deepseek_api_key/i.test(serialized)) {
    throw new Error('审计记录疑似包含密钥或Authorization信息');
  }
  return clone;
}

function createAuditLogger(root) {
  const auditRoot = path.resolve(root);
  function write(record) {
    fs.mkdirSync(auditRoot, { recursive: true });
    const auditId = record.auditId || `AQ-${new Date().toISOString().replace(/[-:.TZ]/g, '')}-${crypto.randomBytes(4).toString('hex')}`;
    const payload = safeRecord({ ...record, auditId });
    const file = path.join(auditRoot, `${new Date().toISOString().slice(0, 10)}.jsonl`);
    fs.appendFileSync(file, `${JSON.stringify(payload)}\n`, 'utf8');
    return { auditId, file };
  }
  return { write };
}

module.exports = { createAuditLogger, safeRecord };
