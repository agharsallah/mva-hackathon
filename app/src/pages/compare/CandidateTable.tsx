import { useMemo } from 'react';

import { usePanelAnnotations } from '../../api/hooks';
import type { PanelAnnotationRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { Loaded } from '../../components/QueryState';
import { withoutCoordinates } from '../../lib/aiExport/redact';
import { dec, int } from '../../lib/format';
import { C, impactTone } from '../../lib/palette';
import { cx, TEXT } from '../../lib/ui';
import { af, candidates, isPathogenic } from './rarity';

/**
 * The distilled list: everything left after two filters that a causal recessive variant
 * cannot fail — it must be rare in the healthy population, and it must be able to change
 * the protein. Nothing about phase (which parental copy each variant sits on) is proven
 * here, and with no parents in this dataset it cannot be.
 *
 * This table is meant to be short. A two-row result is the finding, not an empty state.
 */
export function CandidateTable() {
  const q = usePanelAnnotations();
  // The rows carry the proband's real chromosome and position; an export must not.
  const exportData = useMemo(
    () => (q.data ? withoutCoordinates(q.data.data) : undefined),
    [q.data],
  );

  const columns: Column<PanelAnnotationRow>[] = [
    {
      key: 'gene',
      header: 'gene',
      render: (r) => (
        <span className="font-mono font-semibold text-chrome-100">{r.gene ?? '—'}</span>
      ),
    },
    {
      key: 'csq',
      header: 'consequence',
      render: (r) => <span className="font-mono">{r.consequence}</span>,
    },
    {
      key: 'impact',
      header: 'impact',
      render: (r) => (
        <span className={cx('font-mono font-semibold', TEXT[impactTone(r.impact)])}>
          {r.impact}
        </span>
      ),
    },
    {
      key: 'af',
      header: 'gnomAD AF',
      align: 'right',
      render: (r) =>
        r.gnomad_af === null ? (
          <span
            className="font-semibold text-raw-400"
            title="absent from gnomAD — not frequency zero"
          >
            novel
          </span>
        ) : (
          af(r.gnomad_af)
        ),
    },
    {
      key: 'grpmax',
      header: 'grpmax',
      align: 'right',
      render: (r) =>
        r.gnomad_af_grpmax === null ? (
          <span className="text-chrome-600">—</span>
        ) : (
          af(r.gnomad_af_grpmax)
        ),
    },
    {
      key: 'clin',
      header: 'ClinVar',
      render: (r) =>
        r.clin_sig === null ? (
          <span className="text-chrome-600">no record</span>
        ) : (
          <span
            className={
              isPathogenic(r.clin_sig) ? 'font-semibold text-broken-400' : 'text-chrome-400'
            }
          >
            {r.clin_sig}
          </span>
        ),
    },
    { key: 'gt', header: 'GT', align: 'right', render: (r) => <span>{r.gt}</span> },
    {
      key: 'vaf',
      header: 'VAF',
      align: 'right',
      render: (r) =>
        r.vaf === null ? <span className="text-chrome-600">n/a</span> : dec(r.vaf, 3),
    },
    { key: 'qual', header: 'QUAL', align: 'right', render: (r) => dec(r.qual, 1) },
    {
      key: 'filter',
      header: 'FILTER',
      align: 'right',
      render: (r) => (
        <span className={r.filter === 'PASS' ? 'text-good-400' : 'text-broken-400'}>
          {r.filter}
        </span>
      ),
    },
  ];

  return (
    <Exhibit
      title="Candidate list — rare in the population and able to change the protein"
      legend={
        <>
          Two filters, both required: <span className="font-mono">is_rare_recessive</span> (rare
          enough in gnomAD that healthy carriers are plausible but two hits are not) and{' '}
          <span className="font-mono">is_protein_altering</span> (the consequence changes the
          protein sequence). Impact colour: <Chip color={C.broken}>HIGH</Chip> ·{' '}
          <Chip color={C.decision}>MODERATE</Chip>. A{' '}
          <span className="text-raw-400">purple &ldquo;novel&rdquo;</span> is absent from gnomAD,
          sorted ahead of every measured frequency because absent is rarer than rare.{' '}
          <span className="text-broken-400">Red ClinVar text</span> = an asserted pathogenic
          classification; <span className="text-good-400">green FILTER</span> = the caller kept the
          record.
        </>
      }
      reading="A short list is the intended outcome. Sorted most-damaging first, then rarest first."
      data={exportData}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={220}>
        {(rows) => {
          const hits = candidates(rows);
          const byGene = new Map<string, number>();
          for (const h of hits) {
            // Protein-altering implies a gene, but the contract allows null — bucket it visibly.
            const g = h.gene ?? 'no gene (intergenic)';
            byGene.set(g, (byGene.get(g) ?? 0) + 1);
          }
          const paired = [...byGene.entries()].filter(([, n]) => n >= 2);

          return (
            <div className="space-y-3">
              <p className="text-[11px] text-chrome-500">
                {int(rows.length)} annotated records in →{' '}
                <span className="text-chrome-200">{int(hits.length)}</span> survive both filters, in{' '}
                {byGene.size} gene{byGene.size === 1 ? '' : 's'}
              </p>
              <DataTable
                rows={hits}
                columns={columns}
                rowKey={(r, i) => `${r.gene}:${r.consequence}:${i}`}
                empty="no record clears both filters — nothing here is both rare and protein-altering"
              />
              {paired.length > 0 ? (
                <Callout tone="decision" title="Two hits in one gene — the compound-het shape">
                  <strong>{paired.map(([g, n]) => `${g} (${n})`).join(', ')}</strong> carries more
                  than one rare, protein-altering, heterozygous record. That is the <em>shape</em>{' '}
                  of a compound heterozygote (two different broken copies of one gene, one inherited
                  from each parent). It is not proof:
                  <strong> phase is unproven</strong> — nothing here shows the two variants sit on
                  different copies rather than both on the same one, and with a single sample and no
                  parents this dataset cannot settle it from genotypes alone. Read-backed phasing or
                  a parental sample would.
                </Callout>
              ) : (
                <Callout tone="neutral" title="No gene carries two hits">
                  Every surviving record is alone in its gene, so no compound-heterozygous pair is
                  visible at these thresholds. Either the partner variant is suppressed behind a
                  FILTER, is outside the panel, or is a variant class this callset does not
                  represent.
                </Callout>
              )}
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
