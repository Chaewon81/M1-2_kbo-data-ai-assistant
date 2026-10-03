// Actual deployed-page capture. No GPT calls; CRUD mode uses one disposable 2099 record.
const { chromium } = require('../../.tools/capture/node_modules/playwright-core');
const fs = require('node:fs');
const path = require('node:path');
const frontend = 'https://m1-2kbo-data-ai-assistant.vercel.app';
const backend = 'https://m1-2-kbo-data-ai-assistant.onrender.com';
const mode = process.argv[2] || 'public';
const key = process.env.CAPTURE_DEMO_KEY || '';
const output = path.resolve('picture/submission');
fs.mkdirSync(output, { recursive: true });

(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'ko-KR' });
  let aiCalls = 0, syncWritesBlocked = 0;
  await context.route(`${backend}/**`, async route => {
    const request = route.request();
    if (request.method() === 'POST' && request.url().endsWith('/api/chat')) {
      aiCalls++;
      return route.abort();
    }
    if (request.method() === 'POST' && request.url().endsWith('/api/sync')) {
      syncWritesBlocked++;
      // Read the actual saved status instead of triggering a synchronization write.
      const response = await context.request.get(`${backend}/api/sync/status`, { headers: { 'X-Demo-Key': key } });
      return route.fulfill({ response });
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  const shots = [];
  const capture = async (name, target = page) => {
    await target.evaluate(() => document.fonts.ready);
    await target.screenshot({ path: path.join(output, name), fullPage: true });
    shots.push(name);
  };
  const api = async (endpoint, options = {}) => {
    const response = await context.request.fetch(`${backend}${endpoint}`, {
      ...options, headers: { 'X-Demo-Key': key, ...(options.headers || {}) }, timeout: 45000,
    });
    if (!response.ok()) throw new Error(`API ${endpoint.split('?')[0]} HTTP ${response.status()}`);
    return response.json();
  };
  let recordId = null;
  try {
    await page.goto(frontend, { waitUntil: 'networkidle', timeout: 45000 });
    if (mode === 'public') {
      await capture('01_DEPLOYED_HOME.png');
      await page.setViewportSize({ width: 390, height: 844 });
      await capture('02_MOBILE_HOME.png');
    } else {
      const status = await api('/api/chat/status');
      if (status.provider !== 'openai' || status.mode !== 'real') throw new Error('Expected real OpenAI deployment');
      const firebase = await api('/api/firebase/status');
      if (!firebase.connected) throw new Error('Expected connected Firestore');
      await page.locator('#demoKey').fill(key);
      await page.locator('#accessForm').evaluate(form => form.requestSubmit());
      await page.waitForFunction(() => document.querySelectorAll('#conversationList .conversation-item').length > 0);
      const list = await api('/api/conversations');
      let chosen;
      for (const candidate of list.items.slice(0, 20)) {
        const conversation = await api(`/api/conversations/${candidate.id}`);
        if (conversation.summary?.count && conversation.messages.some(x => x.role === 'assistant' && !x.content.includes('[개발용 Mock'))) {
          chosen = conversation;
          break;
        }
      }
      if (!chosen) throw new Error('No saved non-Mock conversation with Summary found');
      await page.locator(`.conversation-item[data-id="${chosen.id}"] .conversation-title`).click();
      await page.waitForFunction(() => document.querySelector('#summaryContent .summary-grid'));
      await page.locator('#dataRows .delete-btn').first().waitFor({ timeout: 90000 });
      // Expand the existing scroll region for evidence, without changing its content.
      await page.locator('#chatMessages').evaluate(el => {
        el.style.height = 'auto'; el.style.maxHeight = 'none'; el.style.overflow = 'visible'; el.scrollTop = 0;
      });
      await capture('03_CHAT_SUMMARY_RELOADED.png');
      await page.locator('.workspace').screenshot({ path: path.join(output, '04_CHAT_SUMMARY_DETAIL.png') });
      shots.push('04_CHAT_SUMMARY_DETAIL.png');
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator(`.conversation-item[data-id="${chosen.id}"] .conversation-title`).click();
      await page.waitForFunction(() => document.querySelector('#summaryContent .summary-grid'));
      const mobileControls = await page.evaluate(() => ['message', 'dataDate', 'dataTeam', 'dataOpponent', 'dataFor', 'dataAgainst'].every(id => {
        const rect = document.getElementById(id).getBoundingClientRect();
        return rect.width > 0 && rect.left >= 0 && rect.right <= innerWidth;
      }));
      if (!mobileControls) throw new Error('Mobile form controls overflow the viewport');
      await capture('05_MOBILE_CONVERSATION.png');
      if (await page.locator('.sidebar').evaluate(el => getComputedStyle(el).display) === 'none') throw new Error('Mobile conversations are hidden');
      await page.setViewportSize({ width: 1440, height: 1000 });
      if (mode === 'crud') {
        await page.locator('#dataDate').fill('2099-01-01');
        await page.locator('#dataTeam').selectOption('KIA');
        await page.locator('#dataOpponent').fill('LG');
        await page.locator('#dataFor').fill('3');
        await page.locator('#dataAgainst').fill('1');
        const responsePromise = page.waitForResponse(r => r.url() === `${backend}/api/data` && r.request().method() === 'POST');
        await page.locator('#dataForm button[type="submit"]').click();
        const response = await responsePromise;
        if (response.status() !== 201) throw new Error(`CRUD POST HTTP ${response.status()}`);
        const created = await response.json();
        recordId = created.id;
        const stored = await api(`/api/data/${encodeURIComponent(recordId)}`);
        if (!stored.is_manual || stored.date !== '2099-01-01') throw new Error('Stored synthetic record mismatch');
        await page.locator(`#dataRows button[data-id="${encodeURIComponent(recordId)}"]`).waitFor();
        await page.locator('.data-panel').screenshot({ path: path.join(output, '06_DATA_CREATED.png') });
        shots.push('06_DATA_CREATED.png');
        // Capture real authenticated API response in the browser without showing the key.
        const evidence = await context.newPage();
        await evidence.route(`${backend}/api/data/**`, route => route.continue({ headers: { ...route.request().headers(), 'X-Demo-Key': key } }));
        await evidence.goto(`${backend}/api/data/${encodeURIComponent(recordId)}`, { waitUntil: 'networkidle' });
        await capture('07_STORED_DATA_API.png', evidence);
        await evidence.close();
        page.once('dialog', dialog => dialog.accept());
        const deletionPromise = page.waitForResponse(r => r.url().includes(encodeURIComponent(recordId)) && r.request().method() === 'DELETE');
        await page.locator(`#dataRows button[data-id="${encodeURIComponent(recordId)}"]`).click();
        const deletion = await deletionPromise;
        if (!deletion.ok()) throw new Error(`CRUD DELETE HTTP ${deletion.status()}`);
        await page.waitForFunction(id => ![...document.querySelectorAll('#dataRows button')].some(x => x.dataset.id === encodeURIComponent(id)), recordId);
        await page.locator('.data-panel').screenshot({ path: path.join(output, '08_DATA_DELETED.png') });
        shots.push('08_DATA_DELETED.png');
        recordId = null;
      }
    }
    const docs = await context.newPage();
    await docs.goto(`${backend}/docs`, { waitUntil: 'networkidle', timeout: 45000 });
    await docs.locator('.swagger-ui .info').waitFor();
    await capture('09_DEPLOYED_SWAGGER.png', docs);
    console.log(JSON.stringify({ status: 'PASS', mode, checked_at: new Date().toISOString(), shots, ai_calls: aiCalls,
      sync_post_replaced_with_read_only_status: syncWritesBlocked, synthetic_record_removed: recordId === null,
      chat_scroll_region_expanded_for_capture: mode !== 'public' }));
  } finally {
    if (recordId) {
      const cleanup = await context.request.delete(`${backend}/api/data/${encodeURIComponent(recordId)}`, { headers: { 'X-Demo-Key': key } });
      console.log(JSON.stringify({ cleanup_http: cleanup.status(), retained_deletion_marker: true }));
    }
    await browser.close();
  }
})().catch(error => { console.error(`Capture failed: ${error.name}: ${error.message.replaceAll(key || 'UNUSED_KEY', '[redacted]')}`); process.exitCode = 1; });
