/**
 * The scene builder is where a wrong answer would be *invisible*: a colour painted on the
 * wrong residue looks exactly as convincing as a colour painted on the right one. So the
 * assertions below are about identity and provenance first (the translation ids must match,
 * a candidate must land on its own residue index, an unplaceable one must be reported) and
 * about appearance second.
 */

import { describe, expect, it } from 'vitest';

import type { GeneStructure, ProteinStructure } from '../../../api/types';
import {
  buildProteinScene,
  emphasise,
  isCandidate,
  isLowConfidence,
  PLDDT_FLOOR,
  residueId,
  sliceProteinScene,
} from './buildScene';
import { domainAt, domainToneMap, NO_DOMAIN } from './encodings';

const PROTEIN = 'ENSP00000000001';

/** A 10-residue chain along x, 5 Å apart, with residue 8 below the confidence floor. */
function structure(over: Partial<ProteinStructure> = {}): ProteinStructure {
  return {
    gene: 'TESTGENE',
    protein: PROTEIN,
    uniprot: 'X00000',
    provenance: 'alphafold',
    model_url: 'https://example.invalid/model.cif',
    version: '6',
    protein_length: 10,
    residues: Array.from({ length: 10 }, (_, i) => ({
      n: i + 1,
      aa: 'ACDEFGHIKL'[i],
      ca: [i * 5, 0, 0] as [number, number, number],
      plddt: i + 1 === 8 ? 42 : 95,
    })),
    covered: [[1, 10]],
    secondary: [{ kind: 'helix', start: 2, end: 4 }],
    partners: [],
    ...over,
  };
}

function geneStructure(over: Partial<GeneStructure> = {}): GeneStructure {
  return {
    gene: 'TESTGENE',
    ensembl_id: 'ENSG00000000001',
    chrom: '1',
    start: 1,
    end: 2,
    strand: 1,
    biotype: 'protein_coding',
    transcript: 'ENST00000000001',
    protein: PROTEIN,
    protein_length: 10,
    exons: [],
    // `in_panel` is the flag that decides whether alleles exist at all; these fixtures are
    // panel genes, which is the only case in which `candidates` is non-empty.
    in_panel: true,
    domains: [
      { source: 'Pfam', accession: 'PF1', name: 'head', start_aa: 1, end_aa: 4, interpro: null },
      { source: 'Pfam', accession: 'PF2', name: 'tail', start_aa: 7, end_aa: 10, interpro: null },
      { source: 'Smart', accession: 'SM1', name: 'tail', start_aa: 6, end_aa: 10, interpro: null },
    ],
    candidates: [
      {
        consequence: 'stop_gained',
        impact: 'HIGH',
        rsid: 'rs1',
        rare: true,
        clin_sig: null,
        gt: '0/1',
        filter: 'PASS',
        label: 'stop gained · rs1',
        protein_pos: 2,
        reason: null,
      },
      {
        consequence: 'missense_variant',
        impact: 'MODERATE',
        rsid: null,
        rare: false,
        clin_sig: null,
        gt: '0/1',
        filter: 'PASS',
        label: 'missense',
        protein_pos: 8,
        reason: null,
      },
      {
        consequence: 'splice_region_variant',
        impact: 'LOW',
        rsid: null,
        rare: true,
        clin_sig: null,
        gt: '0/1',
        filter: 'PASS',
        label: 'splice region',
        protein_pos: null,
        reason: 'VEP reports no amino-acid position',
      },
    ],
    ...over,
  };
}

function built() {
  const result = buildProteinScene(structure(), geneStructure());
  if (!result.ok) throw new Error(`expected a scene, got ${result.error.kind}`);
  return result.build;
}

describe('buildProteinScene — the identity guard', () => {
  it('refuses to paint when the model and the annotations name different translations', () => {
    const result = buildProteinScene(structure({ protein: 'ENSP00000000002' }), geneStructure());
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.kind).toBe('protein-mismatch');
    expect(result.error.message).toContain('ENSP00000000002');
    expect(result.error.message).toContain(PROTEIN);
  });

  it('refuses a gene whose canonical transcript has no protein', () => {
    const result = buildProteinScene(structure(), geneStructure({ protein: null }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.kind).toBe('no-protein');
  });

  it('refuses a model with no coordinates', () => {
    const result = buildProteinScene(structure({ residues: [] }), geneStructure());
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error.kind).toBe('no-residues');
  });
});

