/**
 * The cross-gene exhibits, mounted against mocked hooks.
 *
 * What is worth testing here is not the picture — jsdom has no WebGL, so `SceneFallback`
 * renders instead (see `viz3d/README.md`) — but the four things that decide whether the
 * exhibit tells the truth about a gene it cannot paint:
 *
 *  1. the picker groups the set, and says which group can carry an allele;
 *  2. picking a gene is held in the URL, so one link cites one comparison;
 *  3. a non-coding gene renders a named callout and **no canvas**;
 *  4. an off-panel gene renders the fold *and* the "nothing is painted, and here is why"
 *     callout — the one claim the whole widening of this exhibit rests on.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../../../../api/client';
import type { GeneStructure, ProteinStructure, StructureGene } from '../../../../api/types';

/** Every hook the two exhibits and the explorer reach for, driven from this one object. */
const state = {
  genes: [] as StructureGene[],
  protein: {} as Record<string, { data?: ProteinStructure; error?: Error }>,
  anatomy: {} as Record<string, { data?: GeneStructure; error?: Error }>,
};

const wrap = <T,>(data: T | undefined) =>
  data === undefined
    ? undefined
    : { data, cachedAt: null, source: 'test', origin: 'fixture' as const };

/**
 * The metrics table draws one Plotly bar chart, and `Plot` is mocked out whole rather than
 * having its library stubbed.
 *
 * `Plot` resolves a dynamic `import('plotly.js-dist-min')` and then calls `setReady(true)`.
 * That state update lands a microtask after the render, i.e. outside `act()`, so every
 * assertion in this file printed a React "not wrapped in act(...)" warning — a wall of noise
 * in `pnpm run check` for a chart that cannot draw in jsdom anyway. Nothing here asserts on
 * the picture; `Plot`'s own contract is tested where the component lives.
 */
vi.mock('../../../../components/Plot', () => ({
  Plot: () => <div data-testid="plot-stub" />,
}));

vi.mock('../../../../api/hooks', () => ({
  useStructureGenes: () => ({
    data: wrap(state.genes),
    error: null,
    isLoading: false,
  }),
  useProteinStructure: (gene: string | null) => ({
    data: gene ? wrap(state.protein[gene]?.data) : undefined,
    error: gene ? (state.protein[gene]?.error ?? null) : null,
    isLoading: false,
  }),
  useGeneStructure: (gene: string | null) => ({
    data: gene ? wrap(state.anatomy[gene]?.data) : undefined,
    error: gene ? (state.anatomy[gene]?.error ?? null) : null,
    isLoading: false,
  }),
  useHetPairs: () => ({ data: undefined, error: null, isLoading: false }),
  useGeneStructures: (genes: readonly string[]) =>
    genes.map((gene) => ({ data: wrap(state.anatomy[gene]?.data), error: null })),
  useProteinStructures: (genes: readonly string[]) =>
    genes.map((gene) => ({ data: wrap(state.protein[gene]?.data), error: null })),
}));

const { ProteinExplorer } = await import('../ProteinExplorer');
const { StructureCompare } = await import('./StructureCompare');
const { StructureMetricsTable } = await import('./StructureMetricsTable');

const PROTEIN = (gene: string) => `ENSP-${gene}`;

function structureOf(gene: string): ProteinStructure {
  return {
    gene,
    protein: PROTEIN(gene),
    uniprot: `P-${gene}`,
    provenance: 'alphafold',
    model_url: 'https://example.invalid/m.cif',
    version: '6',
    protein_length: 6,
    residues: Array.from({ length: 6 }, (_, i) => ({
      n: i + 1,
      aa: 'A',
      ca: [i, 0, 0] as [number, number, number],
      plddt: 90,
    })),
    covered: [[1, 6]],
    secondary: [{ kind: 'helix', start: 1, end: 3 }],
    partners: [],
  };
}

function anatomyOf(gene: string, inPanel: boolean): GeneStructure {
  return {
    gene,
    ensembl_id: `ENSG-${gene}`,
    chrom: '1',
    start: 1,
    end: 2,
    strand: 1,
    biotype: 'protein_coding',
    transcript: `ENST-${gene}`,
    protein: PROTEIN(gene),
    protein_length: 6,
    exons: [],
    domains: [],
    in_panel: inPanel,
    candidates: inPanel
      ? [
          {
            consequence: 'missense_variant',
            impact: 'MODERATE',
            rsid: 'rs1',
            rare: true,
            clin_sig: null,
            gt: '0/1',
            filter: 'PASS',
            label: 'missense · rs1',
            protein_pos: 2,
            reason: null,
          },
        ]
      : [],
  };
}

