/**
 * The probe payload builder: dashboard candidates in, a submission CSV out.
 *
 * This is the last unautomated step of the endgame. Everything upstream ranks alleles;
 * the file that gets uploaded to the HuggingFace Space was still assembled by hand, and a
 * hand-typed coordinate is the one mistake that costs a whole submission out of eighteen
 * rather than a row out of ten. Here the numbers only ever move by reference.
 *
 * The browser owns *ordering and shape*. Every challenge rule — the ten-row cap, the epcr
 * interval, the chr prefix, the finding types, the proband id — is enforced server-side by
 * `mva.pipeline.submission`, which is the same module the offline pipeline writes with. The
 * builder never renders a CSV of its own: an unvalidated preview is a file someone uploads.
 */

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Callout } from '../../components/Explainer';
import { CandidatePicker } from './CandidatePicker';
import { PayloadTable } from './PayloadTable';
import { downloadCsv, useProbeBuild } from './useProbeBuild';
import {
  MAX_ROWS,
  addRow,
  ingestPairParam,
  moveRow,
  patchRow,
  removeRow,
  toRequest,
  type DraftRow,
} from './probePayload';
import { PAIR_PARAM } from '../compare/comparator';

const FILENAME = 'track1_submission.csv';

const LOG_COMMAND = `uv run mva-warehouse probe-log --by <member> --type <S|P|F> \\
    --payload-file ${FILENAME} --response '<scorer reply>' \\
    --rationale '<what this probe decides>'`;

export function ProbeBuilder() {
  const [rows, setRows] = useState<DraftRow[]>([]);
  const [copied, setCopied] = useState(false);
  const [params, setParams] = useSearchParams();
  const { result, error, building, build, clear } = useProbeBuild();

  /** Any edit invalidates the last verdict — a stale "valid" beside changed rows is a lie. */
  function edit(next: DraftRow[]) {
    setRows(next);
    clear();
    setCopied(false);
  }

  /**
   * A pair handed over from another exhibit (`/probes?pair=…`, written by the Compare
   * page's comparator) is staged once and the parameter is dropped, so a reload does not
   * re-add the row and the address bar stops advertising a payload that is now editable
   * state. The ref survives React StrictMode's double-mount, which would otherwise stage
   * the pair twice in development.
   */
  const ingested = useRef(false);
  useEffect(() => {
    if (ingested.current) return;
    ingested.current = true;
    const raw = params.get(PAIR_PARAM);
    if (!raw) return;
    setRows((current) => ingestPairParam(current, raw, 'from the pair comparator'));
    setParams(
      (prev) => {
        const out = new URLSearchParams(prev);
        out.delete(PAIR_PARAM);
        return out;
      },
      { replace: true },
    );
  }, [params, setParams]);

  const errors = result?.problems.filter((p) => p.severity === 'error') ?? [];
  const warnings = result?.problems.filter((p) => p.severity === 'warning') ?? [];

  return (
    <div className="space-y-4">
      <Callout tone="decision" title="Building costs nothing. Submitting costs 1 of 18.">
        This page renders and checks the file. Nothing leaves the machine, no budget moves, and you can
        rebuild as often as you like. The spend happens when the CSV is uploaded to the challenge Space —
        and that spend is only recoverable as knowledge if it is written down. After any real submission:
        <pre className="mt-2 overflow-x-auto rounded-md border border-amber-900/50 bg-zinc-950 p-2 font-mono text-[11px] leading-relaxed text-amber-200">
          {LOG_COMMAND}
        </pre>
      </Callout>

      <div className="grid gap-4 xl:grid-cols-2">
        <CandidatePicker
          canAdd={rows.length < MAX_ROWS}
          onAdd={(first, second, label) => edit(addRow(rows, first, second, label))}
        />

        <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-medium text-zinc-300">
              Payload <span className="text-zinc-500">· {rows.length} of {MAX_ROWS} rows</span>
            </div>
            {rows.length > 0 && (
              <button
                type="button"
                onClick={() => edit([])}
                className="rounded-md border border-zinc-700 px-2 py-1 text-[11px] text-zinc-400 hover:bg-zinc-800"
              >
                clear
              </button>
            )}
          </div>

          <PayloadTable
            rows={rows}
            onMove={(id, delta) => edit(moveRow(rows, id, delta))}
            onRemove={(id) => edit(removeRow(rows, id))}
            onPatch={(id, patch) => edit(patchRow(rows, id, patch))}
          />

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={rows.length === 0 || building}
              onClick={() => build(toRequest(rows))}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500"
            >
              {building ? 'validating…' : 'Validate & build'}
            </button>
            <span className="text-[11px] text-zinc-500">
              checked against <span className="font-mono">mva.pipeline.submission</span> — the same rules
              the offline pipeline writes with
            </span>
          </div>

          {error && (
            <p className="rounded-md border border-red-900/60 bg-red-950/30 p-2.5 text-[11px] leading-relaxed text-red-300">
              The API did not answer: <span className="font-mono">{error.message}</span>. Nothing was
              validated — there is no offline fallback here on purpose, because a builder that pretends to
              check a file is worse than one that refuses. Start the API
              (<span className="font-mono">uv run mva-viz-api</span>) and press the button again.
            </p>
          )}

          {result && <Verdict result={result} errors={errors} warnings={warnings} />}
        </div>
      </div>

      {result?.valid && result.csv && (
        <div className="space-y-2 rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-medium text-zinc-300">
              {FILENAME} <span className="text-zinc-500">· contigs are chr-prefixed on the way out</span>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  void navigator.clipboard.writeText(result.csv).then(() => setCopied(true));
                }}
                className="rounded-md border border-zinc-700 px-2 py-1 text-[11px] text-zinc-300 hover:bg-zinc-800"
              >
                {copied ? 'copied' : 'copy'}
              </button>
              <button
                type="button"
                onClick={() => downloadCsv(result.csv, FILENAME)}
                className="rounded-md border border-emerald-800 px-2 py-1 text-[11px] text-emerald-300 hover:bg-emerald-950/40"
              >
                download
              </button>
            </div>
          </div>
          <pre className="overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-[11px] leading-relaxed text-zinc-200">
            {result.csv}
          </pre>
        </div>
      )}

      <Legend />
    </div>
  );
}

