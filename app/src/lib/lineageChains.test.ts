import { describe, expect, it } from 'vitest';

import { type ChainEdge, chainOf, sourcesFor, splitChains } from './lineageChains';

const edge = (schema: string, table: string, source: string, at = '2026-01-01'): ChainEdge => ({
  produced_at: at,
  target_schema: schema,
  target_table: table,
  source_ref: source,
});

describe('lineage chains', () => {
  it('names a chain by the prefix of the table each edge writes', () => {
    expect(chainOf(edge('track2', 'it4.generators.prism', 'x'))).toBe('it4');
    expect(chainOf(edge('track2', 'transfer.BLM.prism_sweep', 'x'))).toBe('transfer.BLM');
    expect(chainOf(edge('track2', 'transfer_comparison', 'x'))).toBe('track2');
    expect(chainOf(edge('results', 'gene_biallelic', 'x'))).toBe('results');
  });

  it('walks a chain back to its roots and folds a chain it fully reaches into it', () => {
    const upstream = edge('submissions', 'track1/iteration-1', 'results.gene_biallelic');
    const card = edge('track2', 'targets', 'track1/iteration-1', '2026-01-02');
    const it4 = edge('track2', 'it4.candidates', 'https://example.org/prism.csv', '2026-01-03');
    const other = edge('track2', 'transfer.BLM.candidates', 'case.json', '2026-01-04');
    const chains = splitChains([upstream, card, it4, other]);

    // The Track 1 edge is reached from the `track2` chain, so it is not offered on its own.
    expect(chains.map((c) => c.id)).toEqual(['it4', 'track2', 'transfer.BLM']);
    const track2 = chains.find((c) => c.id === 'track2')!;
    expect(track2.edges).toEqual([card, upstream]);
    expect(track2.own).toBe(1);
    // A transfer case sorts after the proband's own chains even when it is newer.
    expect(chains.at(-1)!.transfer).toBe(true);
  });

  it('keeps a source no edge names beside whichever chain is shown', () => {
    const a = edge('track2', 'it4.x', 'file-a');
    const b = edge('track2', 'transfer.BLM.x', 'file-b');
    const sources = [{ ref: 'file-a' }, { ref: 'file-b' }, { ref: 'clinical.md' }];
    expect(sourcesFor(sources, [a, b], [a]).map((s) => s.ref)).toEqual(['file-a', 'clinical.md']);
  });
});
