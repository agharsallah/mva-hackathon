import type { Exon, GeneStructure, GeneCandidate, ProteinDomain } from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — `/api/panel/gene-structure`. Default gene when none is given: BUB1B.
 *
 * ***SHAPE ONLY — not a measurement.*** The live endpoint assembles this from three
 * Ensembl REST calls. Nothing in `data/panel-gene-structure.json` or below was read from
 * Ensembl:
 *
 * - **Coordinates are synthetic.** They ride the same arithmetic ladder as
 *   `locusFixture` (1000, 2000, 3000 …) so the gene track lines up with the QUAL/VAF
 *   tracks offline. They are not genomic coordinates and must never be quoted as such.
 * - **Exon count and protein length are BUB1B-*shaped*, not BUB1B.** 23 exons and a
 *   ~1050 aa protein is the right order of magnitude for the real gene; the individual
 *   exon spans (`buildExons` below) are a generated pattern.
 * - **Domain names are real domain *names* at invented offsets.** BUBR1 genuinely
 *   carries a KEN box, a TPR (tetratricopeptide-repeat) region and a C-terminal kinase
 *   domain — the *positions* in the JSON are placed to make a readable figure, not
 *   measured.
 * - **Candidates are invented alleles.** The proband's are never committed.
 *
 * The app badges every one of these `fixture`, and the offline exhibit says so.
 */
interface Template {
  ensembl_id: string;
  chrom: string;
  start: number;
  end: number;
  strand: number;
  biotype: string | null;
  transcript: string | null;
  protein: string | null;
  protein_length: number | null;
  domains: ProteinDomain[];
  candidates: GeneCandidate[];
}

/** `n` evenly spaced exon boxes across `[from, to]`, widening toward the middle. */
function buildExons(n: number, from: number, to: number): Exon[] {
  const step = (to - from) / n;
  return Array.from({ length: n }, (_, i) => {
    const anchor = from + i * step;
    const width = Math.round(step * (0.12 + 0.18 * Math.sin((i / n) * Math.PI)));
    return { n: i + 1, start: Math.round(anchor), end: Math.round(anchor) + width, id: `ENSE0000000${i + 1}` };
  });
}

export async function geneStructureFixture(gene: string): Promise<GeneStructure> {
  const t = await rows<Template>('panel-gene-structure');
  const exons = buildExons(23, 1000, 121_000);
  return {
    gene,
    ensembl_id: t.ensembl_id,
    chrom: t.chrom,
    start: t.start,
    end: t.end,
    strand: t.strand,
    biotype: t.biotype,
    transcript: t.transcript,
    protein: t.protein,
    protein_length: t.protein_length,
    exons,
    domains: t.domains,
    candidates: t.candidates,
  };
}
