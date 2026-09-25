import type {
  ZooCase,
  ZooGeneScores,
  ZooLineage,
  ZooMerge,
  ZooModel,
  ZooRanks,
  ZooReport,
  ZooReports,
  ZooRun,
} from '../../api/types/zoo';
import type { Entry } from '../loader';
import { rows } from '../loader';

/**
 * Model-zoo fixtures — **captured from the live API**, not synthesised.
 *
 * Every payload below was taken from a running `mva-viz-api` on 2026-09-23 (run
 * `it4-5e25dd45eee2`, six lanes) by `tools/capture_zoo_fixtures.py`, which `GET`s each
 * route and keeps the envelope's `data` verbatim; each file records
 * `"_captured": true`, the capture date and the API's own `source` line, which is the string
 * the registry then shows next to the exhibit. Nothing here is shaped by hand.
 *
 * **One deliberate redaction**, recorded in the file as `_redacted` and stated on the page
 * that shows it: `hgvs_c` / `hgvs_p` are nulled in `zoo-gene.json`. They are this patient's
 * own allele spellings; the live API serves them and a tracked file does not carry them.
 *
 * The two path-parameter routes (`/reports/{key}`, `/scores/gene/{symbol}`) are registered
 * once per captured key: a fixture is a snapshot of concrete answers, so the registry lists
 * the concrete paths rather than pretending to serve every model and every gene. A gene the
 * callset has no record for (`CEP57`) is deliberately *not* captured — the live route answers
 * 404 for it, and the client is supposed to surface that, not paper over it with a fixture.
 */

interface Wrapped<T> {
  /** True when the payload came off a live route rather than being assembled by hand. */
  _captured: boolean;
  captured_at: string;
  /** The API's own provenance line for this payload, carried through to the exhibit. */
  source: string;
  /** Field paths removed before committing, when any were. */
  _redacted?: string[];
  payload: T;
}

async function unwrap<T>(name: string): Promise<T> {
  return (await rows<Wrapped<T>>(name)).payload;
}

/** The provenance line an exhibit prints: the API's own source, marked as a capture. */
const from = (what: string, on = '2026-09-23'): string =>
  `captured ${on} from the live route · ${what}`;

/**
 * The merged report was re-captured on 2026-09-25, after it gained its hand-written headline
 * (close-out C4). The six lane reports were fetched again in the same pass and came back
 * identical to the 2026-09-23 capture, so they keep that date. The reports route reads
 * committed Markdown only, so the capture ran the real route in-process
 * (`TestClient(create_app())`), with the same wrapper as `tools/capture_zoo_fixtures.py`.
 */
const MERGED_CAPTURED = '2026-09-25';

/** The report keys captured: one per lane that ran, plus the cross-lane `merged` one. */
const REPORT_KEYS = ['merged', 'alphamissense', 'esm1b', 'esm2', 'gpnmsa', 'revel', 'spliceai'];

/** The genes captured. Any other symbol has no offline answer, and the page says so. */
const GENES = ['BUB1B', 'NBPF3'];

const reportEntry = (key: string): Entry => ({
  source: from(
    key === 'merged' ? 'docs/iteration4/report.md' : `docs/iteration4/reports/${key}.md`,
    key === 'merged' ? MERGED_CAPTURED : undefined,
  ),
  load: async () => (await unwrap<ZooReports>('zoo-reports'))[key] as ZooReport,
});

const geneEntry = (symbol: string): Entry => ({
  source: from(
    'pg.results.it4_allele_records ⋈ pg.warehouse.allele_scores (hgvs_c/hgvs_p redacted)',
  ),
  load: async () => (await unwrap<Record<string, ZooGeneScores>>('zoo-gene'))[symbol],
});

export const zooEntries: Record<string, Entry> = {
  '/api/zoo/case': {
    source: from('src/mva/zoo/zoo.example.toml'),
    load: () => unwrap<ZooCase>('zoo-case'),
  },
  '/api/zoo/models': {
    source: from(
      'src/mva/zoo/models.toml + models.d/*.toml, pg.warehouse.allele_scores, pg.results.it4_allele_records',
    ),
    load: () => unwrap<ZooModel[]>('zoo-models'),
  },
  '/api/zoo/ranks': {
    source: from('pg.results.it4_model_ranks, build/it4/merged.json (the two allele percentiles)'),
    load: () => unwrap<ZooRanks>('zoo-ranks'),
  },
  '/api/zoo/merge': {
    source: from('build/it4/merged.json, pg.results.it4_allele_records'),
    load: () => unwrap<ZooMerge>('zoo-merge'),
  },
  '/api/zoo/runs': {
    source: from('docs/iteration4/runs/*.json'),
    load: () => unwrap<ZooRun[]>('zoo-runs'),
  },
  '/api/zoo/lineage': {
    source: from('pg.warehouse.data_lineage'),
    load: () => unwrap<ZooLineage>('zoo-lineage'),
  },
  ...Object.fromEntries(REPORT_KEYS.map((key) => [`/api/zoo/reports/${key}`, reportEntry(key)])),
  ...Object.fromEntries(GENES.map((gene) => [`/api/zoo/scores/gene/${gene}`, geneEntry(gene)])),
};
