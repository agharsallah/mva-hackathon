/**
 * The structure gene set, as the picker and the metrics table need it.
 *
 * `GET /api/panel/structure-genes` returns a flat, display-ordered list. Two things every
 * consumer needs on top of that, and both belong in one pure module rather than in three
 * components:
 *
 * 1. **The groups, read off the payload.** `StructureGene` carries `group`, `group_label`
 *    and `group_order`, so the picker's `<optgroup>`s, the table's badges, the legend and the
 *    bar colours are all derived here from the data — no module in the app knows which
 *    groups this case uses, and a new reference table renames or re-ranks them for free.
 *    Colour is assigned by **rank**, not by id ({@link groupTones}), so a renamed group keeps
 *    its colour and a fourth group gets a fourth tone instead of falling through to grey.
 *
 *    The grouping is not cosmetic, but the *claim* rides on `in_panel`, never on a group id:
 *    `in_panel` decides whether the proband has any allele on that gene at all. The callset
 *    was annotated over the panel BED, so a gene outside it has an empty `candidates` list
 *    *because no annotation was ever run there* — never because the proband is clean at that
 *    locus. Anything reading "fold only" is reading `in_panel`.
 * 2. **A lookup that tells "not loaded yet" apart from "not in the set".** Same distinction
 *    `known()` in `lib/urlstate.ts` draws, and for the same reason: until the list arrives a
 *    URL-held gene has to be taken at face value.
 *
 * Pure: no React, no API client, no three.
 */

import type { StructureGene } from '../../../api/types';
import type { SelectGroup } from '../../../components/Controls';
import type { Tone } from '../../../lib/palette';

/**
 * The two genes the side-by-side comparison opens on — **this case's** two, and the one
 * knowingly case-specific constant in this module.
 *
 * Declared here rather than in the exhibit because the explorer's "compare with this gene"
 * button writes the same URL keys and needs the same defaults, so that a click on it while
 * A is already the default leaves the URL clean. {@link compareDefaults} is what a foreign
 * gene set falls back to when neither symbol is in the set.
 */
export const COMPARE_A = 'BUB1B';
export const COMPARE_B = 'TRIP13';

/**
 * The symbols this set should open on, best first: the ones {@link COMPARE_A} /
 * {@link COMPARE_B} (or a caller's `prefer` list) name *if the set holds them*, then every
 * `in_panel` row, then everything else.
 *
 * The preference order is the reuse contract. A project whose reference table names other
 * genes gets a working default out of the box, and it gets it from `in_panel` — the one
 * semantic flag — never from a group id, which a new case is free to rename.
 */
function preferredSymbols(genes: readonly StructureGene[], prefer: readonly string[]): string[] {
  const named = prefer.filter((symbol) => geneEntry(genes, symbol));
  const rest = [...genes.filter((gene) => gene.in_panel), ...genes].map((gene) => gene.symbol);
  return [...new Set([...named, ...rest])];
}

/** The gene an exhibit opens on, and what an unknown `?gene=` falls back to. */
export function defaultGene(genes: readonly StructureGene[], prefer = COMPARE_A): string {
  return preferredSymbols(genes, [prefer])[0] ?? prefer;
}

/** The two symbols the side-by-side comparison opens on for *this* set. */
export function compareDefaults(genes: readonly StructureGene[]): [string, string] {
  const picked = preferredSymbols(genes, [COMPARE_A, COMPARE_B]);
  return [picked[0] ?? COMPARE_A, picked[1] ?? COMPARE_B];
}

/**
 * Alias → current symbol, mirroring `mva.viz.geneset.ALIASES` (and the offline fixture's own
 * copy in `fixtures/shape/structure-genes.ts` — three copies of one entry, because neither
 * layer may import the others and a generated map would be a build step for six characters).
 * `CCDC84` is HGNC's *previous* symbol for `CENATAC`.
 */
export const GENE_ALIASES: Readonly<Record<string, string>> = { CCDC84: 'CENATAC' };

