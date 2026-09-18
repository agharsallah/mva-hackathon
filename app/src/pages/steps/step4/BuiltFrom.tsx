import type { Origin } from '../../../api/client';
import type { Step4Payload } from '../../../api/types';
import { Section } from '../../../components/Controls';
import { Exhibit } from '../../../components/Exhibit';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';
import { binLabel, log10, ratio, share } from './metrics';

/** The props every step-4 section takes: the payload, and where it came from. */
export interface SectionProps {
  data: Step4Payload;
  source?: string;
  origin?: Origin;
}

/**
 * What the ordering was built from: the measured value of a symptom rank, and which
 * calibrated tool actually spoke for each consequence class.
 *
 * A lane with a published calibration that answers for one allele in fifty contributed
 * almost nothing to this ordering, which is a fact about this run rather than about the tool.
 */
export function BuiltFrom({ data, source, origin }: SectionProps) {
  const lanesSilent = data.lanes.find((row) => row.scored_by === 'no lane spoke');

  return (
    <Section title="What the ordering was built from">
      {(data.ranking.phenotype_bins ?? []).length > 0 && (
        <Exhibit
          title="What a symptom rank is worth, measured rather than assumed"
          legend={
            <>
              <strong style={{ color: C.good }}>green</strong> = the rank argues for the gene ·{' '}
              <strong style={{ color: C.broken }}>red</strong> = against it. Each bar is the
              fraction of held-out causal genes that landed in that band of ranks, divided by the
              fraction of all genes the band contains. A gene nobody has curated is worth{' '}
              {ratio(data.ranking.phenotype_unranked_lr)}× — below 1, never zero, which is why{' '}
              {share((data.ranking.genes_uncurated_scored ?? 0) / (data.ranking.genes_scored || 1))}{' '}
              of the genes scored here are ordered rather than discarded.
            </>
          }
          source={source}
          origin={origin}
          data={data.ranking.phenotype_bins}
        >
          <Plot
            height={320}
            data={[
              {
                type: 'bar',
                x: (data.ranking.phenotype_bins ?? []).map(binLabel),
                y: (data.ranking.phenotype_bins ?? []).map((bin) => log10(bin.likelihood_ratio)),
                text: (data.ranking.phenotype_bins ?? []).map(
                  (bin) => `${ratio(bin.likelihood_ratio)}×`,
                ),
                textposition: 'outside',
                marker: {
                  color: (data.ranking.phenotype_bins ?? []).map((bin) =>
                    bin.likelihood_ratio > 1 ? C.good : C.broken,
                  ),
                },
              },
            ]}
            layout={{
              xaxis: { title: 'rank the symptom ranker gave the gene' },
              yaxis: { title: 'log₁₀ likelihood ratio' },
              showlegend: false,
            }}
          />
        </Exhibit>
      )}

      {data.lanes.length > 0 && (
        <Exhibit
          title="Which tool actually spoke, per consequence class"
          legend={
            <>
              One calibrated tool per consequence class, chosen before any score was seen. This is
              the coverage that resulted.{' '}
              {lanesSilent
                ? `${share(lanesSilent.percent / 100)} of allele slots had no lane with anything to say.`
                : ''}{' '}
              CADD and LOFTEE are absent entirely: Ensembl&rsquo;s REST endpoint serves neither
              plugin, and the absence is recorded rather than worked around.
            </>
          }
          source={source}
          origin={origin}
          data={data.lanes}
        >
          <Plot
            height={420}
            data={[
              {
                type: 'bar',
                orientation: 'h',
                x: [...data.lanes].reverse().map((row) => row.allele_slots),
                y: [...data.lanes].reverse().map((row) => `${row.lane_class} → ${row.scored_by}`),
                text: [...data.lanes].reverse().map((row) => `${row.percent}%`),
                textposition: 'outside',
                marker: { color: C.machinery },
              },
            ]}
            layout={{
              xaxis: { title: 'allele slots the lane spoke for' },
              margin: { l: 220, r: 80 },
              showlegend: false,
            }}
          />
        </Exhibit>
      )}
    </Section>
  );
}
