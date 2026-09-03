/**
 * GET /api/health/dependencies — liveness of every backing service this app depends on.
 *
 * Unlike the rest of the API, this endpoint never returns 5xx: a dead dependency is a
 * `down` row in `checks`, not an exception. See scratchpad/health-contract.md for the
 * full contract this was transcribed from.
 */

/** `skipped` means "not configured" (e.g. no S3 credentials) — not a failure. */
export type HealthStatus = 'up' | 'degraded' | 'down' | 'skipped';

/**
 * `internal` — ours, required. `upstream` — ours, optional service (e.g. the reads API).
 * `third-party` — someone else's live service (Ensembl). `snapshot` — ingested reference
 * data, not a live service at all.
 */
export type DependencyKind = 'internal' | 'upstream' | 'third-party' | 'snapshot';

export interface DependencyCheck {
  /** Stable slug, one of: viz-api, warehouse, object-store, parquet, reads-api, ensembl,
   * reference-snapshots. */
  id: string;
  name: string;
  kind: DependencyKind;
  status: HealthStatus;
  /** Integer milliseconds; `null` when skipped. */
  latency_ms: number | null;
  /** This check's own timeout budget in ms — the number a `timed out after Ns` blew
   * through, and the one `MVA_HEALTH_TIMEOUTS` changes. Per check, because the probes
   * cost wildly different amounts (a WAN Postgres greet vs. pinging this process). */
  timeout_ms: number;
  /** When *this row* was measured. Per check rather than per payload, because
   * `?only=<id>` re-probes one service and serves the rest as last measured — the board
   * must be able to say which cards are older than the page. */
  checked_at: string;
  /** One line, what was actually observed. Never a secret. */
  detail: string;
  /** Actionable text, may be multi-line shell advice; `null` when status is `up`. */
  remedy: string | null;
  /** The app page names that stop working when this check is down. */
  powers: string[];
  /** Where it was probed, credentials stripped; `null` if not applicable. */
  endpoint: string | null;
}

export interface HealthDependencies {
  /** When this payload was assembled. Individual rows may be older — see
   * `DependencyCheck.checked_at`. */
  checked_at: string;
  /** `down` if any `internal` check is down; else `degraded` if any check is down or
   * degraded; else `up`. `skipped` never degrades this. */
  overall: HealthStatus;
  checks: DependencyCheck[];
}
