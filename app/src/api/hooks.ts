/**
 * One react-query hook per endpoint. All of them are the same three lines, so the file
 * stays a table of contents for the API rather than logic.
 *
 * Retries are off: a down API should surface immediately (the client falls back to
 * fixtures on its own), and a 503 from the reads proxy is a state to render, not to retry.
 */

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { useMemo } from 'react';

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
  PhenotypeDelta,
  PhenotypeGeneDetail,
  PhenotypeRanking,
  PhenotypeTerms,
  ProbeLedgerRow,
  ProteinStructure,
  QualityLevelRow,
  ReadPartitionRow,
  ReadRunRow,
  ReferenceProvenanceRow,
  RegionWindow,
  SearchResolution,
  SequencingYieldRow,
  SourceObjectRow,
  StructureGene,
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
/**
 * The curated gene set the structure explorer may show, in display order.
 *
 * Reads a committed reference TSV server-side, so it answers on a checkout where nothing has
 * been ingested. `in_panel` is the one flag that decides whether a gene can carry the
 * proband's alleles at all: the callset was annotated over the 8-gene panel BED, so every
 * other gene in this set is fold-only — its structure is public reference data and nothing
 * patient-derived is painted on it.
 */
export const useStructureGenes = () => useEndpoint<StructureGene[]>('/api/panel/structure-genes');

/** ~5–15 s cold (two Ensembl calls, the AlphaFold API, then a ~1 MB mmCIF), then disk-cached. */
export const useProteinStructure = (gene: string | null) =>
  useEndpoint<ProteinStructure>('/api/panel/protein-structure', gene ? { gene } : undefined, {
    enabled: !!gene,
  });
/**
 * The same two endpoints as above, for **many genes at once**, one query each.
 *
 * `useQueries` rather than a loop of `useGeneStructure` calls because the gene list is
 * dynamic (it comes from `/api/panel/structure-genes`), and React's hook order may not
 * depend on data. The per-gene results come back in the order the symbols were passed, so a
 * table can render one row per gene with its **own** loading and error state — a gene whose
 * fold is missing does not blank the other rows.
 *
 * Cost: 2 × N requests. Both endpoints are disk-cached server-side and served from a
 * committed fixture offline, so a warm call is cheap; a cold live call is not, which is why
 * the cross-gene table is the only caller — and why it passes `enabled: false` until the
 * table is actually in the reader's viewport.
 *
 * The symbol list is **deduped** before the fan-out. Two identical symbols would otherwise
 * produce two queries under one key — React Query serves both from one request, but the
 * caller gets two result slots and renders the gene twice.
 *
 * `combine` narrows each result to the two fields a row cares about, and — the reason it is
 * here rather than in the caller — makes the returned array **referentially stable**: a raw
 * `useQueries` return is a fresh array of fresh objects on every render, so a consumer's
 * `useMemo` over it never hits. The cross-gene table's rows each build a full protein scene,
 * so that miss cost ~44 chain walks on every unrelated re-render of the page.
 */
function useEndpointEach<T>(path: string, genes: readonly string[], enabled = true) {
  const unique = useMemo(() => [...new Set(genes)], [genes]);
  return useQueries({
    queries: unique.map((gene) => ({
      queryKey: [path, { gene }],
      queryFn: ({ signal }: { signal: AbortSignal }) => get<T>(path, { gene }, signal),
      enabled,
      retry: false,
      staleTime: FIVE_MIN,
      gcTime: 30 * FIVE_MIN,
      refetchOnWindowFocus: false,
    })),
    combine: (results) =>
      results.map((result) => ({ data: result.data, error: result.error ?? null })),
  });
}

export const useGeneStructures = (genes: readonly string[], enabled = true) =>
  useEndpointEach<GeneStructure>('/api/panel/gene-structure', genes, enabled);

export const useProteinStructures = (genes: readonly string[], enabled = true) =>
  useEndpointEach<ProteinStructure>('/api/panel/protein-structure', genes, enabled);

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
/**
 * Reference data provenance: one row per committed reference table or offline fixture
 * directory, read off the `*provenance.json` manifest committed beside the bytes.
 *
 * Not lineage. The three hooks above read `warehouse.data_lineage`, which records a
 * *derivation* (table X was computed from object Y). Reference data is **fetched**, so it
 * has no upstream table and no transform — a manifest (URL + version + hash) is what it
 * has instead.
 */
