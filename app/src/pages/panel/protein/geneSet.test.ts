/**
 * The gene-set grouping, driven from **invented** groups.
 *
 * This module is the frontend half of the reuse claim in
 * `docs/notes/reusable-structure-toolkit.md`: that the picker, the metrics table's badges
 * and legend, and the bar colours all read their words, their order and their colour
 * assignment off `GET /api/panel/structure-genes`, so a foreign reference table needs no
 * code change.
 *
 * So every group id, label and rank below is made up, and none of the three this case uses
 * appears anywhere. A component or a helper that still knew `panel` / `mva-sac` /
 * `extended` would pass its own tests and fail every one of these.
 */

import { describe, expect, it } from 'vitest';

import type { StructureGene } from '../../../api/types';
import { TONE_MARK } from '../../../lib/palette';
import { structureRow } from './compare/metrics';
import { compareDefaults, defaultGene, geneGroupings, geneGroups, groupTones } from './geneSet';

/** One row. Nothing is defaulted that the test is about. */
function row(over: Partial<StructureGene> & { symbol: string }): StructureGene {
  return {
    ensembl_id: `ENSG-${over.symbol}`,
    group: 'alpha',
    group_label: 'Alpha things',
    group_order: 0,
    in_panel: false,
    biotype: 'protein_coding',
    coding: true,
    note: '',
    ...over,
  };
}

/**
 * A foreign set: three groups nothing in this repo names, and the group ranked **0** is
 * written **last** in the payload — so anything that took display order from row order
 * rather than from `group_order` gets it wrong here.
 */
const FOREIGN: StructureGene[] = [
  row({ symbol: 'GAMMA1', group: 'gamma', group_label: 'Gamma set (fold only)', group_order: 2 }),
  row({ symbol: 'BETA1', group: 'beta', group_label: 'Beta set (fold only)', group_order: 1 }),
  row({ symbol: 'BETA2', group: 'beta', group_label: 'Beta set (fold only)', group_order: 1 }),
  row({
    symbol: 'ALPHA1',
    group: 'alpha',
    group_label: 'Alpha set (the annotated ones)',
    group_order: 0,
    in_panel: true,
  }),
  row({
    symbol: 'ALPHA2-AS1',
    group: 'alpha',
    group_label: 'Alpha set (the annotated ones)',
    group_order: 0,
    in_panel: true,
    coding: false,
    biotype: 'lncRNA',
  }),
];

describe('geneGroupings — the display groups, derived from the payload', () => {
  it('orders groups by group_order, not by the row order of the payload', () => {
    expect(geneGroupings(FOREIGN).map((group) => group.id)).toEqual(['alpha', 'beta', 'gamma']);
  });

  it('carries each group its own label, from the data', () => {
    expect(geneGroupings(FOREIGN).map((group) => group.label)).toEqual([
      'Alpha set (the annotated ones)',
      'Beta set (fold only)',
      'Gamma set (fold only)',
    ]);
  });

  it('keeps every row, in payload order within its group', () => {
    expect(geneGroupings(FOREIGN).map((group) => group.genes.map((gene) => gene.symbol))).toEqual([
      ['ALPHA1', 'ALPHA2-AS1'],
      ['BETA1', 'BETA2'],
      ['GAMMA1'],
    ]);
  });

  it('falls back to the group id when the table states no label', () => {
    const bare = [row({ symbol: 'X1', group: 'kinases', group_label: '', group_order: 0 })];
    expect(geneGroupings(bare)[0]?.label).toBe('kinases');
  });

  it('breaks a tie on first appearance, so an unranked table reads in file order', () => {
    const tied = [
      row({ symbol: 'S1', group: 'second', group_order: 0 }),
      row({ symbol: 'F1', group: 'first', group_order: 0 }),
    ];
    expect(geneGroupings(tied).map((group) => group.id)).toEqual(['second', 'first']);
  });

  it('handles a set with one group and a set with none', () => {
    expect(geneGroupings([]).length).toBe(0);
    expect(geneGroupings([FOREIGN[0] as StructureGene]).length).toBe(1);
  });
});

