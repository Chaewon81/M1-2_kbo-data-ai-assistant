const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const {publicConfig, build} = require('../../frontend/build_config.cjs');

const config = publicConfig({API_BASE_URL: 'https://kbo-api.example.com/', OPENAI_API_KEY: 'NOT_PUBLIC', DEMO_ACCESS_KEY: 'NOT_PUBLIC'});
assert.deepEqual(config, {apiBaseUrl: 'https://kbo-api.example.com', requireAccess: true});
assert(!JSON.stringify(config).includes('NOT_PUBLIC'));
for (const value of ['', 'http://127.0.0.1:8000', 'https://localhost', 'https://user:pass@example.com', 'https://example.com/api', 'https://example.com?key=secret']) {
  assert.throws(() => publicConfig({API_BASE_URL: value}));
}
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'kbo-build-test-'));
build({API_BASE_URL: 'https://kbo-api.example.com'}, out);
assert.deepEqual(fs.readdirSync(out).sort(), ['app.js', 'config.js', 'data.css', 'index.html', 'prediction.css', 'provenance.css', 'style.css'].sort());
assert(fs.readFileSync(path.join(out, 'config.js'), 'utf8').includes('https://kbo-api.example.com'));
assert(!fs.existsSync(path.join(out, 'build_config.cjs')));
fs.writeFileSync(path.join(out, 'unexpected-secret.txt'), 'test-only-marker');
assert.throws(() => build({API_BASE_URL: 'https://kbo-api.example.com'}, out), /unexpected files/);

const source = fs.readFileSync(path.join(__dirname, '../../frontend/app.js'), 'utf8');
const prefix = source.slice(0, source.indexOf('let conversationId'));
const requests = [];
const context = vm.createContext({Headers, Error, sessionStorage: {getItem: () => 'demo-example-key'},
  KBO_CONFIG: config, fetch: async (url, options) => { requests.push({url, options}); return {status: 200}; }});
vm.runInContext(prefix + '\nglobalThis.testApi = apiFetch;', context);
(async () => {
  await context.testApi('https://kbo-api.example.com/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}});
  assert.equal(requests[0].options.headers.get('X-Demo-Key'), 'demo-example-key');
  assert.equal(requests[0].options.headers.get('Content-Type'), 'application/json');
  vm.runInContext('demoAccessKey = "";', context);
  await assert.rejects(context.testApi('/api/chat'), /접근 키/);
  assert.equal(requests.length, 1);
  console.log('Deployment frontend assertions PASS (public config, asset whitelist, access header, missing key)');
})().catch(error => {console.error(error); process.exitCode = 1;});
