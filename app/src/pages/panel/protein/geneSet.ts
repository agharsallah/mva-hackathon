/**
 * The structure gene set, as the picker and the metrics table need it.
 *
 * `GET /api/panel/structure-genes` returns a flat, display-ordered list. Two things every
 * consumer needs on top of that, and both belong in one pure module rather than in three
 * components:
 *
 * 1. **The three groups, with the words that say what each one means for the reader.** The
 *    split is not cosmetic: `in_panel` decides whether the proband has any allele on that
 *    gene at all. The callset was annotated over the eight-gene panel BED, so a gene outside
 *    it has an empty `candidates` list *because no annotation was ever run there* — never
 *    because the proband is clean at that locus. Every label below says "fold only" for
 *    exactly that reason.
 * 2. **A lookup that tells "not loaded yet" apart from "not in the set".** Same distinction
 *    `known()` in `lib/urlstate.ts` draws, and for the same reason: until the list arrives a
 *    URL-held gene has to be taken at face value.
 *
 * Pure: no React, no API client, no three.
 */

import type { StructureGene } from '../../../api/types';
import type { SelectGroup } from '../../../components/Controls';

/**
 * The two genes the side-by-side comparison opens on: the canonical MVA gene (MVA type 1)
 * and the standout of this case. Declared here rather than in the exhibit because the
 * explorer's "compare with this gene" button writes the same URL key and needs the same
 * default, so that a click on it while A is already BUB1B leaves the URL clean.
 */
export const COMPARE_A = 'BUB1B';
export const COMPARE_B = 'TRIP13';

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

/** Display order of the groups, and the one sentence each heading has to carry. */
export const GROUP_ORDER: readonly StructureGene['group'][] = ['panel', 'mva-sac', 'extended'];

export const GROUP_LABEL: Readonly<Record<StructureGene['group'], string>> = {
  panel: 'annotated panel (alleles painted)',
  'mva-sac': 'MVA / SAC genes (fold only)',
  extended: 'extended (fold only)',
};

/** Short form, for a table cell and a fact-sheet row where the long label will not fit. */
export const GROUP_SHORT: Readonly<Record<StructureGene['group'], string>> = {
  panel: 'panel',
  'mva-sac': 'MVA / SAC',
  extended: 'extended',
};

/** `<optgroup>`s for the gene picker, in {@link GROUP_ORDER}, empty groups dropped. */
export function geneGroups(genes: readonly StructureGene[]): SelectGroup<string>[] {
  return GROUP_ORDER.map((group) => ({
    label: GROUP_LABEL[group],
    options: genes
      .filter((gene) => gene.group === group)
      .map((gene) => ({
        value: gene.symbol,
        // A non-coding gene stays in the list and says so, rather than being hidden: the set
        // is a reference table, and "this gene has no protein" is a fact worth reading.
        label: gene.coding ? gene.symbol : `${gene.symbol} — non-coding, no protein`,
      })),
  })).filter((group) => group.options.length > 0);
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
