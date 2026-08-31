import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout, type Trace } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { useGeneStructure } from '../../api/hooks';
import type { GeneCandidate, GeneStructure, ProteinDomain } from '../../api/types';
import { C, impactColor } from '../../lib/palette';
import { int } from '../../lib/format';

/** Stem heights, cycled so neighbouring labels do not sit on the same line. */
const STEMS = [1.0, 1.45, 1.2, 1.7];

/**
 * Protein-domain lollipop: where each protein-altering allele lands on the folded protein.
 *
 * The locus tracks answer "where in the *gene*". This answers "where in the *protein*",
 * which is the question that decides whether an allele matters. A protein is a chain of
 * amino acids that folds into a few semi-independent working parts — **domains** — and a
 * change inside the catalytic domain of an enzyme is a different event from the same
 * change in a linker between domains.
 *
 * Two axes' worth of honesty are enforced here: an allele VEP could not place in
 * amino-acid space is **listed with its reason** next to the plot rather than dropped,
 * and no genomic coordinate is drawn at all — the payload does not carry one.
 */
export function DomainLollipop({ gene }: { gene: string }) {
  const q = useGeneStructure(gene);

  return (
    <Exhibit
      title={`Protein domains — where ${gene}'s protein-altering alleles land`}
      legend={
        <>
          x = position along the protein, in amino acids (aa), 1 → the C-terminus. The grey bar is the whole
          protein chain. <Chip color={C.machinery}>Blue bars</Chip> are annotated domains, one lane per source
          database (Pfam, SMART, PROSITE, Gene3D, SUPERFAMILY, CDD, PRINTS) — several lanes describing the same
          region is agreement, not duplication. Lollipops are this proband's protein-altering alleles:{' '}
          <Chip color={C.broken}>HIGH</Chip> truncates or destroys the protein,{' '}
          <Chip color={C.decision}>MODERATE</Chip> swaps one amino acid,{' '}
          <Chip color={C.machinery}>LOW/MODIFIER</Chip> is unlikely to matter. A hollow head means the allele is
          <em> not</em> rare in gnomAD, so it is a poor recessive candidate. Alleles VEP could not place are
          listed to the right with the reason.
        </>
      }
      reading="A HIGH-impact lollipop landing inside or upstream of a functional domain is the shape a damaging recessive allele has: it removes the part of the protein that does the work."
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={340}>
        {(structure) => <Lollipop structure={structure} />}
      </Loaded>
    </Exhibit>
  );
}

function Lollipop({ structure }: { structure: GeneStructure }) {
  const length = structure.protein_length;
  const placed = structure.candidates.filter((c) => c.protein_pos !== null);
  const unplaced = structure.candidates.filter((c) => c.protein_pos === null);

  if (!length) {
    return (
      <p className="p-6 text-center text-sm text-zinc-500">
        {structure.gene} has no protein on its canonical transcript ({structure.transcript ?? 'unknown'}), so
        there is no amino-acid axis to draw.
      </p>
    );
  }

  const lanes = laneOf(structure.domains);
  const depth = lanes.size || 1;
  const top = 2.2;

  return (
    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
      <Plot
        height={300}
        data={[...domainTraces(structure.domains, lanes), ...stemTraces(placed), backbone(length, depth)]}
        layout={baseLayout({
          margin: { l: 128, r: 16, t: 26, b: 46 },
          showlegend: false,
          bargap: 0.35,
          xaxis: {
            title: { text: `amino-acid position (1 – ${int(length)} aa)`, font: { color: C.inkDim, size: 12 } },
            range: [0, length + 1],
            gridcolor: C.grid,
            tickfont: { color: C.inkDim, size: 10 },
          },
          yaxis: {
            range: [-(depth + 0.6), top],
            zeroline: false,
            showgrid: false,
            tickfont: { color: C.inkDim, size: 10 },
            tickvals: [...lanes.values()].map((lane) => -lane - 1),
            ticktext: [...lanes.keys()],
            fixedrange: true,
          },
        })}
      />
      <Unplaceable rows={unplaced} placed={placed.length} transcript={structure.transcript} />
    </div>
  );
}

/** Source database → lane index. One lane per source, in first-appearance order. */
function laneOf(domains: ProteinDomain[]): Map<string, number> {
  const lanes = new Map<string, number>();
  for (const d of domains) if (!lanes.has(d.source)) lanes.set(d.source, lanes.size);
  return lanes;
}

