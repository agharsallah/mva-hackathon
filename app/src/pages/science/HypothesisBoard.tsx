import { useState } from 'react';

import { useHypotheses } from '../../api/hooks';
import type { HypothesisRow } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { iso } from '../../lib/format';
import { C } from '../../lib/palette';
import { CARD, cx } from '../../lib/ui';
import { type Claim, claims, STATUS_ORDER, statusColor } from './hypothesis';
import { Confidence, EmptyRegister } from './register';

/**
 * The hypothesis board: one card per registered claim, showing the current belief and
 * keeping every earlier revision one click away.
 *
 * The register is append-only, so "the claim" is really a stack of revisions. The card
 * shows the top of the stack; the history expander is what makes the append-only-ness
 * visible instead of merely true.
 */
export function HypothesisBoard() {
  const query = useHypotheses();
  return (
    <Exhibit
      title="Hypothesis board"
      legend={
        <>
          Card border and status pill carry the claim's state:{' '}
          <Chip color={C.machinery}>blue = proposed</Chip>,{' '}
          <Chip color={C.decision}>yellow = testing</Chip>,{' '}
          <Chip color={C.good}>green = supported</Chip>, <Chip color={C.broken}>red = refuted</Chip>
          , <Chip color={C.absent}>grey = superseded</Chip> — the same five colours{' '}
          <span className="font-mono">mva.science.hypothesis.Status</span> uses. A dash means the
          field is empty in the register, never that its value is zero.
        </>
      }
      reading="Every card was written down before its test ran, refutation condition included. That is the only thing separating a hypothesis from a description of what the data turned out to say."
      data={query.data?.data}
      source={query.data?.source}
      cachedAt={query.data?.cachedAt}
      origin={query.data?.origin}
    >
      <Loaded query={query} height={220}>
        {(register) =>
          register.rows.length === 0 ? (
            <EmptyRegister
              tableExists={register.table_exists}
              title="No hypothesis yet — the register opens when step 1 makes its first claim"
              verb="mva-science hypothesis-add"
            >
              Step 0 is platform machinery and takes no hypotheses: its reasoning is decisions, not
              claims about the patient, and the register refuses a claim filed under it. Nothing has
              been asserted about this child yet, so there is nothing here to argue with.
            </EmptyRegister>
          ) : (
            <Board rows={register.rows} />
          )
        }
      </Loaded>
    </Exhibit>
  );
}

function Board({ rows }: { rows: HypothesisRow[] }) {
  const grouped = claims(rows);
  const present = STATUS_ORDER.filter((s) => grouped.some((c) => c.latest.status === s));
  const other = grouped.filter((c) => !STATUS_ORDER.includes(c.latest.status));

  return (
    <div className="space-y-4">
      {present.map((status) => (
        <Group
          key={status}
          status={status}
          items={grouped.filter((c) => c.latest.status === status)}
        />
      ))}
      {other.length > 0 && <Group status="unrecognised status" items={other} />}
    </div>
  );
}

function Group({ status, items }: { status: string; items: Claim[] }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-sm" style={{ background: statusColor(status) }} />
        <span className="text-xs font-medium text-chrome-400">{status}</span>
        <span className="font-mono text-micro text-chrome-600">{items.length}</span>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {items.map((claim) => (
          <Card key={claim.latest.hypothesis_id} claim={claim} />
        ))}
      </div>
    </div>
  );
}

function Card({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  const row = claim.latest;
  const color = statusColor(row.status);

  return (
    <article className={cx(CARD, 'space-y-2')} style={{ borderColor: `${color}55` }}>
      <header className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs font-semibold text-chrome-100">{row.hypothesis_id}</span>
        <span
          className="rounded-pill px-2 py-px text-xs font-medium"
          style={{ background: `${color}22`, color }}
        >
          {row.status}
        </span>
        <span className="rounded-pill bg-chrome-800 px-2 py-px font-mono text-micro text-chrome-400">
          {row.step}
        </span>
        {row.gene && (
          <span
            className="rounded-pill bg-raw-500/15 px-2 py-px font-mono text-micro text-raw-300"
            title="the gene this claim is about"
          >
            {row.gene}
          </span>
        )}
        {row.path && (
          <span
            className="rounded-pill bg-chrome-800 px-2 py-px font-mono text-micro text-chrome-400"
            title="which line of attack this claim belongs to"
          >
            {row.path}
          </span>
        )}
      </header>

      <p className="text-sm leading-relaxed text-chrome-200">{row.statement}</p>

      <dl className="space-y-2 text-xs leading-relaxed">
        <div>
          <dt className="inline font-semibold text-chrome-400">Prediction</dt>
          <dd className="inline text-chrome-400"> — {row.prediction}</dd>
        </div>
        <div>
          <dt className="inline font-semibold text-broken-300/80">Refuted by</dt>
          <dd className="inline text-chrome-400"> — {row.refuted_by}</dd>
        </div>
      </dl>

      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-t border-line pt-2">
        <div className="flex items-baseline gap-2">
          <span className="text-xs font-medium text-chrome-400">confidence</span>
          <Confidence value={row.confidence} inline />
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          className="rounded-control border border-line-strong px-2 py-0.5 text-micro text-chrome-400 hover:bg-chrome-800"
        >
          {open
            ? 'hide history'
            : `${claim.history.length} revision${claim.history.length === 1 ? '' : 's'}`}
        </button>
      </div>

      {row.reasoning && (
        <p className="text-micro leading-relaxed text-chrome-400">{row.reasoning}</p>
      )}

      {open && <History history={claim.history} />}
    </article>
  );
}

/** Every revision, oldest first. Nothing here was ever edited; each line is its own row. */
function History({ history }: { history: HypothesisRow[] }) {
  return (
    <ol className="space-y-2 rounded-card border border-line bg-chrome-950/60 p-3">
      {history.map((r) => (
        <li key={r.revision} className="flex flex-wrap items-baseline gap-2 text-micro">
          <span className="font-mono text-chrome-400">r{r.revision}</span>
          <span className="font-mono text-chrome-600">{iso(r.recorded_at)}</span>
          <span className="font-medium" style={{ color: statusColor(r.status) }}>
            {r.status}
          </span>
          <Confidence value={r.confidence} inline />
          {r.reasoning && <span className="basis-full text-chrome-400">{r.reasoning}</span>}
        </li>
      ))}
      <li className="border-t border-line pt-2 text-micro leading-relaxed text-chrome-600">
        Append-only: a changed belief is a new revision row, never an edit to the one above it.
      </li>
    </ol>
  );
}
