/**
 * The pair comparator's rules, as pure functions over the `/api/panel/het-pairs` payload.
 *
 * Two things live here and nothing else: **which two variants are selected** (index
 * arithmetic over the endpoint's `variants` array, which is both axes of its pair matrix),
 * and **how the pair is handed to the probe builder** (the query-parameter encoding).
 *
 * The phase rule is deliberately *not* here. It is owned by
 * `mva.pipeline.compound_het.classify_phase`, applied server-side in `mva.viz.phase`, and
 * shipped as the payload's `pairs` list. This module only looks a cell up in that list; a
 * second copy of "same PID, same PGT means cis" in the browser is exactly the drift the
 * repo's one-owner rule forbids. A pair the server did not resolve is *unknown*, which is
 * the honest default and the common case (~99.7 % of BUB1B's grid).
 *
 * **Encode here, decode there.** `encodePairParam` writes `chrom:pos:ref:alt+chrom:pos:ref:alt`
 * — deliberately the same grammar the probe builder's free-entry box already parses, so the
 * reader is `probePayload.parseLines`, which owns that grammar, and there is no second
 * parser to drift from it.
 */

import type { PanelHetPair, PanelHetVariant } from '../../api/types';
import type { VariantRef } from '../../api/types/probebuild';
import { C } from '../../lib/palette';

// --- selection ---------------------------------------------------------------

/**
 * Read one selection index out of the URL. Junk, out of range, or absent ⇒ `fallback`.
 *
 * The empty string is checked first and on purpose: `Number('')` is `0`, so without it an
 * absent parameter would silently read as "the first variant" instead of as the default.
 */
export function pickIndex(raw: string, count: number, fallback: number): number {
  if (raw.trim() === '') return fallback;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 0 || n >= count) return fallback;
  return n;
}

/**
 * The two variants the exhibit opens on: the first two that are both rare and
 * protein-altering, because that is the only pair shape a recessive hypothesis allows.
 * Falls back to the first two rows when the gene has fewer than two such alleles — an
 * unhelpful default beats an empty card.
 */
export function defaultSelection(variants: PanelHetVariant[]): [number, number] {
  const candidates = variants
    .map((v, i) => ({ v, i }))
    .filter(({ v }) => v.is_rare_recessive === true && v.is_protein_altering === true)
    .map(({ i }) => i);
  if (candidates.length >= 2) return [candidates[0], candidates[1]];
  return [0, Math.min(1, variants.length - 1)];
}

/** The primary handle for a variant: what it does, not where it is. */
export function variantLabel(v: PanelHetVariant): string {
  if (!v.annotated) return 'not annotated';
  const consequence = (v.consequence ?? 'unknown consequence')
    .replace(/_variant$/, '')
    .replace(/_/g, ' ');
  return v.rsid ? `${consequence} · ${v.rsid}` : consequence;
}

/** Dropdown text. Position stays out of it — it belongs in the card's detail rows. */
export function optionLabel(v: PanelHetVariant, index: number): string {
  const vaf = v.vaf === null ? 'VAF —' : `VAF ${v.vaf.toFixed(2)}`;
  const multi = v.gt === '1/2' ? ` · ${v.gt} allele ${v.allele_ix}` : '';
  return `#${index + 1}  ${variantLabel(v)} · ${vaf}${multi}`;
}

/** `15:12345 C>T` — the detail line, and the only place a coordinate is rendered. */
export const coordinate = (v: PanelHetVariant): string =>
  `${v.chrom}:${v.pos} ${v.ref}>${v.alt}`;

export const toRef = (v: PanelHetVariant): VariantRef => ({
  chrom: v.chrom,
  pos: v.pos,
  ref: v.ref,
  alt: v.alt,
});

// --- the verdict -------------------------------------------------------------

export type PairPhase = 'trans' | 'auto-trans' | 'cis' | 'unknown';

export interface PairVerdict {
  phase: PairPhase;
  headline: string;
  color: string;
  /** What the phase call means for the hypothesis, in one sentence. */
  meaning: string;
}

