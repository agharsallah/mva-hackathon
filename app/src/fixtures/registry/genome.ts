/**
 * Genome and reads fixture entries: contig-level QC, the karyogram's density and BAF
 * maps, and the sequencing-reads domain (runs, partitions, flowcell, per-cycle quality).
 *
 * `allele-balance`, `contig-density`, `reads/runs` and `reads/partitions` are static
 * tables with no request params — their rows are pre-rendered into `data/*.json` and
 * loaded verbatim. `density-bins`, `baf-bins` and `flowcell` are param-dependent
 * (chromosome, lane/read/shard), so only their constant tables live in JSON; the shaping
 * logic that turns those constants into rows stays in `shape/`.
 */

import type { SequencingYieldRow } from '../../api/types';
import { rows, type Entry } from '../loader';
import { densityBinsFixture } from '../shape/density-bins';
import { bafBinsFixture } from '../shape/baf-bins';
import { flowcellFixture } from '../shape/flowcell';
import { cycleQualityFixture, qualityLevelsFixture } from '../shape/read-quality';

export const genomeEntries: Record<string, Entry> = {
  '/api/genome/allele-balance': {
    source: 'results.allele_balance_flags',
    load: () => rows('genome-allele-balance'),
  },
  '/api/genome/contig-density': {
    source: 'results.contig_density',
    load: () => rows('genome-contig-density'),
  },
  '/api/genome/density-bins': {
    source: 'results.variant_density_bins',
    load: (p) => densityBinsFixture(p?.chrom as string | undefined),
  },
  // Carries one SYNTHETIC shifted arm so the karyogram is exercisable offline. The live
  // table is flat; nothing here is a measurement.
  '/api/genome/baf-bins': {
    source: 'SYNTHETIC shifted arm — never measured',
    load: (p) => bafBinsFixture(p?.chrom as string | undefined),
  },
  '/api/reads/runs': {
    source: 'reads/runs.parquet',
    load: () => rows('reads-runs'),
  },
  '/api/reads/partitions': {
    source: 'reads/manifest.parquet',
    load: () => rows('reads-partitions'),
  },
  '/api/reads/flowcell': {
    source: 'one shard parquet, column-pruned',
    load: (p) =>
      Promise.resolve(
        flowcellFixture(Number(p?.lane ?? 1), Number(p?.read ?? 1), Number(p?.shard ?? 0)),
      ),
  },
  '/api/reads/cycle-quality': {
    source: '100k-row sample per partition',
    load: () => Promise.resolve(cycleQualityFixture()),
  },
  '/api/reads/quality-levels': {
    source: 'sampled per partition',
    load: () => qualityLevelsFixture(),
  },
  // MEASURED. `results.sequencing_yield`, all four rows. Reads and bases are
  // **estimates**: they come from each FASTQ's compressed size and its first read's
  // length, because counting means decompressing 79 GB. `/api/reads/runs` carries the
  // counted figure.
  '/api/reads/yield': {
    source: 'results.sequencing_yield',
    load: () => rows<SequencingYieldRow[]>('reads-yield'),
  },
};
