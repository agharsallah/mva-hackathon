import { Link } from 'react-router-dom';

import type { IterationsOverview, SubmissionOverview } from '../../api/types';
import { Badge } from '../../components/Badge';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { TONE_MARK } from '../../lib/palette';
import { STATE_MEANING, STATE_TONE } from '../submissions/iteration';
import { coverageShare, coverageTone, iterationNumber, primaryResearch, shortReply } from './model';

/**
 * Every submission folder in one table: its state, who judges it, which research iterations
 * it cites, and how well its data is explained. Each row opens the folder's dossier; each
 * cited research iteration opens that iteration's page on the folder's own track.
 */

const LINK = 'text-machinery-300 hover:text-machinery-200 hover:underline';

function columns(data: IterationsOverview): Column<SubmissionOverview>[] {
  const route = (iteration: string, track: string): string | null => {
    const r = data.research.find((x) => x.iteration === iteration);
    return r?.routes[track as 'track1' | 'track2'] ?? null;
  };
  return [
    {
      key: 'key',
      header: 'folder',
      render: (s) => (
        <Link to={`/submissions?it=${s.key}`} className={`font-mono ${LINK}`}>
          {s.key}
        </Link>
      ),
    },
    {
      key: 'state',
      header: 'state',
      render: (s) => (
        <Badge tone={STATE_TONE[s.state]} title={STATE_MEANING[s.state]}>
          {s.state}
        </Badge>
      ),
    },
    { key: 'judged_by', header: 'judged by', render: (s) => s.judged_by },
    {
      key: 'research',
      header: 'research cited',
      sortValue: (s) => s.research.join(','),
      render: (s) =>
        s.research.length === 0 ? (
          <span className="text-chrome-600">none</span>
        ) : (
          <span className="flex flex-wrap gap-2">
            {s.research.map((r) => {
              const to = route(r, s.track);
              const primary = r === primaryResearch(s);
              const label = `it ${iterationNumber(r)}${primary ? ' ◆' : ''}`;
              return to ? (
                <Link
                  key={r}
                  to={to}
                  className={`font-mono ${LINK}`}
                  title={primary ? `built from ${r}` : `quotes ${r}`}
                >
                  {label}
                </Link>
              ) : (
                <span key={r} className="font-mono" title={`${r} has no page on this track`}>
                  {label}
                </span>
              );
            })}
          </span>
        ),
    },
    {
      key: 'reply',
      header: 'reply',
      render: (s) =>
        s.reply ? (
          <span className="text-good-300" title={s.reply}>
            {shortReply(s.reply)}
          </span>
        ) : (
          <span className="text-chrome-500">{s.uploaded ? '—' : 'not uploaded'}</span>
        ),
    },
    { key: 'entries', header: 'entries', align: 'right', render: (s) => s.entries },
    { key: 'hypotheses', header: 'claims', align: 'right', render: (s) => s.hypotheses },
    { key: 'figures', header: 'figures', align: 'right', render: (s) => s.figures },
    {
      key: 'lineage',
      header: 'lineage edges',
      align: 'right',
      sortValue: (s) => (s.lineage.available ? s.lineage.edges : null),
      render: (s) => (s.lineage.available ? s.lineage.edges : 'ledger down'),
    },
    {
      key: 'catalog',
      header: 'data with lineage',
      sortValue: (s) => coverageShare(s.catalog),
      render: (s) => (
        <Badge tone={coverageTone(s.catalog)} title={`${s.catalog.produced} produced here`}>
          {s.catalog.with_lineage} / {s.catalog.datasets}
        </Badge>
      ),
    },
  ];
}

export function FoldersTable({ data, source }: { data: IterationsOverview; source?: string }) {
  return (
    <Exhibit
      title="Every submission folder"
      legend={
        <>
          State: <Chip color={TONE_MARK.good}>green frozen</Chip> = uploaded, never edited again ·{' '}
          <Chip color={TONE_MARK.decision}>yellow ready</Chip> = built and rehearsed, the gate
          before an upload · <Chip color={TONE_MARK.machinery}>blue draft</Chip> = still being
          written. In <em>research cited</em>, ◆ marks the iteration the folder is built from (the
          newest it cites). <em>Data with lineage</em> = datasets with an edge or manifest over
          datasets the folder’s entries name: <Chip color={TONE_MARK.good}>all</Chip> ·{' '}
          <Chip color={TONE_MARK.decision}>half or more</Chip> ·{' '}
          <Chip color={TONE_MARK.broken}>under half</Chip>.
        </>
      }
      reading="A folder cites research iterations through the methodology entries in its README's contributions table — so a folder can rest on more than one route through the case, and a route can feed more than one folder."
      data={data.submissions}
      source={source}
    >
      <DataTable
        rows={data.submissions}
        columns={columns(data)}
        rowKey={(s) => s.key}
        empty="no submissions/<track>/iteration-n/ folder yet"
      />
    </Exhibit>
  );
}
