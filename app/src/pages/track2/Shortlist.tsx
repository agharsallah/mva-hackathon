/**
 * The shortlist — the rows the report is allowed to argue from, and the rows it is not.
 *
 * The table splits on one word in the `verdict` column. `argue` means a person read a paper
 * showing the drug acts on this direction's mechanism. Everything else says *context trial
 * only*: the drug is already registered in a study of the child's tumour, which is a fact
 * about oncology practice and not a finding about a broken checkpoint. Those rows are kept —
 * hiding them would misrepresent the search — but behind a toggle, off by default, so the
 * eleven rows that carry an argument are not buried under fifty that do not.
 */

import { useState } from 'react';

import type { ShortlistRow } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Toggle } from '../../components/Controls';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cx, RULE, WELL } from '../../lib/ui';
import { splitShortlist } from './ladderModel';
import { PmidList } from './Pmids';
import { T } from './Term';

function columns(withRank: boolean): Column<ShortlistRow>[] {
  const rank: Column<ShortlistRow>[] = withRank
    ? [
        {
          key: 'rank',
          header: '#',
          align: 'right',
          render: (r) => (
            <span className="tabular-nums font-mono text-xs text-chrome-400">{r.rank ?? '—'}</span>
          ),
        },
      ]
    : [];
  return [
    ...rank,
    {
      key: 'drug_name',
      header: 'drug',
      render: (r) => <span className="font-mono text-xs text-chrome-100">{r.drug_name}</span>,
    },
    {
      key: 'direction_id',
      header: 'direction',
      render: (r) => <Badge tone="machinery">{r.direction_id}</Badge>,
    },
    {
      key: 'rung',
      header: 'rung',
      align: 'right',
      render: (r) => <Badge tone={(r.rung ?? 0) >= 4 ? 'good' : 'decision'}>{r.rung ?? '—'}</Badge>,
    },
    {
      key: 'why',
      header: 'why it is placed there',
      render: (r) => <span className="inline-block max-w-[52ch] text-chrome-300">{r.why}</span>,
    },
    {
      key: 'pediatric_evidence',
      header: 'paediatric evidence',
      render: (r) => (
        <span className="inline-block max-w-[28ch] text-chrome-400">
          {r.pediatric_evidence || 'none found'}
        </span>
      ),
    },
    {
      key: 'curated_pmids',
      header: 'papers',
      sortable: false,
      render: (r) => <PmidList pmids={r.curated_pmids} />,
    },
    {
      key: 'targets',
      header: 'targets',
      sortable: false,
      render: (r) => (
        <span className="font-mono text-micro text-chrome-500">{r.targets.join(' ')}</span>
      ),
    },
  ];
}

export function Shortlist({ shortlist, source }: { shortlist: ShortlistRow[]; source?: string }) {
  const [showContext, setShowContext] = useState(false);
  const { argue, contextOnly } = splitShortlist(shortlist);

  return (
    <Exhibit
      title="The shortlist — the rows the report may argue from"
      legend={
        <>
          <Chip color={C.good}>green = rung 4 or 5</Chip>, <Chip color={C.decision}>yellow =</Chip>{' '}
          rung 2 or 3 — the kind of evidence, not a ranking of how good the drug is. The{' '}
          <span className="font-mono">#</span> column is the shortlist&rsquo;s own order: rung
          first, then a result on the molecule itself before an inherited one, then paediatric
          evidence, then literature volume last and on purpose. Every paper opens on PubMed. The
          collapsed block holds the rows whose only evidence is a registered trial in the tumour.
        </>
      }
      reading={`${argue.length} rows may be argued; ${contextOnly.length} more are registered trials in the child's tumour and are shown only when asked for. This page ends in a shortlist, not a prescription.`}
      data={{ argue: argue.length, context_only: contextOnly.length }}
      source={source}
      controls={
        <Toggle on={showContext} onChange={setShowContext}>
          show context-trial rows ({contextOnly.length})
        </Toggle>
      }
    >
      <div className="space-y-4">
        <p className="max-w-[95ch] font-serif text-note leading-relaxed text-chrome-300">
          A{' '}
          <T
            slug="shortlist"
            term="shortlist"
            plain="the ladder rows the report may argue: rung 2 or better, not standard of care, not an anti-direction"
          />{' '}
          is the filtered output of the ladder above, ordered by the reasons printed in its own{' '}
          <em>why</em> column. Read it the way you would read a triage queue, not a ranking of
          efficacy: the order says which rows have the most to look at, never which drug works.
        </p>

        <div data-testid="shortlist-argue">
          <DataTable<ShortlistRow>
            rows={argue}
            rowKey={(r) => `${r.drug_name}:${r.direction_id}`}
            pageSize={0}
            columns={columns(true)}
          />
        </div>

        <div className={cx(WELL, 'border-l-2', RULE.machinery)}>
          <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-400">
            <strong className="text-machinery-300">
              {contextOnly.length} rows say &ldquo;context trial only&rdquo;.
            </strong>{' '}
            Each is an approved drug with a registered study in the child&rsquo;s tumour and no
            curated result on the mechanism. That is evidence the drug is{' '}
            <em>already being tried</em> in this cancer — a fact about current oncology practice,
            not a finding about the broken checkpoint. They are kept so the search is auditable and
            separated so they cannot be read as a mechanism argument.
          </p>
          {showContext && (
            <div className="mt-3" data-testid="shortlist-context">
              <DataTable<ShortlistRow>
                rows={contextOnly}
                rowKey={(r) => `${r.drug_name}:${r.direction_id}`}
                filterable
                filterLabel="find a drug"
                maxHeight={420}
                columns={columns(false)}
              />
            </div>
          )}
        </div>
      </div>
    </Exhibit>
  );
}