/**
 * The server's cell for this pair, or null. `i`/`j` index the payload's `variants` in the
 * order it arrived, and the list is upper-triangular, so the lookup normalises the order.
 */
export function lookupPair(pairs: PanelHetPair[], i: number, j: number): PanelHetPair | null {
  const lo = Math.min(i, j);
  const hi = Math.max(i, j);
  return pairs.find((p) => Math.min(p.i, p.j) === lo && Math.max(p.i, p.j) === hi) ?? null;
}

const UNKNOWN: PairVerdict = {
  phase: 'unknown',
  headline: 'unknown phase — neither proven nor excluded',
  color: C.absent,
  meaning:
    'Physical (read-backed) phasing needs both alleles on one read pair, which reaches about 300 bp. ' +
    'Beyond that the callset says nothing about which copy each allele sits on, so this pair stays live: ' +
    'it is not evidence for a compound heterozygote, and it is not evidence against one.',
};

export function pairVerdict(pairs: PanelHetPair[], i: number, j: number): PairVerdict {
  const cell = lookupPair(pairs, i, j);
  if (!cell) return UNKNOWN;
  if (cell.phase === 'cis') {
    return {
      phase: 'cis',
      headline: 'resolved cis — excluded',
      color: C.broken,
      meaning:
        'Both alleles sit on the same copy of the chromosome, so the other copy is intact. ' +
        'A recessive gene needs both copies broken, so this pair cannot be the cause. Do not probe it.',
    };
  }
  if (cell.auto) {
    return {
      phase: 'auto-trans',
      headline: 'auto-trans — proven by the 1/2 genotype alone',
      color: C.decision,
      meaning:
        'These are the two different ALT alleles of one multi-allelic record: one copy of each, so one ' +
        'per haplotype. Compound heterozygosity stated by the genotype with no phasing involved — a ' +
        'different kind of evidence from a phased trans call, and worth reading as such.',
    };
  }
  return {
    phase: 'trans',
    headline: 'resolved trans — a proven compound heterozygote',
    color: C.good,
    meaning:
      'Read-backed phasing put the two alleles on opposite copies of the chromosome. Both copies of the ' +
      'gene carry a different broken allele, which is exactly the configuration a recessive disease needs.',
  };
}

// --- is this pair worth spending a rank on? ----------------------------------

export interface PairCheck {
  bothRare: boolean;
  bothProteinAltering: boolean;
  notCis: boolean;
  distinct: boolean;
  /** All four, which is the bar for putting the pair in a submission row. */
  worth: boolean;
}

export function pairCheck(
  a: PanelHetVariant,
  b: PanelHetVariant,
  verdict: PairVerdict,
  distinct: boolean,
): PairCheck {
  const bothRare = a.is_rare_recessive === true && b.is_rare_recessive === true;
  const bothProteinAltering = a.is_protein_altering === true && b.is_protein_altering === true;
  const notCis = verdict.phase !== 'cis';
  return {
    bothRare,
    bothProteinAltering,
    notCis,
    distinct,
    worth: bothRare && bothProteinAltering && notCis && distinct,
  };
}

// --- the hand-off ------------------------------------------------------------

/** The query parameter `/probes` reads a staged pair from. */
export const PAIR_PARAM = 'pair';

const encodeVariant = (v: VariantRef): string => `${v.chrom}:${v.pos}:${v.ref}:${v.alt}`;

/**
 * `chrom:pos:ref:alt+chrom:pos:ref:alt` — one row, two alleles.
 *
 * The `+` is the pair join the builder's free-entry grammar already uses. It must be
 * percent-encoded in a URL (a bare `+` in a query string decodes to a space), which
 * {@link probesPairHref} does.
 */
export const encodePairParam = (a: VariantRef, b: VariantRef): string =>
  `${encodeVariant(a)}+${encodeVariant(b)}`;

/** The link that stages this pair as a row on the probe builder. */
export const probesPairHref = (a: VariantRef, b: VariantRef): string =>
  `/probes?${PAIR_PARAM}=${encodeURIComponent(encodePairParam(a, b))}`;
