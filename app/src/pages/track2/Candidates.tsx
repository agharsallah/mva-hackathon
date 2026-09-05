/**
 * The candidate table: every drug-target interaction the public sources reported, filtered.
 *
 * A row is an **interaction**, not a drug — the same molecule appears once per target it
 * acts on and per source that reported it, which is why the header counts distinct drugs
 * separately from rows. The approved-only toggle is ON by default because Track 2's rules
 * admit market-approved drugs only; turning it off shows the evidence behind that filter
 * rather than hiding it.
 */

import { useMemo, useState } from 'react';

import type { CandidateRow, Track2Summary } from '../../api/types';
import { Badge } from '../../components/Badge';
import { Select, TextFilter, Toggle } from '../../components/Controls';
import { DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { StatTile } from '../../components/StatTile';
import { int } from '../../lib/format';
import { C } from '../../lib/palette';
import { BarChart } from './CandidateCharts';
import {
  approvedDrugsPerSeedTarget,
  type CandidateFilters,
  DEFAULT_FILTERS,
  directionIds,
  filterCandidates,
  rowsPerSource,
  sourceNames,
} from './candidateFilters';
import { T } from './Term';

const distinct = (rows: CandidateRow[]): number =>
  new Set(rows.map((r) => r.drug_name.toLowerCase())).size;

export function Candidates({
  candidates,
  summary,
  source,
}: {
  candidates: CandidateRow[];
  summary: Track2Summary;
  source?: string;
}) {
  const [filters, setFilters] = useState<CandidateFilters>(DEFAULT_FILTERS);
  const set = <K extends keyof CandidateFilters>(key: K, value: CandidateFilters[K]) =>
    setFilters((f) => ({ ...f, [key]: value }));

  const directions = useMemo(() => directionIds(candidates), [candidates]);
  const sources = useMemo(() => sourceNames(candidates), [candidates]);
  const rows = useMemo(() => filterCandidates(candidates, filters), [candidates, filters]);
  const perSeed = useMemo(() => approvedDrugsPerSeedTarget(candidates), [candidates]);
  const perSource = useMemo(() => rowsPerSource(candidates), [candidates]);

  return (
    <Exhibit
      title="Candidate drugs — every interaction the public sources reported"
      legend={
        <>
          <Chip color={C.good}>green = market-approved</Chip> — ChEMBL phase 4, an Open Targets
          phase-4 record, or a DGIdb approved flag; these are the only rows Track 2 may propose.{' '}
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — the reporting source and the
          target it was found against. In the two charts, the solid bar is the approved subset and
          the pale bar behind it the total. A <Badge tone="good">FDA label</Badge> tag means openFDA
          returned a label for the drug.
        </>
      }
      reading={`${int(summary.candidates.total)} drug-target rows over ${int(summary.candidates.distinct_drugs)} distinct molecules; ${int(summary.candidates.approved)} rows and ${int(summary.candidates.distinct_approved_drugs)} molecules are market-approved, and ${int(summary.candidates.with_fda_label)} rows carry an FDA label. None of them acts on the broken protein itself — every one comes from a neighbour, which is exactly what the register's H011 predicted.`}
      data={{ summary: summary.candidates, shown: rows.length }}
      source={source}
      controls={
        <div className="flex flex-wrap items-center gap-2">
          <Toggle on={filters.approvedOnly} onChange={(v) => set('approvedOnly', v)}>
            approved only
          </Toggle>
          <Select
            label="direction"
            value={filters.direction}
            options={[
              { value: 'all', label: 'all directions' },
              ...directions.map((d) => ({ value: d, label: d })),
            ]}
            onChange={(v) => set('direction', v)}
          />
          <Select
            label="source"
            value={filters.source}
            options={[
              { value: 'all', label: 'all sources' },
              ...sources.map((s) => ({ value: s, label: s })),
            ]}
            onChange={(v) => set('source', v)}
          />
          <TextFilter
            label="find"
            value={filters.text}
            onChange={(v) => set('text', v)}
            placeholder="drug, target or mechanism"
          />
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile
            label="rows shown"
            tone="good"
            value={int(rows.length)}
            sub={`of ${int(candidates.length)} in the table`}
          />
          <StatTile
            label="distinct molecules shown"
            value={int(distinct(rows))}
            sub="a molecule appears once per target and source"
          />
          <StatTile
            label="approved, in total"
            tone="good"
            value={int(summary.candidates.approved)}
            sub={`${int(summary.candidates.distinct_approved_drugs)} distinct molecules`}
          />
          <StatTile
            label="with an FDA label"
            tone="machinery"
            value={int(summary.candidates.with_fda_label)}
            sub="openFDA returned a label"
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <figure className="space-y-1">
            <figcaption className="text-xs font-semibold text-chrome-200">
              Approved drugs per seed target
            </figcaption>
            <BarChart
              bars={perSeed}
              color={C.good}
              label={`distinct market-approved drugs for each of the top ${perSeed.length} seed targets`}
            />
            <p className="text-micro text-chrome-500">
              Distinct molecules, not rows. The gene the child&rsquo;s variants sit in does not
              appear at all — no approved drug acts on it.
            </p>
          </figure>
          <figure className="space-y-1">
            <figcaption className="text-xs font-semibold text-chrome-200">
              Candidate rows per source
            </figcaption>
            <BarChart
              bars={perSource}
              color={C.good}
              totalColor={C.machinery}
              label="approved and total candidate rows reported by each public source"
            />
            <p className="text-micro text-chrome-500">
              Solid = approved, pale = all rows. A row can carry several sources, so these sum to
              more than the table.
            </p>
          </figure>
        </div>

        <p className="max-w-[95ch] text-micro leading-relaxed text-chrome-500">
          The mechanism text in each row is the source&rsquo;s own{' '}
          <T
            slug="mechanism-of-action-moa"
            term="mechanism of action"
            plain="what the drug does to the protein — blocks it, activates it, degrades it"
          />
          , unedited. Sources:{' '}
          <T
            slug="open-targets-platform"
            term="Open Targets"
            plain="a target-disease evidence platform"
          />
          ,{' '}
          <T
            slug="chembl"
            term="ChEMBL"
            plain="a database of drug-like molecules and their targets"
          />{' '}
          and{' '}
          <T
            slug="dgidb-drug-gene-interaction-database"
            term="DGIdb"
            plain="an aggregator of drug-gene interaction claims from many databases"
          />
          .
        </p>

        <DataTable<CandidateRow>
          rows={rows}
          rowKey={(r, i) => `${r.drug_id}|${r.target_symbol}|${i}`}
          empty="no candidate matches these filters"
          maxHeight={560}
          columns={[
            {
              key: 'drug_name',
              header: 'drug',
              render: (r) => <span className="text-chrome-100">{r.drug_name}</span>,
            },
            {
              key: 'approved',
              header: 'status',
              sortValue: (r) => r.approved,
              render: (r) => (
                <span className="flex flex-wrap gap-1">
                  {r.approved ? (
                    <Badge tone="good">approved</Badge>
                  ) : (
                    <Badge>phase {r.max_phase ?? '?'}</Badge>
                  )}
                  {r.fda_label && <Badge tone="good">FDA label</Badge>}
                </span>
              ),
            },
            {
              key: 'target_symbol',
              header: 'target',
              render: (r) => (
                <span className="flex items-center gap-1.5">
                  <span className="font-mono text-xs text-chrome-200">{r.target_symbol}</span>
                  <Badge tone={r.target_role === 'seed' ? 'raw' : 'machinery'}>
                    {r.target_role}
                  </Badge>
                </span>
              ),
            },
            {
              key: 'direction_ids',
              header: 'directions',
              sortValue: (r) => r.direction_ids.join(','),
              render: (r) => (
                <span className="font-mono text-micro text-chrome-400">
                  {r.direction_ids.join(' ') || '—'}
                </span>
              ),
            },
            {
              key: 'interaction_or_moa',
              header: 'mechanism of action',
              render: (r) => <span className="text-chrome-400">{r.interaction_or_moa || '—'}</span>,
            },
            {
              key: 'action_type',
              header: 'action',
              render: (r) => (
                <span className="font-mono text-micro text-chrome-400">{r.action_type || '—'}</span>
              ),
            },
            {
              key: 'source',
              header: 'reported by',
              sortValue: (r) => r.source.join(','),
              render: (r) => (
                <span className="font-mono text-micro text-machinery-400">
                  {r.source.join(' · ')}
                </span>
              ),
            },
          ]}
        />
      </div>
    </Exhibit>
  );
}
