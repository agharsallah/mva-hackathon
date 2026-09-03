/**
 * `ProteinStructure` + `GeneStructure` (+ optional `PanelHetPairs`) -> a `viz3d`
 * `Scene3D` of kind `protein`.
 *
 * This is the *only* case-specific code in the 3D protein exhibit: `viz3d` never learns
 * what a `GeneCandidate` is, and this module never imports three. Everything here is a
 * pure function over API rows, which is what makes it the unit-test surface — the
 * component below it only wires state to the scene this file returns.
 *
 * Three invariants it enforces, because each one would otherwise paint a colour onto the
 * wrong amino acid:
 *
 * 1. **`structure.protein` must equal `geneStructure.protein`.** The candidate offsets
 *    (`protein_pos`) are indices into one particular translation; the coordinates are
 *    indices into another. If the two ids disagree, every painted residue is on a
 *    different sequence, so the build fails with a typed error the page renders as a
 *    Callout rather than drawing something wrong.
 * 2. **A candidate with no `protein_pos`, or one pointing past the modelled chain, is
 *    reported, never dropped** — same rule the 2D lollipop follows.
 * 3. **Confidence is a first-class field, not a footnote.** AlphaFold is a *prediction*;
 *    `plddt` below 70 supports no spatial claim, so it rides in `meta` (where it becomes a
 *    colour-by option and a filter for free) and `dimLowConfidence` can grey those
 *    residues out — the treatment `docs/step-0/notes/three-js-behind-one-wrapper.md` §2
 *    asks for.
 *
 * No genomic coordinate can reach a scene built here: the payloads carry an amino-acid
 * index and a model-frame ångström triple, and nothing else.
 */

import type {
  GeneCandidate,
  GeneStructure,
  PanelHetPairs,
  ProteinStructure,
} from '../../../api/types';
import { impactTone, type Tone } from '../../../lib/palette';
import type { Datum3D, Scene3D, Vec3 } from '../../../viz3d';
import { domainAt, domainToneMap, proteinEncodings } from './encodings';

/** Residue-sphere radius in unit-box units, and the multiplier a candidate is drawn at. */
const RESIDUE_RADIUS = 0.022;
const CANDIDATE_SIZE = 2.4;
/** Multiplier for a residue the active emphasis filter rejects — smaller *and* grey. */
const DIM_SIZE = 0.6;

/** A `protein` scene, narrowed out of the `Scene3D` union. */
export type ProteinScene = Extract<Scene3D, { kind: 'protein' }>;

/** The pLDDT floor below which a position supports no spatial claim. AlphaFold's own advice. */
export const PLDDT_FLOOR = 70;

/** Residue id — `r737`. An amino-acid index, deliberately never a genomic position. */
export const residueId = (n: number): string => `r${n}`;

/** One candidate allele that landed on a modelled residue. */
export interface PlacedCandidate {
  id: string;
  /** `GeneCandidate.label`, e.g. `"stop gained · rs000000001"`. */
  label: string;
  /** 1-based residue index on the translation. */
  n: number;
  aa: string;
  at: Vec3;
  impact: string;
  consequence: string;
  rare: boolean;
  plddt: number | null;
  domain: string;
  clinSig: string | null;
  /** Phase of this allele against the rest of the gene, when `het-pairs` could match it. */
  hetIndex: number | null;
}

/** A candidate the model could not place, with the reason, so nothing is silently lost. */
export interface UnplacedCandidate {
  label: string;
  impact: string;
  reason: string;
}

export interface ProteinSceneError {
  kind: 'protein-mismatch' | 'no-protein' | 'no-residues';
  message: string;
}

export interface ProteinSceneBuild {
  scene: ProteinScene;
  placed: readonly PlacedCandidate[];
  unplaced: readonly UnplacedCandidate[];
  /** Residues the model actually carries coordinates for. */
  modelled: number;
  /** `protein_length - modelled`: residues the model does not cover, i.e. unmeasured. */
  unmodelled: number;
  /** Modelled residues at or above {@link PLDDT_FLOOR}. */
  confident: number;
  /**
   * `confident` over the residues that **carry a pLDDT**, 0–1 — not over `modelled`. Same
   * denominator rule as `compare/metrics.ts`: an experimental structure carries no pLDDT at
   * all, and dividing by the modelled count would report 0 % confident for a measured
   * structure. `null` for exactly that case (no pLDDT column).
   */
  confidentFraction: number | null;
  /** Domain name -> the tone it is drawn in, for the legend. `none` included. */
  domainTones: Readonly<Record<string, Tone>>;
}

