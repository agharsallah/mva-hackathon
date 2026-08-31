/**
 * Fixture registry: path → envelope.
 *
 * The fetch wrapper consults this only when the API is unreachable (or the endpoint is
 * not implemented yet) and fixtures are enabled. Every fixture module documents which of
 * its numbers are measured and which fill a shape.
 *
 * `cached_at` is null and `source` is prefixed "fixture:" so the origin is visible in the
 * UI and can never be mistaken for a live table.
 */

import type { Envelope } from '../api/types';
import type { Params } from '../api/client';
import { overviewFixture } from './overview';
import { alleleBalanceFixture, contigDensityFixture, densityBinsFixture } from './genome';
import {
  depthDistributionFixture,
  filtersFixture,
  genotypesFixture,
  indelLengthsFixture,
  substitutionsFixture,
  tstvFixture,
} from './callset';
import { locusFixture, panelGenesFixture } from './panel';
import {
  cycleQualityFixture,
  flowcellFixture,
  qualityLevelsFixture,
  readPartitionsFixture,
  readRunsFixture,
} from './reads';
import { derivationsFixture, lineageFixture, probeLedgerFixture, sourcesFixture } from './provenance';

function env<T>(data: T, source: string): Envelope<T> {
  return { data, cached_at: null, source: `fixture: ${source}` };
}

type Builder = (params?: Params) => Envelope<unknown>;

const registry: Record<string, Builder> = {
  '/api/overview': () => env(overviewFixture, 'measured aggregates, executed exploration runs'),
  '/api/genome/allele-balance': () => env(alleleBalanceFixture, 'results.allele_balance_flags'),
  '/api/genome/contig-density': () => env(contigDensityFixture, 'results.contig_density'),
  '/api/genome/density-bins': (p) =>
    env(densityBinsFixture(p?.chrom as string | undefined), 'results.variant_density_bins'),
  '/api/callset/filters': () => env(filtersFixture, 'bcftools stats FILTER section'),
  '/api/callset/genotypes': () => env(genotypesFixture, 'bcftools stats genotype counts'),
  '/api/callset/depth-distribution': () => env(depthDistributionFixture, 'bcftools stats DP section'),
  '/api/callset/substitutions': () => env(substitutionsFixture, 'bcftools stats ST section'),
  '/api/callset/tstv': () => env(tstvFixture, 'bcftools stats TSTV section'),
  '/api/callset/indel-lengths': () => env(indelLengthsFixture, 'bcftools stats IDD section'),
  '/api/panel/genes': () => env(panelGenesFixture, 'results.panel_gene_density + panel BED'),
  '/api/panel/locus': (p) =>
    env(locusFixture((p?.gene as string | undefined) ?? 'BUB1B'), 'SYNTHETIC positions — never real'),
  '/api/reads/runs': () => env(readRunsFixture, 'reads/runs.parquet'),
  '/api/reads/partitions': () => env(readPartitionsFixture, 'reads/manifest.parquet'),
  '/api/reads/flowcell': (p) =>
    env(
      flowcellFixture(Number(p?.lane ?? 1), Number(p?.read ?? 1), Number(p?.shard ?? 0)),
      'one shard parquet, column-pruned',
    ),
  '/api/reads/cycle-quality': () => env(cycleQualityFixture, '100k-row sample per partition'),
  '/api/reads/quality-levels': () => env(qualityLevelsFixture, 'sampled per partition'),
  '/api/provenance/lineage': () => env(lineageFixture, 'meta.lineage'),
  '/api/provenance/derivations': () => env(derivationsFixture, 'meta.derivations'),
  '/api/provenance/sources': () => env(sourcesFixture, 'delivery manifest'),
  '/api/probe/ledger': () => env(probeLedgerFixture, 'probe ledger (empty: 0/18 spent)'),
};

export function fixtureFor(path: string, params?: Params): Envelope<unknown> | undefined {
  return registry[path]?.(params);
}
