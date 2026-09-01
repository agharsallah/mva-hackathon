import { Chip, Exhibit } from '../../components/Exhibit';
import { Plot, baseLayout } from '../../components/Plot';
import { Loaded } from '../../components/QueryState';
import { Select } from '../../components/Controls';
import { useReadPartitions } from '../../api/hooks';
import { C } from '../../lib/palette';
import { dec, int } from '../../lib/format';
import { useUrlEnum } from '../../lib/urlstate';

type Metric = 'gib' | 'reads' | 'shards';

const METRICS: { value: Metric; label: string }[] = [
  { value: 'gib', label: 'stored GiB' },
  { value: 'reads', label: 'reads' },
  { value: 'shards', label: 'shard files' },
];

/**
 * The read store's shape. The billion delivered reads were converted from gzipped FASTQ
 * (a line-oriented text stream you can only read start to finish) into partitioned,
 * sharded parquet (a columnar format where a query can touch just the columns and shards
 * it needs). This treemap is what that store looks like: 8 partitions, 272 shards.
 */
export function StoreShape() {
  // `?store.metric=reads`. See lib/urlstate.
  const [metric, setMetric] = useUrlEnum<Metric>('store.metric', 'gib', METRICS.map((m) => m.value));
  const q = useReadPartitions();
  return (
    <Exhibit
      title="Read store shape — 8 partitions, 272 shards"
      controls={<Select value={metric} options={METRICS} onChange={setMetric} label="size by" />}
      legend={
        <>
          Treemap: each tile is one partition (lane × read direction), area ∝ the selected metric.{' '}
          <Chip color={C.raw}>R1 partitions</Chip> · <Chip color={C.machinery}>R2 partitions</Chip>. A shard is
          one parquet file; sharding is what lets a query read a slice of the store instead of all of it.
        </>
      }
      reading="Every partition is the same size — 34 shards each, evenly split. That uniformity is what makes a k-mer probe run predictable: no partition is a straggler."
      data={q.data?.data}
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={380}>
        {(rows) => {
          const value = (r: (typeof rows)[number]) =>
            metric === 'gib' ? r.gib : metric === 'reads' ? r.reads : r.shards;
          const labels = rows.map((r) => `L${r.lane} R${r.read_num}`);
          const totalGib = rows.reduce((a, r) => a + r.gib, 0);
          const totalShards = rows.reduce((a, r) => a + r.shards, 0);
          const totalReads = rows.reduce((a, r) => a + r.reads, 0);
          return (
            <>
              <Plot
                height={340}
                data={[
                  {
                    type: 'treemap',
                    labels,
                    parents: labels.map(() => ''),
                    values: rows.map(value),
                    marker: {
                      colors: rows.map((r) => (r.read_num === 1 ? C.raw : C.machinery)),
                      line: { color: C.paper, width: 2 },
                    },
                    textinfo: 'label+value',
                    textfont: { color: '#f5f5f5', size: 12 },
                    customdata: rows.map((r) => [r.shards, r.reads, r.gib]),
                    hovertemplate:
                      '%{label}<br>%{customdata[0]} shards<br>%{customdata[1]:,} reads<br>' +
                      '%{customdata[2]:.2f} GiB<extra></extra>',
                  },
                ]}
                layout={baseLayout({ margin: { l: 4, r: 4, t: 4, b: 4 } })}
              />
              <div className="mt-2 grid gap-2 text-[11px] text-zinc-500 sm:grid-cols-3">
                <span>
                  {rows.length} partitions · <span className="font-mono text-zinc-300">{int(totalShards)}</span>{' '}
                  shards
                </span>
                <span>
                  <span className="font-mono text-zinc-300">{int(totalReads)}</span> reads stored
                </span>
                <span>
                  <span className="font-mono text-blue-400">{dec(totalGib, 2)} GiB</span> parquet vs 78.90 GiB
                  gzip source
                </span>
              </div>
            </>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
