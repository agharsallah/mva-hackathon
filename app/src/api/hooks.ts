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
  HypothesisRegister,
  IndelLengthRow,
  Job,
  LineageRow,
  LocusVariant,
  ObservedExpectedRow,
  Overview,
  PanelAnnotationRow,
  PanelConstraintRow,
  PanelGeneRow,
  PanelHetPairs,
  ProbeLedgerRow,
  QualityLevelRow,
  ReadPartitionRow,
  ReadRunRow,
  SourceObjectRow,
  SubstitutionRow,
  TsTv,
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
export const useDepthDistribution = () => useEndpoint<DepthBinRow[]>('/api/callset/depth-distribution');
export const useSubstitutions = () => useEndpoint<SubstitutionRow[]>('/api/callset/substitutions');
export const useTsTv = () => useEndpoint<TsTv>('/api/callset/tstv');
export const useIndelLengths = () => useEndpoint<IndelLengthRow[]>('/api/callset/indel-lengths');
export const useObservedExpected = () =>
  useEndpoint<ObservedExpectedRow[]>('/api/callset/observed-expected');
export const useCandidateFunnel = () => useEndpoint<FunnelStageRow[]>('/api/callset/funnel');

export const usePanelGenes = () => useEndpoint<PanelGeneRow[]>('/api/panel/genes');
export const usePanelConstraint = () => useEndpoint<PanelConstraintRow[]>('/api/panel/constraint');
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

export const useReadRuns = () => useEndpoint<ReadRunRow[]>('/api/reads/runs');
export const useReadPartitions = () => useEndpoint<ReadPartitionRow[]>('/api/reads/partitions');
export const useFlowcell = (lane: number, read: number, shard: number) =>
  useEndpoint<FlowcellBinRow[]>('/api/reads/flowcell', { lane, read, shard });
export const useCycleQuality = () => useEndpoint<CycleQualityRow[]>('/api/reads/cycle-quality');
export const useQualityLevels = () => useEndpoint<QualityLevelRow[]>('/api/reads/quality-levels');

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
