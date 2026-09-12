import type { Step1Payload } from '../../../api/types';
import { Plot } from '../../../components/Plot';
import { C } from '../../../lib/palette';

/**
 * What the target set is made of, and how many rows earned their place.
 *
 * Two of the tiers are a ranking cutoff — `core` is the top of the symptom score, `net` is
 * the rest of the window — and one is prior knowledge: `mechanism-term` genes were admitted
 * because the ontology annotates them under a chromosome-instability root, whatever they
 * scored. The distinction is drawn in colour because a rediscovery claim may only be made
 * on the rows that earned their rank.
 */
const TIER_COLOR: Record<string, string> = {
  core: C.good,
  net: C.machinery,
  'mechanism-term': C.decision,
  uncurated: C.absent,
};

export function Tiers({ payload }: { payload: Step1Payload }) {
  const rows = payload.tiers;
  return (
    <Plot
      height={260}
      data={[
        {
          type: 'bar',
          orientation: 'h',
          x: rows.map((r) => r.genes),
          y: rows.map((r) => r.tier),
          marker: { color: rows.map((r) => TIER_COLOR[r.tier] ?? C.machinery) },
          text: rows.map((r) => `${r.genes}`),
          textposition: 'auto',
          hovertemplate: '%{y}: %{x} genes<extra></extra>',
        },
      ]}
      layout={{
        xaxis: { title: 'genes' },
        yaxis: { automargin: true },
        annotations: [
          {
            xref: 'paper',
            yref: 'paper',
            x: 1,
            y: 1.12,
            xanchor: 'right',
            showarrow: false,
            font: { size: 11, color: C.decision },
            text:
              `${payload.set_sizes.earned_by_score ?? '—'} of ${payload.set_sizes.targets ?? '—'} earned their rank; ` +
              `${payload.set_sizes.by_mechanism_rule ?? '—'} entered by the mechanism rule alone`,
          },
        ],
      }}
    />
  );
}
