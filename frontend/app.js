const API_BASE_URL = (globalThis.KBO_CONFIG?.apiBaseUrl || 'http://127.0.0.1:8000').replace(/\/$/, '');
let demoAccessKey = '';
try { demoAccessKey = sessionStorage.getItem('kbo-demo-key') || ''; } catch (_) {}

async function apiFetch(url, options = {}) {
  if (globalThis.KBO_CONFIG?.requireAccess && !demoAccessKey) {
    throw new Error('상단에서 시연 접근 키를 입력해주세요.');
  }
  const headers = new Headers(options.headers || {});
  if (demoAccessKey) headers.set('X-Demo-Key', demoAccessKey);
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) throw new Error('시연 접근 키가 없거나 올바르지 않습니다.');
  return response;
}
let conversationId = null;
const $ = (id) => document.getElementById(id);
let chatBusy = false;
let syncBusy = false;
let liveSummaryRequest = 0;
let syncStatusUnknown = false;

async function fetchSyncJson(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  let timer;
  try {
    return await Promise.race([
      (async () => {
        const response = await apiFetch(url, { ...options, signal: controller.signal });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || '갱신 상태 조회 실패');
        return data;
      })(),
      new Promise((_, reject) => {
        timer = setTimeout(() => {
          const error = new Error('서버 작업 상태 확인 불가: 요청 시간 초과');
          error.name = 'SyncTimeout';
          reject(error);
          controller.abort();
        }, timeoutMs);
      })
    ]);
  } finally { clearTimeout(timer); }
}

