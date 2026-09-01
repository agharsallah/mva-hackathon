import { useState } from 'react';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout, type Trace } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { Select } from '../../components/Controls';
import { Callout } from '../../components/Explainer';
import { DataTable, type Column } from '../../components/DataTable';
import { usePanelSuppressed } from '../../api/hooks';
import type { PanelFilterCensusRow, PanelSuppressed, PanelSuppressedRecord } from '../../api/types';
import { C, impactColor } from '../../lib/palette';
import { dec, int } from '../../lib/format';

/**
 * Reds and yellows for suppression reasons, heaviest reason first.
 *
 * Deliberately assigned by *rank*, not by reason name: the exhibit is meant to transfer to
 * another callset whose caller writes different FILTER labels, and a hard-coded
 * `MQ40 → red` map would silently render an unknown label as grey. Red = the record was
 * thrown out of every downstream analysis; yellow = it was, too, but on a softer test.
 * PASS is the one green.
 */
const REASON_RAMP = [C.broken, '#f97316', C.decision, '#b91c1c', '#fbbf24', C.brokenDim];

/** What the caller's own FILTER labels mean, in plain words. Unknown labels fall through. */
const REASON_MEANING: Record<string, string> = {
  MQ40: 'mapping quality below 40 — the reads carrying this call could sit somewhere else',
  QD2: 'quality-by-depth below 2 — confidence too low for the number of reads behind it',
  LowQual: 'the caller’s overall site-quality floor',
};

function meaningOf(filter: string): string {
  return filter
    .split(';')
    .map((r) => REASON_MEANING[r] ?? r)
    .join(' · ');
}

/**
 * Suppressed-call mining view — PASS against every suppression reason, per candidate gene.
 *
 * The premise the exhibit exists to teach: a VCF's `FILTER` column is **not** a delete.
 * The caller kept the record and wrote down which threshold it failed, so a non-PASS row
 * is a call with a warning label rather than an absence of evidence. Every other panel
 * exhibit in this app is PASS-only by construction; this is the one that looks at what
 * those discarded.
 *
 * That matters here for a mechanical reason. `MQ40` fires where reads map ambiguously —
 * segmental duplications, repeats, subtelomeric sequence — which is exactly where a real
 * variant is hardest to call and easiest to lose. A compound heterozygote needs *two*
 * damaging alleles in one gene; if the second one is sitting behind an `MQ40` flag, a
 * PASS-only search will never find it and will report the gene as carrying one variant.
 *
 * Two grains, one payload: the census (every gene, every FILTER value, PASS included) is
 * always the whole panel because the chart compares genes; the record table below is one
 * gene at a time.
 */
