import { useGenotypes } from '../../api/hooks';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot } from '../../components/Plot';
import { baseLayout } from '../../components/plotLayout';
import { Loaded } from '../../components/QueryState';
import { int, pct } from '../../lib/format';
import { C } from '../../lib/palette';

/**
 * Genotype composition. The point of the figure is the 1/2 slice: those sites carry two
 * *different* non-reference alleles, which is a compound heterozygote established by the
 * genotype field alone — no phasing, no parents, no inference.
 */
export function GenotypeDonut() {
  const q = useGenotypes();
  const COLOR: Record<string, string> = { '0/1': C.machinery, '1/1': C.raw, '1/2': C.good };

  return (
    <Exhibit
      title="Genotype composition"
      legend={
        <>
          <Chip color={C.machinery}>0/1 heterozygous (one reference copy, one variant copy)</Chip> ·{' '}
          <Chip color={C.raw}>1/1 homozygous variant (both copies changed)</Chip> ·{' '}
          <Chip color={C.good}>
            1/2 two different variant alleles — a compound heterozygote proven by genotype
          </Chip>
          . Slice angle is the share of called sites.
        </>
      }
      reading={
        <>
          The 1/2 slice is the search space this case is built on: 66,860 sites where the caller
          itself says the two copies carry different changes.
        </>
      }
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={320}>
        {(rows) => {
          const total = rows.reduce((a, r) => a + r.count, 0);
          const multi = rows.find((r) => r.label === '1/2');
          return (
            <div className="grid gap-4 lg:grid-cols-[1fr_240px]">
              <Plot
                height={300}
                data={[
                  {
                    type: 'pie',
                    hole: 0.58,
                    labels: rows.map((r) => r.label),
                    values: rows.map((r) => r.count),
                    marker: {
                      colors: rows.map((r) => COLOR[r.label] ?? C.absent),
                      line: { color: C.paper, width: 2 },
                    },
                    pull: rows.map((r) => (r.label === '1/2' ? 0.08 : 0)),
                    textinfo: 'label+percent',
                    textfont: { color: C.paper, size: 12 },
                    hovertemplate: '%{label}: %{value:,} sites (%{percent})<extra></extra>',
                    sort: false,
                  },
                ]}
                layout={baseLayout({
                  margin: { l: 10, r: 10, t: 10, b: 10 },
                  showlegend: false,
                  annotations: [
                    {
                      text: `${(total / 1e6).toFixed(2)} M<br><span style="font-size:10px">called sites</span>`,
                      showarrow: false,
                      font: { color: C.ink, size: 16 },
                      x: 0.5,
                      y: 0.5,
                    },
                  ],
                })}
              />
              <div className="space-y-2 self-center">
                {rows.map((r) => (
                  <div key={r.label} className="rounded-card border border-line bg-panel p-3">
                    <div className="flex items-center justify-between">
                      <span
                        className="font-mono text-sm"
                        style={{ color: COLOR[r.label] ?? C.absent }}
                      >
                        {r.label}
                      </span>
                      <span className="font-mono text-xs text-chrome-400">
                        {pct((r.count / total) * 100)}
                      </span>
                    </div>
                    <div className="mt-0.5 font-mono text-xs text-chrome-300">{int(r.count)}</div>
                  </div>
                ))}
                {multi && (
                  <p className="text-micro leading-relaxed text-good-300/90">
                    1/2 = compound het by genotype. {int(multi.count)} sites need no parental data
                    to establish that both copies are altered.
                  </p>
                )}
              </div>
            </div>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
