#!/usr/bin/env node
/**
 * Gate 4 — bundle budget.
 *
 * Nothing today stops a change from quietly growing the *initial payload* — the JS the browser
 * has to download and run before the app can paint anything, as opposed to a page's own
 * chunk (fetched only when that page is visited) or Plotly's chunk (fetched only when a
 * chart actually mounts). This repo already lived through exactly that regression once:
 * `src/fixtures/README.md` records the entry chunk shrinking from 296.89 kB / 96.87 kB to
 * 236.44 kB / 77.19 kB raw/gzip when the fixture rows were moved out of it and into
 * `import()`ed JSON files. This script is the mechanical gate that catches it happening
 * again — by any change, not just a fixture one.
 *
 * WHAT THIS SCRIPT DOES
 *   1. Runs `pnpm run build` (skip with `--skip-build` if the caller already has a fresh
 *      `dist/`), producing the exact artifact a real deploy would ship.
 *   2. Reads the entry chunk's filename out of `dist/index.html`'s `<script type="module">`
 *      tag — not guessed from a naming convention, so a build-config change that renames
 *      the entry can't silently point this check at the wrong file.
 *   3. Measures every emitted `.js`/`.css` chunk's raw size (`fs.statSync`) and gzip size
 *      (`zlib.gzipSync`, Node's own gzip — no external tool, no assumption about what
 *      compression a CDN will apply, just a fixed, reproducible number to budget against).
 *   4. Checks the budgets below, prints a table of every chunk either way (so the numbers
 *      are visible even on a pass), and exits non-zero with a clear diff on any failure.
 *
 * RE-BLESSING THE BUDGETS
 * Run `node tools/bundle-budget.mjs`, read the reported entry raw/gzip numbers from a build
 * you trust (clean tree, `pnpm install --frozen-lockfile` deps), and update BUDGETS below with a comment
 * recording the date and why the new number is acceptable. Never move a budget to make a
 * regression pass without that explicit, dated justification — the whole point of this gate
 * is that "the bundle grew" should be a conversation, not a silent fact.
 */

import { execSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const APP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DIST = path.join(APP_ROOT, 'dist');
const ASSETS = path.join(DIST, 'assets');
const FIXTURE_DATA_DIR = path.join(APP_ROOT, 'src/fixtures/data');
const PAGES_DIR = path.join(APP_ROOT, 'src/pages');

// --- the budget, in one clearly-marked block ---------------------------------------------
//
// WHY THIS MEASURES MORE THAN THE ENTRY CHUNK
// The first version budgeted the entry chunk alone. That is not what a browser downloads
// before it can paint: dist/index.html also carries <link rel="modulepreload"> tags, and
// the bundler is free to move code out of the entry into those. It did exactly that on
// 2026-09-02 — the entry "shrank" from 236 kB to 160 kB while a preloaded QueryState
// chunk appeared at 87 kB, so the entry-only gate reported an improvement for a payload
// that had actually grown. The budget is therefore the SUM of the entry chunk and every
// chunk index.html preloads: the number that survives a chunking change.
//
// Measured 2026-09-02 against a clean `pnpm run build`: 244.50 kB raw / 78.91 kB gzip
// across 2 initial files. The commit before the footer landed measured 237.02 / 76.63 in
// a clean worktree; the footer's live dependency-status query is the +7.5 kB raw.
// Budgets give ~6% headroom — enough for incidental churn, not enough to hide a real
// regression.
//
// Re-blessed 2026-09-03: 267.65 kB raw / 85.06 kB gzip across 3 initial files. HEAD before
// the change measured 259.58 / 83.11 in a clean worktree; the +8 kB raw is the information
// architecture that now lives in the entry chunk — the two-tier header (section tabs + the
// active section's pages), the manifest-driven page header and journey footer, and the
// footer sitemap (`src/app/PageFrame.tsx`, `src/components/{Header,PageHeader,journey}.tsx`).
// That is shell, so it belongs in first paint; no page code moved into the entry.
//
// Re-blessed 2026-09-03 (later the same day): 280.52 kB raw / 89.92 kB gzip. The in-page
// navigation joined the shell — the section registry, the "On this page" rail, the jump
// select and the ⌘K button. The palette's dialog body is a lazy chunk (PaletteDialog, ~3.7 kB)
// fetched on first open, so only the hotkey and the button ride in first paint.
const BUDGETS = Object.freeze({
  INITIAL_RAW_BYTES: 290_000,
  INITIAL_GZIP_BYTES: 92_000,
});

const KB = (bytes) => `${(bytes / 1000).toFixed(2)} kB`;

function buildIfNeeded() {
  if (process.argv.includes('--skip-build')) {
    console.log('--skip-build passed: using whatever is already in dist/');
    return;
  }
  console.log('> pnpm run build');
  execSync('pnpm run build', { cwd: APP_ROOT, stdio: 'inherit' });
}

/**
 * Every JS file dist/index.html makes the browser fetch before first paint: the module
 * entry plus each modulepreload. Read out of the HTML rather than guessed from filenames,
 * so a chunking or naming change cannot point this gate at the wrong set.
 */
function findInitialFiles() {
  const htmlPath = path.join(DIST, 'index.html');
  if (!existsSync(htmlPath)) {
    console.error(`No dist/index.html — did the build run? (looked in ${DIST})`);
    process.exit(1);
  }
  const html = readFileSync(htmlPath, 'utf-8');
  const entry = findEntryFile();
  const preloads = [...html.matchAll(/rel="modulepreload"[^>]+href="[^"]*\/assets\/([^"]+\.js)"/g)]
    .map((m) => m[1])
    .filter((f) => f !== entry);
  return { entry, initial: [entry, ...preloads] };
}

function findEntryFile() {
  const htmlPath = path.join(DIST, 'index.html');
  if (!existsSync(htmlPath)) {
    console.error(`No dist/index.html — did the build run? (looked in ${DIST})`);
    process.exit(1);
  }
  const html = readFileSync(htmlPath, 'utf-8');
  // The entry is whatever dist/index.html actually loads as its module-type <script>, not
  // a guessed naming pattern — a build-config change that renames the entry chunk can't
  // silently point this check at the wrong file.
  const match = html.match(/<script[^>]+type="module"[^>]+src="[^"]*\/assets\/([^"]+\.js)"/);
  if (!match) {
    console.error('Could not find a module <script src="/assets/*.js"> tag in dist/index.html.');
    process.exit(1);
  }
  return match[1];
}

/**
 * Does any page actually import the 3D module? Source-level check (a plain string scan of
 * src/pages/**), because "three must have its own chunk" is only a meaningful assertion once
 * something renders a 3D exhibit.
 */
function importsViz3d() {
  const stack = [PAGES_DIR];
  while (stack.length > 0) {
    const dir = stack.pop();
    if (!existsSync(dir)) continue;
    for (const item of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, item.name);
      if (item.isDirectory()) stack.push(full);
      else if (/\.tsx?$/.test(item.name) && /from '.*viz3d/.test(readFileSync(full, 'utf-8'))) {
        return true;
      }
    }
  }
  return false;
}

function measureAssets() {
  const files = readdirSync(ASSETS).filter((f) => f.endsWith('.js') || f.endsWith('.css'));
  return files
    .map((file) => {
      const buf = readFileSync(path.join(ASSETS, file));
      return { file, raw: buf.length, gzip: gzipSync(buf).length };
    })
    .sort((a, b) => b.raw - a.raw);
}

/**
 * Defense-in-depth beyond the raw-size budget: re-serialize every committed fixture
 * `data/*.json` file the same way Vite's JSON transform would, and check the exact text
 * doesn't appear inside the entry chunk. This is a shape check, not a proof — a fixture
 * payload embedded with different key order or spread across several literals would slip
 * past it — but it directly verifies the specific rule ("no fixture payload in the entry
 * chunk"), rather than only inferring it from a size threshold.
 */
function findInlinedFixturePayloads(entryText) {
  if (!existsSync(FIXTURE_DATA_DIR)) return [];
  const hits = [];
  for (const file of readdirSync(FIXTURE_DATA_DIR).filter((f) => f.endsWith('.json'))) {
    const raw = readFileSync(path.join(FIXTURE_DATA_DIR, file), 'utf-8');
    let minified;
    try {
      minified = JSON.stringify(JSON.parse(raw));
    } catch {
      continue;
    }
    // Skip trivially short payloads (e.g. "{}") where a substring match would be noise.
    if (minified.length > 20 && entryText.includes(minified)) hits.push(file);
  }
  return hits;
}

function printTable(rows, entryFile) {
  console.log('\nTop chunks by raw size:');
  const top = rows.slice(0, 15);
  const nameWidth = Math.max(...top.map((r) => r.file.length), 20) + 2;
  console.log('file'.padEnd(nameWidth) + 'raw'.padStart(12) + 'gzip'.padStart(12) + '  role');
  for (const r of top) {
    const role =
      r.file === entryFile
        ? 'entry'
        : /plotly/i.test(r.file)
          ? 'plotly'
          : /three/i.test(r.file)
            ? 'three'
            : '';
    console.log(
      r.file.padEnd(nameWidth) + KB(r.raw).padStart(12) + KB(r.gzip).padStart(12) + `  ${role}`,
    );
  }
  console.log(`(${rows.length} chunk(s) total)`);
}

function main() {
  buildIfNeeded();

  if (!existsSync(ASSETS)) {
    console.error(`No dist/assets directory found at ${ASSETS} after build.`);
    process.exit(1);
  }

  const { entry: entryFile, initial } = findInitialFiles();
  const rows = measureAssets();
  const entry = rows.find((r) => r.file === entryFile);
  const problems = [];

  const initialRows = initial.map((file) => {
    const row = rows.find((r) => r.file === file);
    if (!row)
      problems.push(`initial chunk "${file}" (from dist/index.html) not found in dist/assets`);
    return row;
  });
  const initialRaw = initialRows.reduce((sum, r) => sum + (r?.raw ?? 0), 0);
  const initialGzip = initialRows.reduce((sum, r) => sum + (r?.gzip ?? 0), 0);

  if (!entry) {
    problems.push(`entry chunk "${entryFile}" (from dist/index.html) not found in dist/assets`);
  }
  if (initialRaw > BUDGETS.INITIAL_RAW_BYTES) {
    problems.push(
      `initial payload raw ${KB(initialRaw)} exceeds the ${KB(BUDGETS.INITIAL_RAW_BYTES)} budget ` +
        `(over by ${KB(initialRaw - BUDGETS.INITIAL_RAW_BYTES)})`,
    );
  }
  if (initialGzip > BUDGETS.INITIAL_GZIP_BYTES) {
    problems.push(
      `initial payload gzip ${KB(initialGzip)} exceeds the ${KB(BUDGETS.INITIAL_GZIP_BYTES)} budget ` +
        `(over by ${KB(initialGzip - BUDGETS.INITIAL_GZIP_BYTES)})`,
    );
  }
  for (const file of initial) {
    if (/plotly/i.test(file)) problems.push(`initial chunk "${file}" matches /plotly/i`);
    // three is loaded by exactly one module (src/viz3d/core/loadThree.ts) with a dynamic
    // import, so it must never appear in the set the browser fetches before first paint.
    // What it costs when it *is* fetched, measured on this checkout (three 0.185.1,
    // 2026-09-03): the emitted `three.module-*.js` chunk is 529.85 kB raw / 131.78 kB gzip
    // — the number this script prints in the table above. (The 365.55 kB raw / 87.12 kB gzip
    // often quoted for three is its prebuilt `three.module.min.js`, which this app never
    // fetches; rolldown bundles and minifies three's ESM sources itself.)
    if (/three/i.test(file)) problems.push(`initial chunk "${file}" matches /three/i`);
  }

  if (/plotly/i.test(entryFile)) {
    problems.push(`entry chunk "${entryFile}" itself matches /plotly/i`);
  }
  const plotlyChunks = rows.filter((r) => /plotly/i.test(r.file));
  if (plotlyChunks.length === 0) {
    problems.push(
      'no emitted chunk matches /plotly/i — Plotly may have been inlined elsewhere or removed',
    );
  }

  // The mirror guard for three: if any page reaches src/viz3d, a `three` chunk must exist —
  // its absence would mean the library got inlined into a page chunk (which the initial-set
  // check above cannot see) or dropped. Conditioned on a real consumer so the gate stays
  // honest if viz3d is ever removed, rather than asserting a chunk for code nobody imports.
  if (importsViz3d() && rows.filter((r) => /three/i.test(r.file)).length === 0) {
    problems.push(
      'a page imports src/viz3d but no emitted chunk matches /three/i — three may have been ' +
        'inlined into a page chunk instead of dynamically imported by viz3d/core/loadThree.ts',
    );
  }

  // Both content checks run over every initial chunk: code the bundler moved out of the
  // entry into a preloaded sibling is still downloaded before first paint.
  for (const file of initial) {
    const chunkPath = path.join(ASSETS, file);
    if (!existsSync(chunkPath)) continue;
    const text = readFileSync(chunkPath, 'utf-8');
    if (/plotly\.js/i.test(text)) {
      problems.push(`initial chunk "${file}" contains a "plotly.js" signature string`);
    }
    for (const fixture of findInlinedFixturePayloads(text)) {
      problems.push(
        `initial chunk "${file}" contains the full payload of fixtures/data/${fixture}`,
      );
    }
  }

  printTable(rows, entryFile);

  if (problems.length > 0) {
    console.error('\nBUNDLE BUDGET FAILED:');
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }

  console.log(
    `\nBundle budget OK. First paint downloads ${initial.length} JS file(s): ` +
      `${KB(initialRaw)} raw / ${KB(initialGzip)} gzip ` +
      `(budget ${KB(BUDGETS.INITIAL_RAW_BYTES)} / ${KB(BUDGETS.INITIAL_GZIP_BYTES)}).\n` +
      `  entry ${entryFile}: ${KB(entry.raw)} raw / ${KB(entry.gzip)} gzip` +
      (initial.length > 1 ? `\n  preloaded: ${initial.slice(1).join(', ')}` : ''),
  );
}

main();
