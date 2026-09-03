/**
 * `metrics.ts` — the cross-gene reduction. Every case below is a statement the table would
 * otherwise get quietly wrong: a `null` rendered as a zero, a denominator taken from the
 * wrong set, or an off-panel gene reported as having no alleles.
 */

import { describe, expect, it } from 'vitest';

import { ApiError } from '../../../../api/client';
import type {
  GeneCandidate,
  GeneStructure,
  ProteinResidue,
  ProteinStructure,
  SecondarySegment,
  StructureGene,
} from '../../../../api/types';
import { isNonCodingError, structureMetrics, structureRow } from './metrics';

const PROTEIN = 'ENSP00000000001';

/** Ten residues on a straight line 5 Å apart, so every distance is arithmetic. */
function residues(plddt: (n: number) => number | null): ProteinResidue[] {
  return Array.from({ length: 10 }, (_, i) => ({
    n: i + 1,
    aa: 'A',
    ca: [5 * i, 0, 0] as [number, number, number],
    plddt: plddt(i + 1),
  }));
}

function structure(over: Partial<ProteinStructure> = {}): ProteinStructure {
  return {
    gene: 'GENE1',
    protein: PROTEIN,
    uniprot: 'P00001',
    provenance: 'alphafold',
    model_url: 'https://example.invalid/model.cif',
    version: '6',
    protein_length: 20,
    residues: residues((n) => (n <= 6 ? 90 : 30)),
    covered: [[1, 10]],
    secondary: [],
    partners: [],
    ...over,
  };
}

function candidate(over: Partial<GeneCandidate> = {}): GeneCandidate {
  return {
    consequence: 'missense_variant',
    impact: 'MODERATE',
    rsid: null,
    rare: true,
    clin_sig: null,
    gt: '0/1',
    filter: 'PASS',
    label: 'missense',
    protein_pos: 1,
    reason: null,
    ...over,
  };
}

function anatomy(over: Partial<GeneStructure> = {}): GeneStructure {
  return {
    gene: 'GENE1',
    ensembl_id: 'ENSG00000000001',
    chrom: '1',
    start: 1,
    end: 2,
    strand: 1,
    biotype: 'protein_coding',
    transcript: 'ENST00000000001',
    protein: PROTEIN,
    protein_length: 20,
    exons: [],
    domains: [],
    in_panel: true,
    candidates: [],
    ...over,
  };
}

function entry(over: Partial<StructureGene> = {}): StructureGene {
  return {
    symbol: 'GENE1',
    ensembl_id: 'ENSG00000000001',
    group: 'panel',
    group_label: 'the annotated panel',
    group_order: 0,
    in_panel: true,
    biotype: 'protein_coding',
    coding: true,
    note: 'test',
    ...over,
  };
}

describe('structureMetrics — denominators', () => {
  it('measures modelled residues against the translation length, not against itself', () => {
    const m = structureMetrics(structure(), anatomy(), entry());
    expect(m.modelled).toBe(10);
    expect(m.length).toBe(20);
    expect(m.modelledFraction).toBeCloseTo(0.5);
  });

  it('measures pLDDT ≥ 70 against the residues that carry a pLDDT', () => {
    const m = structureMetrics(structure(), anatomy(), entry());
    expect(m.confident).toBe(6);
    expect(m.confidentFraction).toBeCloseTo(0.6);
  });

  it('reports no confidence at all for an experimental structure, never 0 %', () => {
    const m = structureMetrics(
      structure({ provenance: 'pdb', residues: residues(() => null) }),
      anatomy(),
      entry(),
    );
    expect(m.confident).toBeNull();
    expect(m.confidentFraction).toBeNull();
    expect(m.provenance).toBe('pdb');
  });
});

describe('structureMetrics — absence is never zero', () => {
  it('reports null helix/strand when the file annotates no secondary structure', () => {
    const m = structureMetrics(structure({ secondary: [] }), anatomy(), entry());
    expect(m.helixFraction).toBeNull();
    expect(m.strandFraction).toBeNull();
  });

  it('counts a helix segment over the translation length, and 0 for the absent kind', () => {
    const secondary: SecondarySegment[] = [{ kind: 'helix', start: 1, end: 5 }];
    const m = structureMetrics(structure({ secondary }), anatomy(), entry());
    expect(m.helixFraction).toBeCloseTo(5 / 20);
    // Annotation exists, and it says "no strand here" — that IS zero, not null.
    expect(m.strandFraction).toBe(0);
  });

  it('clamps a segment that runs past the translation', () => {
    const secondary: SecondarySegment[] = [{ kind: 'strand', start: 15, end: 999 }];
    const m = structureMetrics(structure({ secondary }), anatomy(), entry());
    expect(m.strandFraction).toBeCloseTo(6 / 20);
  });

  it('lists domains once each, in chain order', () => {
    const m = structureMetrics(
      structure(),
      anatomy({
        domains: [
          {
            source: 'Pfam',
            accession: 'PF2',
            name: 'kinase',
            start_aa: 8,
            end_aa: 12,
            interpro: null,
          },
          {
            source: 'SMART',
            accession: 'SM1',
            name: 'TPR',
            start_aa: 2,
            end_aa: 4,
            interpro: null,
          },
          {
            source: 'Gene3D',
            accession: 'G1',
            name: 'kinase',
            start_aa: 9,
            end_aa: 11,
            interpro: null,
          },
        ],
      }),
      entry(),
    );
    expect(m.domains).toEqual(['TPR', 'kinase']);
  });
});

