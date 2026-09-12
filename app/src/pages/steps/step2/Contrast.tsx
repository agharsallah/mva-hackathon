import type { Step2Contrast } from '../../../api/types';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';

/**
 * The step's central finding, drawn twice on one axis.
 *
 * Same genes, same reads, same enumeration — only the filter differs. Without a rarity and
 * consequence filter the decoys score *higher* than the targets, because every person
 * carries about two heterozygous differences per gene and "two variants in one gene"
 * describes a genome rather than a patient. With the filter, and with every read-derived
 * allele scored rather than only the ones the delivered callset already reported, the two
 * sets come out level.
 *
 * Both bars are drawn at the same scale on purpose. The unfiltered pair is fifty times the
 * filtered one, and seeing that is the point: the filter is doing all of the work.
 */
export function Contrast({ rows }: { rows: Step2Contrast[] }) {
  const labels = rows.map((r) => r.filter);
  return (
    <Plot
      height={300}
      data={[
        {
          type: 'bar',
          name: 'target genes',
          x: labels,
          y: rows.map((r) => r.target_rate),
          marker: { color: C.good },
          text: rows.map((r) => `${r.target_biallelic}/${r.target_genes}`),
          textposition: 'outside',
          hovertemplate: '%{x}<br>targets %{text} = %{y:.4f}<extra></extra>',
        },
        {
          type: 'bar',
          name: 'decoy genes',
          x: labels,
          y: rows.map((r) => r.decoy_rate),
          marker: { color: C.broken },
          text: rows.map((r) => `${r.decoy_biallelic}/${r.decoy_genes}`),
          textposition: 'outside',
          hovertemplate: '%{x}<br>decoys %{text} = %{y:.4f}<extra></extra>',
        },
      ]}
      layout={{
        barmode: 'group',
        yaxis: { title: 'share of genes with a biallelic candidate', tickformat: '.0%' },
        legend: { orientation: 'h', y: 1.15 },
      }}
    />
  );
}