export function SuppressedCalls() {
  const [gene, setGene] = useState('TRIP13');
  const q = usePanelSuppressed();

  return (
    <div className="space-y-4">
      <Exhibit
        title="PASS against suppressed, per candidate gene and per filter reason"
        legend={
          <>
            <Chip color={C.good}>green</Chip> = <span className="font-mono">PASS</span>, the records every
            other exhibit on this page uses. Every other colour is one suppression reason, in{' '}
            <Chip color={C.broken}>reds</Chip> and <Chip color={C.decision}>yellows</Chip>, assigned heaviest
            reason first so the ordering is stable across callsets. <strong>Left panel</strong>: each gene’s
            records as a share of that gene, so a small gene is comparable to a large one — the bars all reach
            100 %. <strong>Right panel</strong>: the suppressed records alone, as counts, which is the actual
            size of the search space. A gene missing from the right panel has nothing suppressed. A{' '}
            <span className="font-mono">;</span>-joined label such as{' '}
            <span className="font-mono">LowQual;QD2</span> is <em>one</em> record that tripped two thresholds,
            counted once — never split in two.
          </>
        }
        reading="TRIP13 is the case: an established MVA gene with 12 records, of which 6 are suppressed — 5 MQ40 and 1 QD2 — the worst PASS share on the panel by a wide margin. All six are heterozygous with 2–11 alternate reads. TRIP13 sits near the chromosome 5 telomere in hard-to-map sequence, so half its evidence being flagged is a statement about mappability, not about the child."
        // The census only: it is per-gene counts and carries no coordinate. The record
        // half of the payload does, so it never leaves the browser — see the table below.
        data={q.data?.data.census}
        source={q.data?.source}
        cachedAt={q.data?.cachedAt}
        origin={q.data?.origin}
      >
        <Loaded query={q} height={420}>
          {(payload) => <CensusChart census={payload.census} />}
        </Loaded>
      </Exhibit>

      <Callout tone="decision" title="What a FILTER value actually is, and why a flagged het is worth opening">
        <p>
          <strong>The caller kept these records.</strong> <span className="font-mono">FILTER</span> is a text
          column on the row, not a deletion: GATK’s <span className="font-mono">VariantFiltration</span> writes
          the name of every threshold the record failed and leaves the row in the file. So &ldquo;suppressed&rdquo;
          means <em>downstream tools are expected to skip it</em>, and that expectation is a heuristic tuned for
          a population study, not a verdict about this child.
        </p>
        <p className="mt-2">
          <strong>MQ40</strong> = mean <em>mapping quality</em> under 40. Mapping quality is the aligner’s
          confidence that a read came from where it placed it, so MQ40 fires wherever the genome repeats itself
          and a read could have come from two places. <strong>QD2</strong> = <em>quality by depth</em> under 2:
          the site’s confidence score divided by the reads behind it, which catches a call that only looks
          confident because it is deeply covered. Both are proxies for &ldquo;hard to sequence here&rdquo;, and
          hard-to-sequence regions still contain variants.
        </p>
        <p className="mt-2">
          A <strong>suppressed heterozygous call in a candidate gene</strong> is therefore exactly the shape a
          hidden second allele takes: one broken copy, thin read support, in sequence the aligner mistrusts. It
          is not proof of anything — the evidence to confirm one lives in the raw reads, not in the VCF — but it
          is the cheapest place to look before re-calling 80 GB of FASTQ.
        </p>
      </Callout>

      <Loaded query={q} height={260}>
        {(payload, meta) => (
          <RecordTable
            payload={payload}
            gene={gene}
            onGene={setGene}
            source={meta.source}
            cachedAt={meta.cachedAt}
            origin={meta.origin}
          />
        )}
      </Loaded>
    </div>
  );
}

/** Suppression reasons across the whole panel, heaviest first — that order fixes the colours. */
function reasonOrder(census: PanelFilterCensusRow[]): string[] {
  const totals = new Map<string, number>();
  for (const row of census) {
    if (row.is_pass) continue;
    totals.set(row.filter, (totals.get(row.filter) ?? 0) + row.n);
  }
  return [...totals.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([f]) => f);
}