describe('buildProteinScene — the scene', () => {
  it('puts one residue datum on the backbone per modelled residue, in order', () => {
    const { scene } = built();
    expect(scene.kind).toBe('protein');
    expect(scene.residues).toHaveLength(10);
    expect(scene.backbone).toHaveLength(10);
    expect(scene.residues.map((r) => r.id)).toEqual(
      Array.from({ length: 10 }, (_, i) => residueId(i + 1)),
    );
    expect(scene.residues[0].at).toEqual([0, 0, 0]);
    expect(scene.unit).toBe('Å');
  });

  it('places each candidate on its own protein_pos and reports the one it cannot place', () => {
    const { placed, unplaced } = built();
    expect(placed.map((p) => [p.label, p.n])).toEqual([
      ['stop gained · rs1', 2],
      ['missense', 8],
    ]);
    expect(unplaced).toHaveLength(1);
    expect(unplaced[0].label).toBe('splice region');
    expect(unplaced[0].reason).toContain('no amino-acid position');
  });

  it('reports a candidate outside the modelled chain rather than dropping it', () => {
    const gs = geneStructure();
    gs.candidates[1].protein_pos = 99;
    const result = buildProteinScene(structure(), gs);
    if (!result.ok) throw new Error('expected a scene');
    expect(result.build.placed).toHaveLength(1);
    expect(result.build.unplaced[0].reason).toContain('outside the modelled chain');
  });

  it('sizes candidate residues up and paints them in their impact tone', () => {
    const { scene } = built();
    const stop = scene.residues[1];
    const plain = scene.residues[0];
    expect(stop.tone).toBe('broken');
    expect(scene.residues[7].tone).toBe('decision');
    expect(stop.size).toBeGreaterThan(plain.size ?? 1);
    expect(plain.tone).toBeUndefined();
  });

  it('carries every per-residue fact the tooltip, filters and export read', () => {
    const { scene } = built();
    expect(scene.residues[1].meta).toEqual({
      n: 2,
      aa: 'C',
      plddt: 95,
      domain: 'head',
      secondary: 'helix',
      candidate: 'stop gained · rs1',
      impact: 'HIGH',
      rare: 'rare',
      clin_sig: null,
      consequence: 'stop_gained',
      confidence: 'high',
    });
    expect(scene.residues[4].meta?.candidate).toBeNull();
    expect(scene.residues[4].meta?.domain).toBe(NO_DOMAIN);
    expect(scene.residues[4].meta?.secondary).toBe('coil');
  });

  it('counts confidence honestly, and only over residues that have a pLDDT', () => {
    const build = built();
    expect(build.modelled).toBe(10);
    expect(build.unmodelled).toBe(0);
    expect(build.confident).toBe(9);
    expect(build.confidentFraction).toBeCloseTo(0.9);
  });

  it('reports the residues a model does not cover as unmeasured', () => {
    const result = buildProteinScene(
      structure({ protein_length: 20 }),
      geneStructure({ protein_length: 20 }),
    );
    if (!result.ok) throw new Error('expected a scene');
    expect(result.build.unmodelled).toBe(10);
  });

  it('has no pLDDT fraction for an experimental structure', () => {
    const model = structure({ provenance: 'pdb' });
    model.residues = model.residues.map((r) => ({ ...r, plddt: null }));
    const result = buildProteinScene(model, geneStructure());
    if (!result.ok) throw new Error('expected a scene');
    expect(result.build.confidentFraction).toBeNull();
  });

  it('declares every encoding the explorer offers, domain first', () => {
    const { scene } = built();
    expect(scene.encodings?.map((e) => e.id)).toEqual([
      'domain',
      'plddt',
      'impact',
      'secondary',
      'rarity',
    ]);
    expect(scene.color.id).toBe('domain');
  });
});

describe('domain assignment', () => {
  it('picks the smallest annotated domain covering a residue', () => {
    // 'tail' is annotated 7–10 by Pfam and 6–10 by Smart; the tighter one wins, and both
    // carry the same name so they share one colour.
    expect(domainAt(geneStructure().domains, 8)).toBe('tail');
    expect(domainAt(geneStructure().domains, 6)).toBe('tail');
    expect(domainAt(geneStructure().domains, 5)).toBe(NO_DOMAIN);
  });

  it('assigns tones by where the domain starts, and never red', () => {
    const tones = domainToneMap(geneStructure().domains);
    expect(tones).toEqual({ none: 'neutral', head: 'machinery', tail: 'raw' });
    expect(Object.values(tones)).not.toContain('broken');
  });

  it('falls to grey past the fourth domain rather than reusing a colour', () => {
    const many = Array.from({ length: 6 }, (_, i) => ({
      source: 'Pfam',
      accession: `PF${i}`,
      name: `d${i}`,
      start_aa: i + 1,
      end_aa: i + 2,
      interpro: null,
    }));
    const tones = domainToneMap(many);
    expect(tones.d4).toBe('neutral');
    expect(tones.d5).toBe('neutral');
    expect(new Set([tones.d0, tones.d1, tones.d2, tones.d3]).size).toBe(4);
  });
});

describe('sliceProteinScene', () => {
  it('trims the backbone as well as the spheres, so the camera can refit', () => {
    const { scene } = built();
    const cut = sliceProteinScene(scene, 3, 5);
    expect(cut.residues.map((r) => r.meta?.n)).toEqual([3, 4, 5]);
    expect(cut.backbone).toEqual([
      [10, 0, 0],
      [15, 0, 0],
      [20, 0, 0],
    ]);
  });

  it('is the identity when the window covers everything', () => {
    const { scene } = built();
    expect(sliceProteinScene(scene, 1, 10)).toBe(scene);
  });

  it('accepts a reversed window', () => {
    const { scene } = built();
    expect(sliceProteinScene(scene, 5, 3).residues).toHaveLength(3);
  });
});

describe('emphasise', () => {
  it('greys and shrinks a rejected residue instead of deleting it', () => {
    const { scene } = built();
    const dimmed = emphasise(scene, (datum) => !isLowConfidence(datum));
    expect(dimmed.residues).toHaveLength(scene.residues.length);
    const low = dimmed.residues[7];
    expect(low.tone).toBe('neutral');
    expect(low.size).toBeLessThan(scene.residues[7].size ?? 1);
    // Accepted residues are untouched, object identity included.
    expect(dimmed.residues[0]).toBe(scene.residues[0]);
  });
});

describe('residue classification', () => {
  it('reads low confidence off the pLDDT floor, and never off a null', () => {
    const { scene } = built();
    expect(PLDDT_FLOOR).toBe(70);
    expect(isLowConfidence(scene.residues[7])).toBe(true);
    expect(isLowConfidence(scene.residues[0])).toBe(false);
    expect(isLowConfidence({ id: 'x', label: 'x', at: [0, 0, 0], value: 0 })).toBe(false);
  });

  it('recognises a candidate by the label in its meta', () => {
    const { scene } = built();
    expect(isCandidate(scene.residues[1])).toBe(true);
    expect(isCandidate(scene.residues[0])).toBe(false);
  });
});
