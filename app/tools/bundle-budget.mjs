#!/usr/bin/env node
/**
 * Gate 4 — bundle budget.
 *
 * Nothing today stops a change from quietly growing the *entry* chunk — the JS the browser
 * has to download and run before the app can paint anything, as opposed to a page's own
 * chunk (fetched only when that page is visited) or Plotly's chunk (fetched only when a
 * chart actually mounts). This repo already lived through exactly that regression once:
 * `src/fixtures/README.md` records the entry chunk shrinking from 296.89 kB / 96.87 kB to
 * 236.44 kB / 77.19 kB raw/gzip when the fixture rows were moved out of it and into
 * `import()`ed JSON files. This script is the mechanical gate that catches it happening
 * again — by any change, not just a fixture one.
 *
 * WHAT THIS SCRIPT DOES
 *   1. Runs `npm run build` (skip with `--skip-build` if the caller already has a fresh
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
 * you trust (clean tree, `npm ci`-equivalent deps), and update BUDGETS below with a comment
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

// --- the budget, in one clearly-marked block ---------------------------------------------
//
// Measured 2026-09-02 against a clean `npm run build` on this commit: entry chunk was
// 236.44 kB raw / 77.19 kB gzip (see `src/fixtures/README.md`'s own before/after table,
// which independently confirms the same raw figure). Budgets below give ~3.5 kB raw and
// ~3 kB gzip of headroom over that measurement — enough to absorb incidental churn, not
// enough to hide a real regression.
const BUDGETS = Object.freeze({
  ENTRY_RAW_BYTES: 245_000,
  ENTRY_GZIP_BYTES: 80_000,
});

const KB = (bytes) => `${(bytes / 1000).toFixed(2)} kB`;

function buildIfNeeded() {
  if (process.argv.includes('--skip-build')) {
    console.log('--skip-build passed: using whatever is already in dist/');
    return;
  }
  console.log('> npm run build');
  execSync('npm run build', { cwd: APP_ROOT, stdio: 'inherit' });
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
    const role = r.file === entryFile ? 'entry' : /plotly/i.test(r.file) ? 'plotly' : '';
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

  const entryFile = findEntryFile();
  const rows = measureAssets();
  const entry = rows.find((r) => r.file === entryFile);
  const problems = [];

  if (!entry) {
    problems.push(`entry chunk "${entryFile}" (from dist/index.html) not found in dist/assets`);
  } else {
    if (entry.raw > BUDGETS.ENTRY_RAW_BYTES) {
      problems.push(
        `entry chunk raw ${KB(entry.raw)} exceeds the ${KB(BUDGETS.ENTRY_RAW_BYTES)} budget ` +
          `(over by ${KB(entry.raw - BUDGETS.ENTRY_RAW_BYTES)})`,
      );
    }
    if (entry.gzip > BUDGETS.ENTRY_GZIP_BYTES) {
      problems.push(
        `entry chunk gzip ${KB(entry.gzip)} exceeds the ${KB(BUDGETS.ENTRY_GZIP_BYTES)} budget ` +
          `(over by ${KB(entry.gzip - BUDGETS.ENTRY_GZIP_BYTES)})`,
      );
    }
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

  if (entry) {
    const entryText = readFileSync(path.join(ASSETS, entryFile), 'utf-8');
    if (/plotly\.js/i.test(entryText)) {
      problems.push(
        'entry chunk text contains a "plotly.js" signature string — Plotly code may be inlined',
      );
    }
    const inlined = findInlinedFixturePayloads(entryText);
    for (const file of inlined) {
      problems.push(`entry chunk contains the full serialized payload of fixtures/data/${file}`);
    }
  }

  printTable(rows, entryFile);

  if (problems.length > 0) {
    console.error('\nBUNDLE BUDGET FAILED:');
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }

  console.log(
    `\nBundle budget OK. Entry: ${KB(entry.raw)} raw / ${KB(entry.gzip)} gzip ` +
      `(budget ${KB(BUDGETS.ENTRY_RAW_BYTES)} / ${KB(BUDGETS.ENTRY_GZIP_BYTES)}).`,
  );
}

main();