export type ProteinSceneResult =
  { ok: true; build: ProteinSceneBuild } | { ok: false; error: ProteinSceneError };

/** Residue index -> `helix` / `strand` / `coil`. Absence of annotation reads as coil. */
function secondaryMap(structure: ProteinStructure): Map<number, 'helix' | 'strand'> {
  const out = new Map<number, 'helix' | 'strand'>();
  for (const seg of structure.secondary) {
    for (let n = seg.start; n <= seg.end; n++) out.set(n, seg.kind);
  }
  return out;
}

/** Rarity as a word, because `meta` holds strings and numbers — never a bare boolean. */
const rarity = (rare: boolean): string => (rare ? 'rare' : 'common');

/**
 * Match a candidate allele to a row of `het-pairs`, so a pair can carry a phase verdict.
 *
 * **Only `rsid` is trusted.** The amino-acid payload deliberately carries no coordinate, so
 * the two payloads share exactly one identifier; matching on consequence alone would happily
 * pair the wrong two missense alleles. No rsid means no match, which reads as *unknown
 * phase* — never as cis or trans.
 */
function hetIndexOf(candidate: GeneCandidate, pairs?: PanelHetPairs): number | null {
  if (!pairs || !candidate.rsid) return null;
  const i = pairs.variants.findIndex((v) => v.rsid === candidate.rsid);
  return i < 0 ? null : i;
}

/**
 * Build the scene. Returns a typed error rather than throwing, because every failure here is
 * something the page has to *show* (a Callout naming the mismatch), not something to swallow.
 */
export function buildProteinScene(
  structure: ProteinStructure,
  geneStructure: GeneStructure,
  pairs?: PanelHetPairs,
): ProteinSceneResult {
  if (!geneStructure.protein) {
    return {
      ok: false,
      error: {
        kind: 'no-protein',
        message:
          `${geneStructure.gene} has no protein on its canonical transcript ` +
          `(${geneStructure.transcript ?? 'unknown'}), so there is no residue axis to paint.`,
      },
    };
  }
  if (structure.protein !== geneStructure.protein) {
    return {
      ok: false,
      error: {
        kind: 'protein-mismatch',
        message:
          `the 3D model is for translation ${structure.protein} but the gene structure ` +
          `places its alleles on ${geneStructure.protein}. Amino-acid offsets are only ` +
          'meaningful on the translation they were computed against, so nothing is painted: ' +
          'a residue drawn on the wrong sequence is worse than no figure.',
      },
    };
  }
  if (structure.residues.length === 0) {
    return {
      ok: false,
      error: {
        kind: 'no-residues',
        message: `the model for ${structure.protein} carries no alpha-carbon coordinates.`,
      },
    };
  }

  const domainTones = domainToneMap(geneStructure.domains);
  const secondary = secondaryMap(structure);
  const byN = new Map(structure.residues.map((r) => [r.n, r]));

  const placed: PlacedCandidate[] = [];
  const unplaced: UnplacedCandidate[] = [];
  for (const c of geneStructure.candidates) {
    if (c.protein_pos === null) {
      unplaced.push({
        label: c.label,
        impact: c.impact ?? 'unknown',
        reason: c.reason ?? 'VEP reported no amino-acid position',
      });
      continue;
    }
    const residue = byN.get(c.protein_pos);
    if (!residue) {
      unplaced.push({
        label: c.label,
        impact: c.impact ?? 'unknown',
        reason:
          `residue ${c.protein_pos} is outside the modelled chain ` +
          `(${structure.residues.length} of ${structure.protein_length} residues modelled), ` +
          'so it has no coordinates to sit on',
      });
      continue;
    }
    placed.push({
      id: residueId(residue.n),
      label: c.label,
      n: residue.n,
      aa: residue.aa,
      at: residue.ca,
      impact: c.impact ?? 'none',
      consequence: c.consequence,
      rare: c.rare,
      plddt: residue.plddt,
      domain: domainAt(geneStructure.domains, residue.n),
      clinSig: c.clin_sig,
      hetIndex: hetIndexOf(c, pairs),
    });
  }
  const candidateAt = new Map(placed.map((p) => [p.n, p]));

  const residues: Datum3D[] = structure.residues.map((r) => {
    const candidate = candidateAt.get(r.n);
    return {
      id: residueId(r.n),
      label: candidate ? `${r.aa}${r.n} — ${candidate.label}` : `${r.aa}${r.n}`,
      at: r.ca,
      // The scene's default numeric channel. pLDDT where the model reports one (an AlphaFold
      // prediction); the residue index otherwise (an experimental PDB structure has no
      // per-residue confidence, and `0` for every residue would make `describeScene`'s
      // "highest by value" an alphabetical id sort dressed up as a finding).
      value: r.plddt ?? r.n,
      // A candidate's colour is its impact, always: the verdict must not disappear when the
      // reader switches the ramp to pLDDT or to domains.
      tone: candidate ? impactTone(candidate.impact) : undefined,
      size: candidate ? CANDIDATE_SIZE : 1,
      meta: {
        n: r.n,
        aa: r.aa,
        plddt: r.plddt,
        domain: domainAt(geneStructure.domains, r.n),
        secondary: secondary.get(r.n) ?? 'coil',
        candidate: candidate?.label ?? null,
        impact: candidate?.impact ?? 'none',
        rare: candidate ? rarity(candidate.rare) : null,
        clin_sig: candidate?.clinSig ?? null,
        consequence: candidate?.consequence ?? null,
        confidence: r.plddt === null ? 'not reported' : r.plddt >= PLDDT_FLOOR ? 'high' : 'low',
      },
    };
  });

  const withPlddt = structure.residues.filter((r) => r.plddt !== null);
  const confident = withPlddt.filter((r) => (r.plddt ?? 0) >= PLDDT_FLOOR).length;
  const declared = proteinEncodings(domainTones);

  return {
    ok: true,
    build: {
      scene: {
        kind: 'protein',
        title: `${structure.gene} — the fold, with this proband's alleles on it`,
        axes: {
          x: { label: 'x in the model frame', unit: 'Å' },
          y: { label: 'y in the model frame', unit: 'Å' },
          z: { label: 'z in the model frame', unit: 'Å' },
        },
        color: declared[0],
        encodings: declared,
        unit: 'Å',
        radius: RESIDUE_RADIUS,
        backbone: structure.residues.map((r) => r.ca),
        residues,
      },
      placed,
      unplaced,
      modelled: structure.residues.length,
      unmodelled: Math.max(structure.protein_length - structure.residues.length, 0),
      confident,
      confidentFraction: withPlddt.length === 0 ? null : confident / withPlddt.length,
      domainTones,
    },
  };
}

