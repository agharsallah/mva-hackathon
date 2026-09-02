import { useMemo } from 'react';

import { useVcfFields } from '../../api/hooks';
import type { FieldKind, VcfFieldRow } from '../../api/types';
import { type Column, DataTable } from '../../components/DataTable';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { C } from '../../lib/palette';

/**
 * The callset's own schema, as its VCF header declares it.
 *
 * A VCF is a row-oriented record format whose header is a self-describing schema: every
 * `##FILTER`, `##INFO` and `##FORMAT` line declares one field, its type and a prose
 * description. Three namespaces, three different scopes:
 *
 * - **FILTER** — the caller's vetoes. A record's FILTER column carries the names of the
 *   ones that fired, or `PASS`. This is the vocabulary the funnel above is counting.
 * - **INFO** — per-*site* annotations, one value per record regardless of samples.
 * - **FORMAT** — per-*sample* fields. The FORMAT column lists the keys, in the record's
 *   own order, and the sample column carries the matching values. That order is a
 *   convention and not a guarantee, which is why every derivation in this repo locates
 *   `GT`/`AD`/`DP` by key rather than by position.
 *
 * Every description here is the caller's own text, verbatim out of `warehouse.vcf_fields`.
 * None of it is our writing, which is the point: this is what the delivery says about
 * itself, and it is the list against which "the VCF carries no annotation worth ranking
 * on" is checkable rather than asserted.
 */

const KIND_COLOR: Record<FieldKind, string> = {
  FILTER: C.decision,
  INFO: C.machinery,
  FORMAT: C.raw,
};

const KIND_SCOPE: Record<FieldKind, string> = {
  FILTER: 'a veto the caller can raise on a record',
  INFO: 'one value per site, whatever the sample count',
  FORMAT: 'one value per sample, keyed by the record’s own FORMAT column',
};

/**
 * Fields the rest of the app actually reads, so the table shows what is load-bearing.
 *
 * Keyed by `kind:id`, not by id: `DP` is declared twice — once in INFO as the site's
 * combined depth and once in FORMAT as this sample's — and they are read in different
 * places. Collapsing them would put the wrong sentence on one of the two rows.
 */
const USED: Record<string, string> = {
  'FILTER:PASS': 'the funnel’s first stage',
  'FILTER:MQ40': 'the largest single veto — 177,522 records',
  'FILTER:QD2': 'the second largest veto',
  'FORMAT:GT': 'every genotype call in the repo',
  'FORMAT:AD': 'the allele depths behind every VAF and the BAF karyogram',
  'FORMAT:DP': 'per-sample depth, on the pair matrix and the locus track',
  'FORMAT:PGT': 'the phase pairs on the Panel page',
  'FORMAT:PID': 'the phase-set id those pairs are grouped by',
  'INFO:DP': 'site depth — the depth histogram on this page',
  'INFO:DB': 'the only usable annotation the delivery ships — dbSNP membership',
  'INFO:AF': 'the zygosity split above (NOT a population frequency here)',
};

const usage = (r: VcfFieldRow): string | undefined => USED[`${r.kind}:${r.id}`];

export function HeaderFields() {
  const q = useVcfFields();

  const columns: Column<VcfFieldRow>[] = useMemo(
    () => [
      {
        key: 'kind',
        header: 'namespace',
        render: (r) => (
          <span
            className="rounded px-1.5 py-px font-mono text-[10px]"
            style={{ color: KIND_COLOR[r.kind], background: `${KIND_COLOR[r.kind]}1a` }}
            title={KIND_SCOPE[r.kind]}
          >
            {r.kind}
          </span>
        ),
      },
      {
        key: 'id',
        header: 'field',
        render: (r) => <span className="font-mono font-semibold text-chrome-100">{r.id}</span>,
      },
      {
        key: 'description',
        header: 'what the header says it is',
        render: (r) => <span className="text-chrome-300">{r.description}</span>,
      },
      {
        key: 'used',
        header: 'where we read it',
        sortValue: (r) => usage(r) ?? null,
        render: (r) => {
          const where = usage(r);
          return where ? (
            <span className="text-good-400/90">{where}</span>
          ) : (
            <span className="text-chrome-600">—</span>
          );
        },
      },
    ],
    [],
  );

  return (
    <Exhibit
      title="The callset's own schema — every field its VCF header declares"
      legend={
        <>
          One row per header declaration, grouped by namespace:{' '}
          <Chip color={C.decision}>FILTER — a veto on a record</Chip> ·{' '}
          <Chip color={C.machinery}>INFO — one value per site</Chip> ·{' '}
          <Chip color={C.raw}>FORMAT — one value per sample</Chip>. Descriptions are the
          caller&apos;s own text, verbatim. The last column is green where something in this repo
          actually reads the field and <span className="text-chrome-500">—</span> where nothing
          does. Sortable; the filter box matches any cell.
        </>
      }
      reading={
        <>
          This list is the evidence for a claim the whole project rests on:{' '}
          <strong>the delivery ships no annotation worth ranking on</strong>. Every INFO field is a
          caller statistic — depth, strand bias, rank-sum tests — with no VEP consequence, no gnomAD
          frequency, no ClinVar verdict and no CADD score among them. The one exception is{' '}
          <code className="text-chrome-300">DB</code>, a bare dbSNP-membership flag. Everything the
          Panel page ranks on had to be fetched and joined by us.
        </>
      }
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={420}>
        {(rows) => {
          const counts = rows.reduce<Record<string, number>>((a, r) => {
            a[r.kind] = (a[r.kind] ?? 0) + 1;
            return a;
          }, {});
          return (
            <>
              <DataTable
                rows={rows}
                columns={columns}
                rowKey={(r) => `${r.kind}:${r.id}`}
                maxHeight={460}
                filterable
                filterLabel="find a field"
                filterPlaceholder="e.g. depth, phasing, MQ"
              />
              <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-chrome-500">
                {(['FILTER', 'INFO', 'FORMAT'] as FieldKind[]).map((kind) => (
                  <span key={kind}>
                    <span className="font-mono" style={{ color: KIND_COLOR[kind] }}>
                      {counts[kind] ?? 0}
                    </span>{' '}
                    {kind} — {KIND_SCOPE[kind]}
                  </span>
                ))}
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
