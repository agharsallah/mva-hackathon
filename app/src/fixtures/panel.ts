import type {
  LocusVariant,
  PanelAnnotationRow,
  PanelConstraintRow,
  PanelGeneRow,
  VariantImpact,
} from '../api/types';
import { prng } from './prng';

/**
 * FIXTURE — MVA candidate panel scorecard.
 *
 * MEASURED: gene, chrom, n_all, n_pass, variants_per_mb, pct_pass for every row below.
 *
 * SYNTHETIC BY DESIGN: `start` / `end` are placeholders (1,000,000-based) — this repo
 * never commits a genomic coordinate, so the fixture carries none. `span_bp` is derived
 * from the measured n_all / variants_per_mb, which is a size, not a location. The live
 * API supplies the real interval and the Ensembl id from the panel BED.
 */
function gene(
  g: string,
  chrom: string,
  nAll: number,
  nPass: number,
  perMb: number,
  pctPass: number,
  note: string,
): PanelGeneRow {
  const spanBp = Math.round((nAll / perMb) * 1e6);
  return {
    gene: g,
    chrom,
    start: 1_000_000, // synthetic placeholder — see module note
    end: 1_000_000 + spanBp, // synthetic placeholder
    ensembl_id: '', // supplied by the live API from the panel BED
    note,
    n_all: nAll,
    n_pass: nPass,
    n_filtered: nAll - nPass,
    span_bp: spanBp,
    variants_per_mb: perMb,
    pct_pass: pctPass,
  };
}

/**
 * variants_per_mb is a measured anchor for BUB1B, CENPE, CEP192, SMC5 and TP53. For
 * CEP57, TRIP13 and DICER1 only the counts were recorded, so the density below is a
 * 1000.0 placeholder; the live API returns the measured value.
 */
export const panelGenesFixture: PanelGeneRow[] = [
  gene('BUB1B', 'chr15', 80, 76, 798.8, 95.0, 'spindle assembly checkpoint; the canonical MVA gene'),
  gene('CEP57', 'chr11', 13, 13, 1000.0, 100.0, 'centrosomal, microtubule nucleation; MVA type 2'),
  gene('TRIP13', 'chr5', 12, 6, 1000.0, 50.0, 'AAA-ATPase, checkpoint silencing; MVA type 3'),
  gene('CENPE', 'chr4', 169, 166, 1269.6, 98.2, 'centromere kinesin, chromosome congression'),
  gene('CEP192', 'chr18', 255, 251, 1467.4, 98.4, 'centrosome maturation and duplication'),
  gene('SMC5', 'chr9', 125, 124, 915.0, 99.2, 'SMC5/6 complex, genome stability'),
  gene('DICER1', 'chr14', 87, 87, 1000.0, 100.0, 'miRNA processing; tumour-predisposition overlap'),
  gene('TP53', 'chr17', 120, 118, 1824.6, 98.3, 'tumour suppressor; mitotic surveillance'),
];

/**
 * FIXTURE — locus explorer.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY.*** The live endpoint returns real patient
 * coordinates; committing one would break the project's patient-data rule. So the
 * positions here are a plain arithmetic ladder (1000, 2000, 3000, …) and are obviously
 * not genomic. Only the *shape* of the response is faithful: a QUAL spread, a mix of
 * PASS and suppressed records, 0/1 · 1/1 · 1/2 genotypes, depths around the 44x mode
 * and VAFs around 0.5.
 */
export function locusFixture(geneName: string): LocusVariant[] {
  const row = panelGenesFixture.find((g) => g.gene.toUpperCase() === geneName.toUpperCase());
  const n = row ? Math.min(row.n_all, 120) : 40;
  const rand = prng(geneName.split('').reduce((a, c) => a + c.charCodeAt(0), 7));
  const bases = ['A', 'C', 'G', 'T'];
  const out: LocusVariant[] = [];
  for (let i = 0; i < n; i++) {
    const r = rand();
    const filter = r < 0.05 ? 'MQ40' : r < 0.08 ? 'QD2' : 'PASS';
    const gtRoll = rand();
    const gt = gtRoll < 0.6 ? '0/1' : gtRoll < 0.94 ? '1/1' : '1/2';
    const dp = Math.max(6, Math.round(44 + (rand() - 0.5) * 26));
    const vaf = gt === '1/1' ? 0.94 + rand() * 0.06 : 0.42 + rand() * 0.17;
    const adAlt = Math.round(dp * vaf);
    out.push({
      pos: (i + 1) * 1000, // SYNTHETIC — a counter, not a coordinate
      ref: bases[Math.floor(rand() * 4)],
      alt: bases[Math.floor(rand() * 4)],
      qual: Math.round((filter === 'PASS' ? 200 + rand() * 1600 : 20 + rand() * 90) * 10) / 10,
      filter,
      gt,
      dp,
      ad_ref: dp - adAlt,
      ad_alt: adAlt,
      vaf: Math.round(vaf * 1000) / 1000,
      gq: Math.min(99, Math.round(30 + rand() * 69)),
    });
  }
  return out;
}

/**
 * FIXTURE — gnomAD constraint + ClinVar counts per panel gene.
 *
 * ***SHAPE ONLY — none of these numbers is a measurement from this project.*** The live
 * endpoint reads them from the gnomAD constraint table and a ClinVar summary; until it
 * answers, these fill the chart so the exhibit is readable offline, and the app badges
 * every one of them `fixture`.
 *
 * The shape it deliberately exercises is the counter-intuitive one the exhibit exists to
 * show: MVA is **recessive**, so healthy carriers of a single broken copy are common and
 * the established MVA genes score as *unconstrained* (pLI ≈ 0, LOEUF ≫ 0.35). TRIP13
 * carries `null` constraint to exercise the unknown rendering — null is "no row in the
 * source table", never "unconstrained".
 */
