/**
 * What a resolved query turns into: a summary line, a density strip, and the records.
 *
 * The summary line is not decoration. A search box that shows only rows teaches the user
 * that an empty table means "nothing there", when it may mean "the name resolved from
 * dbSNP and this callset never called the site" — a completely different fact. So the
 * resolver, its provenance and its caveat are stated *above* the data, every time.
 */

import { Chip, Exhibit } from '../../components/Exhibit';
import { DataTable, type Column } from '../../components/DataTable';
import { Loaded } from '../../components/QueryState';
import { useRegion } from '../../api/hooks';
import type { RegionVariant, RegionWindow, SearchResolution } from '../../api/types';
import { C } from '../../lib/palette';
import { dec, int } from '../../lib/format';
import { DensityLegend, DensityStrip, bin } from './DensityStrip';

const KIND_LABEL: Record<SearchResolution['kind'], string> = {
  region: 'region',
  gene: 'gene symbol',
  rsid: 'rsID',
};

/** Colour a resolver by what it cost: the panel and the callset are ours, Ensembl is not. */
function sourceTone(source: string): string {
  if (source.startsWith('ensembl')) return 'text-purple-300';
  if (source.startsWith('pg.') || source.startsWith('ressources')) return 'text-emerald-300';
  return 'text-zinc-300';
}

export function Resolution({ found }: { found: SearchResolution }) {
  const span = found.end - found.start + 1;
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-[11px] uppercase tracking-wider text-zinc-400">
          {KIND_LABEL[found.kind]}
        </span>
        <span className="font-mono text-sm text-zinc-100">{found.label}</span>
        <span className="text-xs text-zinc-500">{int(span)} bp window</span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-zinc-400">
        resolved by{' '}
        <span className={`font-mono ${sourceTone(found.source)}`}>{found.source}</span>
        {found.note && <> — {found.note}</>}
      </p>
    </div>
  );
}

export function RegionResult({ found }: { found: SearchResolution }) {
  const q = useRegion({ chrom: found.chrom, start: found.start, end: found.end });
  return (
    <Loaded query={q} height={420}>
      {(window, meta) => (
        <Window
          window={window}
          found={found}
          source={meta.source}
          cachedAt={meta.cachedAt}
          origin={meta.origin}
        />
      )}
    </Loaded>
  );
}

function Window({
  window,
  found,
  source,
  cachedAt,
  origin,
}: {
  window: RegionWindow;
  found: SearchResolution;
  source: string;
  cachedAt: string | null;
  origin: 'api' | 'fixture';
}) {
  const bins = bin(window.variants, window.start, window.end);
  const pass = window.variants.filter((v) => v.filter === 'PASS').length;
  const multi = window.variants.filter((v) => v.gt === '1/2').length;
  const named = window.variants.filter((v) => v.id).length;

  if (window.n === 0) return <EmptyWindow found={found} source={source} origin={origin} />;

  return (
    <div className="space-y-4">
      <Exhibit
        title="Where the records sit in the window"
        legend={<DensityLegend bp={bins.bp} />}
        reading="A gene-shaped window is rarely flat: dense bars are well-covered stretches, gaps are repetitive or poorly mapped ones. Red stacked on green marks where the caller was least sure, which is where a real variant is most likely to be hidden."
        source={source}
        cachedAt={cachedAt}
        origin={origin}
      >
        <DensityStrip variants={window.variants} start={window.start} end={window.end} />
        <div className="mt-2 grid gap-2 text-[11px] text-zinc-500 sm:grid-cols-4">
          <span>
            records <span className="font-mono text-zinc-300">{int(window.n)}</span>
          </span>
          <span>
            PASS <span className="font-mono text-emerald-400">{int(pass)}</span> ·{' '}
            <span className="font-mono text-red-400">{int(window.n - pass)}</span> suppressed
          </span>
          <span>
            1/2 sites <span className="font-mono text-amber-400">{int(multi)}</span>
          </span>
          <span>
            carry an rsID <span className="font-mono text-zinc-300">{int(named)}</span>
          </span>
        </div>
      </Exhibit>

      <Exhibit
        title="Every record in the window"
        legend={
          <>
            One row per VCF record, in position order. <Chip color={C.good}>PASS</Chip> is a record
            the caller kept, <Chip color={C.broken}>anything else</Chip> a record it kept but
            flagged — suppressed, not deleted. <span className="font-mono">GT</span> is the
            genotype: <span className="font-mono">0/1</span> one copy changed,{' '}
            <span className="font-mono">1/1</span> both copies changed,{' '}
            <span className="font-mono">1/2</span> two <em>different</em> changes, one per copy.{' '}
            <span className="font-mono">VAF</span> is the share of reads carrying the alternate
            allele; it is <span className="font-mono">—</span> on a{' '}
            <span className="font-mono">1/2</span> record, where there is no single alternate to
            attribute reads to. A blank <span className="font-mono">rsID</span> means the VCF wrote{' '}
            <span className="font-mono">.</span> — the site has no dbSNP name here.
          </>
        }
        reading="Two different damaging records in one gene is the shape Track 1 is looking for, so scan for pairs, not for single rows — and treat a suppressed record as evidence, not as absence."
        source={source}
        cachedAt={cachedAt}
        origin={origin}
      >
        <DataTable rows={window.variants} columns={COLUMNS} rowKey={(r) => `${r.pos}-${r.alt}`} maxHeight={520} />
      </Exhibit>
    </div>
  );
}

