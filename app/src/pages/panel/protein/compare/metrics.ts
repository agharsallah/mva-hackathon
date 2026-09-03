/**
 * One gene's fold, reduced to the numbers two folds can be compared by.
 *
 * The 3D exhibit answers "where does this allele sit" for one gene. The moment there is more
 * than one gene in the set, the reader's question changes to "is this fold like the others" —
 * and that needs a row of numbers per gene, not a picture per gene. This module is that
 * reduction, and it is deliberately the whole computation: `StructureCompare`'s fact sheet
 * and `StructureMetricsTable`'s rows are both rendered off one `StructureMetrics`, so the two
 * exhibits can never disagree about a percentage.
 *
 * Four rules the numbers obey, each of them a claim that would otherwise be quietly wrong:
 *
 * 1. **A denominator is stated, never assumed.** `modelledFraction` is over the *translation*
 *    length (the residue axis); `confidentFraction` is over the residues that actually carry
 *    a pLDDT, because an experimental structure carries none and dividing by the modelled
 *    count would report 0 % confident for a measured structure.
 * 2. **Absence of an annotation is `null`, never zero.** A coordinate file with no
 *    `_struct_conf` records annotates no secondary structure; `helixFraction` is then `null`
 *    ("not annotated"), not 0 ("all coil"). Same for pLDDT on a PDB entry.
 * 3. **Off-panel means the allele columns are `null`, not empty.** `GeneStructure.in_panel`
 *    false means no annotation was ever run over that gene — the callset was annotated
 *    against the eight-gene panel BED — so "0 alleles placed" would read as a statement about
 *    the proband. It is a statement about the pipeline's scope.
 * 4. **Placement and distance are computed by the exhibit's own rules**, not re-derived:
 *    `buildProteinScene` owns "which candidate landed on which modelled residue" and
 *    `candidateDistances` owns the Cα distance, so a metric and the drawn figure agree by
 *    construction. A translation-id mismatch therefore surfaces here too, as `mismatch`.
 *
 * Pure module: no React, no three, no API client.
 */

import { ApiError } from '../../../../api/client';
import type { GeneStructure, ProteinStructure, StructureGene } from '../../../../api/types';
import { buildProteinScene, PLDDT_FLOOR, type ProteinSceneResult } from '../buildScene';
import { candidateDistances } from '../distances';

export interface StructureMetrics {
  gene: string;
  /** The set's free-form group id — short, so it renders as a badge. Carries no claim. */
  group: string;
  /** The words for {@link group}, from the payload; a fact sheet shows these, not the id. */
  groupLabel: string;
  /** True only for the annotated panel — the flag that decides whether alleles exist at all. */
  inPanel: boolean;
  /** Residues on the canonical translation: the axis every count below indexes into. */
  length: number;
  /** Residues the model carries alpha-carbon coordinates for. */
  modelled: number;
  /** `modelled / length`, 0–1. `null` when the translation length is unknown. */
  modelledFraction: number | null;
  /** Modelled residues at or above the pLDDT floor. `null` for a structure with no pLDDT. */
  confident: number | null;
  /** `confident` over the residues that carry a pLDDT, 0–1. `null` = no confidence column. */
  confidentFraction: number | null;
  /** Residues in an annotated helix / strand, over `length`. `null` = not annotated. */
  helixFraction: number | null;
  strandFraction: number | null;
  /** Distinct annotated domain names, in chain order. */
  domains: readonly string[];
  /** Candidate alleles on a modelled residue. `null` off-panel: nothing was annotated. */
  allelesPlaced: number | null;
  /** Candidates with no place on the fold, with a stated reason. `null` off-panel. */
  allelesUnplaced: number | null;
  /** Closest Cα distance between two placed alleles, in ångström. `null` under two. */
  closestPairAngstrom: number | null;
  /** Whether both ends of that closest pair are at or above the pLDDT floor. */
  closestPairConfident: boolean | null;
  provenance: ProteinStructure['provenance'];
  version: string | null;
  uniprot: string | null;
  protein: string;
  /**
   * Set when the two payloads name different translations, so the row says so instead of
   * printing allele numbers computed against the wrong sequence. Structural columns stay
   * valid — they come from the coordinate file alone.
   */
  mismatch: string | null;
}

/** Residues covered by segments of one kind, as a fraction of `length`. */
function secondaryFraction(
  structure: ProteinStructure,
  kind: 'helix' | 'strand',
  length: number,
): number | null {
  if (structure.secondary.length === 0 || length <= 0) return null;
  const covered = new Set<number>();
  for (const segment of structure.secondary) {
    if (segment.kind !== kind) continue;
    const lo = Math.max(1, Math.min(segment.start, segment.end));
    const hi = Math.min(length, Math.max(segment.start, segment.end));
    for (let n = lo; n <= hi; n++) covered.add(n);
  }
  return covered.size / length;
}

/** Distinct domain names, ordered by where each first starts on the chain. */
function domainNames(anatomy: GeneStructure): string[] {
  const firstStart = new Map<string, number>();
  for (const domain of anatomy.domains) {
    const seen = firstStart.get(domain.name);
    if (seen === undefined || domain.start_aa < seen) firstStart.set(domain.name, domain.start_aa);
  }
  return [...firstStart.entries()].sort((a, b) => a[1] - b[1]).map(([name]) => name);
}