function renderSyncState(state) {
  const labels = { disabled: '개발 모드: 자동 갱신 꺼짐', idle: '아직 자동 갱신하지 않았습니다.',
    running: '공식 경기 데이터를 갱신 중입니다. 현재 저장 데이터를 먼저 보여드립니다.',
    success: '최근 갱신 성공 (공식 기록의 반영 지연 가능)',
    failed: '갱신 실패: 기존 데이터를 사용합니다.', stale: '이전 갱신 중단: 다시 새로고침하세요.' };
  $('syncStatus').textContent = `${labels[state.status] || '갱신 상태 확인 중'}${state.error ? ` ${state.error}` : ''}`;
  const lastSuccess = state.last_success_at ? new Date(state.last_success_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '없음';
  const targetSeason = state.target_season || state.target_date?.slice(0, 4) || '미확인';
  $('syncDates').textContent = `수집 대상 시즌: ${targetSeason} · 마지막 갱신 성공(KST): ${lastSuccess} · 성공한 수집 기준일: ${state.last_checked_date || '없음'} · 저장된 최신 완료 경기: ${state.latest_game_date || '미확인'}${state.status === 'running' ? ` · 이번 확인 대상: ${state.target_date || '-'}` : ''}`;
}

async function loadLiveSummary() {
  const version = ++liveSummaryRequest;
  const params = new URLSearchParams({ team: $('team').value, season: $('season').value, last_n: $('lastN').value });
  try {
    const r = await apiFetch(`${API_BASE_URL}/api/data/summary?${params}`);
    if (!r.ok) throw new Error();
    const s = await r.json();
    if (version !== liveSummaryRequest) return;
    const m = s.metrics || {};
    const rate = m.win_rate == null ? '산정 불가' : `${(m.win_rate * 100).toFixed(1)}%`;
    $('liveSummary').textContent = s.count ? `현재 ${params.get('team')} · ${params.get('season')} · ${s.period?.from || '-'} ~ ${s.period?.to || '-'} · ${m.wins}승 ${m.losses}패 ${m.draws}무 · 승률 ${rate}` : '현재 조건의 완료 경기 데이터가 없습니다.';
  } catch (_) { if (version === liveSummaryRequest) $('liveSummary').textContent = '현재 요약 조회 실패. 저장된 대화는 변경하지 않습니다.'; }
}

async function requestGameSync() {
  if (syncBusy) return;
  syncBusy = true;
  try {
    // After an uncertain request, inspect the existing job without another POST.
    let state = syncStatusUnknown
      ? await fetchSyncJson(`${API_BASE_URL}/api/sync/status`)
      : await fetchSyncJson(`${API_BASE_URL}/api/sync`, { method: 'POST' });
    syncStatusUnknown = false;
    renderSyncState(state);
    let attempts = 0;
    while (state.status === 'running' && attempts++ < 30) {
      await new Promise((resolve) => setTimeout(resolve, 10000));
      state = await fetchSyncJson(`${API_BASE_URL}/api/sync/status`);
      renderSyncState(state);
    }
    if (state.status === 'running') {
      syncStatusUnknown = true;
      $('syncStatus').textContent = '갱신이 계속 진행 중입니다. 데이터 새로고침으로 상태를 다시 확인하세요.';
    }
    if (state.status === 'success' || state.status === 'failed') {
      // Live state only. Never replace the Summary in an opened/saved conversation.
      loadData();
      loadLiveSummary();
    }
  } catch (error) {
    syncStatusUnknown = true;
    $('syncStatus').textContent = `서버 작업 상태 확인 불가: ${error.message}. 서버 갱신 실패가 확정된 것은 아닙니다. 기존 데이터를 사용하며 데이터 새로고침으로 상태를 다시 확인하세요.`;
  }
  finally { syncBusy = false; }
}

function showAiMode(model, provider = '', configured = true) {
  const mock = model === 'mock';
  $('modeLabel').textContent = mock ? '개발용 Mock 모드' : `${provider || 'AI'} · ${model}${configured ? ' (연결 확인 전)' : ' · API 키 미설정'}`;
  const heading = document.querySelector('.chat-panel .panel-heading');
  heading.querySelector('.badge').textContent = mock ? 'MOCK' : 'AI';
  heading.querySelector('p').textContent = mock ? '실제 AI 호출 없이 흐름을 테스트합니다.' : `선택한 경기 Summary를 ${model}에 전달합니다.`;
}

async function loadAiStatus() {
  try {
    const response = await apiFetch(`${API_BASE_URL}/api/chat/status`);
    if (!response.ok) throw new Error();
    const data = await response.json();
    showAiMode(data.model, data.provider, data.configured);
  } catch (_) { $('modeLabel').textContent = 'AI 설정 상태 확인 실패'; }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
}

function addMessage(text, role) {
  const el = document.createElement('div');
  el.className = `message ${role}`;
  el.innerHTML = `<span>${escapeHtml(text).replace(/\n/g, '<br>')}</span>`;
  $('chatMessages').appendChild(el);
  $('chatMessages').scrollTop = $('chatMessages').scrollHeight;
}

function showSummary(summary) {
  if (!summary || !summary.count) {
    $('summaryPeriod').textContent = '조회된 경기 데이터가 없습니다.';
    $('summaryContent').innerHTML = '<div class="summary-empty">선택한 조건의 완료 경기 데이터가 없습니다.</div>';
    return;
  }
  const m = summary.metrics || {};
  const recent = summary.recent || {};
  const p = summary.period || {};
  const matchup = summary.head_to_head;
  $('summaryPeriod').textContent = `${matchup ? `${matchup.team_a} vs ${matchup.team_b} · 시즌 상대전적 · ` : ''}${p.from || '-'} ~ ${p.to || '-'} · ${summary.count}경기`;
  $('summaryContent').innerHTML = `<div class="summary-grid"><div class="stat"><small>승률</small><strong>${((m.win_rate || 0) * 100).toFixed(1)}%</strong></div><div class="stat"><small>평균 득실차</small><strong>${m.average_run_diff ?? 0}</strong></div><div class="stat"><small>승 / 패 / 무</small><strong>${m.wins || 0} / ${m.losses || 0} / ${m.draws || 0}</strong></div><div class="stat"><small>최근 ${recent.window || 0}경기</small><strong>${((recent.win_rate || 0) * 100).toFixed(1)}%</strong></div></div><p class="trend">현재 추세: ${escapeHtml(summary.trend || '확인 불가')}</p>`;
}

function resetChat() {
  if (chatBusy) return;
  conversationId = null;
  $('chatMessages').innerHTML = '<div class="welcome-message"><div><strong>안녕하세요! KBO AI입니다.</strong><p>팀과 시즌을 선택하고 궁금한 점을 질문해보세요.</p></div></div>';
  $('summaryPeriod').textContent = '질문을 보내면 Summary가 표시됩니다.';
  $('summaryContent').innerHTML = '<div class="summary-empty">아직 분석 데이터가 없습니다.</div>';
}

async function loadConversations() {
  try {
    const r = await apiFetch(`${API_BASE_URL}/api/conversations`);
    const data = await r.json();
    $('conversationList').innerHTML = data.items?.length ? data.items.map((x) => `<div class="conversation-item" data-id="${escapeHtml(x.id)}"><span class="conversation-title">${escapeHtml(x.title)}</span><button class="conversation-delete" data-id="${escapeHtml(x.id)}" type="button">×</button></div>`).join('') : '<p class="muted">아직 저장된 대화가 없습니다.</p>';
  } catch (_) { $('conversationList').innerHTML = '<p class="muted">API 서버를 확인해주세요.</p>'; }
}

async function loadConversation(id) {
  const r = await apiFetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(id)}`);
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || '대화를 불러오지 못했습니다.');
  conversationId = data.id;
  $('chatMessages').innerHTML = '';
  (data.messages || []).forEach((m) => addMessage(m.content, m.role));
  if (data.summary) showSummary(data.summary);
  else $('summaryContent').innerHTML = '<div class="summary-empty">이 대화에는 저장된 Summary가 없습니다.</div>';
}

async function loadData() {
  try {
    const r = await apiFetch(`${API_BASE_URL}/api/data?limit=20`);
    const data = await r.json();
    $('dataRows').innerHTML = (data.items || []).map((item) => `<tr><td>${item.date}</td><td>${escapeHtml(item.team)}</td><td>${escapeHtml(item.opponent)}</td><td>${item.runs_for} : ${item.runs_against}</td><td>${item.result}</td><td><span class="source-badge ${item.is_manual ? 'manual' : 'kbo'}">${item.is_manual ? '사용자 수정' : 'KBO 수집'}</span></td><td><button class="delete-btn" data-id="${encodeURIComponent(item.id)}">삭제</button></td></tr>`).join('') || '<tr><td colspan="7" class="table-empty">데이터가 없습니다.</td></tr>';
  } catch (_) { $('dataRows').innerHTML = '<tr><td colspan="7" class="table-empty">API 서버를 확인해주세요.</td></tr>'; }
}

async function loadPitchers(selectId, teamId) {
  const old = $(selectId);
  if (!old) return;
  const select = old.tagName === 'SELECT' ? old : Object.assign(document.createElement('select'), { id: selectId });
  if (old !== select) old.replaceWith(select);
  select.innerHTML = '<option value="">투수 선택 안 함</option>';
  try {
    const season = $('predictionSeason').value;
    const team = $(teamId).value;
    const r = await apiFetch(`${API_BASE_URL}/api/pitchers?season=${season}&team=${encodeURIComponent(team)}`);
    const data = await r.json();
    (data.items || []).forEach((item) => {
      const option = document.createElement('option');
      option.value = item.player;
      option.dataset.playerId = item.player_id;
      option.textContent = `${item.player} (ERA ${item.era}, WHIP ${item.whip})`;
      select.appendChild(option);
    });
  } catch (_) { /* 투수 통계가 없으면 선택 없이 fallback */ }
}

$('chatForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = $('message');
  const message = input.value.trim();
  if (!message || chatBusy) return;
  chatBusy = true;
  addMessage(message, 'user');
  input.value = '';
  const button = event.submitter || event.target.querySelector('[type="submit"]');
  button.disabled = true;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60000);
  const loading = document.createElement('div');
  loading.className = 'message assistant';
  loading.textContent = '답변을 생성하고 있습니다...';
  $('chatMessages').appendChild(loading);
  try {
    const r = await apiFetch(`${API_BASE_URL}/api/chat`, { signal: controller.signal, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, conversation_id: conversationId, team: $('team').value, season: Number($('season').value), last_n: Number($('lastN').value) }) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Chat 요청에 실패했습니다.');
    conversationId = data.conversation_id;
    showAiMode(data.model);
    if (data.model !== 'mock') $('modeLabel').textContent = `실제 AI 응답 · ${data.model}`;
    addMessage(data.answer, 'assistant');
    showSummary(data.summary);
    loadConversations();
  } catch (error) { addMessage(`오류: ${error.name === 'AbortError' ? '응답 대기 시간이 초과되었습니다. 대화 목록을 확인한 뒤 다시 시도하세요.' : error.message}`, 'assistant'); }
  finally { clearTimeout(timer); loading.remove(); button.disabled = false; chatBusy = false; }
});

$('newChat').addEventListener('click', resetChat);
$('refreshData').addEventListener('click', () => { loadData(); loadLiveSummary(); requestGameSync(); });
$('conversationList').addEventListener('click', async (event) => {
  const deleteButton = event.target.closest('.conversation-delete');
  if (deleteButton) {
    event.stopPropagation();
    if (!confirm('이 대화를 삭제할까요?')) return;
    const r = await apiFetch(`${API_BASE_URL}/api/conversations/${encodeURIComponent(deleteButton.dataset.id)}`, { method: 'DELETE' });
    if (r.ok) { if (conversationId === deleteButton.dataset.id) resetChat(); loadConversations(); }
    return;
  }
  const item = event.target.closest('.conversation-item');
  if (item) loadConversation(item.dataset.id).catch((e) => addMessage(`오류: ${e.message}`, 'assistant'));
});

$('dataForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const date = $('dataDate').value;
  const runsFor = Number($('dataFor').value);
  const runsAgainst = Number($('dataAgainst').value);
  const team = $('dataTeam').value;
  const opponent = $('dataOpponent').value.trim();
  const result = runsFor > runsAgainst ? 'W' : runsFor < runsAgainst ? 'L' : 'D';
  const payload = { date, season: Number(date.slice(0, 4)), team, opponent, home_away: 'home', runs_for: runsFor, runs_against: runsAgainst, result, run_diff: runsFor - runsAgainst, value: runsFor - runsAgainst, status: 'completed', game_id: `ui-${Date.now()}-${team}`, memo: `${team} ${runsFor}:${runsAgainst} ${opponent}` };
  const r = await apiFetch(`${API_BASE_URL}/api/data`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  if (!r.ok) { alert('데이터 추가에 실패했습니다.'); return; }
  event.target.reset();
  loadData();
});

$('dataRows').addEventListener('click', async (event) => {
  const button = event.target.closest('.delete-btn');
  if (!button || !confirm('이 경기 기록을 삭제할까요?')) return;
  const r = await apiFetch(`${API_BASE_URL}/api/data/${button.dataset.id}`, { method: 'DELETE' });
  if (r.ok) loadData(); else alert('삭제에 실패했습니다.');
});

$('predictionForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const a = $('pitcherA');
  const b = $('pitcherB');
  const body = { team_a: $('teamA').value, team_b: $('teamB').value, season: Number($('predictionSeason').value), last_n: Number($('predictionLastN').value), pitcher_a: a?.value || null, pitcher_a_id: a?.selectedOptions?.[0]?.dataset.playerId || null, pitcher_b: b?.value || null, pitcher_b_id: b?.selectedOptions?.[0]?.dataset.playerId || null };
  $('predictionResult').textContent = '예측을 계산하는 중...';
  try {
    const r = await apiFetch(`${API_BASE_URL}/api/predictions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || '예측에 실패했습니다.');
    const dates = data.pitcher_stats_as_of || {};
    $('predictionResult').innerHTML = `<div class="probability"><span><strong>${escapeHtml(data.team_a)}</strong> ${(data.team_a_probability * 100).toFixed(1)}%</span><span><strong>${escapeHtml(data.team_b)}</strong> ${(data.team_b_probability * 100).toFixed(1)}%</span></div><div>선택한 투수: ${escapeHtml(data.pitchers?.team_a || '미선택')} / ${escapeHtml(data.pitchers?.team_b || '미선택')}</div><div>투수 통계 반영: ${data.pitcher_stats_applied ? '예' : '아니오'} · A팀 기준일: ${escapeHtml(dates.team_a || '없음')} · B팀 기준일: ${escapeHtml(dates.team_b || '없음')}</div><ul class="prediction-limitations">${(data.limitations || []).map((x) => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`;
  } catch (error) { $('predictionResult').textContent = `오류: ${error.message}`; }
});