/** Resolved, and nothing there. The one state a search box usually gets wrong. */
function EmptyWindow({
  found,
  source,
  origin,
}: {
  found: SearchResolution;
  source: string;
  origin: 'api' | 'fixture';
}) {
  const dbsnp = found.source.startsWith('ensembl');
  return (
    <div className="rounded-xl border border-amber-800/60 bg-amber-950/25 p-5">
      <div className="text-xs font-semibold uppercase tracking-wider text-amber-300">
        resolved, and the callset has no record here
      </div>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-300">
        <span className="font-mono text-zinc-100">{found.label}</span> is a real place —{' '}
        {dbsnp
          ? 'dbSNP placed it via Ensembl, and this callset never called a variant at it.'
          : 'the window resolved, and this callset carries no record inside it.'}{' '}
        That is a <strong>finding, not a failure</strong>: the proband is reference here, or the
        site was never covered well enough to call. It is a different fact from an unknown name,
        which would have been a 404 before this panel was reached.
      </p>
      <p className="mt-2 font-mono text-[11px] text-zinc-600">
        {origin === 'fixture' && (
          <span className="mr-1.5 rounded bg-amber-500/15 px-1 py-px text-amber-400">fixture</span>
        )}
        {source}
      </p>
    </div>
  );
}

const COLUMNS: Column<RegionVariant>[] = [
  { key: 'pos', header: 'position', render: (r) => int(r.pos), align: 'right' },
  {
    key: 'id',
    header: 'rsID',
    render: (r) =>
      r.id ? <span className="font-mono text-zinc-300">{r.id}</span> : <span className="text-zinc-700">—</span>,
  },
  {
    key: 'change',
    header: 'ref → alt',
    render: (r) => (
      <span className="font-mono">
        <span className="text-zinc-500">{r.ref}</span>
        <span className="text-zinc-600"> → </span>
        <span className="text-zinc-200">{r.alt}</span>
      </span>
    ),
  },
  { key: 'qual', header: 'QUAL', render: (r) => dec(r.qual, 1), align: 'right' },
  {
    key: 'filter',
    header: 'FILTER',
    render: (r) => (
      <span className={r.filter === 'PASS' ? 'text-emerald-400' : 'text-red-400'}>{r.filter}</span>
    ),
  },
  {
    key: 'gt',
    header: 'GT',
    render: (r) => (
      <span className={r.gt === '1/2' ? 'font-mono text-amber-400' : 'font-mono text-zinc-300'}>
        {r.gt ?? '—'}
      </span>
    ),
  },
  { key: 'dp', header: 'depth', render: (r) => int(r.dp), align: 'right' },
  {
    key: 'ad',
    header: 'alt / ref reads',
    render: (r) => (r.ad_alt === null ? '—' : `${int(r.ad_alt)} / ${int(r.ad_ref)}`),
    align: 'right',
  },
  { key: 'vaf', header: 'VAF', render: (r) => (r.vaf === null ? '—' : dec(r.vaf, 3)), align: 'right' },
  { key: 'gq', header: 'GQ', render: (r) => int(r.gq), align: 'right' },
];
