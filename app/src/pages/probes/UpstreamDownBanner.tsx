/**
 * The reads API is a separate service from the viz API, and only it can touch the read
 * store. When it is down the viz API answers 503 — an actionable state, so the banner
 * carries the exact command that fixes it rather than a generic error.
 */
export function UpstreamDownBanner({ detail }: { detail?: string }) {
  return (
    <div className="rounded-xl border border-red-900/60 bg-red-950/25 p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-red-300">
        Reads API unreachable — probes cannot run
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-zinc-300">
        Every other page in this app reads precomputed tables and works without it. Probing needs
        the service that owns the 1.07-billion-read parquet store. Start it, then submit again:
      </p>
      <pre className="mt-2 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-[11px] text-emerald-300">
        MVA_API_TOKEN=&lt;secret&gt; uv run mva-reads-api --host 0.0.0.0 --port 8765
      </pre>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-500">
        The viz API proxies it — it needs <code className="text-zinc-400">MVA_READS_API_URL</code>{' '}
        and <code className="text-zinc-400">MVA_API_TOKEN</code> in its own environment to reach the
        service above.
      </p>
      {detail && <p className="mt-2 font-mono text-[11px] text-red-400/80">{detail}</p>}
    </div>
  );
}
