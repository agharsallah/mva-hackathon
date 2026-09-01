import type { DerivationRow, LineageRow, ProbeLedgerRow, ReadRunRow, SourceObjectRow } from '../../api/types';
import { rows } from '../loader';

/**
 * FIXTURE — the delivery, one row per object.
 * MEASURED: 12 objects, every sha256 verified against the vendor manifest, 78.9 GiB of
 * gzipped FASTQ. File names below are placeholders; the live API reads the real manifest.
 * The four non-FASTQ rows are seeded from `data/provenance-sources.json`; FASTQ rows are
 * derived from `data/reads-runs.json`.
 */
export async function sourcesFixture(): Promise<SourceObjectRow[]> {
  const [statics, readRuns] = await Promise.all([
    rows<SourceObjectRow[]>('provenance-sources'),
    rows<ReadRunRow[]>('reads-runs'),
  ]);
  return [
    ...readRuns.map((r) => ({
      file_name: r.source,
      kind: 'fastq.gz',
      role: 'reads',
      size_bytes: r.source_bytes,
      hash_verified: true,
      sha256_source: 'vendor manifest',
      version_id: 'v1',
      lane: r.lane,
      read_num: r.read_num,
    })),
    ...statics,
  ];
}

/**
 * FIXTURE — lineage. Every derived table records where it came from, by what transform,
 * with which tool. Shape mirrors pg.meta.lineage; the live API serves the real rows.
 */
export async function lineageFixture(): Promise<LineageRow[]> {
  return rows<LineageRow[]>('provenance-lineage');
}

/** FIXTURE — each derivation carries the question it was built to answer. */
export async function derivationsFixture(): Promise<DerivationRow[]> {
  return rows<DerivationRow[]>('provenance-derivations');
}

/** FIXTURE — MEASURED: the oracle ledger is empty. 0 of 18 probes spent. */
export async function probeLedgerFixture(): Promise<ProbeLedgerRow[]> {
  return [];
}
