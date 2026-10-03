// Small VM tests for real sync functions, not a browser/end-to-end test.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/app.js'), 'utf8');
const prefix = source.slice(0, source.indexOf('function showAiMode'));

function setup(fetch, shortTimeout = false) {
  const elements = Object.fromEntries(['syncStatus', 'syncDates', 'liveSummary', 'team', 'season', 'lastN', 'summaryContent'].map(id => [id, { value: '', textContent: '' }]));
  Object.assign(elements.team, { value: 'KIA' });
  Object.assign(elements.season, { value: '2026' });
  Object.assign(elements.lastN, { value: '10' });
  elements.summaryContent.textContent = 'saved conversation snapshot';
  let refreshes = 0;
  const context = vm.createContext({ document: { getElementById: id => elements[id] }, fetch,
    URLSearchParams, Date, Promise, Error, AbortController, Headers,
    setTimeout: (callback, delay) => setTimeout(callback, delay === 10000 ? 0 : shortTimeout ? 5 : delay), clearTimeout,
    loadData: () => { refreshes++; } });
  vm.runInContext(prefix + '\nconversationId = "saved"; globalThis.api = {requestGameSync, loadLiveSummary, fetchSyncJson};', context);
  return { context, elements, api: context.api, refreshes: () => refreshes };
}

const response = data => ({ ok: true, json: async () => data });
const summary = { count: 10, period: { from: '2026-09-12', to: '2026-09-30' }, metrics: { wins: 5, losses: 5, draws: 0, win_rate: 0.5 } };

(async () => {
  const requests = [];
  const state = setup(async (url, options) => {
    requests.push({url, options});
    if (url.endsWith('/api/sync')) return response({status: 'running', target_date: '2026-10-01'});
    if (url.endsWith('/api/sync/status')) return response({status: 'success', target_season: 2026, last_checked_date: '2026-10-01', latest_game_date: '2026-10-01'});
    return response(summary);
  });
  await Promise.all([state.api.requestGameSync(), state.api.requestGameSync()]);
  await state.api.loadLiveSummary();
  assert.equal(requests.filter(x => x.options?.method === 'POST').length, 1);
  assert.equal(state.refreshes(), 1);
  assert.equal(state.elements.summaryContent.textContent, 'saved conversation snapshot');
  assert.equal(vm.runInContext('conversationId', state.context), 'saved');
  assert(requests.every(x => !x.url.includes('/api/chat')));
  assert(state.elements.liveSummary.textContent.includes('50.0%'));
  assert(state.elements.syncDates.textContent.includes('수집 대상 시즌: 2026'));
  assert(state.elements.syncDates.textContent.includes('저장된 최신 완료 경기'));

  const failed = setup(async () => ({ok: false, json: async () => ({detail: 'quota'})}));
  await failed.api.requestGameSync();
  assert(failed.elements.syncStatus.textContent.includes('quota'));
  assert.equal(failed.elements.summaryContent.textContent, 'saved conversation snapshot');
  assert.equal(failed.refreshes(), 0);

  const disabled = setup(async () => response({status: 'disabled'}));
  await disabled.api.requestGameSync();
  assert(disabled.elements.syncStatus.textContent.includes('꺼짐'));
  assert.equal(disabled.refreshes(), 0);

  const hanging = setup(() => new Promise(() => {}));
  await assert.rejects(hanging.api.fetchSyncJson('/api/sync', {}, 5), /시간 초과/);
  const hangingBody = setup(async () => ({ok: true, json: () => new Promise(() => {})}));
  await assert.rejects(hangingBody.api.fetchSyncJson('/api/sync/status', {}, 5), /시간 초과/);

  const timeoutFlow = setup(() => new Promise(() => {}), true);
  await timeoutFlow.api.requestGameSync();
  assert.equal(vm.runInContext('syncBusy', timeoutFlow.context), false);
  assert(timeoutFlow.elements.syncStatus.textContent.includes('상태 확인 불가'));
  assert.equal(timeoutFlow.elements.summaryContent.textContent, 'saved conversation snapshot');

  const recoveryRequests = [];
  let broken = true;
  const recovery = setup(async (url, options) => {
    recoveryRequests.push({url, options});
    if (broken) throw new Error('network unavailable');
    if (url.endsWith('/api/sync/status')) return response({status: 'success', target_season: 2026});
    return response(summary);
  });
  await recovery.api.requestGameSync();
  assert.equal(vm.runInContext('syncBusy', recovery.context), false);
  assert(recovery.elements.syncStatus.textContent.includes('실패가 확정된 것은 아닙니다'));
  assert.equal(recovery.elements.summaryContent.textContent, 'saved conversation snapshot');
  broken = false;
  await recovery.api.requestGameSync();
  assert.equal(recoveryRequests.filter(x => x.options?.method === 'POST').length, 1);
  assert.equal(recoveryRequests.filter(x => x.url.endsWith('/api/sync/status')).length, 1);
  console.log('Frontend sync VM tests: 7 PASS (not browser E2E)');
})().catch(error => { console.error(error); process.exitCode = 1; });
