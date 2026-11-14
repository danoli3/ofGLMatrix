// No npm dependencies; Node 24 supplies fetch and WebSocket.
import { spawn } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, 'artifacts');
mkdirSync(out, { recursive: true });
const webgl = process.env.WEBGL;
if (!['1', '2'].includes(webgl)) throw new Error('WEBGL must be 1 or 2');
const browser = process.env.CHROME_BIN || '/usr/bin/google-chrome';
const logs = [];
const children = [];
let ws;
let exitCode = 1;
let report = { cases: [], error: 'Browser test did not complete.' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const deadline = setTimeout(() => {
  logs.push('CI timeout');
  for (const child of children) child.kill('SIGKILL');
  writeFileSync(join(out, 'browser.log'), logs.join('\n'));
  process.exit(1);
}, 120000);

try {
  const webroot = join(root, 'glMatrixWeb/bin/em/glMatrixWeb');
  const html = readdirSync(webroot).find((file) => file.endsWith('.html'));
  if (!html) throw new Error(`No built HTML in ${webroot}`);
  const server = spawn('python3', [join(root, 'ci/serve.py'), webroot], { stdio: 'ignore' });
  children.push(server);
  server.on('error', (error) => logs.push(String(error)));
  const chrome = spawn(browser, [
    '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
    '--remote-debugging-port=9222', `--user-data-dir=${mkdtempSync(join(tmpdir(), 'glmatrix-'))}`,
    '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--enable-webgl',
    '--window-size=1040,760', '--hide-scrollbars', '--no-first-run',
    ...(webgl === '1' ? ['--disable-webgl2'] : []), 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'pipe'] });
  children.push(chrome);
  chrome.on('error', (error) => logs.push(String(error)));
  chrome.stderr.on('data', (data) => logs.push(String(data)));
  let target;
  for (let i = 0; i < 100 && !target; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9222/json/list')).json();
      target = list.find((tab) => tab.type === 'page');
    } catch { /* Chrome is still starting. */ }
    if (!target) await sleep(200);
  }
  if (!target) throw new Error('Chrome did not expose a page');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve); ws.addEventListener('error', reject); });
  let id = 0;
  const pending = new Map();
  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    }
    if (message.method === 'Runtime.consoleAPICalled') logs.push(message.params.args.map((arg) => arg.value ?? arg.description ?? '').join(' '));
    if (message.method === 'Runtime.exceptionThrown') logs.push(JSON.stringify(message.params));
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const key = ++id;
    pending.set(key, { resolve, reject });
    ws.send(JSON.stringify({ id: key, method, params }));
  });
  const evaluate = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true })).result.value;
  await send('Runtime.enable');
  await send('Page.enable');
  // Wait for the HTTP server too; a failed initial navigation must not masquerade as an app failure.
  const url = `http://127.0.0.1:8765/${html}?webgl=${webgl}`;
  for (let i = 0; i < 50; i++) {
    try { if ((await fetch(url)).ok) break; } catch { /* server startup */ }
    await sleep(100);
  }
  await send('Page.navigate', { url });
  let title = '';
  for (let i = 0; i < 300 && !title.includes('GL_MATRIX requested='); i++) {
    await sleep(200);
    title = await evaluate('document.title') || '';
  }
  const context = await evaluate(`(() => {
    const canvas = document.querySelector('canvas');
    if (!canvas) return null;
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return null;
    return { webgl: typeof WebGL2RenderingContext !== 'undefined' && gl instanceof WebGL2RenderingContext ? 2 : 1,
      version: gl.getParameter(gl.VERSION), renderer: gl.getParameter(gl.RENDERER) };
  })()`);
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(out, 'webgl.png'), Buffer.from(shot.data, 'base64'));
  const expected = webgl === '1' ? 'ES 2.0' : 'ES 3.0';
  const pass = title.includes(`requested="${expected}"`) && title.includes(' RESULT=PASS') && context?.webgl === Number(webgl);
  report = { openFrameworks: process.env.OF_SHA, webgl, context, error: '',
    cases: [{ case: `WebGL ${webgl}`, status: pass ? 'PASS' : 'FAIL', detail: title || 'No app result' }] };
  console.log(report);
  logs.push(JSON.stringify(report));
  exitCode = pass ? 0 : 1;
} catch (error) {
  report.error = String(error.message || error);
  logs.push(String(error.stack || error));
  console.error(error);
} finally {
  writeFileSync(join(out, 'results.json'), JSON.stringify(report, null, 2) + '\n');
  clearTimeout(deadline);
  ws?.close();
  for (const child of children) child.kill('SIGTERM');
  writeFileSync(join(out, 'browser.log'), logs.join('\n') + '\n');
}
process.exit(exitCode);
