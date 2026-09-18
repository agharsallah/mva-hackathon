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
 * What the DNA alone would have nominated — the control, not a null.
 *
 * The leader of the combined ranking is not the leader of this one, which is the honest
 * reading of the result: it is supported by the symptom route and the DNA route together,
 * not by a genome-wide scan that found the gene on its own.
 */
export function Ablation({ data, source, origin }: SectionProps) {
  return (
    <Section title="How much of this is the symptoms?">
      <Exhibit
        title="What the DNA alone would have nominated"
        legend={
          <>
            The same table with the phenotype lane set to 1 for every gene. Not a null — a control.
            The leader of the combined ranking is not the leader of this one, which is the honest
            reading of the result: it is supported by the two routes together, not by a genome-wide
            scan that found the gene on its own.
          </>
        }
        source={source}
        origin={origin}
        data={data.nulls_summary.genotype_only_top}
      >
        <table className="w-full text-sm">
          <thead className="text-xs text-chrome-400">
            <tr className="border-b border-chrome-800">
              <th className="py-1 pr-3 text-right">#</th>
              <th className="py-1 pr-3">gene</th>
              <th className="py-1 pr-3">shape</th>
              <th className="py-1 pr-3 text-right">DNA alone</th>
              <th className="py-1 pr-3 text-right">both routes</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {(data.nulls_summary.genotype_only_top ?? []).slice(0, 10).map((row, i) => (
              <tr key={row.gene} className="border-b border-chrome-900/60">
                <td className="py-1 pr-3 text-right text-chrome-400">{i + 1}</td>
                <td className="py-1 pr-3 font-medium">{row.gene}</td>
                <td className="py-1 pr-3">{row.shape}</td>
                <td className="py-1 pr-3 text-right">{ratio(row.lr)}</td>
                <td className="py-1 pr-3 text-right">
                  {ratio(data.leaders.find((leader) => leader.gene === row.gene)?.combined_lr)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Exhibit>
    </Section>
  );
}
