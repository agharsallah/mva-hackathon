/**
 * The offline structure fixtures answer the *same* refusals the live routes do.
 *
 * `src/test/fixtures.test.ts` hashes the payloads that succeed. It cannot cover the two
 * cases where the honest answer is an error, and those are exactly the cases a fixture
 * layer is tempted to paper over: a gene with no protein, and a gene that is not in the
 * set at all. Before this WP, *any* symbol got BUB1B's backbone with its own name on it.
 */
import { describe, expect, it } from 'vitest';

import { ApiError } from '../../api/client';
import { fixtureFor } from '..';

const GENE = '/api/panel/gene-structure';
const PROTEIN = '/api/panel/protein-structure';

const status = async (path: string, gene: string): Promise<number> => {
  try {
    await fixtureFor(path, { gene });
  } catch (err) {
    return (err as ApiError).status;
  }
  throw new Error(`${path}?gene=${gene} resolved, but should have refused`);
};

describe('the offline structure fixtures', () => {
  it('refuse a fold for a non-coding gene with the live route’s 422 and sentence', async () => {
    await expect(fixtureFor(PROTEIN, { gene: 'DICER1-AS1' })).rejects.toThrow(
      /DICER1-AS1 has no protein-coding canonical transcript/,
    );
    expect(await status(PROTEIN, 'MAMDC2-AS1')).toBe(422);
  });

  it('still serve a non-coding gene’s real exon track, with no protein', async () => {
    const payload = (await fixtureFor(GENE, { gene: 'DICER1-AS1' }))?.data as {
      protein: string | null;
      domains: unknown[];
      exons: unknown[];
      in_panel: boolean;
    };
    expect(payload.protein).toBeNull();
    expect(payload.domains).toEqual([]);
    expect(payload.exons.length).toBeGreaterThan(0);
    expect(payload.in_panel).toBe(false);
  });

  it('404 a symbol in neither the panel BED nor the gene set, on both routes', async () => {
    expect(await status(GENE, 'SONIC')).toBe(404);
    expect(await status(PROTEIN, 'SONIC')).toBe(404);
  });

  it('resolve the one Ensembl-verified alias, case-insensitively', async () => {
    const payload = (await fixtureFor(GENE, { gene: 'ccdc84' }))?.data as { gene: string };
    expect(payload.gene).toBe('CENATAC');
  });

  it('give the proband’s alleles to panel genes only', async () => {
    const of = async (gene: string) =>
      (await fixtureFor(GENE, { gene }))?.data as { in_panel: boolean; candidates: unknown[] };
    expect((await of('BUB1B')).candidates.length).toBeGreaterThan(0);
    const offPanel = await of('BUB1');
    expect(offPanel.in_panel).toBe(false);
    expect(offPanel.candidates).toEqual([]);
  });
});