/**
 * Reduce one gene's two payloads to one row.
 *
 * `entry` supplies the group and `in_panel`; when the caller has no set entry (an API older
 * than `/api/panel/structure-genes`) it falls back to `GeneStructure.in_panel` and an
 * *unnamed* group. Unnamed rather than a guessed id, because no group id is known to this
 * module: the conservative reading is carried by `in_panel` alone — fold only, no alleles
 * claimed — and inventing a group name here would put a word on screen the set never said.
 */
export function structureMetrics(
  structure: ProteinStructure,
  anatomy: GeneStructure,
  entry?: StructureGene,
  /**
   * The scene the caller already built from the same two payloads, so the build is not
   * repeated. `buildProteinScene` walks every residue of a 300–2,500-residue chain; the
   * cross-gene table calls this once per gene and had been paying for it twice.
   */
  prebuilt?: ProteinSceneResult,
): StructureMetrics {
  const length = structure.protein_length > 0 ? structure.protein_length : anatomy.protein_length;
  const axis = length ?? 0;
  const inPanel = entry?.in_panel ?? anatomy.in_panel;

  const withPlddt = structure.residues.filter((residue) => residue.plddt !== null);
  const confident = withPlddt.filter((residue) => (residue.plddt ?? 0) >= PLDDT_FLOOR).length;

  const built = prebuilt ?? buildProteinScene(structure, anatomy);
  const placed = built.ok ? built.build.placed : [];
  const closest = built.ok ? candidateDistances(placed, undefined, 1)[0] : undefined;

  return {
    gene: structure.gene,
    group: entry?.group ?? '',
    groupLabel: entry?.group_label || entry?.group || 'group not stated',
    inPanel,
    length: axis,
    modelled: structure.residues.length,
    modelledFraction: axis > 0 ? structure.residues.length / axis : null,
    confident: withPlddt.length === 0 ? null : confident,
    confidentFraction: withPlddt.length === 0 ? null : confident / withPlddt.length,
    helixFraction: secondaryFraction(structure, 'helix', axis),
    strandFraction: secondaryFraction(structure, 'strand', axis),
    domains: domainNames(anatomy),
    allelesPlaced: inPanel && built.ok ? placed.length : null,
    allelesUnplaced: inPanel && built.ok ? built.build.unplaced.length : null,
    closestPairAngstrom: inPanel && closest ? closest.angstrom : null,
    closestPairConfident: inPanel && closest ? closest.confident : null,
    provenance: structure.provenance,
    version: structure.version,
    uniprot: structure.uniprot,
    protein: structure.protein,
    mismatch: built.ok ? null : built.error.message,
  };
}

// --- the cross-gene table's rows -------------------------------------------------------

/**
 * HTTP 422 from `/api/panel/protein-structure` means exactly one thing, and it is not an
 * error in the reader's sense: the gene has no protein-coding canonical transcript, so there
 * is no residue axis to fetch coordinates for. Owned here so the compare view, the explorer
 * and the table all agree on what a 422 is.
 */
export function isNonCodingError(error: Error | null | undefined): boolean {
  return error instanceof ApiError && error.status === 422;
}

/** One endpoint's answer for one gene, reduced to the two things a row cares about. */
export interface PayloadSlot<T> {
  data: T | null;
  error: Error | null;
}

/** What a table row can be. Each value renders as its own words — never as a blank cell. */
export type RowKind = 'loading' | 'non-coding' | 'error' | 'mismatch' | 'ready';

export interface StructureRow {
  gene: string;
  /** The set's free-form group id. Short, so it renders as a badge. Carries no claim. */
  group: string;
  /** The words for {@link group}, for a tooltip or a heading. */
  groupLabel: string;
  /** The group's rank in the set — what the group column sorts by and the tone is picked by. */
  groupOrder: number;
  inPanel: boolean;
  coding: boolean;
  kind: RowKind;
  /** Why there is no metrics object, in the reader's words. Empty for a `ready` row. */
  note: string;
  metrics: StructureMetrics | null;
}

/**
 * One gene's two in-flight payloads -> one row.
 *
 * Pure, and the reason the table can show a per-row state: every row is computed from that
 * gene's own two results, so a gene whose fold is missing carries its own note and leaves
 * every other row intact.
 */
export function structureRow(
  entry: StructureGene,
  model: PayloadSlot<ProteinStructure>,
  anatomy: PayloadSlot<GeneStructure>,
): StructureRow {
  const base = {
    gene: entry.symbol,
    group: entry.group,
    groupLabel: entry.group_label || entry.group,
    groupOrder: entry.group_order,
    inPanel: entry.in_panel,
    coding: entry.coding,
    metrics: null,
  };
  if (!entry.coding || isNonCodingError(model.error)) {
    return { ...base, kind: 'non-coding', note: 'non-coding, no protein' };
  }
  const error = model.error ?? anatomy.error;
  if (error) return { ...base, kind: 'error', note: error.message };
  if (!model.data || !anatomy.data) return { ...base, kind: 'loading', note: 'loading…' };

  const built = buildProteinScene(model.data, anatomy.data);
  if (!built.ok) {
    return { ...base, kind: 'mismatch', note: 'the two payloads name different translations' };
  }
  return {
    ...base,
    kind: 'ready',
    note: '',
    metrics: structureMetrics(model.data, anatomy.data, entry, built),
  };
}