describe('geneGroups — the <optgroup>s the picker renders', () => {
  it('labels each optgroup from the data and lists the genes under it', () => {
    expect(geneGroups(FOREIGN)).toEqual([
      {
        label: 'Alpha set (the annotated ones)',
        options: [
          { value: 'ALPHA1', label: 'ALPHA1' },
          { value: 'ALPHA2-AS1', label: 'ALPHA2-AS1 — non-coding, no protein' },
        ],
      },
      {
        label: 'Beta set (fold only)',
        options: [
          { value: 'BETA1', label: 'BETA1' },
          { value: 'BETA2', label: 'BETA2' },
        ],
      },
      { label: 'Gamma set (fold only)', options: [{ value: 'GAMMA1', label: 'GAMMA1' }] },
    ]);
  });
});

describe('groupTones — colour by rank, never by id', () => {
  it('gives the rank-0 group the "goal" tone and each later group its own', () => {
    const tones = groupTones(FOREIGN);
    expect(tones.get('alpha')).toBe('good');
    expect(tones.get('beta')).toBe('machinery');
    expect(tones.get('gamma')).toBe('neutral');
    // The tones resolve to three different hexes, which is what a legend and a bar need.
    const hexes = [...tones.values()].map((tone) => TONE_MARK[tone]);
    expect(new Set(hexes).size).toBe(3);
  });

  it('keeps a group its colour when it is renamed, because rank decides', () => {
    const renamed = FOREIGN.map((gene) =>
      gene.group === 'alpha' ? { ...gene, group: 'kinases' } : gene,
    );
    expect(groupTones(renamed).get('kinases')).toBe(groupTones(FOREIGN).get('alpha'));
  });

  it('gives a fourth group a fourth tone rather than falling through to grey', () => {
    const four = [
      ...FOREIGN,
      row({ symbol: 'DELTA1', group: 'delta', group_label: 'Delta', group_order: 3 }),
    ];
    const tones = groupTones(four);
    expect(tones.get('delta')).toBe('decision');
    expect(new Set(tones.values()).size).toBe(4);
  });
});

describe('the metrics row, over a foreign set', () => {
  const slot = { data: null, error: null };

  it('carries the group id, its words and its rank through to the table row', () => {
    const built = structureRow(FOREIGN[0] as StructureGene, slot, slot);
    expect(built.group).toBe('gamma');
    expect(built.groupLabel).toBe('Gamma set (fold only)');
    // The group column sorts on this, so the table's groups read in the set's own order.
    expect(built.groupOrder).toBe(2);
  });

  it('reads "can this row claim an allele" off in_panel, never off the group id', () => {
    expect(structureRow(FOREIGN[0] as StructureGene, slot, slot).inPanel).toBe(false);
    expect(structureRow(FOREIGN[3] as StructureGene, slot, slot).inPanel).toBe(true);
  });

  it('sorts the group column into group order for a foreign set', () => {
    const rows = FOREIGN.map((gene) => structureRow(gene, slot, slot));
    const sorted = [...rows].sort((a, b) => a.groupOrder - b.groupOrder);
    expect(sorted.map((r) => r.group)).toEqual(['alpha', 'alpha', 'beta', 'beta', 'gamma']);
  });
});

describe('the defaults a foreign set opens on', () => {
  it('prefers an in_panel row when this case s own symbols are absent', () => {
    expect(defaultGene(FOREIGN)).toBe('ALPHA1');
    expect(compareDefaults(FOREIGN)).toEqual(['ALPHA1', 'ALPHA2-AS1']);
  });

  it('keeps a named preference when the set holds it', () => {
    expect(defaultGene(FOREIGN, 'GAMMA1')).toBe('GAMMA1');
  });

  it('falls back to the first row when nothing is flagged in_panel', () => {
    const foldOnly = FOREIGN.map((gene) => ({ ...gene, in_panel: false }));
    expect(defaultGene(foldOnly)).toBe('GAMMA1');
    expect(compareDefaults(foldOnly)).toEqual(['GAMMA1', 'BETA1']);
  });

  it('never returns an empty symbol for an empty set', () => {
    expect(defaultGene([])).toBeTruthy();
    expect(compareDefaults([]).every(Boolean)).toBe(true);
  });
});