function CensusChart({ census }: { census: PanelFilterCensusRow[] }) {
  const reasons = reasonOrder(census);
  const color = (filter: string) =>
    filter === 'PASS' ? C.good : REASON_RAMP[reasons.indexOf(filter) % REASON_RAMP.length];

  // Genes ordered by how much of them is suppressed, so the mining target leads.
  const suppressedPct = new Map<string, number>();
  const suppressedN = new Map<string, number>();
  for (const row of census) {
    if (row.is_pass) continue;
    suppressedPct.set(row.gene, (suppressedPct.get(row.gene) ?? 0) + row.pct_of_gene);
    suppressedN.set(row.gene, (suppressedN.get(row.gene) ?? 0) + row.n);
  }
  const genes = [...new Set(census.map((r) => r.gene))].sort(
    (a, b) => (suppressedPct.get(b) ?? 0) - (suppressedPct.get(a) ?? 0) || a.localeCompare(b),
  );

  const cell = (gene: string, filter: string) => census.find((r) => r.gene === gene && r.filter === filter);

  const traces: Trace[] = [];
  for (const filter of ['PASS', ...reasons]) {
    const rows = genes.map((g) => cell(g, filter));
    traces.push({
      type: 'bar',
      name: filter,
      legendgroup: filter,
      x: genes,
      y: rows.map((r) => r?.pct_of_gene ?? 0),
      customdata: rows.map((r) => [r?.n ?? 0, meaningOf(filter)]),
      marker: { color: color(filter), line: { width: 0 } },
      hovertemplate: `%{x} · ${filter}<br>%{customdata[0]:,} records, %{y:.2f} %<br>%{customdata[1]}<extra></extra>`,
    });
    if (filter === 'PASS') continue;
    // The same reason again on the right axis pair, as a count — the search-space size.
    traces.push({
      type: 'bar',
      name: filter,
      legendgroup: filter,
      showlegend: false,
      xaxis: 'x2',
      yaxis: 'y2',
      x: genes,
      y: rows.map((r) => r?.n ?? 0),
      marker: { color: color(filter), line: { width: 0 } },
      hovertemplate: `%{x} · ${filter}<br>%{y:,} suppressed records<extra></extra>`,
    });
  }

  const totalSuppressed = [...suppressedN.values()].reduce((a, b) => a + b, 0);
  const axis = { type: 'category' as const, gridcolor: 'rgba(0,0,0,0)', tickfont: { color: C.inkDim, size: 10 } };

  return (
    <Plot
      height={400}
      data={traces}
      layout={baseLayout({
        margin: { l: 52, r: 46, t: 30, b: 60 },
        barmode: 'stack',
        bargap: 0.32,
        xaxis: { ...axis, domain: [0, 0.5], tickangle: -35 },
        xaxis2: { ...axis, domain: [0.6, 1], tickangle: -35, anchor: 'y2' },
        yaxis: {
          title: { text: 'share of the gene’s records (%)', font: { color: C.inkDim, size: 11 } },
          range: [0, 100],
          gridcolor: C.grid,
          tickfont: { color: C.inkDim, size: 10 },
        },
        yaxis2: {
          title: { text: 'suppressed records', font: { color: C.inkDim, size: 11 } },
          anchor: 'x2',
          gridcolor: C.grid,
          tickfont: { color: C.inkDim, size: 10 },
        },
        annotations: [
          {
            xref: 'paper',
            yref: 'paper',
            x: 0,
            y: 1.1,
            showarrow: false,
            text: 'every record, as a share of its gene',
            font: { color: C.inkDim, size: 11 },
          },
          {
            xref: 'paper',
            yref: 'paper',
            x: 0.6,
            y: 1.1,
            showarrow: false,
            text: `the suppressed ones alone — ${int(totalSuppressed)} records to mine`,
            font: { color: C.inkDim, size: 11 },
          },
        ],
        legend: { orientation: 'h', y: -0.26, x: 0, font: { color: C.inkDim, size: 11 } },
      })}
    />
  );
}

