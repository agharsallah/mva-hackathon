/**
 * Three behaviours of the protein explorer that only a real browser can confirm:
 *
 * 1. `?gene=bub1b` is canonicalised to `BUB1B` before any request is spent (the title and the
 *    URL both read the set's spelling).
 * 2. The cross-gene metrics table does not fetch until it is scrolled near the viewport — its
 *    placeholder line is on the page before the scroll and the 23 rows only after.
 * 3. In the comparison, turning "sync cameras" off, orbiting one canvas, and turning it back on
 *    re-aligns the other canvas.
 *
 *     URL_BASE=http://127.0.0.1:<port> node tools/verify-explorer-gating.mjs
 */

import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { boxDrift, chromiumPath, loadPlaywright, measureFill } from './viz3d-measure.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
const URL_BASE = process.env.URL_BASE ?? 'http://127.0.0.1:5173';
const say = (line) => console.log(line);

const { chromium } = await loadPlaywright(HERE, REPO);
const browser = await chromium.launch({
  executablePath: chromiumPath(undefined),
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: 1340, height: 900 } });
const requests = [];
page.on('request', (r) => requests.push(r.url()));

// 1. canonicalisation
await page.goto(`${URL_BASE}/panel?gene=bub1b`, { waitUntil: 'networkidle' });
await page.waitForTimeout(800);
const title = await page.textContent('text=/The fold in 3D — where/');
say(`- ?gene=bub1b -> url ${new URL(page.url()).search} · title "${title?.trim()}"`);
const lower = requests.filter((u) => u.includes('gene=bub1b'));
say(`- requests carrying the lower-case symbol: ${lower.length}`);
for (const u of lower) say(`    ${new URL(u).pathname}`);

// 2. in-view gating of the metrics table
const gatedBefore = await page.$('text=/Scroll here and the table fills in/');
const rowsBefore = await page.$$('table tbody tr >> text=/fold only|non-coding/');
say(`- before scrolling: gate note present ${!!gatedBefore}, metric rows ${rowsBefore.length}`);
await page.evaluate(() => {
  const el = [...globalThis.document.querySelectorAll('h3, h2, figcaption, p')].find((n) =>
    n.textContent?.includes('Every gene in the set, as numbers'),
  );
  el?.scrollIntoView({ block: 'start' });
});
await page.waitForTimeout(2500);
const gatedAfter = await page.$('text=/Scroll here and the table fills in/');
const compareButtons = await page.$$('button:has-text("→A")');
say(
  `- after scrolling: gate note present ${!!gatedAfter}, rows with a compare control ${compareButtons.length}`,
);

// 3. sync off -> orbit -> sync on re-aligns
await page.goto(`${URL_BASE}/panel?prot.cmpA=BUB1B&prot.cmpB=TRIP13`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const canvases = await page.$$('canvas');
const leftIndex = canvases.length - 2;
const rightIndex = canvases.length - 1;
const left = canvases[leftIndex];
const sync = page.getByRole('button', { name: /sync cameras/ });
await sync.click(); // off
const beforeRight = await measureFill(page, rightIndex);
const lb = await left.boundingBox();
await page.mouse.move(lb.x + lb.width / 2, lb.y + lb.height / 2);
await page.mouse.down();
await page.mouse.move(lb.x + lb.width / 2 + 160, lb.y + lb.height / 2 + 40, { steps: 12 });
await page.mouse.up();
await page.waitForTimeout(700);
const rightWhileOff = await measureFill(page, rightIndex);
await sync.click(); // on again
await page.waitForTimeout(900);
const rightAfterOn = await measureFill(page, rightIndex);
const offDrift = boxDrift(beforeRight, rightWhileOff);
const onDrift = boxDrift(rightWhileOff, rightAfterOn);
say(
  `- right canvas: while sync OFF and left orbited, drift ${offDrift} (expect ~0); ` +
    `after sync ON again, drift ${onDrift} (expect > 0.03) — ` +
    `${(onDrift ?? 0) > 0.03 ? 'RESYNCED' : 'did not resync'}`,
);

await browser.close();
