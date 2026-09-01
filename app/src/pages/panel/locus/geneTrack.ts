import type { GeneStructure } from '../../../api/types';
import type { Trace } from '../../../components/Plot';
import { C } from '../../../lib/palette';

/**
 * The gene-structure track: exon boxes, an intron line, and a strand arrow.
 *
 * Kept out of `LocusExplorer.tsx` because it is pure data shaping — given a
 * `GeneStructure` it returns Plotly traces on `yaxis3`, sharing the locus x axis. That
 * makes the track testable by reading it, and keeps the page component about layout.
 *
 * Software-engineer reading of the biology: a gene is a byte range on the chromosome,
 * but only some of the bytes survive to the output. **Exons** are the kept slices,
 * **introns** the discarded ones between them, and the **strand** is which direction the
 * range is read in — the minus strand is read right-to-left on the coordinate axis, so
 * exon 1 sits at the *high* coordinate there.
 */

/** Plotly axis ids the track draws on. */
export const GENE_AXIS = 'y3';

export interface GeneTrackParts {
  traces: Trace[];
  /** Layout annotations (the TSS label and its arrow). Merge into `layout.annotations`. */
  annotations: Record<string, unknown>[];
}

export function geneTrack(structure: GeneStructure): GeneTrackParts {
  const exons = structure.exons ?? [];
  const total = exons.length;
  const forward = structure.strand >= 0;
  // Transcription starts at the first exon in *transcript* order, which the API already
  // numbered — so this works on both strands without a second orientation rule here.
  const first = exons[0];
  const tss = first ? (forward ? first.start : first.end) : structure.start;

  const traces: Trace[] = [
    {
      type: 'scatter',
      mode: 'lines',
      name: 'intron',
      legendgroup: 'gene',
      showlegend: false,
      hoverinfo: 'skip',
      xaxis: 'x',
      yaxis: GENE_AXIS,
      x: [structure.start, structure.end],
      y: [0, 0],
      line: { color: C.machineryDim, width: 2 },
    },
  ];

  if (total > 0) {
    traces.push({
      type: 'bar',
      orientation: 'h',
      name: 'exon',
      legendgroup: 'gene',
      showlegend: false,
      xaxis: 'x',
      yaxis: GENE_AXIS,
      base: exons.map((e) => e.start),
      x: exons.map((e) => Math.max(e.end - e.start + 1, 1)),
      y: exons.map(() => 0),
      width: 1.1,
      marker: { color: C.machinery, line: { color: C.paper, width: 0.5 } },
      customdata: exons.map((e) => [e.n, total, e.end - e.start + 1, e.start, e.end]),
      hovertemplate:
        'exon %{customdata[0]}/%{customdata[1]}<br>' +
        '%{customdata[3]:,}–%{customdata[4]:,}<br>%{customdata[2]:,} bp<extra></extra>',
    });
  }

  return {
    traces,
    annotations: [
      {
        x: tss,
        y: 0,
        xref: 'x',
        yref: GENE_AXIS,
        ax: forward ? -34 : 34,
        ay: 0,
        axref: 'pixel',
        ayref: 'pixel',
        text: forward ? 'TSS →' : '← TSS',
        showarrow: true,
        arrowhead: 3,
        arrowsize: 1,
        arrowwidth: 1.2,
        arrowcolor: C.ink,
        font: { color: C.ink, size: 10 },
        xanchor: forward ? 'right' : 'left',
      },
    ],
  };
}

/** The y-axis object for the gene track: a thin lane with no ticks of its own. */
export function geneAxis(domain: [number, number]): Record<string, unknown> {
  return {
    domain,
    range: [-1, 1],
    showgrid: false,
    zeroline: false,
    showticklabels: false,
    title: { text: 'gene', font: { color: C.inkDim, size: 12 } },
    fixedrange: true,
  };
}
