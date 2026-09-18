/**
 * Panel (c) of the hero: **the output** — the funnel from every approved drug down to the
 * eleven with a curated result, the rows set aside beside it, and the artefacts a reviewer
 * would open next.
 *
 * The funnel is the honest shape of the search: three of its four steps are automated and a
 * decoy card would clear them too, which is exactly why the last step (a paper a person
 * read) is the only green one.
 */

import type { MeasuredFact } from '../../../api/types';
import { Badge } from '../../../components/Badge';
import { Chip, Exhibit } from '../../../components/Exhibit';
import { Plot, type Trace } from '../../../components/Plot';
import { baseLayout } from '../../../components/plotLayout';
import { StatTile } from '../../../components/StatTile';
import { REPO_BLOB } from '../../../lib/dictionary';
import { int } from '../../../lib/format';
import { C, TONE_MARK } from '../../../lib/palette';
import { cx, RULE, WELL } from '../../../lib/ui';
import { ANCHOR, type FunnelStage } from './heroModel';

/** Where the material behind this page lives, as links a reviewer can follow. */
export interface Artefact {
  label: string;
  hint: string;
  /** A same-page anchor (`#…`), an app route (`/…`) or a repository path. */
  href: string;
  /** A repository path is turned into a blob URL; anything else is used verbatim. */
  repo?: boolean;
}

export interface OutputProps {
  stages: FunnelStage[];
  setAside: { total: number; byVerdict: Array<[string, number]> };
  artefacts: Artefact[];
  unmeasured: MeasuredFact[];
  source?: string;
}

export function Output({ stages, setAside, artefacts, unmeasured, source }: OutputProps) {
  const traces: Trace[] = [
    {
      type: 'bar',
      orientation: 'h',
      // Plotly draws a horizontal bar chart bottom-up, so the widest step has to be last.
      y: [...stages].reverse().map((s) => s.label),
      x: [...stages].reverse().map((s) => s.value),
      text: [...stages].reverse().map((s) => int(s.value)),
      textposition: 'outside',
      // The widest bar's label sits past the axis; without this Plotly clips it to the plot area.
      cliponaxis: false,
      textfont: { color: C.ink, size: 12 },
      marker: {
        color: [...stages].reverse().map((s) => TONE_MARK[s.tone]),
        line: { color: C.grid, width: 1 },
      },
      hovertext: [...stages].reverse().map((s) => s.note),
      hovertemplate: '%{y}: %{x} drugs<br>%{hovertext}<extra></extra>',
    },
  ];

  return (
    <Exhibit
      title="The output — the funnel, and what it rests on"
      id="track2-output"
      legend={
        <>
          One bar per step of the search, widest first.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — an automated test any card
          would pass: the drug is approved, and it was placed on a rung.{' '}
          <Chip color={C.decision}>yellow = a decision point</Chip> — the pre-registered cut at rung
          2, below which a row is named and never submitted.{' '}
          <Chip color={C.good}>green = the goal</Chip> — a curated result, a PubMed paper read by a
          person. <Chip color={C.broken}>red = set aside</Chip> — the do-not table, counted beside
          the funnel rather than inside it, because those rows were removed on purpose.
        </>
      }
      reading={`${int(stages[0]?.value ?? 0)} approved drugs entered; ${int(stages.at(-1)?.value ?? 0)} carry a result a person read. The three steps before it are automated, which is what the decoy control measures — a wrong gene reaches them too.`}
      data={{ stages, set_aside: setAside }}
      source={source}
    >
      <div className="space-y-4" data-testid="output-panel">
        <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
          <Plot
            height={230}
            data={traces}
            layout={baseLayout({
              margin: { l: 118, r: 72, t: 8, b: 32 },
              bargap: 0.35,
              xaxis: {
                gridcolor: C.grid,
                tickfont: { color: C.inkDim, size: 10 },
                rangemode: 'tozero',
              },
              yaxis: { tickfont: { color: C.inkDim, size: 11 }, automargin: true },
            })}
          />
          <div className="grid content-start gap-3">
            <StatTile
              label="set aside"
              tone="broken"
              value={int(setAside.total)}
              sub={setAside.byVerdict.map(([v, n]) => `${n} ${v}`).join(' · ')}
            />
            {stages.map((s) => (
              <div key={s.label} className="text-micro leading-relaxed text-chrome-400">
                <span className="tabular-nums font-mono text-chrome-200">{int(s.value)}</span>{' '}
                <span className="text-chrome-300">{s.label}</span> — {s.note}
              </div>
            ))}
          </div>
        </div>

        {unmeasured.length > 0 && (
          <ul className="flex flex-wrap gap-2" data-testid="unmeasured-chips">
            {unmeasured.map((f) => (
              <li key={f.id}>
                <Badge tone="decision" title={f.value}>
                  {f.id} unmeasured — {f.fact} ({f.step} not run)
                </Badge>
              </li>
            ))}
          </ul>
        )}

        <div className={cx(WELL, 'border-l-2 space-y-2', RULE.machinery)}>
          <h4 className="text-xs font-semibold text-chrome-200">The artefacts behind this page</h4>
          <ul className="flex flex-wrap gap-2" data-testid="artefact-links">
            {artefacts.map((a) => (
              <li key={a.label}>
                <a
                  href={a.repo ? `${REPO_BLOB}${a.href}` : a.href}
                  title={a.hint}
                  className="inline-flex items-center rounded-control border border-line bg-panel px-2 py-1 text-micro text-chrome-300 transition hover:border-line-strong hover:text-chrome-100"
                >
                  {a.label}
                </a>
              </li>
            ))}
          </ul>
          <p className="text-micro text-chrome-500">
            Every one of them is committed:{' '}
            <a
              href={`#${ANCHOR.catalog}`}
              className="underline decoration-chrome-700 underline-offset-2 hover:text-chrome-300"
            >
              the tables
            </a>{' '}
            carry a provenance manifest, and the methodology entries carry the exact commands.
          </p>
        </div>
      </div>
    </Exhibit>
  );
}
