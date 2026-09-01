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
import { bafBinsFixture } from './karyogram';
import {
  depthDistributionFixture,
  filtersFixture,
  genotypesFixture,
  indelLengthsFixture,
  observedExpectedFixture,
  substitutionsFixture,
  tstvFixture,
} from './callset';
import { candidateFunnelFixture } from './funnel';
import { sequencingYieldFixture, vcfFieldsFixture, zygositySplitFixture } from './orphans';
import { catalogObjectsFixture } from './catalog-objects';
import { catalogColumnsFixture } from './catalog-semantics';
import { catalogTablesFixture } from './catalog-tables';
import { geneStructureFixture } from './gene-structure';
import {
  locusFixture,
  panelAnnotationsFixture,
  panelConstraintFixture,
  panelGenesFixture,
} from './panel';
import { clinvarPresenceFixture } from './clinvar';
import { panelBackgroundFixture } from './panel-background';
import { panelHetPairsFixture } from './panel-pairs';
import { panelSuppressedFixture } from './panel-suppressed';
import {
  cycleQualityFixture,
  flowcellFixture,
  qualityLevelsFixture,
  readPartitionsFixture,
  readRunsFixture,
} from './reads';
import { derivationsFixture, lineageFixture, probeLedgerFixture, sourcesFixture } from './provenance';
import { evidenceRegisterFixture, hypothesisRegisterFixture } from './science';
import { regionEnvelope, searchEnvelope } from './search';

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
  // Carries one SYNTHETIC shifted arm so the karyogram is exercisable offline. The live
  // table is flat; nothing here is a measurement.
  '/api/genome/baf-bins': (p) =>
    env(bafBinsFixture(p?.chrom as string | undefined), 'SYNTHETIC shifted arm — never measured'),
  '/api/callset/filters': () => env(filtersFixture, 'bcftools stats FILTER section'),
  '/api/callset/genotypes': () => env(genotypesFixture, 'bcftools stats genotype counts'),
  '/api/callset/depth-distribution': () => env(depthDistributionFixture, 'bcftools stats DP section'),
  '/api/callset/substitutions': () => env(substitutionsFixture, 'bcftools stats ST section'),
  '/api/callset/tstv': () => env(tstvFixture, 'bcftools stats TSTV section'),
  '/api/callset/indel-lengths': () => env(indelLengthsFixture, 'bcftools stats IDD section'),
  '/api/callset/observed-expected': () =>
    env(observedExpectedFixture, 'measured aggregates vs PLACEHOLDER published bands'),
  '/api/callset/funnel': () => env(candidateFunnelFixture, 'results.candidate_funnel'),
  '/api/callset/zygosity-split': () => env(zygositySplitFixture, 'results.stats_af'),
  '/api/callset/fields': () => env(vcfFieldsFixture, 'warehouse.vcf_fields'),
  '/api/panel/genes': () => env(panelGenesFixture, 'results.panel_gene_density + panel BED'),
  '/api/panel/constraint': () =>
    env(panelConstraintFixture, 'PLACEHOLDER gnomAD constraint + ClinVar counts'),
  // Transcribed from the executed derivation, so the offline exhibit shows the real
  // result rather than a plausible-looking one. Still marked `fixture:` in the UI.
  '/api/panel/background': () =>
    env(panelBackgroundFixture, 'transcribed results.panel_gene_background'),
  // `gene` is optional here, unlike /api/panel/locus: omitted means the whole panel.
  '/api/panel/annotations': (p) =>
    env(panelAnnotationsFixture(p?.gene as string | undefined), 'SYNTHETIC positions — never real'),
  '/api/panel/locus': (p) =>
    env(locusFixture((p?.gene as string | undefined) ?? 'BUB1B'), 'SYNTHETIC positions — never real'),
  '/api/panel/het-pairs': (p) =>
    env(
      panelHetPairsFixture((p?.gene as string | undefined) ?? 'BUB1B'),
      'SYNTHETIC positions — never real',
    ),
  // The per-gene ClinVar P/LP counts are MEASURED off the committed extract; every
  // callset-side hit and every position is shaped so the exhibit has one of each state.
  '/api/panel/clinvar-presence': (p) =>
    env(
      clinvarPresenceFixture(p?.gene as string | undefined),
      'measured ClinVar P/LP counts, SHAPED hits, SYNTHETIC positions',
    ),
  // The per-gene, per-FILTER census is MEASURED; the record positions are synthetic.
  '/api/panel/suppressed': (p) =>
    env(
      panelSuppressedFixture(p?.gene as string | undefined),
      'measured per-gene FILTER census, SYNTHETIC record positions',
    ),
  '/api/panel/gene-structure': (p) =>
    env(
      geneStructureFixture((p?.gene as string | undefined) ?? 'BUB1B'),
      'BUB1B-SHAPED structure — synthetic coordinates, domains not measured',
    ),
  '/api/reads/runs': () => env(readRunsFixture, 'reads/runs.parquet'),
  '/api/reads/partitions': () => env(readPartitionsFixture, 'reads/manifest.parquet'),
  '/api/reads/flowcell': (p) =>
    env(
      flowcellFixture(Number(p?.lane ?? 1), Number(p?.read ?? 1), Number(p?.shard ?? 0)),
      'one shard parquet, column-pruned',
    ),
  '/api/reads/cycle-quality': () => env(cycleQualityFixture, '100k-row sample per partition'),
  '/api/reads/quality-levels': () => env(qualityLevelsFixture, 'sampled per partition'),
  '/api/reads/yield': () => env(sequencingYieldFixture, 'results.sequencing_yield'),
  '/api/catalog/objects': () => env(catalogObjectsFixture, 'object ledger + delivery manifest'),
  '/api/catalog/tables': () => env(catalogTablesFixture, 'warehouse catalogue + meta.lineage'),
  '/api/catalog/columns': () =>
    env(catalogColumnsFixture, 'information_schema.columns + the column-meaning registry'),
  '/api/provenance/lineage': () => env(lineageFixture, 'meta.lineage'),
  '/api/provenance/derivations': () => env(derivationsFixture, 'meta.derivations'),
  '/api/provenance/sources': () => env(sourcesFixture, 'delivery manifest'),
  '/api/probe/ledger': () => env(probeLedgerFixture, 'probe ledger (empty: 0/18 spent)'),
  // Both carry their own envelope: `search` answers nothing at all for a query it cannot
  // resolve honestly, so the client re-raises the real error instead of faking a 404.
  '/api/search': (p) => searchEnvelope(p),
  '/api/callset/region': (p) => regionEnvelope(p),
  // INVENTED claims. The live register is empty and its tables do not exist yet; these
  // exist so the populated layout can be reviewed before there is anything real to show.
  '/api/science/hypotheses': () => env(hypothesisRegisterFixture, 'INVENTED research register'),
  '/api/science/evidence': () => env(evidenceRegisterFixture, 'INVENTED research register'),
};

export function fixtureFor(path: string, params?: Params): Envelope<unknown> | undefined {
  return registry[path]?.(params);
}