function gene(over: Partial<StructureGene> & { symbol: string }): StructureGene {
  return {
    ensembl_id: `ENSG-${over.symbol}`,
    group: 'panel',
    in_panel: true,
    biotype: 'protein_coding',
    coding: true,
    note: 'test',
    ...over,
  };
}

/** Prints the query string, so a URL assertion needs no router internals. */
function Url() {
  return <span data-testid="url">{useLocation().search}</span>;
}

function mount(node: ReactNode, at = '/panel') {
  return render(
    <MemoryRouter initialEntries={[at]}>
      {node}
      <Url />
    </MemoryRouter>,
  );
}

const url = () => screen.getByTestId('url').textContent ?? '';

/**
 * Assertions read the rendered *text*, not a queried element, on purpose: several of the
 * sentences under test are one text node beside a `<strong>` inside a Callout, so a
 * `getByText` would match the node and three of its ancestors and fail as ambiguous.
 */
const text = (): string => document.body.textContent ?? '';
const count = (needle: string): number => text().split(needle).length - 1;

beforeEach(() => {
  state.genes = [
    gene({ symbol: 'BUB1B' }),
    gene({ symbol: 'TRIP13' }),
    gene({ symbol: 'MAD2L1', group: 'mva-sac', in_panel: false }),
    gene({ symbol: 'TP53', group: 'extended', in_panel: false }),
    gene({
      symbol: 'BUB1B-AS1',
      group: 'extended',
      in_panel: false,
      coding: false,
      biotype: 'lncRNA',
    }),
  ];
  state.protein = Object.fromEntries(
    ['BUB1B', 'TRIP13', 'MAD2L1', 'TP53'].map((g) => [g, { data: structureOf(g) }]),
  );
  state.anatomy = Object.fromEntries(
    state.genes.map((g) => [g.symbol, { data: anatomyOf(g.symbol, g.in_panel) }]),
  );
});

describe('the gene picker', () => {
  it('groups the set and names what each group can show', () => {
    mount(<StructureCompare />);
    const groups = screen
      .getAllByRole('group')
      .map((node) => node.getAttribute('label'))
      .filter((label): label is string => label !== null);
    expect(new Set(groups)).toEqual(
      new Set([
        'annotated panel (alleles painted)',
        'MVA / SAC genes (fold only)',
        'extended (fold only)',
      ]),
    );
  });

  it('labels a non-coding gene as having no protein rather than hiding it', () => {
    mount(<StructureCompare />);
    expect(count('BUB1B-AS1 — non-coding, no protein')).toBeGreaterThan(0);
  });

  it('offers the whole set to the single-gene explorer under the shared ?gene= key', async () => {
    mount(<ProteinExplorer />);
    const picker = screen.getByLabelText('gene');
    await userEvent.selectOptions(picker, 'TP53');
    expect(url()).toContain('gene=TP53');
  });
});

