/**
 * The browser driver behind `docs/step-0/methodology/057-protein-explorer-exhibit.md`.
 *
 * It exists because jsdom has no WebGL: every in-repo test audits `SceneFallback` (the keyboard
 * path) and *nothing* audits the raycast, the camera fit or the frame cost. This is the
 * instrument for those, committed so those numbers are reproducible rather than asserted.
 *
 * What it measures, and how — read this before quoting a number from it:
 *
 *   - **frame rate.** A `requestAnimationFrame` counter in the page over a fixed wall-clock
 *     window (`--fps-ms`, default 3000 ms) while the scene auto-rotates, reported as
 *     `frames / elapsed`. On headless Chromium with software WebGL (`--use-angle=swiftshader`)
 *     there is no vsync cap, so it is a throughput figure: it says the scene is not heavy, it
 *     does not say what a real GPU does.
 *   - **canvas fill.** The fraction of the canvas's shorter side the drawn figure spans — the
 *     check on `core/camera.ts`'s `fitPoints`. See `measureFill` for how, and why not readPixels.
 *   - **the pick path.** Clicks at real canvas coordinates, asserted against `?prot.pick=`.
 *   - **camera stability.** Auto-rotate is stopped, the scene is orbited by a real drag, and the
 *     figure's bounding box is measured before and after a recolour and a filter toggle. Both
 *     change colours only, so the box must not move; a refit would snap the camera back to the
 *     `iso` preset and the box would jump. The check on `viewer.setGeometry`'s "refit only when
 *     the extent changed" rule.
 *
 * Usage (the dev server must already be running in fixture mode):
 *
 *     cd app
 *     VITE_API_URL=http://127.0.0.1:9 pnpm dev --port 5197 --strictPort   # dead port -> fixtures
 *     node tools/verify-protein-explorer.mjs --url http://127.0.0.1:5197
 *
 * `playwright` is not an app dependency — a one-machine instrument, not part of the build — so
 * it is resolved from wherever it is installed (a global `npm i -g playwright` included).
 */

import { mkdirSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

import {
  boxDrift,
  chromiumPath,
  loadPlaywright,
  measureFill,
  measureFps,
} from './viz3d-measure.mjs';

/** Every line of the report goes to stdout as it is measured, so a hang is visible. */
const say = (line) => console.log(line);

const HERE = path.dirname(new URL(import.meta.url).pathname);
const REPO = path.resolve(HERE, '..', '..');

/** `--key=value` and `--key value` both, so the usage line above can be pasted as written. */
const args = new Map();
for (let i = 2; i < process.argv.length; i++) {
  const token = process.argv[i];
  if (!token.startsWith('--')) continue;
  const [key, ...rest] = token.slice(2).split('=');
  if (rest.length > 0) args.set(key, rest.join('='));
  else if (process.argv[i + 1] && !process.argv[i + 1].startsWith('--'))
    args.set(key, process.argv[++i]);
  else args.set(key, 'true');
}
const URL_BASE = args.get('url') ?? 'http://127.0.0.1:5197';
const GENE = args.get('gene') ?? 'BUB1B';
const OUT = path.resolve(args.get('out') ?? path.join(REPO, 'figures', 'exhibits'));
const FPS_MS = Number(args.get('fps-ms') ?? 3000);

async function main() {
  const { chromium } = await loadPlaywright(HERE, REPO);
  mkdirSync(OUT, { recursive: true });
  const executablePath = chromiumPath(args.get('chromium'));
  say(`- chromium: ${executablePath ?? "playwright's bundled build"}`);
  const browser = await chromium.launch({
    executablePath,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  const page = await browser.newPage({ viewport: { width: 1340, height: 1400 } });
  const console_ = [];
  page.on('console', (m) => console_.push(`${m.type()}: ${m.text()}`));
  page.on('pageerror', (e) => console_.push(`pageerror: ${e.message}`));

  /**
   * A clipped *page* screenshot around the canvas, not an element screenshot: playwright's
   * element screenshot waits for the element to be "stable", and a canvas driven by a render
   * loop never satisfies that. `above`/`below` widen the clip so the controls and the legend
   * that decode the picture are in the same frame.
   */
  const shot = async (name, { above = 150, below = 260, target: at } = {}) => {
    const target = at ?? page.locator('canvas[role="img"]').first();
    await target.scrollIntoViewIfNeeded();
    const box = await target.boundingBox();
    const top = Math.max(0, box.y - above);
    const clip = {
      x: 0,
      y: top,
      width: page.viewportSize().width,
      height: Math.min(box.height + (box.y - top) + below, page.viewportSize().height - top),
    };
    await page.screenshot({ path: path.join(OUT, `${name}.png`), clip });
    say(`  wrote ${path.relative(REPO, path.join(OUT, `${name}.png`))}`);
  };

  say(`# protein explorer — ${URL_BASE}/panel?gene=${GENE}`);
  await page.goto(`${URL_BASE}/panel?gene=${GENE}`, { waitUntil: 'domcontentloaded' });
  const canvas = page.locator('canvas[role="img"]').first();
  await canvas.waitFor({ state: 'visible', timeout: 30_000 });
  // `/panel` stacks several exhibits, so the fold starts ~1,900 px down the page. Playwright's
  // mouse takes *viewport* coordinates and silently does nothing outside them, and a clipped
  // screenshot outside the viewport fails — so scroll to it before measuring or clicking.
  await canvas.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500);

  // The default-view box is deterministic (it is `fitPoints` on the `iso` preset), which is what
  // makes the camera-stability check below sharp: a refit lands *exactly* here again.
  const defaultBox = await measureFill(page);

  const label = await canvas.getAttribute('aria-label');
  say(`- canvas named: ${JSON.stringify((label ?? '').slice(0, 90))}…`);
  say(`- no-WebGL note present: ${/no WebGL/i.test(await page.content())}`);

  const fill = defaultBox;
  say(
    fill
      ? `- canvas fill: ${(fill.shorterSide * 100).toFixed(1)} % of the shorter side ` +
          `(${(fill.width * 100).toFixed(1)} % wide x ${(fill.height * 100).toFixed(1)} % high, ` +
          `${(fill.ink * 100).toFixed(1)} % of pixels painted, drawing buffer ${fill.canvas.join('x')})`
      : '- canvas fill: NOT MEASURED (no WebGL context)',
  );

  // The pick path. A fold is mostly empty space in projection, so the canvas centre is not a
  // reliable target — the driver walks a coarse grid and reports the first two real hits, which
  // is what "the raycast works against real WebGL" needs to mean.
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  const hits = [];
  const tried = [];
  for (const dy of [0.5, 0.4, 0.6, 0.3, 0.7]) {
    for (const dx of [0.5, 0.45, 0.55, 0.4, 0.6]) {
      if (hits.length >= 2) break;
      await page.mouse.click(box.x + box.width * dx, box.y + box.height * dy);
      await page.waitForTimeout(350);
      const picked = new URL(page.url()).searchParams.get('prot.pick');
      tried.push(`(${dx},${dy})`);
      if (picked) hits.push(`${picked} at (${dx}, ${dy})`);
    }
    if (hits.length >= 2) break;
  }
  say(
    `- clicks on the canvas: ${tried.length} tried, ${hits.length} hit -> ?prot.pick=${hits.join(', ') || '(none)'}`,
  );

  await shot('protein-explorer-pick');

  // Camera stability. Orbit by hand first — auto-rotate stops on the first pointerdown, and a
  // hand-set orbit is the thing a refit would destroy.
  await canvas.scrollIntoViewIfNeeded();
  const orbitBox = await canvas.boundingBox();
  await page.mouse.move(orbitBox.x + orbitBox.width * 0.5, orbitBox.y + orbitBox.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(
    orbitBox.x + orbitBox.width * 0.5 + 140,
    orbitBox.y + orbitBox.height * 0.5 + 60,
    { steps: 12 },
  );
  await page.mouse.up();
  // OrbitControls damps, so let the orbit settle before the reference measurement — and then
  // measure again with no action at all, to state the instrument's own noise floor.
  await page.waitForTimeout(2000);
  const orbited = await measureFill(page);
  const idle = await measureFill(page);
  say(
    `- default view box ${JSON.stringify(defaultBox?.box)}; after the drag ` +
      `${JSON.stringify(orbited?.box)} (moved ${boxDrift(defaultBox, orbited)}), ` +
      `instrument noise floor ${boxDrift(orbited, idle)} (two reads, no action)`,
  );

  // Addressed by the options it holds: `/panel` has several `<select>`s, and `getByLabel` does
  // not resolve the wrapping <label> the generic controls use.
  const colourBy = page
    .locator('select')
    .filter({ has: page.locator('option', { hasText: 'pLDDT' }) })
    .first();
  for (const [what, act] of [
    // By value, not label: the option reads "pLDDT (model confidence)".
    ['recolour to pLDDT', () => colourBy.selectOption('plddt')],
    [
      'toggle "rare alleles only"',
      () =>
        page
          .getByRole('button', { name: /rare alleles only/i })
          .first()
          .click(),
    ],
  ]) {
    await act().catch((e) => say(`  (control not found: ${e.message.split('\n')[0]})`));
    await page.waitForTimeout(700);
    const now = await measureFill(page);
    // A refit would put the camera back on the preset, so the box would equal the default one.
    // Comparing against *that* is sharp; comparing against the orbited box is not, because the
    // downscaled box quantises to ~0.01 per axis and the tube's silhouette aliases.
    const snapped = boxDrift(defaultBox, now);
    say(
      `- after ${what}: figure box ${JSON.stringify(now?.box)}; distance from the default view ` +
        `${snapped}, from the orbited view ${boxDrift(orbited, now)} — ` +
        `${snapped !== null && snapped > 0.02 ? 'camera HELD the orbit' : 'camera SNAPPED back'}`,
    );
  }
  await page
    .getByRole('button', { name: /rare alleles only/i })
    .first()
    .click()
    .catch(() => {});
  await page.waitForTimeout(400);
  await shot('protein-explorer-plddt');

  await page
    .getByRole('combobox', { name: 'colour by', exact: true })
    .first()
    .selectOption({ label: 'domain' })
    .catch(() => {});
  await page.waitForTimeout(600);
  await shot('protein-explorer-domain');

  await page
    .getByRole('combobox', { name: 'colour by', exact: true })
    .first()
    .selectOption({ index: 0 })
    .catch(() => {});
  // `.first()` throughout: the side-by-side comparison further down the page renders a second
  // "dim low-confidence" toggle and a second colour-by, and a bare locator is a strict-mode
  // violation. The explorer's own controls are the first of each in document order.
  const dim = page.getByRole('button', { name: /dim low-confidence/i }).first();
  await dim.click();
  await page.waitForTimeout(600);
  await shot('protein-explorer-no-dim');
  await dim.click();

  // The pair, from the closest-pairs table — the mouse-free way to build one. `/panel` holds
  // several tables, so the row is addressed by the only button on the page that names a pair.
  const rows = page.locator('button:has-text("↔")');
  if ((await rows.count()) > 0) {
    await rows.first().scrollIntoViewIfNeeded();
    await rows.first().click();
    await page.waitForTimeout(800);
    const url = new URL(page.url());
    say(
      `- distance-table row -> ?prot.a=${url.searchParams.get('prot.a')} ?prot.b=${url.searchParams.get('prot.b')}`,
    );
    await shot('protein-explorer-pair');
  }

  await page
    .getByRole('button', { name: /focus on selection/i })
    .first()
    .click()
    .catch(() => {});
  await page.waitForTimeout(900);
  const focusFill = await measureFill(page);
  say(
    `- canvas fill after focus: ${focusFill ? (focusFill.shorterSide * 100).toFixed(1) + ' %' : 'n/a'}`,
  );
  await shot('protein-explorer-focus');

  // ---------------------------------------------------------------------------------------
  // The side-by-side comparison and the cross-gene metrics table (WP5). Both live under the
  // same /panel route, so the driver stays on the page and addresses them by their controls.
  // ---------------------------------------------------------------------------------------
  say(`# structure comparison — ${URL_BASE}/panel?prot.cmpA=BUB1B&prot.cmpB=TRIP13`);
  await page.goto(`${URL_BASE}/panel?prot.cmpA=BUB1B&prot.cmpB=TRIP13`, {
    waitUntil: 'domcontentloaded',
  });
  const canvases = page.locator('canvas[role="img"]');
  await canvases.first().waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForTimeout(2500);
  say(`- canvases on the page: ${await canvases.count()} (1 explorer + 2 comparison expected)`);

  const cmpA = page.getByRole('combobox', { name: 'A', exact: true });
  const cmpB = page.getByRole('combobox', { name: 'B', exact: true });
  const groupLabels = await page
    .locator('optgroup')
    .evaluateAll((nodes) => [...new Set(nodes.map((n) => n.getAttribute('label')))]);
  say(`- picker groups: ${JSON.stringify(groupLabels)}`);
  say(`- A=${await cmpA.inputValue()} B=${await cmpB.inputValue()}`);

  // The two comparison canvases are the 2nd and 3rd on the page; the right-hand one is
  // measured by index through `measureFill(page, 2)`, so only the left needs a locator.
  const left = canvases.nth(1);
  await left.scrollIntoViewIfNeeded();

  // Sync cameras: orbit the LEFT canvas by hand and assert the RIGHT one moved too. The
  // canvases are separate WebGL contexts, so the only thing that can couple them is the
  // controlled `pose` prop — this is the check on it.
  const beforeRight = await measureFill(page, 2).catch(() => null);
  const lb = await left.boundingBox();
  await page.mouse.move(lb.x + lb.width * 0.5, lb.y + lb.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(lb.x + lb.width * 0.5 + 150, lb.y + lb.height * 0.5 + 70, { steps: 14 });
  await page.mouse.up();
  await page.waitForTimeout(2200);
  const afterRight = await measureFill(page, 2).catch(() => null);
  say(
    `- sync cameras ON: right-hand figure box ${JSON.stringify(beforeRight?.box)} -> ` +
      `${JSON.stringify(afterRight?.box)} (moved ${boxDrift(beforeRight, afterRight)}) — ` +
      `${(boxDrift(beforeRight, afterRight) ?? 0) > 0.02 ? 'FOLLOWED the orbit' : 'did NOT follow'}`,
  );

  // One colour-by drives both canvases.
  await page
    .getByRole('combobox', { name: 'colour by (both)', exact: true })
    .selectOption('plddt')
    .catch((e) => say(`  (shared colour-by not found: ${e.message.split('\n')[0]})`));
  await page.waitForTimeout(900);
  say(`- shared colour-by -> ?prot.cmpBy=${new URL(page.url()).searchParams.get('prot.cmpBy')}`);
  await shot('protein-compare', { target: left, above: 210, below: 420 });

  // Switch side B to an off-panel gene and check the exhibit says nothing is painted.
  //
  // The gene has to be taken from a *fold-only* `<optgroup>`, not just "any symbol that is not
  // one of the two on screen": CEP57 is not BUB1B and not TRIP13, and it is also a panel gene,
  // so picking it made this check assert the absence of a callout that correctly was not there.
  const offPanel = await page
    .locator('optgroup[label*="fold only"] option')
    .first()
    .evaluate((node) => node.value)
    .catch(() => null);
  if (offPanel) {
    await cmpB.selectOption(offPanel);
    await page.waitForTimeout(1600);
    const body = await page.content();
    say(
      `- side B = ${offPanel} (off panel): callout present ${/no annotated alleles/i.test(body)}, ` +
        `URL ?prot.cmpB=${new URL(page.url()).searchParams.get('prot.cmpB')}`,
    );
    await shot('protein-compare-offpanel', { target: left, above: 210, below: 420 });
  }

  say(`# cross-gene metrics table`);
  const table = page.getByRole('button', { name: /put .* on side A of the side-by-side/ }).first();
  if ((await table.count()) > 0) {
    await table.scrollIntoViewIfNeeded();
    const rows = await page
      .getByRole('button', { name: /put .* on side A of the side-by-side/ })
      .count();
    say(`- metrics rows with a compare control: ${rows}`);
    const body = await page.content();
    say(`- "n/a — fold only" present: ${/n\/a — fold only/.test(body)}`);
    say(`- "non-coding, no protein" present: ${/non-coding, no protein/.test(body)}`);
    const bars = page.locator('.js-plotly-plot');
    say(`- plotly charts on the page: ${await bars.count()}`);
    const clip = await table.boundingBox();
    await page.screenshot({
      path: path.join(OUT, 'protein-metrics.png'),
      clip: {
        x: 0,
        y: Math.max(0, clip.y - 620),
        width: page.viewportSize().width,
        height: Math.min(1150, page.viewportSize().height),
      },
    });
    say(`  wrote ${path.relative(REPO, path.join(OUT, 'protein-metrics.png'))}`);
  } else {
    say('- metrics table NOT rendered (no compare controls found)');
  }

  say(`# style guide — ${URL_BASE}/style-guide`);
  // Tear the heavy page down first. `/panel` now holds three WebGL contexts and eight Plotly
  // charts; navigating straight off it starved the software renderer badly enough that
  // `goto` hit its 30 s `domcontentloaded` timeout while the route itself served in 60 ms
  // (measured). `about:blank` disposes the contexts before the next navigation starts.
  await page.goto('about:blank');
  await page.waitForTimeout(500);
  await page.goto(`${URL_BASE}/style-guide`, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });
  const demo = page.locator('canvas[role="img"]').first();
  await demo.waitFor({ state: 'visible', timeout: 30_000 });
  await demo.scrollIntoViewIfNeeded();
  await page.waitForTimeout(2000);
  const demoFill = await measureFill(page);
  say(`- canvas fill: ${demoFill ? (demoFill.shorterSide * 100).toFixed(1) + ' %' : 'n/a'}`);
  await shot('viz3d-style-guide');

  // The frame-rate probe runs **last**. Its own rAF chain competes with three's render loop for
  // the software renderer, and a `drawImage` readback issued right after it queues behind
  // several frames — measured: the next `measureFill` never returned. Cost measurement is
  // therefore the final thing this driver does to a page.
  await page.goto('about:blank');
  await page.waitForTimeout(500);
  await page.goto(`${URL_BASE}/panel?gene=${GENE}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60_000,
  });
  await page.locator('canvas[role="img"]').first().waitFor({ state: 'visible', timeout: 30_000 });
  await page.waitForTimeout(2000);
  const fps = await measureFps(page, FPS_MS);
  say(`- frame rate: ${fps.fps} fps (${fps.frames} frames in ${fps.ms} ms, rAF counter, ${GENE})`);

  // Fixture mode points the client at a dead port, so failed API requests are *expected* and
  // are counted apart from the thing that would be a defect: an error thrown by app code.
  const bad = console_.filter((l) => /^(error|pageerror)/.test(l));
  const network = bad.filter((l) => /Failed to load resource|ERR_|net::/.test(l));
  const app = bad.filter((l) => !network.includes(l));
  say(
    `# console: ${console_.length} message(s) — ${network.length} expected fixture-mode request ` +
      `failure(s), ${app.length} from app code`,
  );
  for (const line of app.slice(0, 10)) say(`  ${line}`);

  await browser.close();
  if (app.length > 0) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
  // A locator error thrown mid-run leaves Chromium open, and an open browser keeps node's
  // event loop alive: the process then hangs instead of exiting non-zero. Measured.
  process.exit(1);
});
