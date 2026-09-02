/**
 * Gate 1 — the patient-data guard.
 *
 * CLAUDE.md's one binding rule: "No genomic coordinate is committed anywhere in this
 * repo." Nothing enforces that today except human review at PR time. This test is a
 * mechanical, offline stand-in for that review, run on every `npm test`.
 *
 * WHAT COUNTS AS "COORDINATE-SHAPED"
 * -----------------------------------
 * A genomic coordinate is a (chromosome, position) pair — think of a chromosome as a very
 * long array and a position as an index into it. The repo's own fixtures need *some*
 * numbers in that shape to draw charts offline, so the rule isn't "no numbers next to a
 * chromosome name" — it's "no number that could plausibly be this patient's real variant
 * position." Two kinds of number are declared safe by the project itself and MUST pass:
 *
 *   1. The synthetic ladder: fixtures invent positions as an arithmetic counter — 1000,
 *      2000, 3000, … or 1000000, 2000000, …  A real VCF position is architecturally never
 *      an exact multiple of 1000 (it is wherever the sequencer's read happened to differ
 *      from the reference, no reason to land on a round number) — so "value % 1000 === 0"
 *      is this repo's own chosen marker for "this is a counter, not a measurement," and is
 *      exactly the reasoning `src/fixtures/README.md` and every SYNTHETIC-tagged fixture
 *      file already documents.
 *   2. Reference-genome constants: the 25 GRCh38 chromosome lengths (`chr1` is
 *      248,956,422 bp long, forever, for every human). That is the coordinate *system*,
 *      published and identical for every genome — not a fact about this patient. Any
 *      position that exactly equals one of those lengths is a system constant, not a
 *      leaked call.
 *
 * MUST FAIL, from the mission brief:
 *   - `chr<N>:<8-digit position>` strings — a chromosome name followed by a colon and a
 *     position, with or without a `-end`, comma-grouped or not. (Written schematically
 *     rather than as a literal: this file is itself scanned, and an illustration that
 *     parsed as a coordinate would fail its own gate.)
 *   - a `chrom`/`pos` (or `contig`/`position`, or a `chrom` + `start`/`end` interval) pair
 *     whose position is not on the ladder above.
 *   - any large position that is neither a ladder value nor a known chromosome length —
 *     the brief calls out 8-9 digits because that's the shape most GRCh38 positions take,
 *     but the check below applies the same rule at any magnitude: a real chromosome name
 *     next to a number that isn't the ladder or a length is exactly the shape being
 *     screened for, regardless of how many digits it has.
 *
 * TWO SCANNERS, ONE RULE
 * ----------------------
 *   - `data/*.json` and every other committed JSON file: parsed and walked structurally,
 *     so `{"chrom": "15", "pos": 40200001}` is caught even split across object keys.
 *   - every committed text file (`.ts`, `.tsx`, `.json`, `.md`, …): scanned line-by-line
 *     for a `chrom:pos` or `chrom:start-end` shaped substring, so a coordinate written into
 *     a comment, a doc string, or UI copy is caught too — that shape doesn't require a JSON
 *     object at all.
 *
 * An interval (`start`+`end`, or a `chrom:start-end` string) only requires `start` to sit
 * on the ladder or match a chromosome length; `end` just has to be greater than `start` and
 * within 10 Mb of it. `end` is architecturally a *derived* value (start + a span), and gene
 * spans are public Ensembl facts, not patient-specific — `search-lookups.json`'s
 * `{"start": 1000000, "end": 1100154}` is exactly this shape and is meant to pass.
 *
 * LIMITS — READ BEFORE TRUSTING A GREEN RUN
 * ------------------------------------------
 * This is a shape check, not a lookup against a real annotation database. It cannot know
 * that a *round* number happens to sit inside a real gene's real span (the detector would
 * wave it through), and it cannot verify a flagged number actually IS this patient's call
 * (it only knows the number doesn't match either declared-safe shape). Every failure here
 * is a lead for a human to check, not an automatic verdict — and per the mission brief, a
 * real-looking failure gets reported, never quietly loosened until it goes green.
 */

import { execSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

const APP_ROOT = path.resolve(__dirname, '../..');

// --- the ladder + reference-length rule --------------------------------------

const lengths = JSON.parse(
  readFileSync(path.join(APP_ROOT, 'src/fixtures/data/genome-grch38-lengths.json'), 'utf-8'),
) as Record<string, number>;
const KNOWN_CHROM_LENGTHS = new Set(Object.values(lengths));

/** A real chromosome name — `15`, `chr15`, `X`, `chrY`, `MT`, `M` — case-insensitive. */
const REAL_CHROM_RE = /^(?:chr)?(?:[1-9]|1\d|2[0-2]|x|y|mt|m)$/i;

function isRealChrom(chrom: unknown): chrom is string {
  return typeof chrom === 'string' && REAL_CHROM_RE.test(chrom.trim());
}

/** The repo's own marker for "this is a counter, not a measurement." */
function isRoundSynthetic(n: number): boolean {
  return Number.isInteger(n) && n > 0 && n % 1000 === 0;
}

function isKnownChromLength(n: number): boolean {
  return KNOWN_CHROM_LENGTHS.has(n);
}

/**
 * AUDITED EXCEPTIONS — enumerated, never a widened rule.
 *
 * Two kinds of coordinate in this repo are neither ladder values nor chromosome lengths and
 * are still not patient data. Each is listed here individually, with the reason, so an
 * exception is a decision someone made and can be re-read — not a class of number the
 * detector silently stopped looking at.
 *
 * 1. PUBLIC GENE SPANS. A gene's start and end on GRCh38 are published Ensembl annotation,
 *    identical for every human, and the same category as a chromosome length: the
 *    coordinate system, not a fact about this patient. BUB1B's span is written into the
 *    panel BED, two methodology entries, the dictionary and the Python test suite; the app
 *    quotes it as the worked example of the region query grammar. Removing it would not
 *    protect the patient, it would only make the app's example stop matching the server's.
 * 2. FORMAT ILLUSTRATIONS. Deliberately toy values (five-digit positions, far below any
 *    panel gene) used in UI copy and payload docs to show the shape of a coordinate string.
 *    They are listed exactly, so a real position can never hide among them.
 *
 * A new entry here needs a reason in this comment. Anything not listed is still a failure.
 */
const PUBLIC_GENE_SPANS: ReadonlySet<number> = new Set([
  40140983,
  40241137, // BUB1B, GRCh38 — panel BED, docs/dictionary.md, tests/test_annotate_vep.py
]);

const FORMAT_ILLUSTRATIONS: ReadonlySet<number> = new Set([
  12345,
  12399,
  54321, // toy positions in probe payload docs and the pair comparator's example
]);

/** A position that this repo's own conventions declare safe to commit. */
function isSafePosition(n: number): boolean {
  return (
    isRoundSynthetic(n) ||
    isKnownChromLength(n) ||
    PUBLIC_GENE_SPANS.has(n) ||
    FORMAT_ILLUSTRATIONS.has(n)
  );
}

/** An interval is safe when its anchor is safe and its span is a plausible gene/region size. */
function isSafeInterval(start: number, end: number): boolean {
  return isSafePosition(start) && end > start && end - start <= 10_000_000;
}

interface Violation {
  file: string;
  where: string;
  found: string;
  reason: string;
}

// --- scanner 1: chrom:pos / chrom:start-end shaped substrings, any text file ------------

// Excludes a preceding word char or dot so "127.0.0.1:8900" (an IP:port) never matches —
// that is a string-matching precision fix, not a loosening of the coordinate rule itself.
const REGION_RE =
  /(?<![\w.])(?:chr)?([1-9]|1\d|2[0-2]|X|Y|MT|M)(?!\w)\s*:\s*([\d,]{4,})(?:\s*[-–]\s*([\d,]+))?/gi;

function scanText(file: string, text: string, violations: Violation[]): void {
  const lines = text.split('\n');
  lines.forEach((line, i) => {
    for (const m of line.matchAll(REGION_RE)) {
      const start = Number(m[2].replace(/,/g, ''));
      const end = m[3] ? Number(m[3].replace(/,/g, '')) : undefined;
      const safe = end !== undefined ? isSafeInterval(start, end) : isSafePosition(start);
      if (!safe) {
        violations.push({
          file,
          where: `line ${i + 1}`,
          found: m[0],
          reason:
            end !== undefined ? 'region start not on the ladder' : 'position not on the ladder',
        });
      }
    }
  });
}

// --- scanner 2: structural walk of parsed JSON, chrom + pos/start(/end) siblings --------

const CHROM_KEYS = ['chrom', 'contig', 'chromosome'];
const POS_KEYS = ['pos', 'position'];

function scanJson(file: string, text: string, violations: Violation[]): void {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return; // not JSON despite the extension — nothing to structurally walk
  }
  walk(data, '$', file, violations);
}

