import type { LocusVariant } from '../../api/types';
import { prng } from '../prng';
import { panelGenesFixture } from './panel-genes';

/**
 * FIXTURE — locus explorer.
 *
 * ***SYNTHETIC POSITIONS, DELIBERATELY.*** The live endpoint returns real patient
 * coordinates; committing one would break the project's patient-data rule. So the
 * positions here are a plain arithmetic ladder (1000, 2000, 3000, …) and are obviously
 * not genomic. Only the *shape* of the response is faithful: a QUAL spread, a mix of
 * PASS and suppressed records, 0/1 · 1/1 · 1/2 genotypes, depths around the 44x mode
 * and VAFs around 0.5.
 *
 * Default gene when none is given: BUB1B.
 */
export async function locusFixture(geneName: string): Promise<LocusVariant[]> {
  const genes = await panelGenesFixture();
  const row = genes.find((g) => g.gene.toUpperCase() === geneName.toUpperCase());
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
