/**
 * The two evidence tables under the candidates: registered trials, and the literature.
 *
 * Both are joined by **query**, not by claim. A trial row is here because a query built
 * from the card ("this candidate drug, in this child's tumour") returned it — so the query
 * string is kept in the row and shown, and a reader can see exactly what was asked. A hit
 * is evidence that somebody has given the drug in this context, never that it worked.
 */

import { useMemo, useState } from 'react';

import type { LiteratureRow, SourceQuery, TrialRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Select } from '../../components/Controls';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { BarChart } from './CandidateCharts';
import { T } from './Term';

const STATUS_TONE = (s: string) =>
  s === 'RECRUITING' ? 'good' : s === 'TERMINATED' || s === 'WITHDRAWN' ? 'broken' : 'neutral';

export function Trials({
  trials,
  trialQueries,
  tumourContext,
  source,
}: {
  trials: TrialRow[];
  trialQueries: SourceQuery[];
  tumourContext: string;
  source?: string;
}) {
  const hits = useMemo(
    () =>
      trialQueries
        .filter((q) => q.family === 'candidate' && q.hits > 0)
        .sort((a, b) => b.hits - a.hits || a.label.localeCompare(b.label))
        .slice(0, 12)
        .map((q) => ({ label: q.label, value: q.hits })),
    [trialQueries],
  );
  const asked = trialQueries.length;
  const answered = trialQueries.filter((q) => q.hits > 0).length;

  return (
    <Exhibit
      title="Trials — has anyone given this drug in this child's tumour context?"
      legend={
        <>
          One bar per candidate drug whose tumour-context query returned a registered study.{' '}
          <Chip color={C.good}>green = a study exists</Chip> — evidence the drug has been given in
          this context, <strong>not</strong> evidence that it worked. In the table,{' '}
          <Badge tone="good">RECRUITING</Badge> is open today and{' '}
          <Badge tone="broken">TERMINATED</Badge> stopped early — a status worth reading before a
          drug is proposed.
        </>
      }
      reading={`${answered} of ${asked} registry queries returned anything, giving ${int(trials.length)} studies. The disease itself returns nothing — ${tumourContext} is what makes any of this searchable, which is why direction D4 exists.`}
      data={{ queries: trialQueries.length, rows: trials.length }}
      source={source}
    >
      <div className="space-y-4">
        <figure className="space-y-1">
          <figcaption className="text-xs font-semibold text-chrome-200">
            Registered studies per candidate drug, in the tumour context
          </figcaption>
          <BarChart
            bars={hits}
            color={C.good}
            label={`registered studies returned for each of the top ${hits.length} candidate drugs in the tumour context`}
          />
        </figure>

        <DataTable<TrialRow>
          rows={trials}
          rowKey={(r, i) => `${r.nct_id}|${i}`}
          filterable
          filterLabel="find a trial"
          maxHeight={460}
          columns={[
            {
              key: 'nct_id',
              header: 'registry id',
              render: (r) => (
                <a
                  className="font-mono text-xs text-machinery-300 underline underline-offset-2 hover:text-machinery-200"
                  href={`https://clinicaltrials.gov/study/${r.nct_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {r.nct_id}
                </a>
              ),
            },
            { key: 'title', header: 'study', render: (r) => r.title },
            { key: 'phase', header: 'phase', render: (r) => r.phase || '—' },
            {
              key: 'overall_status',
              header: 'status',
              render: (r) => <Badge tone={STATUS_TONE(r.overall_status)}>{r.overall_status}</Badge>,
            },
            {
              key: 'interventions',
              header: 'given',
              sortValue: (r) => r.interventions.join(','),
              render: (r) => (
                <span className="text-chrome-400">{r.interventions.join(' · ') || '—'}</span>
              ),
            },
            { key: 'start_date', header: 'started', render: (r) => r.start_date || '—' },
            {
              key: 'query',
              header: 'found by',
              render: (r) => (
                <span className="font-mono text-micro text-chrome-600">{r.query}</span>
              ),
            },
          ]}
        />
      </div>
    </Exhibit>
  );
}

export function Literature({
  literature,
  queries,
  source,
}: {
  literature: LiteratureRow[];
  queries: SourceQuery[];
  source?: string;
}) {
  const names = useMemo(() => [...new Set(literature.map((l) => l.query))].sort(), [literature]);
  const [picked, setPicked] = useState('all');
  const rows = useMemo(
    () => (picked === 'all' ? literature : literature.filter((l) => l.query === picked)),
    [literature, picked],
  );

  return (
    <Exhibit
      title="Literature — what was searched, and what came back"
      legend={
        <>
          One row per article, tagged with the search that returned it.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — the query, kept in the row so
          the join is auditable. <strong>hits</strong> is what the search matched;{' '}
          <strong>kept</strong> is how many were retrieved, capped by the request — a gap between
          the two means the search was broad, not that the rest were rejected.
        </>
      }
      reading={`${int(literature.length)} articles from ${queries.length} searches, each built from the mechanism card: the gene, the pathway, and one per repurposing direction. This is a reading list the ranking still has to work through, not a result.`}
      data={{ queries, rows: literature.length }}
      source={source}
      controls={
        <Select
          label="query"
          value={picked}
          options={[
            { value: 'all', label: `all ${names.length} queries` },
            ...names.map((q) => ({ value: q, label: q.length > 46 ? `${q.slice(0, 45)}…` : q })),
          ]}
          onChange={setPicked}
        />
      }
    >
      <div className="space-y-4">
        <DataTable<SourceQuery>
          rows={queries}
          rowKey={(r) => r.query}
          columns={[
            {
              key: 'family',
              header: 'built from',
              render: (r) => <Badge tone="machinery">{r.family}</Badge>,
            },
            { key: 'label', header: 'subject', render: (r) => r.label },
            {
              key: 'query',
              header: 'query',
              render: (r) => (
                <span className="font-mono text-micro text-chrome-400">{r.query}</span>
              ),
            },
            {
              key: 'hits',
              header: 'hits',
              align: 'right',
              render: (r) => <span className="tabular-nums font-mono text-xs">{int(r.hits)}</span>,
            },
            {
              key: 'kept',
              header: 'kept',
              align: 'right',
              render: (r) => (
                <span className="tabular-nums font-mono text-xs text-good-300">
                  {r.kept === undefined ? '—' : int(r.kept)}
                </span>
              ),
            },
          ]}
        />

        <DataTable<LiteratureRow>
          rows={rows}
          rowKey={(r, i) => `${r.pmid}|${i}`}
          filterable
          filterLabel="find an article"
          maxHeight={460}
          columns={[
            {
              key: 'pmid',
              header: 'PubMed',
              render: (r) => (
                <a
                  className="font-mono text-xs text-machinery-300 underline underline-offset-2 hover:text-machinery-200"
                  href={`https://pubmed.ncbi.nlm.nih.gov/${r.pmid}/`}
                  target="_blank"
                  rel="noreferrer"
                >
                  PMID:{r.pmid}
                </a>
              ),
            },
            { key: 'title', header: 'title', render: (r) => r.title },
            { key: 'journal', header: 'journal', render: (r) => r.journal },
            { key: 'year', header: 'year', align: 'right', render: (r) => String(r.year) },
            {
              key: 'query',
              header: 'found by',
              render: (r) => (
                <span className="font-mono text-micro text-chrome-600">{r.query}</span>
              ),
            },
          ]}
        />

        <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-400">
          Searched through{' '}
          <T
            slug="pubmed-e-utilities"
            term="the PubMed E-utilities"
            plain="the public programmatic interface to the biomedical literature index"
          />
          , and registered studies through{' '}
          <T
            slug="clinicaltrials-gov"
            term="ClinicalTrials.gov"
            plain="the public registry every clinical study has to be listed in"
          />
          .
        </p>
      </div>
    </Exhibit>
  );
}
