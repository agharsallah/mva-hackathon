import { useQualityLevels } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { dec } from '../../lib/format';
import { C, SEVERITY_ORANGE } from '../../lib/palette';

/** Q-score bin → colour: the repo's red-to-green quality ramp. */
const LEVEL_COLOR: Record<number, string> = {
  2: C.broken,
  11: SEVERITY_ORANGE,
  25: C.decision,
  37: C.good,
};

const LEVEL_MEANING: Record<number, string> = {
  2: 'Q2 — no confidence at all (~63 % error); the instrument’s "discard this base" marker',
  11: 'Q11 — about 1 error in 12',
  25: 'Q25 — about 1 error in 316',
  37: 'Q37 — about 1 error in 5000; the good bin, where most bases land',
};

/**
 * The four-level binning, made visible.
 *
 * A phred score is nominally 0–41 per base, but NovaSeq instruments quantise it into a
 * handful of buckets to save storage. In this dataset the *only* values present are
 * {2, 11, 25, 37}. That is not a bug, but it does mean any downstream tool that treats
 * quality as continuous is reading four levels dressed up as a scale — worth knowing
 * before trusting a quality-weighted computation.
 */
export function QualityLevels() {
  const q = useQualityLevels();
  return (
    <Exhibit
      title="Base quality is only four values — the NovaSeq binning"
      legend={
        <>
          Stacked bars, one per partition, normalised to 100 %.{' '}
          <Chip color={LEVEL_COLOR[37]}>Q37</Chip> · <Chip color={LEVEL_COLOR[25]}>Q25</Chip> ·{' '}
          <Chip color={LEVEL_COLOR[11]}>Q11</Chip> · <Chip color={LEVEL_COLOR[2]}>Q2</Chip>. Green
          is good, red is a base the instrument itself disowns. No other phred value occurs anywhere
          in the store.
        </>
      }
      reading="About 93 % of all bases sit in the single Q37 bin. The R2 partitions carry a visibly larger low-quality share — the same degradation the per-cycle curves show, counted instead of plotted."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={360}>
        {(rows) => {
          const keys = [...new Set(rows.map((r) => `${r.lane}:${r.read_num}`))].sort();
          const labels = keys.map((k) => {
            const [l, r] = k.split(':');
            return `L${l} R${r}`;
          });
          const totals = keys.map((k) =>
            rows.filter((r) => `${r.lane}:${r.read_num}` === k).reduce((a, r) => a + r.count, 0),
          );
          const levels = [...new Set(rows.map((r) => r.phred))].sort((a, b) => b - a);
          const q30Share = (readNum: number) => {
            const sel = rows.filter((r) => r.read_num === readNum);
            const total = sel.reduce((a, r) => a + r.count, 0);
            const ok = sel.filter((r) => r.phred >= 30).reduce((a, r) => a + r.count, 0);
            return total ? (ok / total) * 100 : 0;
          };
          return (
            <>
              <Plot
                height={320}
                data={levels.map((phred) => ({
                  type: 'bar',
                  name: `Q${phred}`,
                  x: labels,
                  y: keys.map((k, i) => {
                    const row = rows.find(
                      (r) => `${r.lane}:${r.read_num}` === k && r.phred === phred,
                    );
                    return totals[i] ? ((row?.count ?? 0) / totals[i]) * 100 : 0;
                  }),
                  marker: { color: LEVEL_COLOR[phred] ?? C.absent, line: { width: 0 } },
                  hovertemplate: `Q${phred}<br>%{x}<br>%{y:.2f}% of bases<extra></extra>`,
                }))}
                layout={baseLayout({
                  margin: { l: 56, r: 16, t: 8, b: 40 },
                  barmode: 'stack',
                  bargap: 0.3,
                  xaxis: {
                    type: 'category',
                    gridcolor: 'rgba(0,0,0,0)',
                    tickfont: { color: C.inkDim, size: 11 },
                  },
                  yaxis: {
                    title: { text: '% of bases', font: { color: C.inkDim, size: 12 } },
                    gridcolor: C.grid,
                    tickfont: { color: C.inkDim, size: 11 },
                    range: [0, 100],
                  },
                  legend: { orientation: 'h', y: 1.14, x: 0, font: { color: C.inkDim, size: 11 } },
                })}
              />
              <div className="mt-2 space-y-1 text-micro text-chrome-400">
                <div className="flex flex-wrap gap-x-5">
                  <span>
                    Q30+ share R1{' '}
                    <span className="font-mono text-good-300">{dec(q30Share(1), 1)}%</span>
                  </span>
                  <span>
                    Q30+ share R2{' '}
                    <span className="font-mono text-decision-300">{dec(q30Share(2), 1)}%</span>
                  </span>
                  <span>
                    distinct phred values present{' '}
                    <span className="font-mono text-chrome-300">{levels.length}</span> (
                    {levels.join(', ')})
                  </span>
                </div>
                {levels.map((l) => (
                  <div key={l}>
                    <span className="font-mono" style={{ color: LEVEL_COLOR[l] ?? C.absent }}>
                      Q{l}
                    </span>{' '}
                    — {LEVEL_MEANING[l] ?? 'unlisted level'}
                  </div>
                ))}
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