function Verdict({
  result,
  errors,
  warnings,
}: {
  result: NonNullable<ReturnType<typeof useProbeBuild>['result']>;
  errors: { message: string }[];
  warnings: { message: string }[];
}) {
  return (
    <div className="space-y-2">
      {errors.length > 0 && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/25 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-red-400">
            {errors.length} problem{errors.length === 1 ? '' : 's'} — no file written
          </div>
          <ul className="mt-1 space-y-0.5 text-[11px] text-red-300">
            {errors.map((p) => (
              <li key={p.message}>{p.message}</li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="rounded-lg border border-amber-800/60 bg-amber-950/25 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-amber-400">
            {warnings.length} warning{warnings.length === 1 ? '' : 's'} — the file is legal, the payload
            may not be what you meant
          </div>
          <ul className="mt-1 space-y-0.5 text-[11px] text-amber-300">
            {warnings.map((p) => (
              <li key={p.message}>{p.message}</li>
            ))}
          </ul>
        </div>
      )}

      {result.self_test && (
        <div
          className={`rounded-lg border p-3 ${
            result.self_test.passed
              ? 'border-emerald-800/60 bg-emerald-950/25'
              : 'border-red-900/60 bg-red-950/25'
          }`}
        >
          <div
            className={`text-[11px] font-semibold uppercase tracking-wider ${
              result.self_test.passed ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            self-test {result.self_test.passed ? 'passed' : 'FAILED'}
          </div>
          <div className="mt-1 font-mono text-[11px] text-zinc-300">
            rank_points {result.self_test.rank_points} · f_max {result.self_test.f_max} ·
            full_match_rank {result.self_test.full_match_rank ?? '—'}
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">
            The emitted bytes were parsed back the way the scorer parses them and scored against a
            synthetic answer key equal to row 1's own alleles. It proves the file <em>encodes</em> what
            you staged — the chr prefix, the pair-in-one-row shape, the rank order. It says nothing about
            whether row 1 is correct; only the oracle can say that.
          </p>
        </div>
      )}
    </div>
  );
}

function Legend() {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4 text-[11px] leading-relaxed text-zinc-400">
      <div className="font-semibold uppercase tracking-wider text-zinc-500">Legend</div>
      <ul className="mt-1.5 grid gap-1 sm:grid-cols-2">
        <li>
          <span className="text-emerald-400">green</span> — the file is safe to upload, or rank 1, the
          only rank that scores the maximum.
        </li>
        <li>
          <span className="text-amber-400">yellow</span> — a decision point: an irreversible spend, or a
          payload the scorer will read differently than it looks.
        </li>
        <li>
          <span className="text-red-400">red</span> — a rule violation. No CSV is rendered at all.
        </li>
        <li>
          <span className="text-blue-400">blue</span> — machinery: staged alleles, the validate action.
        </li>
      </ul>
      <div className="mt-3 font-semibold uppercase tracking-wider text-zinc-500">How the file is read</div>
      <ul className="mt-1.5 space-y-1">
        <li>
          <strong>epcr</strong> (estimated probability the row is causal) decides rank, descending. Ties
          break by <em>file order</em>, so equal values make a rank ambiguous and an oracle reply
          undecodable — the ladder is strictly descending for that reason alone.
        </li>
        <li>
          <strong>A pair row is one hypothesis.</strong> Both alleles of a compound heterozygote (two
          different broken copies of the same gene, one from each parent) must sit in the same row; split
          across two rows, a correct answer scores partial credit only.
        </li>
        <li>
          <strong>Single rows fish for partial matches</strong> (intel §9.1). Ten singles plus the reply's{' '}
          <span className="font-mono">partial_match_rank</span> and{' '}
          <span className="font-mono">f_max</span> identify which candidates are true alleles.
        </li>
        <li>
          <strong>A full match anywhere beats any partial</strong> (§8.3) — a full match at rank 6 scores
          10 while a partial at rank 1 would have scored 50. So the final strike carries the confirmed
          pair at rank 1 with nothing above it.
        </li>
        <li>
          <strong>Rows below the winning threshold are free</strong> (§8.4), so curated secondary findings
          with notes cost nothing and feed the qualitative review.
        </li>
      </ul>
    </div>
  );
}
