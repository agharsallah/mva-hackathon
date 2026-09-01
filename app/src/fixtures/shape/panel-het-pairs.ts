import type { PanelHetPair, PanelHetPairs, PanelHetVariant, VariantImpact } from '../../api/types';
import { prng } from '../prng';
import { rows } from '../loader';

/**
 * FIXTURE — the compound-heterozygous pair matrix. `data/panel-het-pairs.json` carries the
 * seven planted rows and the three resolved pairs; everything below is the synthesis that
 * fills the rest of the grid around them.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY.*** The live endpoint returns real patient
 * coordinates and this repo commits none, so positions here are a plain arithmetic
 * ladder (1000, 1040, 2000, …). Only the *shape* is faithful.
 *
 * MEASURED, and the reason the shape is what it is (`ideation/data-findings.md` §2.4,
 * `methodology/006`): on the real BUB1B locus physical phasing resolves **3 trans and 2
 * cis of 1,653 pairs** — 99.7 % unknown. A fixture that resolved a comfortable fraction
 * of its grid would teach the reader the opposite of what the data says, so this one
 * plants exactly three resolved pairs and leaves everything else unknown.
 *
 * The five states the exhibit has to render are all present by construction:
 *
 * | index | state |
 * |---|---|
 * | 0 × 1 | trans — one phase set, opposite haplotypes |
 * | 2 × 3 | cis — one phase set, the same haplotype |
 * | 4 × 5 | auto-trans — the two ALTs of one `1/2` record |
 * | 6 | a het allele VEP never annotated (every flag null) |
 * | everything else | unknown, shaded by rarity |
 *
 * Exactly two alleles are rare **and** protein-altering, matching what the real BUB1B
 * locus leaves after that filter — so the collapsed 2 × 2 state is exercised offline.
 *
 * Default gene when none is given: BUB1B.
 */

const CONSEQUENCES: [string, VariantImpact][] = [
  ['missense_variant', 'MODERATE'],
  ['synonymous_variant', 'LOW'],
  ['intron_variant', 'MODIFIER'],
  ['splice_region_variant', 'LOW'],
  ['3_prime_UTR_variant', 'MODIFIER'],
];

interface Seed {
  pos: number;
  alt: string;
  gt?: string;
  allele_ix?: number;
  pgt?: string | null;
  pid?: string | null;
  consequence?: string;
  impact?: VariantImpact;
  af?: number | null;
  annotated?: boolean;
  rsid?: string | null;
  clin_sig?: string | null;
}

interface PlantedData {
  planted: Seed[];
  resolved: PanelHetPair[];
}

function row(gene: string, seed: Seed): PanelHetVariant {
  const annotated = seed.annotated !== false;
  const impact = annotated ? (seed.impact ?? 'MODIFIER') : null;
  const af = annotated ? (seed.af ?? null) : null;
  return {
    gene,
    chrom: '00', // SYNTHETIC — not a contig
    pos: seed.pos, // SYNTHETIC — a counter, not a coordinate
    ref: 'C',
    alt: seed.alt,
    allele_ix: seed.allele_ix ?? 1,
    gt: seed.gt ?? '0/1',
    qual: 600,
    dp: 40,
    vaf: 0.5,
    pgt: seed.pgt ?? null,
    pid: seed.pid ?? null,
    rsid: annotated ? (seed.rsid ?? null) : null,
    consequence: annotated ? (seed.consequence ?? 'intron_variant') : null,
    impact,
    gnomad_af: af,
    gnomad_af_grpmax: af,
    clin_sig: annotated ? (seed.clin_sig ?? null) : null,
    annotated,
    is_rare_recessive: annotated ? af === null || af < 0.01 : null,
    is_protein_altering: annotated ? impact === 'HIGH' || impact === 'MODERATE' : null,
  };
}

/**
 * One gene's matrix. `n` het alleles: the seven planted ones, then filler that is always
 * unknown and never both rare and protein-altering, so the toggle collapses to exactly
 * the two planted rare protein-altering alleles (indices 0 and 1).
 */
export async function panelHetPairsFixture(gene: string): Promise<PanelHetPairs> {
  const { planted, resolved } = await rows<PlantedData>('panel-het-pairs');
  const rand = prng(gene.split('').reduce((a, c) => a + c.charCodeAt(0), 11));
  const n = Math.max(planted.length, 8 + Math.floor(rand() * 14));
  const variants = planted.map((seed) => row(gene, seed));

  for (let i = variants.length; i < n; i++) {
    const [consequence, impact] = CONSEQUENCES[Math.floor(rand() * CONSEQUENCES.length)];
    // Filler is either common or non-coding, never both rare and protein-altering.
    const af = impact === 'HIGH' || impact === 'MODERATE' ? 0.05 + rand() * 0.3 : rand() * 0.02;
    variants.push(
      row(gene, {
        pos: 4000 + i * 400, // SYNTHETIC — a counter, not a coordinate
        alt: ['A', 'C', 'G', 'T'][Math.floor(rand() * 4)],
        consequence,
        impact,
        af: Math.round(af * 1e5) / 1e5,
      }),
    );
  }

  const total = (variants.length * (variants.length - 1)) / 2;
  const trans = resolved.filter((p) => p.phase === 'trans');
  return {
    gene,
    variants,
    pairs: resolved,
    summary: {
      n_het: variants.length,
      n_pairs: total,
      n_trans: trans.length,
      n_auto_trans: trans.filter((p) => p.auto).length,
      n_cis: resolved.length - trans.length,
      n_unknown: total - resolved.length,
      pct_unknown: total ? Math.round((100 * (total - resolved.length) * 100) / total) / 100 : null,
    },
  };
}
