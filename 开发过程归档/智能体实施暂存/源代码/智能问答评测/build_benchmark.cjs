'use strict';

const path = require('node:path');
const { buildBenchmark } = require('./benchmark_builder.cjs');

function argument(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : null;
}

const projectRoot = argument('--project-root');
const outputRoot = argument('--output');
const result = buildBenchmark({
  projectRoot: projectRoot ? path.resolve(projectRoot) : undefined,
  outputRoot: outputRoot ? path.resolve(outputRoot) : undefined
});

process.stdout.write(`${JSON.stringify({ outputRoot: result.outputRoot, cases: result.manifest.cases.length, status: result.manifest.status }, null, 2)}\n`);
