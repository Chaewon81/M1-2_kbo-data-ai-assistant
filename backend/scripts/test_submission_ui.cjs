// Targeted race guards and mobile stylesheet checks; not a browser E2E test.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/app.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../../frontend/style.css'), 'utf8');
const mobile = css.slice(css.lastIndexOf('@media(max-width:850px)'));
assert.match(mobile, /\.sidebar\{display:flex/);
assert.match(mobile, /\.conversation-delete\{opacity:1/);
assert.match(mobile, /\.app-shell\{flex-direction:column/);
const elements = { teamA: { value: 'KIA' }, predictionSeason: { value: '2026' }, pitcherA: {
  tagName: 'SELECT', innerHTML: '', appended: [], appendChild(item) { this.appended.push(item); }
} };
let firstResolve;
let calls = 0;
const context = vm.createContext({
  $: id => elements[id], API_BASE_URL: 'https://example.test', pitcherRequests: new Map(),
  document: { createElement: () => ({ dataset: {} }) },
  apiFetch: async () => {
    if (++calls === 1) return new Promise(resolve => { firstResolve = resolve; });
    return { json: async () => ({ items: [{ player: '최신 투수', player_id: '2', era: 2, whip: 1 }] }) };
  }
});
vm.runInContext(source.slice(source.indexOf('async function loadPitchers'), source.indexOf("$('chatForm')")), context);
(async () => {
  const stale = context.loadPitchers('pitcherA', 'teamA');
  elements.teamA.value = 'LG';
  await context.loadPitchers('pitcherA', 'teamA');
  firstResolve({ json: async () => ({ items: [{ player: '오래된 투수', player_id: '1', era: 3, whip: 1 }] }) });
  await stale;
  assert.deepEqual(elements.pitcherA.appended.map(x => x.value), ['최신 투수']);
  const loadContext = vm.createContext({ chatBusy: true });
  vm.runInContext(source.slice(source.indexOf('async function loadConversation'), source.indexOf('async function loadData')), loadContext);
  await assert.rejects(loadContext.loadConversation('id'), /답변 생성/);
  assert.match(source, /loadId !== conversationLoadRequest/);
  console.log('Submission UI checks: mobile access, stale pitcher response, Chat navigation guards PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
