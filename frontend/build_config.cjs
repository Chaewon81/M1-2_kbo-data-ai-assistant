// Only public configuration and explicit static assets reach the output folder.
const fs = require('node:fs');
const path = require('node:path');

function publicConfig(env) {
  if (!env.API_BASE_URL) throw new Error('API_BASE_URL is required for deployment');
  const url = new URL(env.API_BASE_URL);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('API_BASE_URL must be a plain HTTPS backend origin');
  }
  if (['localhost', '127.0.0.1', '::1', '[::1]'].includes(url.hostname)) throw new Error('Localhost is not a deployment backend');
  return { apiBaseUrl: url.origin, requireAccess: true };
}

function build(env = process.env, out = path.join(__dirname, '../dist')) {
  const config = publicConfig(env); // Validate before creating output.
  const assets = ['index.html', 'app.js', 'style.css', 'data.css', 'provenance.css', 'prediction.css'];
  if (fs.existsSync(out) && fs.readdirSync(out).some(name => ![...assets, 'config.js'].includes(name))) {
    throw new Error('Output contains unexpected files; inspect it before deploying');
  }
  fs.mkdirSync(out, { recursive: true });
  for (const name of assets) {
    fs.copyFileSync(path.join(__dirname, name), path.join(out, name));
  }
  fs.writeFileSync(path.join(out, 'config.js'), `globalThis.KBO_CONFIG = ${JSON.stringify(config)};\n`, 'utf8');
  return config;
}
module.exports = { publicConfig, build };
if (require.main === module) build();