/**
 * A URL-held or hand-typed gene symbol, in the set's own spelling.
 *
 * The server (`mva.viz.geneset.resolve`) and the fixture both match case-insensitively and
 * accept the alias, so `?gene=bub1b` *works* — but only server-side. Client-side it used to
 * be a distinct string: its own react-query cache key, its own request pair, and the exhibit
 * titled `bub1b` until the gene set arrived and snapped it back. Canonicalising before the
 * value reaches `useUrlKnownOption` or {@link geneEntry} removes all three.
 */
export function canonicalGene(symbol: string): string {
  const upper = symbol.trim().toUpperCase();
  return GENE_ALIASES[upper] ?? upper;
}

/** One display group as the set declares it, plus the rows that belong to it. */
export interface GeneGroup {
  /** The free-form id — short, so it doubles as the badge and table-cell text. */
  id: string;
  /** The sentence a heading or legend shows. Falls back to {@link id}. */
  label: string;
  /** The group's rank, as every row of it stated. Ties break on first appearance. */
  order: number;
  genes: StructureGene[];
}

/**
 * The set's groups, in display order, each with its rows.
 *
 * Derived, never declared: the first row of a group fixes its label, and the group's rank
 * is `group_order`. Ties (or a table that states no order, where the server hands every
 * group the same fallback) break on first appearance, which is the reference table's own
 * row order — so a hand-written two-column TSV still renders in the order it reads in.
 */
export function geneGroupings(genes: readonly StructureGene[]): GeneGroup[] {
  const byId = new Map<string, GeneGroup & { seen: number }>();
  for (const gene of genes) {
    const found = byId.get(gene.group);
    if (found) {
      found.genes.push(gene);
      continue;
    }
    byId.set(gene.group, {
      id: gene.group,
      label: gene.group_label || gene.group,
      order: gene.group_order,
      seen: byId.size,
      genes: [gene],
    });
  }
  return [...byId.values()]
    .sort((a, b) => a.order - b.order || a.seen - b.seen)
    .map(({ id, label, order, genes: rows }) => ({ id, label, order, genes: rows }));
}

/**
 * Group id → the tone its badge and its bar are drawn in, assigned by **rank**.
 *
 * Rank and not id, so that renaming a group keeps its colour and adding a fourth gets a
 * fourth tone rather than falling through to grey. The first group is `good` (green)
 * because rank 0 is the set's own headline group — for this case the annotated panel, the
 * only genes that can carry an allele — and green is this repo's "the goal" tone. The
 * cycle repeats past its length rather than running out.
 */
const TONE_CYCLE: readonly Tone[] = ['good', 'machinery', 'neutral', 'decision', 'raw', 'broken'];

export function groupTones(genes: readonly StructureGene[]): Map<string, Tone> {
  return new Map(
    geneGroupings(genes).map((group, rank) => [
      group.id,
      TONE_CYCLE[rank % TONE_CYCLE.length] as Tone,
    ]),
  );
}

/** `<optgroup>`s for the gene picker, in group order, empty groups dropped. */
export function geneGroups(genes: readonly StructureGene[]): SelectGroup<string>[] {
  return geneGroupings(genes)
    .map((group) => ({
      label: group.label,
      options: group.genes.map((gene) => ({
        value: gene.symbol,
        // A non-coding gene stays in the list and says so, rather than being hidden: the set
        // is a reference table, and "this gene has no protein" is a fact worth reading.
        label: gene.coding ? gene.symbol : `${gene.symbol} — non-coding, no protein`,
      })),
    }))
    .filter((group) => group.options.length > 0);
}

/** Every symbol in the set, in display order — the vocabulary a URL-held gene is checked against. */
export const geneSymbols = (genes: readonly StructureGene[]): string[] =>
  genes.map((gene) => gene.symbol);

/**
 * The set's entry for one symbol, or `undefined` when the set does not hold it — which is
 * both "the list has not arrived" and "this symbol is not in the set". A caller that must
 * tell those apart checks `genes.length === 0` itself; nothing here guesses.
 */
export const geneEntry = (
  genes: readonly StructureGene[],
  symbol: string,
): StructureGene | undefined => {
  const wanted = canonicalGene(symbol);
  return genes.find((gene) => gene.symbol.toUpperCase() === wanted);
};
