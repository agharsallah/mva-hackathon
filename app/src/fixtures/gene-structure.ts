import type { GeneStructure } from '../api/types';

/**
 * FIXTURE — `/api/panel/gene-structure`.
 *
 * ***SHAPE ONLY — not a measurement.*** The live endpoint assembles this from three
 * Ensembl REST calls. Nothing here was read from Ensembl:
 *
 * - **Coordinates are synthetic.** They ride the same arithmetic ladder as
 *   `locusFixture` (1000, 2000, 3000 …) so the gene track lines up with the QUAL/VAF
 *   tracks offline. They are not genomic coordinates and must never be quoted as such.
 * - **Exon count and protein length are BUB1B-*shaped*, not BUB1B.** 23 exons and a
 *   ~1050 aa protein is the right order of magnitude for the real gene; the individual
 *   exon spans are a generated pattern.
 * - **Domain names are real domain *names* at invented offsets.** BUBR1 genuinely
 *   carries a KEN box, a TPR (tetratricopeptide-repeat) region and a C-terminal kinase
 *   domain — the *positions* below are placed to make a readable figure, not measured.
 * - **Candidates are invented alleles.** The proband's are never committed.
 *
 * The app badges every one of these `fixture`, and the offline exhibit says so.
 */
export function geneStructureFixture(gene: string): GeneStructure {
  const exons = buildExons(23, 1000, 121_000);
  return {
    gene,
    ensembl_id: 'ENSG00000000000',
    chrom: '0',
    start: 1000,
    end: 121_000,
    strand: 1,
    biotype: 'protein_coding',
    transcript: 'ENST00000000000',
    protein: 'ENSP00000000000',
    protein_length: 1050,
    exons,
    domains: [
      { source: 'Pfam', accession: 'PF00000', name: 'KEN box (APC/C degron)', start_aa: 26, end_aa: 32, interpro: null },
      { source: 'Pfam', accession: 'PF08311', name: 'Mad3/Bub1 homology region 1 (TPR)', start_aa: 57, end_aa: 179, interpro: 'IPR013212' },
      { source: 'Smart', accession: 'SM00777', name: 'Mad3/Bub1 homology region 1 (TPR)', start_aa: 55, end_aa: 179, interpro: 'IPR013212' },
      { source: 'Gene3D', accession: '1.10.510.10', name: 'Transferase(Phosphotransferase) domain', start_aa: 782, end_aa: 1042, interpro: null },
      { source: 'SuperFamily', accession: 'SSF56112', name: 'Protein kinase-like domain superfamily', start_aa: 791, end_aa: 984, interpro: 'IPR011009' },
    ],
    candidates: [
      {
        consequence: 'stop_gained',
        impact: 'HIGH',
        rsid: 'rs000000001',
        rare: true,
        clin_sig: null,
        gt: '0/1',
        filter: 'PASS',
        label: 'stop gained · rs000000001',
        protein_pos: 737,
        reason: null,
      },
      {
        consequence: 'missense_variant',
        impact: 'MODERATE',
        rsid: null,
        rare: true,
        clin_sig: null,
        gt: '0/1',
        filter: 'PASS',
        label: 'missense',
        protein_pos: 1002,
        reason: null,
      },
      {
        consequence: 'splice_region_variant',
        impact: 'LOW',
        rsid: null,
        rare: false,
        clin_sig: null,
        gt: '0/1',
        filter: 'PASS',
        label: 'splice region',
        protein_pos: null,
        reason:
          'VEP reports no amino-acid position for a splice_region_variant on ENST00000000000',
      },
    ],
  };
}

/** `n` evenly spaced exon boxes across `[from, to]`, widening toward the middle. */
function buildExons(n: number, from: number, to: number) {
  const step = (to - from) / n;
  return Array.from({ length: n }, (_, i) => {
    const anchor = from + i * step;
    const width = Math.round(step * (0.12 + 0.18 * Math.sin((i / n) * Math.PI)));
    return { n: i + 1, start: Math.round(anchor), end: Math.round(anchor) + width, id: `ENSE0000000${i + 1}` };
  });
}
