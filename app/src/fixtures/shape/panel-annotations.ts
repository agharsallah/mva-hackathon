import type { PanelAnnotationRow, VariantImpact } from '../../api/types';
import { prng } from '../prng';
import { rows } from '../loader';
import { panelGenesFixture } from './panel-genes';

/**
 * FIXTURE — per-variant annotations for the whole panel. `gene` omitted = whole panel.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY*** — the same 1000, 2000, 3000 … counter the locus
 * fixture uses, for the same reason: this repo commits no genomic coordinate. Frequencies,
 * consequences and ClinVar strings are shape, not measurement.
 *
 * The shape faithfully reproduces the real distillation: the generated bulk is either
 * common (so not rare-recessive) or non-coding (so not protein-altering), and exactly two
 * hand-placed BUB1B rows (`data/panel-annotations-extra.json`) clear both gates — a
 * `stop_gained` with a ClinVar pathogenic assertion, and a **novel** missense
 * (`gnomad_af: null`, absent from gnomAD). The set also carries a `1/2` multiallelic row
 * with `vaf: null`.
 *
 * The live API carries intergenic rows too (gene: null — the BED pads ±20 kb past each
 * gene), so the fixture exercises that bucket with 12 generated rows.
 */
const CONSEQUENCES: [string, VariantImpact][] = [
  ['intron_variant', 'MODIFIER'],
  ['upstream_gene_variant', 'MODIFIER'],
  ['3_prime_UTR_variant', 'MODIFIER'],
  ['synonymous_variant', 'LOW'],
  ['splice_region_variant', 'LOW'],
  ['missense_variant', 'MODERATE'],
  ['inframe_deletion', 'MODERATE'],
];

export async function panelAnnotationsFixture(geneName?: string): Promise<PanelAnnotationRow[]> {
  const [genes, extra] = await Promise.all([
    panelGenesFixture(),
    rows<PanelAnnotationRow[]>('panel-annotations-extra'),
  ]);
  const bases = ['A', 'C', 'G', 'T'];
  const out: PanelAnnotationRow[] = [];
  let counter = 0;

  for (const g of genes) {
    const rand = prng(g.gene.split('').reduce((a, c) => a + c.charCodeAt(0), 31));
    for (let i = 0; i < g.n_all; i++) {
      counter += 1;
      const r = rand();
      // Protein-altering rows are given a common frequency; rare rows are non-coding.
      // That is what keeps the candidate list at the two hand-placed rows below.
      const coding = r < 0.22;
      const pool = coding ? CONSEQUENCES.slice(5) : CONSEQUENCES.slice(0, 5);
      const [consequence, impact] = pool[Math.floor(rand() * pool.length)];
      const af = coding ? 0.02 + rand() * 0.4 : rand() < 0.12 ? null : rand() * 0.004;
      const grpmax = af === null ? null : Math.min(0.999, Math.round(af * (1.1 + rand() * 0.8) * 1e6) / 1e6);
      const multi = rand() < 0.02;
      const dp = Math.max(6, Math.round(44 + (rand() - 0.5) * 26));
      const filter = rand() < 0.05 ? 'MQ40' : 'PASS';
      out.push({
        chrom: g.chrom,
        pos: counter * 1000, // SYNTHETIC — a counter, not a coordinate
        ref: bases[Math.floor(rand() * 4)],
        alt: bases[Math.floor(rand() * 4)],
        rsid: af === null ? null : `rs${1_000_000 + counter * 37}`,
        gene: g.gene,
        consequence,
        impact,
        gnomad_af: af === null ? null : Math.round(af * 1e6) / 1e6,
        gnomad_af_grpmax: grpmax,
        clin_sig: coding && rand() < 0.15 ? 'Uncertain_significance' : null,
        qual: Math.round((filter === 'PASS' ? 200 + rand() * 1600 : 20 + rand() * 90) * 10) / 10,
        filter,
        gt: multi ? '1/2' : rand() < 0.62 ? '0/1' : '1/1',
        dp,
        vaf: multi ? null : Math.round((0.42 + rand() * 0.17) * 1000) / 1000,
        is_rare_recessive: af === null ? true : af < 0.005,
        is_protein_altering: impact === 'HIGH' || impact === 'MODERATE',
      });
    }
  }

  out.push(...extra);

  const inter = prng(97);
  for (let i = 0; i < 12; i++) {
    counter += 1;
    out.push({
      chrom: genes[i % genes.length].chrom,
      pos: counter * 1000, // SYNTHETIC — a counter, not a coordinate
      ref: bases[Math.floor(inter() * 4)],
      alt: bases[Math.floor(inter() * 4)],
      rsid: `rs${2_000_000 + counter * 41}`,
      gene: null,
      consequence: 'intergenic_variant',
      impact: 'MODIFIER',
      gnomad_af: Math.round(inter() * 0.3 * 1e6) / 1e6,
      gnomad_af_grpmax: Math.round(inter() * 0.4 * 1e6) / 1e6,
      clin_sig: null,
      qual: Math.round((200 + inter() * 900) * 10) / 10,
      filter: 'PASS',
      gt: '0/1',
      dp: Math.max(6, Math.round(44 + (inter() - 0.5) * 26)),
      vaf: Math.round((0.42 + inter() * 0.17) * 1000) / 1000,
      is_rare_recessive: false,
      is_protein_altering: false,
    });
  }

  if (!geneName) return out;
  const want = geneName.toUpperCase();
  return out.filter((r) => r.gene !== null && r.gene.toUpperCase() === want);
}