/**
 * Trim the scene to a residue window — backbone *and* spheres.
 *
 * This is the real zoom: `viz3d` normalises a scene into the unit box from the extent of
 * everything it holds and the camera fits those bounds, so slicing the chain is what makes
 * "focus on this residue" actually fill the canvas. Filtering only the spheres would leave
 * the full-length tube behind and change nothing about the camera.
 */
export function sliceProteinScene(scene: ProteinScene, from: number, to: number): ProteinScene {
  const lo = Math.min(from, to);
  const hi = Math.max(from, to);
  const keep = scene.residues
    .map((datum, index) => ({ datum, index }))
    .filter(({ datum }) => {
      const n = datum.meta?.n;
      return typeof n === 'number' && n >= lo && n <= hi;
    });
  if (keep.length === scene.residues.length) return scene;
  return {
    ...scene,
    residues: keep.map((k) => k.datum),
    backbone: keep.map((k) => scene.backbone[k.index]).filter((at) => at !== undefined),
  };
}

/**
 * Grey out and shrink every residue a predicate rejects, instead of deleting it.
 *
 * Deliberately *not* a `viz3d` layer or filter: those drop datums, and the protein adapter
 * paints the tube from the nearest surviving residue, so a dropped stretch would repaint the
 * chain in a neighbour's colour — a picture that says something false. Greying keeps the
 * chain continuous and says "measured, not emphasised", which is what a filter means here.
 * It is also the treatment the design note asks for below the pLDDT floor.
 */
export function emphasise(scene: ProteinScene, accept: (datum: Datum3D) => boolean): ProteinScene {
  return {
    ...scene,
    residues: scene.residues.map((datum) =>
      accept(datum) ? datum : { ...datum, tone: 'neutral', size: (datum.size ?? 1) * DIM_SIZE },
    ),
  };
}

/** Is this residue below the confidence floor? `null` pLDDT (an experiment) is not "low". */
export function isLowConfidence(datum: Datum3D): boolean {
  const plddt = datum.meta?.plddt;
  return typeof plddt === 'number' && plddt < PLDDT_FLOOR;
}

/** True when the residue carries a candidate allele. */
export function isCandidate(datum: Datum3D): boolean {
  return typeof datum.meta?.candidate === 'string';
}
