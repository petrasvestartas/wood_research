// node shoot.cjs <dir with page.html + ours_/occt_ json> '<[[name, title], ...]>' <out dir>
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const dir = process.argv[2];
const jobs = JSON.parse(fs.existsSync(process.argv[3]) ? fs.readFileSync(process.argv[3], 'utf8') : process.argv[3]);
const outdir = process.argv[4] || dir;
const srv = http.createServer((q, s) => { const f = path.join(dir, decodeURIComponent(q.url.split('?')[0])); fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); s.end(); return; } s.writeHead(200, {'Content-Type': f.endsWith('.html') ? 'text/html' : f.endsWith('.js') ? 'text/javascript' : 'application/json'}); s.end(d); }); }).listen(8797, async () => {
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  for (const [n, t, focus] of jobs) {
    const p = await b.newPage({ viewport: { width: 2010, height: 650 }, deviceScaleFactor: 1 });
    p.on('pageerror', e => console.log('err', n, e.message));
    await p.goto('http://localhost:8797/page.html');
    console.log(n, await p.evaluate(([n, t, focus]) => run(n, t, focus), [n, t, !!focus]));
    await p.waitForTimeout(200);
    await p.screenshot({ path: path.join(outdir, 'cmp_' + n + '.png'), fullPage: true });
    await p.close();
  }
  await b.close(); srv.close();
});
