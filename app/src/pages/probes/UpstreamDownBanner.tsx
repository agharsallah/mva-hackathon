/**
 * The reads API is a separate service from the viz API, and only it can touch the read
 * store. When it is down the viz API answers 503 — an actionable state, so the banner
 * carries the exact command that fixes it rather than a generic error.
 */
import { BOX, cx } from '../../lib/ui';

export function UpstreamDownBanner({ detail }: { detail?: string }) {
  return (
    <div className={cx('rounded-card border p-4', BOX.broken)}>
      <div className="text-xs font-semibold text-broken-300">
        Reads API unreachable — probes cannot run
      </div>
      <p className="mt-2 text-sm leading-relaxed text-chrome-300">
        Every other page in this app reads precomputed tables and works without it. Probing needs
        the service that owns the 1.07-billion-read parquet store. Start it, then submit again:
      </p>
      <pre className="mt-2 overflow-x-auto rounded-card border border-line bg-chrome-950 p-3 font-mono text-micro text-good-300">
        MVA_API_TOKEN=&lt;secret&gt; uv run mva-reads-api --host 0.0.0.0 --port 8765
      </pre>
      <p className="mt-2 text-micro leading-relaxed text-chrome-500">
        The viz API proxies it — it needs <code className="text-chrome-400">MVA_READS_API_URL</code>{' '}
        and <code className="text-chrome-400">MVA_API_TOKEN</code> in its own environment to reach
        the service above.
      </p>
      {detail && <p className="mt-2 font-mono text-micro text-broken-400/80">{detail}</p>}
    </div>
  );
}
