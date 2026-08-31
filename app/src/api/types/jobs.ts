// ---------------------------------------------------------------------------
// Reads-API proxy: asynchronous jobs over the FASTQ store.
// ---------------------------------------------------------------------------

export type JobState = 'queued' | 'running' | 'done' | 'failed' | 'cancelled' | 'lost';

export interface ProbeSpec {
  name?: string;
  sequence: string;
}

/** verdict is the server's call on a count: present / one-lane / error-level / absent. */
export interface ProbeCount {
  probe: string;
  forward: number;
  reverse: number;
  total: number;
  lanes: number;
  verdict: string;
}

export interface ProbeCountResult {
  root: string;
  seconds: number;
  expected: string;
  counts: ProbeCount[];
}

export interface ProbeScanHit {
  probe: string;
  lane: number;
  read_num: number;
  tile: number;
  x: number;
  y: number;
  position: number;
  strand: string;
  sequence: string;
}

export interface ProbeScanResult {
  root: string;
  probes: number;
  seconds: number;
  hits: ProbeScanHit[];
}

/**
 * Job timestamps come off the upstream reads API as **Unix epoch seconds** (floats), not
 * ISO strings — verified against the live service. `Instant` covers both so the formatter
 * can accept either without a crash if the upstream ever changes.
 */
export type Instant = string | number;

export interface Job<R = unknown> {
  id: string;
  verb: string;
  state: JobState;
  params: Record<string, unknown>;
  submitted_at: Instant;
  started_at: Instant | null;
  finished_at: Instant | null;
  elapsed_seconds: number | null;
  result: R | null;
  error: string | null;
}

export type CountJob = Job<ProbeCountResult>;
