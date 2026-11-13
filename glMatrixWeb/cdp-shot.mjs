// node cdp-shot.mjs <url> <out.png> <out.log> [--disable-webgl2]
// Headless Chrome on the real GPU (ANGLE/Metal); waits for the app to put its
// GL_MATRIX result line in document.title, then screenshots the page.
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [url, outPng, outLog, ...extra] = process.argv.slice(2);
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9300 + Math.floor(Math.random() * 500);
const proc = spawn(chrome, [
	'--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'cdp-'))}`,
	'--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--window-size=1040,760',
	'--hide-scrollbars', '--no-first-run', ...extra, 'about:blank',
], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const finish = (code) => { proc.kill('SIGKILL'); process.exit(code); };
setTimeout(() => { console.error('timeout'); finish(2); }, 60000);

let target;
for (let i = 0; i < 50 && !target; i++) {
	try {
		const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
		target = list.find((t) => t.type === 'page');
	} catch { await sleep(200); }
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0;
const pending = new Map();
const logs = [];
ws.addEventListener('message', (ev) => {
	const msg = JSON.parse(ev.data);
	if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg.result); pending.delete(msg.id); }
	if (msg.method === 'Runtime.consoleAPICalled') logs.push(msg.params.args.map((a) => a.value ?? '').join(' '));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });

await send('Runtime.enable');
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1040, height: 760, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url });

let title = '';
for (let i = 0; i < 100 && !title.includes('RESULT='); i++) {
	await sleep(250);
	title = (await send('Runtime.evaluate', { expression: 'document.title', returnByValue: true })).result.value || '';
}
const gl = (await send('Runtime.evaluate', {
	returnByValue: true,
	expression: `(() => { const c = document.querySelector('#canvas'); const g = c && (c.getContext('webgl2') || c.getContext('webgl'));
		const d = g && g.getExtension('WEBGL_debug_renderer_info');
		return g ? { context: (typeof WebGL2RenderingContext !== 'undefined' && g instanceof WebGL2RenderingContext) ? 'webgl2' : 'webgl1',
			version: g.getParameter(g.VERSION), renderer: d ? g.getParameter(d.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER) } : null; })()`,
})).result.value;
await sleep(300);
const shot = await send('Page.captureScreenshot', { format: 'png' });
writeFileSync(outPng, Buffer.from(shot.data, 'base64'));
writeFileSync(outLog, [title, 'browser=' + JSON.stringify(gl), ...logs].join('\n') + '\n');
console.log(title);
console.log('browser=' + JSON.stringify(gl));
finish(title.includes('RESULT=PASS') ? 0 : 1);
