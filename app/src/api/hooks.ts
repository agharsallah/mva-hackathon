/**
 * One react-query hook per endpoint. All of them are the same three lines, so the file
 * stays a table of contents for the API rather than logic.
 *
 * Retries are off: a down API should surface immediately (the client falls back to
 * fixtures on its own), and a 503 from the reads proxy is a state to render, not to retry.
 */

import { useQuery, type UseQueryOptions } from '@tanstack/react-query';

import { get, getBare, type Params, type Result } from './client';
import type {
  AlleleBalanceRow,
  BafBinRow,
  CatalogColumnRow,
  CatalogObjectRow,
  CatalogTableRow,
  ClinvarPresence,
  ContigDensityRow,
  CycleQualityRow,
  DensityBinRow,
  DepthBinRow,
  DerivationRow,
  EvidenceRegister,
  FilterRow,
  FlowcellBinRow,
  FunnelStageRow,
  GeneStructure,
  GenotypeRow,
  HealthDependencies,
  HypothesisRegister,
  IndelLengthRow,
  Job,
  LineageRow,
  LocusVariant,
  ObservedExpectedRow,
  Overview,
  PanelAnnotationRow,
  PanelBackgroundRow,
  PanelConstraintRow,
  PanelGeneRow,
  PanelHetPairs,
  PanelSuppressed,
  ProbeLedgerRow,
  QualityLevelRow,
  ReadPartitionRow,
  ReadRunRow,
  RegionWindow,
  SearchResolution,
  SequencingYieldRow,
  SourceObjectRow,
  SubstitutionRow,
  TsTv,
  VcfFieldRow,
  ZygosityRow,
} from './types';

const FIVE_MIN = 5 * 60 * 1000;

type Opts<T> = Omit<UseQueryOptions<Result<T>, Error>, 'queryKey' | 'queryFn'>;

function useEndpoint<T>(path: string, params?: Params, opts?: Opts<T>) {
  return useQuery<Result<T>, Error>({
    queryKey: [path, params ?? null],
    queryFn: ({ signal }) => get<T>(path, params, signal),
    retry: false,
    staleTime: FIVE_MIN,
    gcTime: 30 * FIVE_MIN,
    refetchOnWindowFocus: false,
    ...opts,
  });
}

export const useOverview = () => useEndpoint<Overview>('/api/overview');
export const useAlleleBalance = () => useEndpoint<AlleleBalanceRow[]>('/api/genome/allele-balance');
export const useContigDensity = () => useEndpoint<ContigDensityRow[]>('/api/genome/contig-density');
export const useDensityBins = (chrom?: string) =>
  useEndpoint<DensityBinRow[]>('/api/genome/density-bins', chrom ? { chrom } : undefined);
export const useBafBins = (chrom?: string) =>
  useEndpoint<BafBinRow[]>('/api/genome/baf-bins', chrom ? { chrom } : undefined);

export const useFilters = () => useEndpoint<FilterRow[]>('/api/callset/filters');
export const useGenotypes = () => useEndpoint<GenotypeRow[]>('/api/callset/genotypes');
export const useDepthDistribution = () =>
  useEndpoint<DepthBinRow[]>('/api/callset/depth-distribution');
export const useSubstitutions = () => useEndpoint<SubstitutionRow[]>('/api/callset/substitutions');
export const useTsTv = () => useEndpoint<TsTv>('/api/callset/tstv');
export const useIndelLengths = () => useEndpoint<IndelLengthRow[]>('/api/callset/indel-lengths');
export const useObservedExpected = () =>
  useEndpoint<ObservedExpectedRow[]>('/api/callset/observed-expected');
export const useCandidateFunnel = () => useEndpoint<FunnelStageRow[]>('/api/callset/funnel');
/** Two rows. `af_bin` is a het/hom split, never a population frequency — see the type. */
export const useZygositySplit = () => useEndpoint<ZygosityRow[]>('/api/callset/zygosity-split');
export const useVcfFields = () => useEndpoint<VcfFieldRow[]>('/api/callset/fields');

export const usePanelGenes = () => useEndpoint<PanelGeneRow[]>('/api/panel/genes');
export const usePanelConstraint = () => useEndpoint<PanelConstraintRow[]>('/api/panel/constraint');
/** Each gene's density and PASS share z-scored against the 1 Mb-window background. */
export const usePanelBackground = () => useEndpoint<PanelBackgroundRow[]>('/api/panel/background');
/** `gene` omitted returns every annotated panel row (~874). */
export const usePanelAnnotations = (gene?: string) =>
  useEndpoint<PanelAnnotationRow[]>('/api/panel/annotations', gene ? { gene } : undefined);
/** ~5 s live: the server pushes the contig down into the raw variant table. */
export const useLocus = (gene: string | null) =>
  useEndpoint<LocusVariant[]>('/api/panel/locus', gene ? { gene } : undefined, {
    enabled: !!gene,
  });