describe('structureMetrics — alleles and the panel boundary', () => {
  it('places candidates and measures the closest pair in ångström', () => {
    const m = structureMetrics(
      structure(),
      anatomy({
        candidates: [
          candidate({ protein_pos: 1, label: 'a' }),
          candidate({ protein_pos: 3, label: 'b' }),
          candidate({ protein_pos: 9, label: 'c' }),
        ],
      }),
      entry(),
    );
    expect(m.allelesPlaced).toBe(3);
    expect(m.allelesUnplaced).toBe(0);
    // Residues 1 and 3 are two 5 Å steps apart on the line.
    expect(m.closestPairAngstrom).toBeCloseTo(10);
    // Residue 9's pLDDT is 30, but the closest pair is 1↔3, both at 90.
    expect(m.closestPairConfident).toBe(true);
  });

  it('reports a candidate the model cannot place instead of dropping it', () => {
    const m = structureMetrics(
      structure(),
      anatomy({
        candidates: [candidate({ protein_pos: null }), candidate({ protein_pos: 18 })],
      }),
      entry(),
    );
    expect(m.allelesPlaced).toBe(0);
    expect(m.allelesUnplaced).toBe(2);
    expect(m.closestPairAngstrom).toBeNull();
  });

  it('nulls both allele columns off-panel — never 0, which would be a claim', () => {
    const m = structureMetrics(
      structure(),
      anatomy({ in_panel: false }),
      entry({ in_panel: false, group: 'mva-sac' }),
    );
    expect(m.inPanel).toBe(false);
    expect(m.group).toBe('mva-sac');
    expect(m.allelesPlaced).toBeNull();
    expect(m.allelesUnplaced).toBeNull();
    expect(m.closestPairAngstrom).toBeNull();
  });

  it('falls back to GeneStructure.in_panel and names no group with no set entry', () => {
    const m = structureMetrics(structure(), anatomy({ in_panel: false }));
    expect(m.inPanel).toBe(false);
    // No group id is invented: only the set may name a group, and `in_panel` alone carries
    // the conservative reading (fold only, no alleles claimed).
    expect(m.group).toBe('');
    expect(m.groupLabel).toBe('group not stated');
  });

  it('reports a translation mismatch and still reports the structural columns', () => {
    const m = structureMetrics(structure(), anatomy({ protein: 'ENSP00000000999' }), entry());
    expect(m.mismatch).toMatch(/only meaningful on the translation/);
    expect(m.allelesPlaced).toBeNull();
    // The coordinate file alone still says how much was modelled.
    expect(m.modelled).toBe(10);
    expect(m.confidentFraction).toBeCloseTo(0.6);
  });
});

describe('structureRow — one row per gene, one state per row', () => {
  const ok = { data: structure(), error: null };
  const okAnatomy = { data: anatomy(), error: null };

  it('is ready when both payloads arrived and agree', () => {
    const row = structureRow(entry(), ok, okAnatomy);
    expect(row.kind).toBe('ready');
    expect(row.note).toBe('');
    expect(row.metrics?.modelled).toBe(10);
  });

  it('is loading while either payload is missing', () => {
    expect(structureRow(entry(), { data: null, error: null }, okAnatomy).kind).toBe('loading');
    expect(structureRow(entry(), ok, { data: null, error: null }).kind).toBe('loading');
  });

  it('says non-coding from the set alone, without an error', () => {
    const row = structureRow(
      entry({ coding: false, biotype: 'lncRNA' }),
      { data: null, error: null },
      okAnatomy,
    );
    expect(row.kind).toBe('non-coding');
    expect(row.note).toBe('non-coding, no protein');
    expect(row.metrics).toBeNull();
  });

  it('reads a 422 as non-coding, and any other status as an error', () => {
    const notCoding = new ApiError(
      'BUB1B-AS1 has no protein-coding canonical transcript',
      422,
      '/api/panel/protein-structure',
    );
    expect(isNonCodingError(notCoding)).toBe(true);
    expect(structureRow(entry(), { data: null, error: notCoding }, okAnatomy).kind).toBe(
      'non-coding',
    );

    const upstream = new ApiError('AlphaFold DB unreachable', 502, '/x');
    expect(isNonCodingError(upstream)).toBe(false);
    const row = structureRow(entry(), { data: null, error: upstream }, okAnatomy);
    expect(row.kind).toBe('error');
    expect(row.note).toMatch(/AlphaFold DB unreachable/);
  });

  it('says mismatch rather than printing allele numbers off the wrong sequence', () => {
    const row = structureRow(entry(), ok, {
      data: anatomy({ protein: 'ENSP00000000999' }),
      error: null,
    });
    expect(row.kind).toBe('mismatch');
    expect(row.metrics).toBeNull();
  });
});