function backbone(length: number, depth: number): Trace {
  return {
    type: 'scatter',
    mode: 'lines',
    x: [1, length],
    y: [0, 0],
    line: { color: C.absent, width: 7 },
    hovertemplate: `the protein chain, 1–${length} aa<extra></extra>`,
    showlegend: false,
    // Drawn last so it sits over the domain lanes' gridless background.
    yaxis: 'y',
    xaxis: 'x',
    customdata: [depth],
  };
}

function domainTraces(domains: ProteinDomain[], lanes: Map<string, number>): Trace[] {
  if (domains.length === 0) return [];
  return [
    {
      type: 'bar',
      orientation: 'h',
      base: domains.map((d) => d.start_aa),
      x: domains.map((d) => Math.max(d.end_aa - d.start_aa + 1, 1)),
      y: domains.map((d) => -(lanes.get(d.source) ?? 0) - 1),
      width: 0.62,
      marker: { color: C.machinery, line: { color: C.paper, width: 0.5 } },
      text: domains.map((d) => d.name),
      textposition: 'inside',
      insidetextanchor: 'middle',
      textfont: { color: C.paper, size: 9 },
      cliponaxis: false,
      customdata: domains.map((d) => [d.source, d.name, d.accession ?? '—', d.start_aa, d.end_aa, d.interpro ?? '—']),
      hovertemplate:
        '<b>%{customdata[1]}</b><br>%{customdata[0]} %{customdata[2]}<br>' +
        'aa %{customdata[3]}–%{customdata[4]}<br>InterPro %{customdata[5]}<extra></extra>',
      showlegend: false,
    },
  ];
}

function stemTraces(placed: GeneCandidate[]): Trace[] {
  if (placed.length === 0) return [];
  const height = (i: number) => STEMS[i % STEMS.length];
  const x: (number | null)[] = [];
  const y: (number | null)[] = [];
  placed.forEach((c, i) => {
    x.push(c.protein_pos, c.protein_pos, null);
    y.push(0, height(i), null);
  });

  return [
    {
      type: 'scatter',
      mode: 'lines',
      x,
      y,
      line: { color: C.inkDim, width: 1 },
      hoverinfo: 'skip',
      showlegend: false,
    },
    {
      type: 'scatter',
      mode: 'markers+text',
      x: placed.map((c) => c.protein_pos),
      y: placed.map((_, i) => height(i)),
      marker: {
        size: 15,
        symbol: 'circle',
        // Hollow = common in gnomAD, i.e. a poor recessive candidate. The colour still
        // carries the severity, so the two facts never collapse into one.
        color: placed.map((c) => (c.rare ? impactColor(c.impact ?? '') : C.paper)),
        line: { color: placed.map((c) => impactColor(c.impact ?? '')), width: 2 },
      },
      text: placed.map((c) => c.label),
      textposition: 'top center',
      textfont: { color: C.ink, size: 10 },
      customdata: placed.map((c) => [
        c.consequence,
        c.impact ?? 'unknown',
        c.rare ? 'rare in gnomAD' : 'not rare in gnomAD',
        c.gt ?? '—',
        c.filter ?? '—',
        c.clin_sig ?? 'no ClinVar entry',
      ]),
      hovertemplate:
        'aa %{x}<br>%{customdata[0]} · %{customdata[1]}<br>%{customdata[2]}<br>' +
        'genotype %{customdata[3]} · %{customdata[4]}<br>ClinVar %{customdata[5]}<extra></extra>',
      showlegend: false,
    },
  ];
}

function Unplaceable({
  rows,
  placed,
  transcript,
}: {
  rows: GeneCandidate[];
  placed: number;
  transcript: string | null;
}) {
  return (
    <aside className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-[11px] leading-relaxed">
      <p className="mb-2 font-semibold text-zinc-300">
        {int(placed)} placed · {int(rows.length)} not placeable
      </p>
      <p className="mb-2 text-zinc-500">
        Domains and positions are both on <span className="font-mono">{transcript ?? 'the canonical transcript'}</span>.
      </p>
      {rows.length === 0 ? (
        <p className="text-zinc-500">
          {placed === 0
            ? 'This gene has no protein-altering allele in the callset, so there is nothing to place.'
            : 'Every protein-altering allele resolved to an amino-acid position.'}
        </p>
      ) : (
        <ul className="space-y-2">
          {rows.map((c, i) => (
            <li key={`${c.label}-${i}`} className="border-l-2 pl-2" style={{ borderColor: impactColor(c.impact ?? '') }}>
              <span className="font-mono text-zinc-300">{c.label}</span>
              <span className="ml-1 text-zinc-500">({c.impact ?? 'unknown impact'})</span>
              <p className="text-zinc-500">{c.reason}</p>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