function RecordTable({
  payload,
  gene,
  onGene,
  source,
  cachedAt,
  origin,
}: {
  payload: PanelSuppressed;
  gene: string;
  onGene: (g: string) => void;
  source?: string;
  cachedAt?: string | null;
  origin?: 'api' | 'fixture';
}) {
  const counts = new Map<string, number>();
  for (const row of payload.census) if (!row.is_pass) counts.set(row.gene, (counts.get(row.gene) ?? 0) + row.n);
  const options = [...new Set(payload.census.map((r) => r.gene))]
    .sort((a, b) => (counts.get(b) ?? 0) - (counts.get(a) ?? 0) || a.localeCompare(b))
    .map((g) => ({ value: g, label: `${g} (${counts.get(g) ?? 0} suppressed)` }));
  const chosen = options.some((o) => o.value === gene) ? gene : (options[0]?.value ?? gene);
  const rows = payload.records.filter((r) => r.gene === chosen);

  const absent = (why: string) => (
    <span className="text-zinc-600" title={why}>
      not annotated
    </span>
  );

  const columns: Column<PanelSuppressedRecord>[] = [
    { key: 'pos', header: 'position', align: 'right', render: (r) => int(r.pos) },
    {
      key: 'allele',
      header: 'ref → alt',
      render: (r) => (
        <span className="font-mono text-zinc-200">
          {r.ref} <span className="text-zinc-600">→</span> {r.alt}
        </span>
      ),
      sortValue: (r) => `${r.ref}>${r.alt}`,
    },
    { key: 'qual', header: 'QUAL', align: 'right', render: (r) => dec(r.qual, 1) },
    {
      key: 'filter',
      header: 'filter reason',
      render: (r) => (
        <span className="font-mono" style={{ color: C.broken }} title={meaningOf(r.filter)}>
          {r.filter}
        </span>
      ),
    },
    {
      key: 'gt',
      header: 'GT',
      render: (r) => (
        <span className="font-mono" style={{ color: r.is_het ? C.decision : C.inkDim }} title={r.is_het ? 'heterozygous — one broken copy, the shape a hidden second allele takes' : 'not heterozygous'}>
          {r.gt}
        </span>
      ),
    },
    { key: 'dp', header: 'DP', align: 'right', render: (r) => int(r.dp) },
    {
      key: 'reads',
      header: 'alt / ref reads',
      align: 'right',
      render: (r) => (r.ad_alt === null ? absent('multi-allelic: no single alternate') : `${int(r.ad_alt)} / ${int(r.ad_ref)}`),
      sortValue: (r) => r.ad_alt,
    },
    {
      key: 'vaf',
      header: 'VAF',
      align: 'right',
      render: (r) =>
        r.vaf === null ? (
          <span className="text-zinc-600" title="multi-allelic record: no single alternate owns the reads">
            n/a
          </span>
        ) : (
          dec(r.vaf, 3)
        ),
    },
    {
      key: 'consequence',
      header: 'consequence',
      render: (r) =>
        r.consequence === null ? (
          absent('VEP was never asked about this allele')
        ) : (
          <span style={{ color: impactColor(r.impact ?? '') }}>{r.consequence}</span>
        ),
    },
    {
      key: 'gnomad_af',
      header: 'gnomAD AF',
      align: 'right',
      render: (r) =>
        !r.annotated ? absent('VEP was never asked about this allele') : r.gnomad_af === null ? (
          <span style={{ color: C.decision }} title="looked up and absent from gnomAD — novel, not frequency zero">
            novel
          </span>
        ) : (
          dec(r.gnomad_af, 4)
        ),
    },
  ];

  return (
    <Exhibit
      title="The suppressed records themselves"
      controls={
        <Select
          value={chosen}
          options={options.length > 0 ? options : [{ value: chosen, label: chosen }]}
          onChange={onGene}
          label="gene"
        />
      }
      legend={
        <>
          One row per record the caller flagged inside the selected gene — the whole search space, nothing
          aggregated away. <span className="font-mono" style={{ color: C.broken }}>Red filter reason</span> is
          the threshold the record failed, verbatim; hover it for what the label means.{' '}
          <span className="font-mono" style={{ color: C.decision }}>Yellow GT</span> marks a heterozygous call —
          the configuration a hidden second allele would have. Consequence is coloured by VEP severity:{' '}
          <Chip color={C.broken}>HIGH</Chip> truncates the protein, <Chip color={C.decision}>MODERATE</Chip>{' '}
          swaps an amino acid, <Chip color={C.machinery}>LOW / MODIFIER</Chip> is silent or non-coding.{' '}
          <span className="text-zinc-600">Grey &ldquo;not annotated&rdquo;</span> means VEP was never asked
          about the allele — absent, never &ldquo;looked up and harmless&rdquo;. Sort any column; the filter box
          matches across every visible cell.
        </>
      }
      reading="Read down the gnomAD AF column first. A suppressed call that is common in the healthy population is a mapping artefact in a known-messy region, not a candidate — that is what every row in this panel turns out to be. The row worth wanting here is the opposite: rare or novel, heterozygous, protein-altering, and flagged. This panel has none, and that absence is a result: no second allele is hiding behind a FILTER in these eight genes, so a missing one has to come from re-calling the reads."
      source={source}
      cachedAt={cachedAt}
      origin={origin}
      // No `data`: every row carries a real patient position, and the export is a channel.
    >
      <DataTable
        rows={rows}
        columns={columns}
        rowKey={(r, i) => `${r.gene}-${r.pos}-${r.alt}-${i}`}
        filterable
        filterPlaceholder="match a reason, a consequence, a genotype…"
        empty={`${chosen} has no suppressed records — every call in it passed the caller's filters`}
      />
    </Exhibit>
  );
}
