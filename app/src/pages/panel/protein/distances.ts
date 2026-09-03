/**
 * How far apart, in space, are the two alleles?
 *
 * This is the question the 2D domain lollipop cannot answer and the reason the 3D exhibit
 * exists. Sequence distance is a poor proxy for spatial distance: a protein folds, so two
 * residues 300 amino acids apart on the chain can pack into one pocket, and two neighbours
 * on the chain can point at opposite faces.
 *
 * The measurement is the **Cα distance** (the straight-line distance between the two
 * residues' alpha carbons — the one backbone atom every amino acid has), in **ångström**
 * (Å, 10⁻¹⁰ m; a C–C bond is ~1.5 Å, a whole domain ~30–40 Å across).
 *
 * What the numbers are **not**: a functional claim. The buckets below are geometric bands
 * on one predicted model. "Same neighbourhood" says the two residues are close enough that
 * one pocket *could* hold both, not that either damages the other's function. Two more
 * limits ride with every row: a distance is only as good as the model's confidence at both
 * ends (`confident` below), and a prediction is not an experiment.
 *
 * Pure module: no React, no three, no API client — it takes placed candidates and returns
 * rows and a `viz3d` link.
 */

import type { PanelHetPairs } from '../../../api/types';
import type { SceneLink, Vec3 } from '../../../viz3d';
import { type PlacedCandidate, PLDDT_FLOOR } from './buildScene';
import { NO_DOMAIN } from './encodings';

/** Geometric band, not a functional verdict. See the module note. */
export type DistanceBucket = 'same neighbourhood' | 'same lobe' | 'far apart';

/** Upper edge of each band, in ångström. */
export const BUCKET_EDGES: readonly { upTo: number; bucket: DistanceBucket; means: string }[] = [
  {
    upTo: 10,
    bucket: 'same neighbourhood',
    means: 'close enough that one binding pocket or interface could contain both residues',
  },
  {
    upTo: 25,
    bucket: 'same lobe',
    means: 'the same structural region of the fold, but not the same pocket',
  },
  {
    upTo: Infinity,
    bucket: 'far apart',
    means: 'different parts of the fold — two independent lesions, not one broken site',
  },
];

export function bucketOf(angstrom: number): DistanceBucket {
  return (BUCKET_EDGES.find((b) => angstrom < b.upTo) ?? BUCKET_EDGES[BUCKET_EDGES.length - 1])
    .bucket;
}

/** Straight-line distance between two model-frame points, in the model's own unit (Å). */
export function distance(a: Vec3, b: Vec3): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

/** Phase of the two alleles, as the callset resolved it. `unknown` is the honest common case. */
export type PairPhase = 'trans' | 'cis' | 'auto-trans' | 'unknown';

export interface CandidateDistance {
  /** `${a.id}|${b.id}` — stable, and an amino-acid index either side. */
  key: string;
  a: PlacedCandidate;
  b: PlacedCandidate;
  /** Cα distance in ångström. */
  angstrom: number;
  /** Amino acids apart along the chain — the thing the 1D lollipop shows, for contrast. */
  sequenceGap: number;
  bucket: DistanceBucket;
  bothRare: boolean;
  /** Both residues lie in the same annotated domain (and it is an actual domain). */
  sameDomain: boolean;
  /** Both ends are at or above the pLDDT floor, so the distance is worth quoting. */
  confident: boolean;
  phase: PairPhase;
}

function phaseOf(a: PlacedCandidate, b: PlacedCandidate, pairs?: PanelHetPairs): PairPhase {
  if (!pairs || a.hetIndex === null || b.hetIndex === null) return 'unknown';
  const [i, j] = [Math.min(a.hetIndex, b.hetIndex), Math.max(a.hetIndex, b.hetIndex)];
  const hit = pairs.pairs.find((p) => Math.min(p.i, p.j) === i && Math.max(p.i, p.j) === j);
  if (!hit) return 'unknown';
  return hit.phase === 'trans' && hit.auto ? 'auto-trans' : hit.phase;
}

/**
 * Every pair of placed candidates, closest first.
 *
 * `k` caps the list; omit it for all of them. The full grid is quadratic, but the input is
 * the set of *protein-altering alleles in one gene* — single digits in practice.
 */
export function candidateDistances(
  placed: readonly PlacedCandidate[],
  pairs?: PanelHetPairs,
  k?: number,
): CandidateDistance[] {
  const out: CandidateDistance[] = [];
  for (let i = 0; i < placed.length; i++) {
    for (let j = i + 1; j < placed.length; j++) {
      const a = placed[i];
      const b = placed[j];
      const angstrom = distance(a.at, b.at);
      out.push({
        key: `${a.id}|${b.id}`,
        a,
        b,
        angstrom,
        sequenceGap: Math.abs(a.n - b.n),
        bucket: bucketOf(angstrom),
        bothRare: a.rare && b.rare,
        sameDomain: a.domain === b.domain && a.domain !== NO_DOMAIN,
        confident: (a.plddt ?? 0) >= PLDDT_FLOOR && (b.plddt ?? 0) >= PLDDT_FLOOR,
        phase: phaseOf(a, b, pairs),
      });
    }
  }
  out.sort((x, y) => x.angstrom - y.angstrom || x.key.localeCompare(y.key));
  return k === undefined ? out : out.slice(0, k);
}

/** `12.3 Å` — one decimal, the precision a predicted model earns. */
export const angstromLabel = (angstrom: number): string => `${angstrom.toFixed(1)} Å`;

/**
 * The picked pair as a drawn line. Yellow (`decision`) when the distance is quotable and
 * grey (`neutral`) when either end is below the pLDDT floor, so an untrustworthy line never
 * looks like a finding.
 */
export function pairLink(row: CandidateDistance): SceneLink {
  return {
    from: row.a.id,
    to: row.b.id,
    label: row.confident
      ? angstromLabel(row.angstrom)
      : `${angstromLabel(row.angstrom)} (low pLDDT)`,
    tone: row.confident ? 'decision' : 'neutral',
  };
}

/** Find one pair by its two residue ids, in either order. */
export function findPair(
  rows: readonly CandidateDistance[],
  a: string,
  b: string,
): CandidateDistance | undefined {
  return rows.find(
    (row) => (row.a.id === a && row.b.id === b) || (row.a.id === b && row.b.id === a),
  );
}
