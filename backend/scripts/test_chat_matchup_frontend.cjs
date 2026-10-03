// Summary renderer regression only; no browser, API, or AI calls.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../../frontend/app.js'), 'utf8');
const functions = source.slice(source.indexOf('function escapeHtml'), source.indexOf('function resetChat'));
const elements = { summaryPeriod: {}, summaryContent: {} };
const context = vm.createContext({ $: id => elements[id] });
vm.runInContext(functions, context);
context.showSummary({ count: 3, period: { from: '2026-09-01', to: '2026-09-02' },
  metrics: { wins: 1, losses: 1, draws: 1, win_rate: .5 },
  head_to_head: { team_a: 'LG', team_b: 'KIA' } });
assert.match(elements.summaryPeriod.textContent, /LG vs KIA.*시즌 상대전적.*3경기/);
context.showSummary({ count: 10, period: {}, metrics: {} });
assert.doesNotMatch(elements.summaryPeriod.textContent, /상대전적/);
context.showSummary({ count: 0, period: null });
assert.match(elements.summaryPeriod.textContent, /없습니다/);
console.log('Chat matchup Summary renderer: 3 checks PASS');
