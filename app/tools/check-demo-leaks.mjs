#!/usr/bin/env node
/**
 * Fail the demo build if anything real reached it: the proband's id, its delivered
 * phenotype terms, headline counts of the real callset, infrastructure hosts, or any
 * secret value from the repo-root `.env`. Usage: node tools/check-demo-leaks.mjs dist-demo
 */
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const dir = process.argv[2] ?? 'dist-demo';

const denied = [
  'PROBAND01',
  'proband01',
  // the real proband's delivered HPO terms (the demo uses the public MVA1 annotation)
  'HP:0000121',
  'HP:0001508',
  'HP:0003202',
  'HP:0001622',
  'HP:0001518',
  'HP:0200067',
  'Nephrocalcinosis',
  'Recurrent spontaneous abortion',
  // headline counts of the real callset and read delivery
  '5012204',
  '4740790',
  '1071835104',
  '5,012,204',
  '271,414',
  '1,071,835,104',
  '136,586,642',
  // infrastructure
  'contaboserver',
  'vmi2938918',
  '38.242.217.131',
  '/api/proxy',
];

const secrets = new Set();
const envFile = new URL('../../.env', import.meta.url);
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, 'utf8').split('\n')) {
    const m = line.match(/^([A-Z_]*(?:TOKEN|PASSWORD|SECRET|KEY)[A-Z_]*)=(.{6,})$/);
    if (m) {
      denied.push(m[2].trim());
      secrets.add(m[2].trim());
    }
  }
}

const files = (d) =>
  readdirSync(d).flatMap((f) =>
    statSync(join(d, f)).isDirectory() ? files(join(d, f)) : [join(d, f)],
  );

let hits = 0;
for (const file of files(dir)) {
  const text = readFileSync(file, 'latin1');
  for (const needle of denied) {
    if (text.includes(needle)) {
      const label = secrets.has(needle) ? '<secret from .env>' : needle;
      console.error(`leak: ${label} in ${file}`);
      hits++;
    }
  }
}
if (hits) {
  console.error(`demo leak check: ${hits} hit(s) — do not share ${dir}`);
  process.exit(1);
}
console.log(`demo leak check: clean (${denied.length} patterns, ${files(dir).length} files)`);
