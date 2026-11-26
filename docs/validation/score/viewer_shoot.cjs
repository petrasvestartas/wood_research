// viewer_shoot.cjs <viewer dist> <scene dir> <out dir> '[[name, width, height], ...]': serves the built viewer with the scene
// dir on one localhost origin (WebGPU needs a secure context), opens ?scene=scenes/<name>.yaml in headless Chromium on
// SwiftShader's WebGPU adapter and writes <out dir>/<name>.png of the canvas at deviceScaleFactor 2.
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const [dist, sceneDir, outDir, jobsJson] = process.argv.slice(2);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.wasm': 'application/wasm', '.css': 'text/css', '.yaml': 'application/yaml', '.json': 'application/json' };
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]);
  const f = /^\/(pb|scenes)\//.test(u) ? path.join(sceneDir, u) : path.join(dist, u === '/' ? 'index.html' : u);
  fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); s.end(); return; } s.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream', 'Cache-Control': 'no-store' }); s.end(d); });
}).listen(0, '127.0.0.1', async () => {
  const port = srv.address().port;
  const b = await chromium.launch({ headless: true, args: ['--enable-unsafe-webgpu', '--use-webgpu-adapter=swiftshader', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-features=Vulkan', '--use-vulkan=swiftshader', '--disable-vulkan-surface'] });
  try {
    for (const [n, w, h] of JSON.parse(jobsJson)) {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
      const p = await ctx.newPage();
      p.on('pageerror', e => console.log('pageerror', n, e.message));
      p.on('console', m => { if (process.env.ALLLOG || m.type() === 'error' || m.type() === 'warning') console.log('console', n, m.text().slice(0, 300)); });
      await p.goto(`http://127.0.0.1:${port}/?scene=scenes/${n}.yaml&data=off&inspect=1&dpr=2&nogrid=1`);
      let last = -1, same = 0;
      for (let t = 0; t < 240 && same < 6; t++) {
        await p.waitForTimeout(500);
        const s = await p.evaluate(() => JSON.parse(document.querySelector('#canvas')?.getAttribute('data-viewer-inspection') || '{}'));
        same = s.objects > 0 && s.frames > 0 && s.objects === last ? same + 1 : 0; last = s.objects;
      }
      await p.screenshot({ path: path.join(outDir, n + '.png'), timeout: 180000, clip: { x: 0, y: 0, width: w, height: h - 36 } }); // without the command line
      console.log('shot', n, last);
      await ctx.close();
    }
  } finally { await b.close(); srv.close(); }
});
