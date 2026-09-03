/**
 * Browser check for the reference-data provenance exhibit on /provenance, driven the same
 * way `verify-protein-explorer.mjs` drives the 3D pages. Run against a dev server you own:
 *
 *   URL_BASE=http://127.0.0.1:<port> node tools/verify-provenance.mjs
 */
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import { chromiumPath, loadPlaywright } from './viz3d-measure.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, '..', '..');
// Pass the dev server you started: URL_BASE=http://127.0.0.1:<port> node tools/verify-provenance.mjs
const URL_BASE = process.env.URL_BASE ?? 'http://127.0.0.1:5173';
const OUT = path.join(REPO, 'figures', 'exhibits');

const say = (l) => console.log(l);

const { chromium } = await loadPlaywright(HERE, REPO);
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ executablePath: chromiumPath(undefined) });
const page = await browser.newPage({ viewport: { width: 1340, height: 1500 } });
const logs = [];
page.on('console', (m) => logs.push(`${m.type()}: ${m.text()}`));
page.on('pageerror', (e) => logs.push(`pageerror: ${e.message}`));

await page.goto(`${URL_BASE}/provenance`, { waitUntil: 'networkidle' });
await page.waitForSelector('text=Reference data — where the public inputs came from', {
  timeout: 20000,
});
say('- exhibit heading present');

// One row per manifest (7 at the time of writing: 5 reference tables + 2 fixture dirs).
const rowNames = await page.$$eval('#reference button[aria-expanded]', (bs) =>
  bs.map((b) => b.textContent.replace(/\s+/g, ' ').trim()),
);
say(`- manifest rows (${rowNames.length}):`);
for (const r of rowNames) say(`    ${r}`);

// The graph's service nodes and dotted manifest edges.
const svgText = await page.$$eval('svg text', (t) => t.map((n) => n.textContent));
const dashed = await page.$$eval('svg path[stroke-dasharray]', (p) => p.length);
const dashedRects = await page.$$eval('svg rect[stroke-dasharray]', (p) => p.length);
say(`- svg: ${dashed} dashed edge path(s), ${dashedRects} dashed node rect(s)`);
say(
  `- service labels: ${svgText.filter((t) => /obolibrary|ensembl|alphafold|reference files/.test(t)).join(' | ')}`,
);
say(`- "manifest" edge labels: ${svgText.filter((t) => t === 'manifest').length}`);

// Expand every row so the screenshot shows the inputs/outputs tables.
const buttons = await page.$$('#reference button[aria-expanded]');
await buttons[0].click();
await buttons[1].click();
await page.waitForTimeout(400);
const inputs = await page.$$eval('#reference table', (t) => t.length);
say(`- expanded 2 rows -> ${inputs} inputs/outputs table(s) rendered`);
const firstUrl = await page.$eval('#reference a[href^="http"]', (a) => a.href);
say(`- first input url is a link: ${firstUrl}`);
const shaTitle = await page.$eval('#reference span[title]', (s) => s.getAttribute('title'));
say(`- sha256 copy-on-hover title: ${shaTitle}`);

// The cross-link anchor.
await page.goto(`${URL_BASE}/panel?tab=protein&gene=TP53`, { waitUntil: 'networkidle' });
await page.waitForTimeout(2500);
const link = await page.$('a[href="/provenance#reference"]');
say(`- protein page provenance-manifest link present: ${link !== null}`);
if (link) {
  await link.click();
  await page.waitForTimeout(1200);
  say(`- clicked -> ${page.url()}`);
  const y = await page.evaluate(
    () => globalThis.document.getElementById('reference')?.getBoundingClientRect().top,
  );
  say(`- #reference top after hash scroll: ${Math.round(y)}px`);
}

await page.goto(`${URL_BASE}/provenance`, { waitUntil: 'networkidle' });
await page.waitForSelector('text=Reference data — where the public inputs came from');
const bs2 = await page.$$('#reference button[aria-expanded]');
await bs2[1].click();
await page.waitForTimeout(500);
const el = await page.$('#reference');
await el.screenshot({ path: path.join(OUT, 'provenance-reference.png') });
say(`- screenshot -> figures/exhibits/provenance-reference.png`);

const bad = logs.filter((l) => l.startsWith('error') || l.startsWith('pageerror'));
say(`- console errors: ${bad.length === 0 ? 'none' : bad.join(' | ')}`);
await browser.close();
