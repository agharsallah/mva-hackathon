import type { Origin } from '../../../api/client';
import type { Step4Payload } from '../../../api/types';
import { Section } from '../../../components/Controls';
import { Exhibit } from '../../../components/Exhibit';
import { ratio } from './metrics';

/** The props every step-4 section takes: the payload, and where it came from. */
export interface SectionProps {
  data: Step4Payload;
  source?: string;
  origin?: Origin;
}

/**
 * The genes no symptom ranker can score at all, and where they landed anyway.
 *
 * 73.6% of protein-coding genes carry no HPO curation, so this is the population step 4
 * exists to reach. The network column says whether a gene entered through STRING proximity
 * — the lane built for exactly this population, which in this run fired for none of them.
 */
export function Uncurated({ data, source, origin }: SectionProps) {
  const uncuratedLeader = data.uncurated[0];

  return (
    <Section title="The genes no symptom ranker can score">
      <Exhibit
        title="Uncurated genes, and where they landed anyway"
        legend={
          <>
            73.6% of protein-coding genes carry no HPO curation, so the symptom ranker returns
            nothing for them. The <strong>network</strong> column says whether a gene entered
            through STRING proximity to the top-ranked genes — the lane built for exactly this
            population.{' '}
            {uncuratedLeader
              ? `The highest-placed one is ${uncuratedLeader.gene}, at rank ${uncuratedLeader.gene_rank} overall.`
              : ''}
          </>
        }
        source={source}
        origin={origin}
        data={data.uncurated}
      >
        <div className="max-h-96 overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-chrome-400">
              <tr className="border-b border-chrome-800">
                <th className="py-1 pr-3 text-right">overall rank</th>
                <th className="py-1 pr-3">gene</th>
                <th className="py-1 pr-3">shape</th>
                <th className="py-1 pr-3 text-right">likelihood ratio</th>
                <th className="py-1 pr-3">network lane</th>
                <th className="py-1 pr-3">decoy</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {data.uncurated.map((row) => (
                <tr key={row.gene} className="border-b border-chrome-900/60">
                  <td className="py-1 pr-3 text-right text-chrome-400">{row.gene_rank}</td>
                  <td className="py-1 pr-3 font-medium">{row.gene}</td>
                  <td className="py-1 pr-3">{row.shape}</td>
                  <td className="py-1 pr-3 text-right">{ratio(row.combined_lr)}</td>
                  <td className="py-1 pr-3">{row.entered_by_network ? 'yes' : 'no'}</td>
                  <td className="py-1 pr-3">{row.is_decoy ? 'yes' : 'no'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Exhibit>
    </Section>
  );
}