function constraint(
  gene: string,
  chrom: string,
  nAll: number,
  nPass: number,
  loeuf: number | null,
  pli: number | null,
  misZ: number | null,
  lofObs: number | null,
  lofExp: number | null,
  clinvar: [number, number, number],
  note: string,
): PanelConstraintRow {
  return {
    gene,
    chrom,
    n_all: nAll,
    n_pass: nPass,
    loeuf,
    pli,
    mis_z: misZ,
    oe_lof: lofObs !== null && lofExp ? Math.round((lofObs / lofExp) * 1000) / 1000 : null,
    lof_obs: lofObs,
    lof_exp: lofExp,
    clinvar_plp: clinvar[0],
    clinvar_vus: clinvar[1],
    clinvar_benign: clinvar[2],
    ensembl_id: '', // supplied by the live API from the panel BED
    note,
  };
}

export const panelConstraintFixture: PanelConstraintRow[] = [
  constraint('BUB1B', 'chr15', 80, 76, 0.98, 0.0, 0.71, 41, 42.1, [38, 214, 61], 'recessive MVA type 1 — carriers are healthy, so it is not LoF-constrained'),
  constraint('CEP57', 'chr11', 13, 13, 1.24, 0.0, -0.32, 19, 18.4, [9, 47, 22], 'recessive MVA type 2 — same carrier logic'),
  constraint('TRIP13', 'chr5', 12, 6, null, null, null, null, null, [6, 31, 14], 'no row in the constraint source — unknown, not unconstrained'),
  constraint('CENPE', 'chr4', 169, 166, 0.86, 0.0, 1.44, 62, 68.9, [4, 96, 55], 'recessive microcephaly gene; also tolerant of single-copy loss'),
  constraint('CEP192', 'chr18', 255, 251, 0.63, 0.02, 2.18, 33, 47.8, [1, 74, 40], 'essential centrosome scaffold, mildly depleted'),
  constraint('SMC5', 'chr9', 125, 124, 0.72, 0.01, 1.96, 21, 27.5, [3, 58, 29], 'genome-stability complex'),
  constraint('DICER1', 'chr14', 87, 87, 0.31, 0.97, 3.42, 12, 51.7, [212, 388, 96], 'dominant tumour-predisposition gene — strongly constrained, as dominance predicts'),
  constraint('TP53', 'chr17', 120, 118, 0.34, 0.94, 3.11, 6, 24.3, [431, 512, 133], 'dominant tumour suppressor — strongly constrained'),
];

const CONSEQUENCES: [string, VariantImpact][] = [
  ['intron_variant', 'MODIFIER'],
  ['upstream_gene_variant', 'MODIFIER'],
  ['3_prime_UTR_variant', 'MODIFIER'],
  ['synonymous_variant', 'LOW'],
  ['splice_region_variant', 'LOW'],
  ['missense_variant', 'MODERATE'],
  ['inframe_deletion', 'MODERATE'],
];

/**
 * FIXTURE — per-variant annotations for the whole panel.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY*** — the same 1000, 2000, 3000 … counter the locus
 * fixture uses, for the same reason: this repo commits no genomic coordinate. Frequencies,
 * consequences and ClinVar strings are shape, not measurement.
 *
 * The shape faithfully reproduces the real distillation: the generated bulk is either
 * common (so not rare-recessive) or non-coding (so not protein-altering), and exactly two
 * hand-placed BUB1B rows clear both gates — a `stop_gained` with a ClinVar pathogenic
 * assertion, and a **novel** missense (`gnomad_af: null`, absent from gnomAD). The set also
 * carries a `1/2` multiallelic row with `vaf: null`.
 */
export function panelAnnotationsFixture(geneName?: string): PanelAnnotationRow[] {
  const bases = ['A', 'C', 'G', 'T'];
  const out: PanelAnnotationRow[] = [];
  let counter = 0;

  for (const g of panelGenesFixture) {
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

  const bub1b = panelGenesFixture[0];
  out.push(
    {
      chrom: bub1b.chrom,
      pos: 900_000, // SYNTHETIC
      ref: 'C',
      alt: 'T',
      rsid: 'rs137852899',
      gene: 'BUB1B',
      consequence: 'stop_gained',
      impact: 'HIGH',
      gnomad_af: 0.0000062,
      gnomad_af_grpmax: 0.0000141,
      clin_sig: 'Pathogenic',
      qual: 1841.6,
      filter: 'PASS',
      gt: '0/1',
      dp: 47,
      vaf: 0.511,
      is_rare_recessive: true,
      is_protein_altering: true,
    },
    {
      chrom: bub1b.chrom,
      pos: 901_000, // SYNTHETIC
      ref: 'G',
      alt: 'A',
      rsid: null,
      gene: 'BUB1B',
      consequence: 'missense_variant',
      impact: 'MODERATE',
      gnomad_af: null, // novel — absent from gnomAD entirely
      gnomad_af_grpmax: null,
      clin_sig: null,
      qual: 1204.3,
      filter: 'PASS',
      gt: '0/1',
      dp: 39,
      vaf: 0.487,
      is_rare_recessive: true,
      is_protein_altering: true,
    },
  );

  // The live API carries intergenic rows (gene: null — the BED pads ±20 kb past each
  // gene), so the fixture must exercise that bucket too.
  const inter = prng(97);
  for (let i = 0; i < 12; i++) {
    counter += 1;
    out.push({
      chrom: panelGenesFixture[i % panelGenesFixture.length].chrom,
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
