import { useMemo } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Callout } from '../../components/Explainer';
import { Loaded } from '../../components/QueryState';
import { DataTable, type Column } from '../../components/DataTable';
import { withoutCoordinates } from '../../lib/aiExport/redact';
import { useClinvarPresence } from '../../api/hooks';
import type { ClinvarPresenceSite, ClinvarPresenceSummary } from '../../api/types';
import { C } from '../../lib/palette';
import { dec, int } from '../../lib/format';

/**
 * The ClinVar cross-check, run inward.
 *
 * Every other exhibit on this page starts from an allele the callset has and asks the
 * world about it. This one starts from every site the world has already called pathogenic
 * inside the candidate panel and asks whether the callset contains it. The bar per gene is
 * therefore mostly grey by construction — a healthy-ish genome carries almost none of the
 * thousands of alleles ClinVar has classified — and that emptiness is the exhibit's point
 * as much as any hit in it.
 */
export function ClinvarPresence() {
  const q = useClinvarPresence();
  // Site rows carry the proband's real chromosome and position; an export must not.
  const exportData = useMemo(
    () => (q.data ? { summary: q.data.data.summary, sites: withoutCoordinates(q.data.data.sites) } : undefined),
    [q.data],
  );

  return (
    <Exhibit
      title="Every ClinVar pathogenic panel site, checked against this callset"
      legend={
        <>
          One track per candidate gene, its full width being every{' '}
          <strong>pathogenic / likely-pathogenic</strong> (P/LP) record ClinVar holds inside that gene.{' '}
          <Chip color={C.good}>green</Chip> = the callset has this exact allele and the caller kept it (PASS) ·{' '}
          <Chip color={C.decision}>yellow</Chip> = present but the caller suppressed it ·{' '}
          <Chip color={C.machineryDim}>blue</Chip> = ClinVar states no alternate allele, so the site could never be
          compared · <Chip color={C.absent}>grey</Chip> = comparable and <em>absent</em> from the callset. Any
          non-zero segment is drawn at least a few pixels wide, so a single hit among a thousand absences is still
          visible; the exact counts are the numbers on the right. In the table below, ★ is ClinVar&apos;s review
          status as its gold-star tier.
        </>
      }
      reading="A green segment is a direct lead: a clinical lab has already argued that exact allele causes disease, and this child carries it. A track that is entirely grey is not a null result — it is evidence the case is not a re-run of any family previously reported in that gene."
      data={exportData}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={480}>
        {(data) => {
          const total = totals(data.summary);
          const leads = data.sites.filter((s) => s.is_het && s.filter === 'PASS');
          return (
            <div className="space-y-4">
              <Totals total={total} />
              <PresenceBars summary={data.summary} />
              <LeadCallout leads={leads} checked={total.n_plp} />
              <SiteTable sites={data.sites} />
              <Caveat uncomparable={total.n_uncomparable} />
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}

// ── the counts ───────────────────────────────────────────────────────────────────────

type Totals = ReturnType<typeof totals>;

function totals(summary: ClinvarPresenceSummary[]) {
  const sum = (pick: (r: ClinvarPresenceSummary) => number) =>
    summary.reduce((acc, row) => acc + pick(row), 0);
  return {
    n_plp: sum((r) => r.n_plp),
    n_present: sum((r) => r.n_present),
    n_present_pass: sum((r) => r.n_present_pass),
    n_present_het: sum((r) => r.n_present_het),
    n_uncomparable: sum((r) => r.n_uncomparable),
    n_absent: sum((r) => r.n_absent),
  };
}

function Totals({ total }: { total: Totals }) {
  return (
    <p className="text-[11px] text-zinc-500">
      <span className="text-zinc-200">{int(total.n_plp)}</span> ClinVar P/LP sites checked across the panel →{' '}
      <span className="text-emerald-400">{int(total.n_present)} present</span> (
      {int(total.n_present_pass)} PASS, {int(total.n_present_het)} heterozygous) ·{' '}
      <span className="text-zinc-400">{int(total.n_absent)} absent</span>
      {total.n_uncomparable > 0 ? (
        <> · <span className="text-blue-400">{int(total.n_uncomparable)} not comparable</span></>
      ) : null}
    </p>
  );
}

// ── the per-gene bars ────────────────────────────────────────────────────────────────

/** Widest track in the set, so genes are comparable to each other and not each to itself. */
const TRACK = 100;

/** Any non-zero segment gets this share of the track, so one hit in a thousand still shows. */
const FLOOR = 1.6;

function segments(row: ClinvarPresenceSummary, scale: number) {
  const present_pass = row.n_present_pass;
  const present_other = row.n_present - row.n_present_pass;
  const raw: { key: string; n: number; color: string; label: string }[] = [
    { key: 'pass', n: present_pass, color: C.good, label: 'present, PASS' },
    { key: 'other', n: present_other, color: C.decision, label: 'present, suppressed by the caller' },
    { key: 'unc', n: row.n_uncomparable, color: C.machineryDim, label: 'ClinVar states no alternate allele' },
    { key: 'absent', n: row.n_absent, color: C.absent, label: 'comparable, not called here' },
  ];
  return raw
    .filter((s) => s.n > 0)
    .map((s) => ({ ...s, width: Math.max(FLOOR, s.n * scale) }));
}

function PresenceBars({ summary }: { summary: ClinvarPresenceSummary[] }) {
  const widest = Math.max(1, ...summary.map((r) => r.n_plp));
  const scale = TRACK / widest;

  return (
    <div className="space-y-1.5">
      {summary.map((row) => (
        <div key={row.gene} className="flex items-center gap-3 text-[11px]">
          <span className="w-16 shrink-0 text-right font-mono font-semibold text-zinc-200">{row.gene}</span>
          <div className="flex h-4 min-w-0 flex-1 items-stretch overflow-hidden rounded-sm bg-zinc-900">
            {row.n_plp === 0 ? (
              <span className="self-center pl-2 text-zinc-600">ClinVar has classified nothing in this gene</span>
            ) : (
              segments(row, scale).map((s) => (
                <div
                  key={s.key}
                  style={{ width: `${s.width}%`, backgroundColor: s.color }}
                  title={`${row.gene}: ${int(s.n)} ${s.label}`}
                />
              ))
            )}
          </div>
          <span className="w-28 shrink-0 tabular-nums text-zinc-500">
            <span className={row.n_present > 0 ? 'font-semibold text-emerald-400' : 'text-zinc-400'}>
              {int(row.n_present)}
            </span>
            {' / '}
            {int(row.n_plp)} present
          </span>
        </div>
      ))}
    </div>
  );
}

// ── the hits ─────────────────────────────────────────────────────────────────────────

function stars(n: number | null): string {
  if (n === null) return '—';
  return '★'.repeat(n) + '☆'.repeat(4 - n);
}

/** What state a site row is in, as one word the table can colour on. */
function state(site: ClinvarPresenceSite): { text: string; color: string } {
  if (site.comparable === false) return { text: 'not comparable', color: C.machinery };
  if (!site.present) return { text: 'absent', color: C.absent };
  if (site.filter === 'PASS') return { text: 'present, PASS', color: C.good };
  return { text: `present, ${site.filter}`, color: C.decision };
}

function SiteTable({ sites }: { sites: ClinvarPresenceSite[] }) {
  const columns: Column<ClinvarPresenceSite>[] = [
    {
      key: 'gene',
      header: 'gene',
      render: (r) => <span className="font-mono font-semibold text-zinc-100">{r.gene}</span>,
    },
    {
      key: 'clnsig',
      header: 'ClinVar classification',
      render: (r) => <span className="font-semibold text-red-400">{r.clnsig}</span>,
    },
    {
      key: 'review_stars',
      header: '★ review',
      sortValue: (r) => r.review_stars,
      render: (r) => (
        <span className="font-mono text-amber-300" title={r.clnrevstat ?? 'no review status stated'}>
          {stars(r.review_stars)}
        </span>
      ),
    },
    {
      key: 'state',
      header: 'in this callset',
      sortValue: (r) => state(r).text,
      render: (r) => {
        const s = state(r);
        return (
          <span className="font-semibold" style={{ color: s.color }}>
            {s.text}
          </span>
        );
      },
    },
    { key: 'gt', header: 'GT', align: 'right', render: (r) => <span className="font-mono">{r.gt ?? '—'}</span> },
    {
      key: 'vaf',
      header: 'VAF',
      align: 'right',
      render: (r) => (r.vaf === null ? <span className="text-zinc-600">—</span> : dec(r.vaf, 3)),
    },
    {
      key: 'dp',
      header: 'DP',
      align: 'right',
      render: (r) => (r.dp === null ? <span className="text-zinc-600">—</span> : int(r.dp)),
    },
    {
      key: 'is_het',
      header: 'one copy?',
      sortValue: (r) => r.is_het,
      render: (r) =>
        r.is_het === null ? (
          <span className="text-zinc-600">—</span>
        ) : (
          <span className={r.is_het ? 'text-emerald-400' : 'text-zinc-400'}>{r.is_het ? 'het' : 'hom'}</span>
        ),
    },
    {
      key: 'variation_id',
      header: 'ClinVar id',
      align: 'right',
      render: (r) => (
        <a
          className="font-mono text-blue-400 hover:underline"
          href={`https://www.ncbi.nlm.nih.gov/clinvar/variation/${r.variation_id}/`}
          target="_blank"
          rel="noreferrer"
        >
          {r.variation_id}
        </a>
      ),
    },
    {
      key: 'condition',
      header: 'condition asserted',
      render: (r) => <span className="text-zinc-400">{(r.condition ?? '—').split('|').join(' · ')}</span>,
    },
  ];

  return (
    <DataTable
      rows={sites}
      columns={columns}
      filterable
      rowKey={(r) => String(r.variation_id)}
      empty="no ClinVar P/LP site in the panel is present in this callset — every one of them was checked and none was called"
    />
  );
}

// ── the two things a reader has to be told ───────────────────────────────────────────

function LeadCallout({ leads, checked }: { leads: ClinvarPresenceSite[]; checked: number }) {
  if (leads.length === 0) {
    return (
      <Callout tone="neutral" title="No previously-classified pathogenic allele is carried heterozygously">
        All {int(checked)} P/LP sites were checked and none came back as a kept heterozygous call. That is a real
        result, not a gap: whatever is causing this case has not been reported in ClinVar at these exact alleles,
        so the answer has to come from the rarity-and-consequence argument above rather than from a prior.
      </Callout>
    );
  }
  const genes = [...new Set(leads.map((l) => l.gene))].join(', ');
  return (
    <Callout tone="decision" title={`${leads.length} previously-classified pathogenic allele${leads.length === 1 ? '' : 's'} carried heterozygously — ${genes}`}>
      A clinical lab has already submitted{' '}
      {leads.length === 1 ? 'this exact allele' : 'these exact alleles'} to ClinVar as pathogenic or likely
      pathogenic, and this child carries one copy, on a call the variant caller kept. This reaches the same allele
      by a different route than the annotation table above does — that one asked VEP what a called allele means,
      this one asked ClinVar which sites to look for and then went looking. Two independent paths agreeing is
      worth more than either alone. It is still <strong>one</strong> copy: a recessive disease needs a second hit
      on the other parental copy, and nothing here supplies it.
    </Callout>
  );
}

function Caveat({ uncomparable }: { uncomparable: number }) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 p-3 text-[11px] leading-relaxed text-zinc-400">
      <p>
        <strong className="text-zinc-300">Presence is a lower bound, not a count.</strong> A site matches only when
        the contig, the position and the reference allele are identical strings and the ClinVar alternate allele is
        one of the callset record&apos;s alternates. Neither side is <em>left-aligned</em> (rewritten to the
        left-most equivalent spelling), so the same one-base insertion written{' '}
        <code className="text-zinc-300">T → TA</code> by ClinVar and{' '}
        <code className="text-zinc-300">TA → TAA</code> by the caller does not join and reads as absent. For
        single-base substitutions the comparison is exact; for insertions and deletions the true presence count can
        only be <em>higher</em> than what is shown.
      </p>
      <p className="mt-2">
        <strong className="text-zinc-300">Review status is assertion quality, not confidence.</strong> ClinVar&apos;s
        gold stars record <em>how</em> a classification was reached, not how strong the evidence is:
        ★★★★ a practice guideline, ★★★ an expert panel, ★★ several labs agreeing under stated criteria, ★ one lab
        under stated criteria, ☆☆☆☆ an assertion with no criteria given. A one-star pathogenic claim is still a
        claim; it just rests on one submitter.
        {uncomparable > 0 ? (
          <>
            {' '}
            {int(uncomparable)} record{uncomparable === 1 ? '' : 's'} in this set state no alternate allele at all
            (ClinVar writes <code className="text-zinc-300">.</code>), so they are marked{' '}
            <em>not comparable</em> and counted as neither present nor absent.
          </>
        ) : null}
      </p>
    </div>
  );
}
