import { useMemo, useState } from 'react';

import { Badge } from '../../components/Badge';
import { dec } from '../../lib/format';
import { jobStateTone } from '../../lib/palette';
import { ProbeResults } from './ProbeResults';
import { UpstreamDownBanner } from './UpstreamDownBanner';
import { isUpstreamDown, parseProbes, useProbeJob } from './useProbeJob';

const PLACEHOLDER = `# one probe per line:  name  SEQUENCE   (name optional)
# only A, C, G, T — 12 to 200 letters
ref_allele    ACGTACGTACGTACGTACGTACGTACGTAC
alt_allele    ACGTACGTACGTACGTTCGTACGTACGTAC`;

/**
 * The probe console.
 *
 * This is the one place in the app that *asks the raw data a new question* rather than
 * displaying a precomputed table. Counting a literal sequence across 1.07 billion reads
 * takes minutes, so the request is a job: submit, then follow it with a server-side
 * long-poll until it terminates.
 */
export function ProbeConsole() {
  const [text, setText] = useState('');
  const { job, error, submitting, waiting, submit, cancel, reset } = useProbeJob();
  const parsed = useMemo(() => parseProbes(text), [text]);
  const valid = parsed.filter((p) => p.valid);
  const invalid = parsed.filter((p) => !p.valid);
  const running = job !== null && (job.state === 'queued' || job.state === 'running');

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="rounded-xl border border-chrome-800 bg-chrome-900/40 p-4">
          <label className="text-xs font-medium text-chrome-300">
            Probes
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={PLACEHOLDER}
              spellCheck={false}
              rows={9}
              className="mt-1.5 w-full resize-y rounded-lg border border-chrome-700 bg-chrome-950 p-3 font-mono text-xs text-chrome-100 placeholder:text-chrome-600 focus:border-machinery-700 focus:outline-none"
            />
          </label>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <button
              disabled={valid.length === 0 || submitting || running}
              onClick={() => submit(valid.map((p) => ({ name: p.name, sequence: p.sequence })))}
              className="rounded-md bg-machinery-600 px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-chrome-800 disabled:text-chrome-500"
            >
              {submitting
                ? 'submitting…'
                : running
                  ? 'running…'
                  : `count ${valid.length || ''} probe${valid.length === 1 ? '' : 's'}`}
            </button>
            {running && (
              <button
                onClick={cancel}
                className="rounded-md border border-broken-800 px-3 py-1.5 text-xs text-broken-300 hover:bg-broken-950/40"
              >
                cancel job
              </button>
            )}
            {job && !running && (
              <button
                onClick={reset}
                className="rounded-md border border-chrome-700 px-3 py-1.5 text-xs text-chrome-400 hover:bg-chrome-800"
              >
                clear result
              </button>
            )}
            <span className="text-[11px] text-chrome-500">
              {valid.length} valid
              {invalid.length > 0 && (
                <span className="text-broken-400"> · {invalid.length} rejected</span>
              )}
            </span>
          </div>
          {invalid.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-[11px] text-broken-400">
              {invalid.map((p) => (
                <li key={p.line}>
                  line {p.line}: {p.problem}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-2 rounded-xl border border-chrome-800 bg-chrome-900/40 p-4">
          <div className="text-xs font-medium text-chrome-300">Job</div>
          {!job && !error && (
            <p className="text-[11px] leading-relaxed text-chrome-500">
              No job submitted. A count runs one pass over the full store — about 5.6 minutes for 20
              probes on the server, so the browser follows it with a 60 s server-side long-poll
              rather than polling.
            </p>
          )}
          {job && (
            <div className="space-y-1.5 font-mono text-[11px]">
              <div className="flex items-center gap-2">
                <Badge tone={jobStateTone(job.state)} className="font-semibold uppercase">
                  {job.state}
                </Badge>
                {waiting && <span className="text-chrome-500">long-polling…</span>}
              </div>
              <div className="text-chrome-500">
                id <span className="text-chrome-300">{job.id}</span>
              </div>
              <div className="text-chrome-500">
                verb <span className="text-chrome-300">{job.verb}</span>
              </div>
              {job.elapsed_seconds !== null && (
                <div className="text-chrome-500">
                  elapsed <span className="text-chrome-300">{dec(job.elapsed_seconds, 1)} s</span>
                </div>
              )}
              {job.error && <div className="text-broken-400">{job.error}</div>}
            </div>
          )}
          {error && !isUpstreamDown(error) && (
            <p className="rounded-md border border-broken-900/60 bg-broken-950/30 p-2 font-mono text-[11px] text-broken-300">
              {error.message}
            </p>
          )}
        </div>
      </div>

      {isUpstreamDown(error) && <UpstreamDownBanner detail={error!.message} />}

      {job?.state === 'done' && job.result && <ProbeResults result={job.result} />}
    </div>
  );
}
