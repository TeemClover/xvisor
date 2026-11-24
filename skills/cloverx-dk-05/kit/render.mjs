// Draws the text layer (headline, subtitles, name tags, product cards, end card) for one clip.
// usage (through rv): node render.mjs <project>/build/<CLIP> [t1,t2,...]   times -> PNG stills, no times -> overlay.mov
import { chromium } from 'playwright';
import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const dir = path.resolve(process.argv[2]);
const kit = path.dirname(fileURLToPath(import.meta.url));
const proj = path.resolve(process.env.RV_PROJECT || path.join(dir, '..', '..'));
const TL = JSON.parse(fs.readFileSync(path.join(dir, 'timeline.json'), 'utf8'));
const FPS = 30, N = Math.round(TL.total * FPS);
// pictures named in the timeline: the project's assets/ wins over the kit's
const names = new Set(['habix-white.png', TL.klogo, TL.end?.logo, TL.end?.img, ...(TL.cards || []).map(c => c.img)].filter(Boolean));
const ASSET = {};
for (const n of names) {
  const hit = [path.join(proj, 'assets', n), path.join(kit, 'assets', n)].find(p => fs.existsSync(p));
  if (!hit) { console.error('ไม่พบภาพ ' + n + ' ใน assets/ ของโปรเจ็กต์หรือของ kit'); process.exit(1); }
  ASSET[n] = pathToFileURL(hit).href;
}
// Playwright's own Chromium if it was installed (npx playwright install chromium), else the Google Chrome on this machine
let browser;
try { browser = await chromium.launch(); } catch { browser = await chromium.launch({ channel: 'chrome' }); }
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
await page.addInitScript(`window.TL=${JSON.stringify(TL)};window.ASSET=${JSON.stringify(ASSET)}`);
await page.goto(pathToFileURL(path.join(kit, 'overlay.html')).href);
await page.evaluate(() => document.fonts.ready);
await page.evaluate(async () => { await Promise.all([...document.images].map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; }))); });
await page.waitForTimeout(300);
if (process.argv[3] !== undefined) {
  for (const t of process.argv[3].split(',').map(Number)) {
    await page.evaluate(t => window.render(t), t);
    await page.screenshot({ path: path.join(dir, `ov_${t.toFixed(2)}.png`), omitBackground: true });
  }
  await browser.close(); process.exit(0);
}
const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
  '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0', path.join(dir, 'overlay.mov')], { stdio: ['pipe', 'inherit', 'inherit'] });
for (let i = 0; i < N; i++) {
  await page.evaluate(t => window.render(t), i / FPS);
  const buf = await page.screenshot({ omitBackground: true, type: 'png' });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close();
console.log('overlay done', path.basename(dir), N);