/** ~5–10 s cold (three Ensembl REST calls), then served from the server's disk cache. */
export const useGeneStructure = (gene: string | null) =>
  useEndpoint<GeneStructure>('/api/panel/gene-structure', gene ? { gene } : undefined, {
    enabled: !!gene,
  });
/** ~0.5–1 s live: a derived table, so no cross product happens inside the request. */
export const useHetPairs = (gene: string | null) =>
  useEndpoint<PanelHetPairs>('/api/panel/het-pairs', gene ? { gene } : undefined, {
    enabled: !!gene,
  });
/**
 * ~1 s live: a derived table, so the ClinVar-to-callset join is already done. `gene`
 * omitted returns all eight panel genes. Only the present and uncomparable sites come
 * back as rows; the absences are counts on `summary`.
 */
export const useClinvarPresence = (gene?: string) =>
  useEndpoint<ClinvarPresence>('/api/panel/clinvar-presence', gene ? { gene } : undefined);
/**
 * ~0.7 s live: two derived tables, 20 rows each. `gene` narrows only the `records` half —
 * the census is always the whole panel, so the same query key serves the whole chart.
 */
export const usePanelSuppressed = (gene?: string) =>
  useEndpoint<PanelSuppressed>('/api/panel/suppressed', gene ? { gene } : undefined);

/** Resolve a typed query to a window. 0.001 s for a region, ~1 s panel, ~2–5 s Ensembl. */
export const useSearch = (q: string | null) =>
  useEndpoint<SearchResolution>('/api/search', q ? { q } : undefined, { enabled: !!q });
/** ~1.5–2.5 s live on the unindexed raw callset layer, then served from the disk cache. */
export const useRegion = (at: { chrom: string; start: number; end: number } | null) =>
  useEndpoint<RegionWindow>('/api/callset/region', at ?? undefined, { enabled: !!at });

export const useReadRuns = () => useEndpoint<ReadRunRow[]>('/api/reads/runs');
export const useReadPartitions = () => useEndpoint<ReadPartitionRow[]>('/api/reads/partitions');
export const useFlowcell = (lane: number, read: number, shard: number) =>
  useEndpoint<FlowcellBinRow[]>('/api/reads/flowcell', { lane, read, shard });
export const useCycleQuality = () => useEndpoint<CycleQualityRow[]>('/api/reads/cycle-quality');
export const useQualityLevels = () => useEndpoint<QualityLevelRow[]>('/api/reads/quality-levels');
/** Per-lane yield **estimated** from the delivered bytes; `useReadRuns` is the count. */
export const useSequencingYield = () => useEndpoint<SequencingYieldRow[]>('/api/reads/yield');

export const useCatalogObjects = () => useEndpoint<CatalogObjectRow[]>('/api/catalog/objects');
export const useCatalogTables = () => useEndpoint<CatalogTableRow[]>('/api/catalog/tables');
export const useCatalogColumns = () => useEndpoint<CatalogColumnRow[]>('/api/catalog/columns');

export const useLineage = () => useEndpoint<LineageRow[]>('/api/provenance/lineage');
export const useDerivations = () => useEndpoint<DerivationRow[]>('/api/provenance/derivations');
export const useSources = () => useEndpoint<SourceObjectRow[]>('/api/provenance/sources');
export const useProbeLedger = () => useEndpoint<ProbeLedgerRow[]>('/api/probe/ledger');

// The register may not exist yet, so both payloads are `{table_exists, rows}` rather than
// a bare list — see `api/types/science.ts`.
export const useHypotheses = () => useEndpoint<HypothesisRegister>('/api/science/hypotheses');
export const useEvidence = () => useEndpoint<EvidenceRegister>('/api/science/evidence');

/**
 * Dependency health board (`Status` page). Every other hook above wants the 5-minute
 * default `staleTime` — the underlying facts barely change between visits. This one is
 * the opposite: it exists to answer "is anything broken *right now*", so a stale "up"
 * card would be actively misleading. Short `staleTime` plus a ~15s poll keeps the board
 * honest without hammering the probes — the server already caches its own probe result
 * for ~10s, so this poll cadence just tracks that.
 */
export const useHealthDependencies = () =>
  useEndpoint<HealthDependencies>('/api/health/dependencies', undefined, {
    staleTime: 5_000,
    refetchInterval: 15_000,
  });

const LIVE_STATES = new Set(['queued', 'running']);

/**
 * Jobs list from the reads-API proxy. No envelope, no fixture: a job queue only exists on
 * a live server. Polls fast while something is in flight and slowly otherwise, so an idle
 * tab is nearly free.
 */
export function useJobs() {
  return useQuery<Job[], Error>({
    queryKey: ['/api/jobs'],
    queryFn: () => getBare<Job[]>('/api/jobs'),
    retry: false,
    refetchInterval: (query) =>
      query.state.data?.some((j) => LIVE_STATES.has(j.state)) ? 4000 : 20_000,
    refetchOnWindowFocus: false,
    staleTime: 0,
  });
}