export const useReferenceProvenance = () =>
  useEndpoint<ReferenceProvenanceRow[]>('/api/provenance/reference');
export const useProbeLedger = () => useEndpoint<ProbeLedgerRow[]>('/api/probe/ledger');

// The register may not exist yet, so both payloads are `{table_exists, rows}` rather than
// a bare list — see `api/types/science.ts`.
export const useHypotheses = () => useEndpoint<HypothesisRegister>('/api/science/hypotheses');
export const useEvidence = () => useEndpoint<EvidenceRegister>('/api/science/evidence');

/** Background poll for the Status board: quiet, because probing costs real round trips
 * to Postgres, MinIO and Ensembl on every pass. */
export const HEALTH_POLL_MS = 1_800_000;

/** The endpoint every health control talks to — the board, and the per-card re-probe. */
export const HEALTH_PATH = '/api/health/dependencies';

/**
 * The board's react-query key for a given `refresh` flag.
 *
 * Exported because the per-card re-probe writes its reply straight into this entry
 * (`setQueryData`) instead of invalidating it: the API answers a partial re-probe with the
 * *whole* board — the named check freshly measured, the rest as last measured — so the
 * reply is already the new state of the page. Invalidating would instead throw away seven
 * good rows and re-probe all seven, which is the cost the per-card button exists to avoid.
 */
export const healthQueryKey = (refresh: boolean) => [
  HEALTH_PATH,
  refresh ? { refresh: true } : null,
];

/**
 * Dependency health board (`Status` page).
 *
 * Two cadences, on purpose. `staleTime` stays short so *opening* the page always probes
 * rather than rendering a cached "up" from half an hour ago — a stale health card is worse
 * than no card. `refetchInterval` is long because each pass costs real round trips to
 * Postgres, MinIO and a third party; an open tab should not generate traffic all day.
 *
 * `refresh` also bypasses the API's own ~10s probe cache, so `/status?refresh` re-probes
 * for real instead of being served whatever the server measured last. It changes the
 * query key too, which is what makes navigating to that URL fetch immediately.
 */
export const useHealthDependencies = (refresh = false) =>
  useEndpoint<HealthDependencies>(HEALTH_PATH, refresh ? { refresh: true } : undefined, {
    staleTime: 5_000,
    refetchInterval: HEALTH_POLL_MS,
  });

/**
 * Re-probe **one** dependency, from that dependency's own card.
 *
 * The page-wide `Re-probe now` costs a round trip to Postgres, MinIO, the reads API and
 * Ensembl at once. After restarting a single service that is six requests nobody asked
 * for, and against a slow dependency it is also the slowest possible way to learn whether
 * the one thing you just fixed came back. `only=<id>&refresh=true` probes that check and
 * serves the rest from the API's per-check cache, so the button costs exactly one probe.
 *
 * A mutation rather than a query: it is an explicit action with a result, not a piece of
 * state the page reads, and `isPending` per id is what the card needs to disable itself.
 */
export function useReprobeCheck(refresh = false) {
  const client = useQueryClient();
  const mutation = useMutation<Result<HealthDependencies>, Error, string>({
    mutationFn: (id) => get<HealthDependencies>(HEALTH_PATH, { only: id, refresh: true }),
    onSuccess: (result) => client.setQueryData(healthQueryKey(refresh), result),
  });
  return {
    reprobe: mutation.mutate,
    /** The id currently in flight, or `null` — one card spins, not the whole board. */
    pendingId: mutation.isPending ? (mutation.variables ?? null) : null,
    error: mutation.error,
  };
}

/**
 * The phenotype ranking (`Phenotype` page).
 *
 * These four read committed reference tables rather than the warehouse, so they answer on
 * a checkout where nobody has run an ingest. They are also the only endpoints in this app
 * whose rows were produced without reading the callset — which is exactly why they are
 * worth having next to everything that did.
 */
export const usePhenotypeTerms = () => useEndpoint<PhenotypeTerms>('/api/phenotype/terms');

export const usePhenotypeGenes = (termSet: string, limit = 50) =>
  useEndpoint<PhenotypeRanking>('/api/phenotype/genes', { term_set: termSet, limit });

export const usePhenotypeGene = (symbol: string, termSet: string) =>
  useEndpoint<PhenotypeGeneDetail>('/api/phenotype/gene', { symbol, term_set: termSet });

export const usePhenotypeDelta = () => useEndpoint<PhenotypeDelta>('/api/phenotype/delta');

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
