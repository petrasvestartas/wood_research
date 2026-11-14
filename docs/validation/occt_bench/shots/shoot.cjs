const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const dir = process.argv[2];
const srv = http.createServer((q, s) => { const f = path.join(dir, decodeURIComponent(q.url.split('?')[0])); fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); s.end(); return; } s.writeHead(200, {'Content-Type': f.endsWith('.html') ? 'text/html' : f.endsWith('.js') ? 'text/javascript' : 'application/json'}); s.end(d); }); }).listen(8791, async () => {
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 2010, height: 650 }, deviceScaleFactor: 1 });
  p.on('console', m => console.log('console', m.text())); p.on('pageerror', e => console.log('err', e.message));
  await p.goto('http://localhost:8791/page.html');
  const jobs = JSON.parse(process.argv[3]);
  for (const [n, t] of jobs) { console.log(n, await p.evaluate(([n, t]) => run(n, t), [n, t])); await p.waitForTimeout(300); await p.screenshot({ path: path.join(dir, 'cmp_' + n + '.png'), fullPage: true }); }
  await b.close(); srv.close();
});