['teamA', 'teamB', 'predictionSeason'].forEach((id) => $(id)?.addEventListener('change', () => { loadPitchers('pitcherA', 'teamA'); loadPitchers('pitcherB', 'teamB'); }));

const chatHeading = document.querySelector('.chat-panel .panel-heading');
if (chatHeading) {
  const button = document.createElement('button');
  button.className = 'refresh-btn';
  button.type = 'button';
  button.textContent = '새 대화';
  button.title = '현재 대화와 Summary 초기화';
  button.addEventListener('click', resetChat);
  chatHeading.appendChild(button);
}

function refreshAllViews() {
  loadAiStatus(); loadConversations(); loadData();
  loadPitchers('pitcherA', 'teamA'); loadPitchers('pitcherB', 'teamB');
  loadLiveSummary(); requestGameSync();
}
$('accessForm')?.addEventListener('submit', (event) => {
  event.preventDefault();
  demoAccessKey = $('demoKey').value.trim();
  try {
    if (demoAccessKey) sessionStorage.setItem('kbo-demo-key', demoAccessKey);
    else sessionStorage.removeItem('kbo-demo-key');
  } catch (_) {}
  $('demoKey').value = '';
  syncStatusUnknown = false;
  refreshAllViews();
});
['team', 'season', 'lastN'].forEach((id) => $(id).addEventListener('change', loadLiveSummary));
if (!globalThis.KBO_CONFIG?.requireAccess || demoAccessKey) refreshAllViews();
else $('syncStatus').textContent = '상단의 시연 접근 키를 입력한 후 연결해주세요.';