function walk(node: unknown, keypath: string, file: string, violations: Violation[]): void {
  if (Array.isArray(node)) {
    node.forEach((v, i) => walk(v, `${keypath}[${i}]`, file, violations));
    return;
  }
  if (node === null || typeof node !== 'object') return;

  const obj = node as Record<string, unknown>;
  const lower = new Map(Object.keys(obj).map((k) => [k.toLowerCase(), k]));
  const chromKey = CHROM_KEYS.map((k) => lower.get(k)).find((k) => k !== undefined);
  const chrom = chromKey ? obj[chromKey] : undefined;

  if (isRealChrom(chrom)) {
    const posKey = POS_KEYS.map((k) => lower.get(k)).find((k) => k !== undefined);
    const startKey = lower.get('start');
    const endKey = lower.get('end');

    if (posKey !== undefined && typeof obj[posKey] === 'number') {
      const pos = obj[posKey] as number;
      if (!isSafePosition(pos)) {
        violations.push({
          file,
          where: `${keypath}.${posKey} (chrom ${String(chrom)})`,
          found: String(pos),
          reason: 'position not on the ladder and not a chromosome length',
        });
      }
    }
    if (startKey !== undefined && typeof obj[startKey] === 'number') {
      const start = obj[startKey] as number;
      const end = endKey !== undefined ? obj[endKey] : undefined;
      const safe = typeof end === 'number' ? isSafeInterval(start, end) : isSafePosition(start);
      if (!safe) {
        violations.push({
          file,
          where: `${keypath}.${startKey}${typeof end === 'number' ? `/${endKey}` : ''} (chrom ${String(chrom)})`,
          found: typeof end === 'number' ? `${start}-${end}` : String(start),
          reason: 'interval start not on the ladder, or span implausibly large',
        });
      }
    }
  }

  for (const [k, v] of Object.entries(obj)) walk(v, `${keypath}.${k}`, file, violations);
}

// --- run both scanners over every committed file under src/ -----------------------------

function committedSrcFiles(): string[] {
  const out = execSync('git ls-files src', { cwd: APP_ROOT, encoding: 'utf-8' });
  return out.split('\n').filter(Boolean);
}

function scanAll(): Violation[] {
  const violations: Violation[] = [];
  for (const rel of committedSrcFiles()) {
    const abs = path.join(APP_ROOT, rel);
    const text = readFileSync(abs, 'utf-8');
    scanText(rel, text, violations);
    if (rel.endsWith('.json')) scanJson(rel, text, violations);
  }
  return violations;
}

function formatViolations(violations: Violation[]): string {
  return violations.map((v) => `  ${v.file} @ ${v.where}: "${v.found}" — ${v.reason}`).join('\n');
}

describe('patient-data guard', () => {
  it('commits no coordinate-shaped content outside the declared synthetic ladder', () => {
    const violations = scanAll();
    expect(violations, `\n${formatViolations(violations)}\n`).toEqual([]);
  });
});

describe('patient-data guard — detector unit checks', () => {
  it('passes the documented 1,000,000-based ladder', () => {
    expect(isSafePosition(1_000_000)).toBe(true);
    expect(isSafePosition(2_000_000)).toBe(true);
    expect(isSafePosition(900_000)).toBe(true); // sub-million counter, e.g. panel-annotations-extra
  });

  it('passes a known GRCh38 chromosome length', () => {
    expect(isSafePosition(248_956_422)).toBe(true); // chr1
    expect(isKnownChromLength(101_991_189)).toBe(true); // chr15
  });

  it('fails a position one off the ladder', () => {
    expect(isSafePosition(1_000_001)).toBe(false);
  });

  it('fails an 8-digit position that is neither ladder nor chromosome length', () => {
    expect(isSafePosition(40_200_001)).toBe(false);
  });

  it('treats a fake chromosome token ("00", "0") as out of scope, not exempt-by-loophole', () => {
    // These aren't real contigs, so no real coordinate system applies to them — but the
    // walk() structural scanner already requires isRealChrom() before checking a position,
    // so this documents the boundary rather than re-testing walk() directly.
    expect(isRealChrom('00')).toBe(false);
    expect(isRealChrom('0')).toBe(false);
    expect(isRealChrom('15')).toBe(true);
    expect(isRealChrom('chrX')).toBe(true);
  });

  it('accepts an interval whose end is a plausible derived span, not just the start', () => {
    expect(isSafeInterval(1_000_000, 1_100_154)).toBe(true); // BUB1B's real span, offset onto the ladder
    expect(isSafeInterval(40_200_001, 40_200_050)).toBe(false); // start itself isn't safe
  });
});