describe('the comparison URL state', () => {
  it('opens on BUB1B against TRIP13 with a clean URL', () => {
    mount(<StructureCompare />);
    expect(screen.getByRole('combobox', { name: 'A' })).toHaveValue('BUB1B');
    expect(screen.getByRole('combobox', { name: 'B' })).toHaveValue('TRIP13');
    expect(url()).toBe('');
  });

  it('writes both sides, the encoding and the camera as separate keys', async () => {
    mount(<StructureCompare />);
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'A' }), 'MAD2L1');
    expect(url()).toContain('prot.cmpA=MAD2L1');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'B' }), 'TP53');
    expect(url()).toContain('prot.cmpB=TP53');
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'colour by (both)' }),
      'plddt',
    );
    expect(url()).toContain('prot.cmpBy=plddt');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'camera (both)' }), 'top');
    expect(url()).toContain('prot.cmpView=top');
  });

  it('canonicalises a lower-case or aliased symbol instead of falling back', () => {
    // The regression: `bub1b` is not literally in the vocabulary, so `known()` dropped it to
    // the default — and `?prot.cmpA=tp53` would silently have shown BUB1B. Canonicalising
    // before the check also means one cache key and one request pair per gene, not two.
    mount(<StructureCompare />, '/panel?prot.cmpA=tp53&prot.cmpB=mad2l1');
    expect(screen.getByRole('combobox', { name: 'A' })).toHaveValue('TP53');
    expect(screen.getByRole('combobox', { name: 'B' })).toHaveValue('MAD2L1');
  });

  it("titles the explorer in the set's spelling for a lower-case ?gene=", () => {
    mount(<ProteinExplorer />, '/panel?gene=bub1b');
    expect(text()).toContain("where BUB1B's alleles sit in space");
    // The picker resolves too, so no request is spent under a second cache key.
    expect(screen.getByRole('combobox', { name: 'gene' })).toHaveValue('BUB1B');
  });

  it('reads a URL-held pair, and falls back when it names a gene outside the set', () => {
    mount(<StructureCompare />, '/panel?prot.cmpA=TP53&prot.cmpB=NOT_A_GENE');
    expect(screen.getByRole('combobox', { name: 'A' })).toHaveValue('TP53');
    expect(screen.getByRole('combobox', { name: 'B' })).toHaveValue('TRIP13');
  });
});

describe('a gene the exhibit must not paint', () => {
  it('renders the off-panel callout beside the fold, naming the annotation scope', () => {
    mount(<StructureCompare />, '/panel?prot.cmpA=MAD2L1');
    expect(count('no annotated alleles: fold only')).toBe(1);
    expect(text()).toContain('because nothing was ever annotated there');
    expect(text()).toContain('eight-gene panel BED');
  });

  it('renders no fold at all for a non-coding gene, and says why', () => {
    mount(<StructureCompare />, '/panel?prot.cmpA=BUB1B-AS1');
    expect(text()).toContain('BUB1B-AS1 is non-coding — there is no protein');
    expect(text()).toContain('biotype lncRNA');
    // One fold, not two: side B still draws (as jsdom's no-WebGL list twin), side A does not.
    expect(count('This browser has no WebGL')).toBe(1);
  });

  it('reads a 422 from the protein endpoint as "non-coding", not as a failure', () => {
    state.protein.TP53 = {
      error: new ApiError(
        'TP53 has no protein-coding canonical transcript',
        422,
        '/api/panel/protein-structure',
      ),
    };
    mount(<ProteinExplorer />, '/panel?gene=TP53');
    expect(text()).toContain('TP53 is non-coding — there is no protein to fold');
    expect(text()).toContain('has no protein-coding canonical transcript');
    expect(text()).not.toContain('Request failed');
  });
});

describe('the cross-gene metrics table', () => {
  it('gives every gene a row, and says "non-coding" rather than leaving cells blank', () => {
    mount(<StructureMetricsTable />);
    for (const symbol of ['BUB1B', 'TRIP13', 'MAD2L1', 'TP53', 'BUB1B-AS1']) {
      expect(text()).toContain(symbol);
    }
    expect(count('non-coding, no protein')).toBe(1);
  });

  it('renders one row per symbol even when the reference set repeats one', () => {
    state.genes = [...state.genes, gene({ symbol: 'BUB1B' })];
    // The gene-name cell is a button, so one button per gene — a duplicate row would give two.
    mount(<StructureMetricsTable onPickGene={() => {}} />);
    expect(screen.getAllByRole('button', { name: 'BUB1B' })).toHaveLength(1);
  });

  it('reads n/a — fold only in the allele columns outside the panel', () => {
    mount(<StructureMetricsTable />);
    // Two off-panel genes have a metrics row (the non-coding one has none), plus the one
    // occurrence in the exhibit's own legend, which decodes the phrase.
    expect(count('n/a — fold only')).toBe(3);
  });

  it('hands a gene to the explorer and to either side of the comparison', async () => {
    const picked: string[] = [];
    const staged: string[] = [];
    mount(
      <StructureMetricsTable
        onPickGene={(g) => picked.push(g)}
        onCompare={(g, slot) => staged.push(`${g}:${slot}`)}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'MAD2L1' }));
    expect(picked).toEqual(['MAD2L1']);
    await userEvent.click(
      screen.getByRole('button', {
        name: 'put TP53 on side B of the side-by-side comparison',
      }),
    );
    expect(staged).toEqual(['TP53:B']);
  });
});
