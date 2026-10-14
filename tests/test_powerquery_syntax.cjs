#!/usr/bin/env node
'use strict';

/**
 * Parse the delivered Power Query M with Microsoft's actual open-source parser.
 * This checks syntax only: it does not evaluate M, compile DAX, refresh data,
 * render report visuals or serialize a PBIX file.
 *
 * Reproduce with Node.js 22 or later, from the project directory:
 *   npm install --no-save @microsoft/powerquery-parser@2.0.0
 *   node tests/test_powerquery_syntax.cjs
 *
 * Node's standard module resolver also honors NODE_PATH. If the package is
 * installed outside the project, set NODE_PATH to that node_modules directory.
 * Example for PowerShell:
 *   $env:NODE_PATH = 'C:\tools\powerquery-check\node_modules'
 *   node tests/test_powerquery_syntax.cjs
 *
 * API reference: https://github.com/microsoft/powerquery-parser
 * TaskUtils.tryLexParse(DefaultSettings, text) parses the unmodified queries.
 */

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const project = path.resolve(__dirname, '..');
const output = path.join(project, 'reports', 'powerquery_syntax_validation.json');
const digest = text => crypto.createHash('sha256').update(text, 'utf8').digest('hex');
const report = {
  status: 'FAIL',
  checked_at_utc: new Date().toISOString(),
  scope: 'Power Query M lexical and syntax parsing only; no M evaluation or native Power BI engine execution.',
  parser_package: '@microsoft/powerquery-parser',
  parser_version: null,
  node_version: process.version,
  parser_api: 'TaskUtils.tryLexParse(DefaultSettings, query)',
  parser_reference: 'https://github.com/microsoft/powerquery-parser',
  queries: [],
  negative_control: null,
  limitations: [
    'M library function resolution, data types and query evaluation are not tested by a syntax parser.',
    'DAX evaluation, Power BI Desktop opening, rendering and PBIX saving are not tested here.'
  ]
};

async function main() {
  let parser;
  try {
    parser = require('@microsoft/powerquery-parser');
    report.parser_version = require('@microsoft/powerquery-parser/package.json').version;
  } catch (error) {
    throw new Error('Microsoft Power Query parser is unavailable. Run npm install --no-save @microsoft/powerquery-parser@2.0.0, or set NODE_PATH to its node_modules directory. ' + error.message);
  }

  const modelRelative = 'powerbi/IRCTC.SemanticModel/model.bim';
  const modelText = fs.readFileSync(path.join(project, modelRelative), 'utf8');
  const model = JSON.parse(modelText);
  report.model_sha256 = digest(modelText);
  const queries = [];

  for (const tableName of ['Bookings', 'DimDate']) {
    const table = model.model.tables.find(item => item.name === tableName);
    if (!table || table.partitions.length !== 1) {
      throw new Error('Expected one embedded M partition on ' + tableName);
    }
    const partition = table.partitions[0];
    if (partition.source.type !== 'm') {
      throw new Error('Expected an M source on ' + tableName);
    }
    const expression = partition.source.expression;
    queries.push({
      name: 'Native model / ' + tableName,
      source_file: modelRelative,
      table: tableName,
      partition: partition.name,
      text: Array.isArray(expression) ? expression.join('\n') : expression
    });
  }

  const manualRelative = 'powerbi/Import_Bookings.pq';
  queries.push({
    name: 'Manual CSV import / Import_Bookings.pq',
    source_file: manualRelative,
    text: fs.readFileSync(path.join(project, manualRelative), 'utf8')
  });

  for (const query of queries) {
    if (typeof query.text !== 'string' || !query.text.trim()) {
      throw new Error('Empty or malformed query source: ' + query.name);
    }
    const task = await parser.TaskUtils.tryLexParse(parser.DefaultSettings, query.text);
    const passed = parser.TaskUtils.isParseStageOk(task);
    const result = {
      name: query.name,
      source_file: query.source_file,
      ...(query.table ? { table: query.table, partition: query.partition } : {}),
      query_sha256: digest(query.text),
      query_utf8_bytes: Buffer.byteLength(query.text, 'utf8'),
      parser_stage: task.stage,
      parser_result_kind: task.resultKind,
      status: passed ? 'PASS' : 'FAIL'
    };
    if (!passed) {
      result.error = task.error?.message || String(task.error);
    }
    report.queries.push(result);
  }

  const invalidM = 'let x = in x';
  const negative = await parser.TaskUtils.tryLexParse(parser.DefaultSettings, invalidM);
  const rejected = parser.TaskUtils.isError(negative);
  report.negative_control = {
    name: 'Missing expression in let binding',
    input: invalidM,
    query_sha256: digest(invalidM),
    expected_result: 'Parser error',
    parser_stage: negative.stage,
    parser_result_kind: negative.resultKind,
    rejected_as_expected: rejected,
    status: rejected ? 'PASS' : 'FAIL'
  };
  if (rejected) {
    report.negative_control.error = negative.error?.message || String(negative.error);
  }

  report.status = report.queries.length === 3 && report.queries.every(query => query.status === 'PASS') && rejected ? 'PASS' : 'FAIL';
}

main().catch(error => {
  report.status = 'FAIL';
  report.execution_error = error.message;
}).finally(() => {
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n', 'utf8');
  console.log(JSON.stringify({
    status: report.status,
    parser: report.parser_package,
    version: report.parser_version,
    queries: report.queries.map(query => ({ name: query.name, status: query.status })),
    negative_control: report.negative_control?.status || 'NOT RUN',
    ...(report.execution_error ? { error: report.execution_error } : {}),
    report: 'reports/powerquery_syntax_validation.json'
  }, null, 2));
  process.exitCode = report.status === 'PASS' ? 0 : 1;
});
