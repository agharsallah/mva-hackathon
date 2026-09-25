import { Badge } from '../../components/Badge';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { C } from '../../lib/palette';
import { BOX, cx } from '../../lib/ui';
import { headlineOf } from './headline';
import { useZooReport } from './hooks';
import { Markdown } from './markdown';
import { ReportFigure } from './ModelReport';

/**
 * What the iteration found, in one table — read from the merged report, never typed in.
 *
 * The same section heads `docs/iteration4/report.md`; every row there cites the methodology
 * entry its number is quoted from, and the page keeps those citations. A merged report without
 * a headline section (an earlier run, another case) says so instead of inventing one.
 */
export function ZooHeadline() {
  const q = useZooReport('merged');

  return (
    <Exhibit
      title="The headline"
      legend={
        <>
          The hand-written headline of the merged report, rendered from the report the API serves.{' '}
          <Chip color={C.decision}>yellow</Chip> = written, not computed: a person&rsquo;s summary
          of measured numbers, each row naming the entry it is quoted from.
        </>
      }
      reading={
        <>
          Each row is a claim with its entry beside it. The rest of this page is the evidence: the
          coverage table shows which lanes abstain on the case pair, the rank bars show where the
          consensus puts it, and the agreement matrix shows how alike the lanes are.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={320}>
        {(report) => {
          const headline = headlineOf(report.markdown);
          if (!headline)
            return (
              <p className="text-xs text-chrome-400">
                The merged report at <code>{report.path}</code> carries no headline section.
              </p>
            );
          return (
            <section className={cx('rounded-control border px-3 py-2', BOX.decision)}>
              <h4 className="mb-1 flex flex-wrap items-baseline gap-2 text-xs font-semibold text-chrome-100">
                {headline.heading}
                <Badge tone="decision">hand-written summary</Badge>
              </h4>
              <Markdown
                markdown={headline.body}
                renderImage={(alt, src) => <ReportFigure alt={alt} path={src} />}
              />
            </section>
          );
        }}
      </Loaded>
    </Exhibit>
  );
}
