import type { ZooModel } from '../../api/types/zoo';
import { Badge } from '../../components/Badge';
import { Select } from '../../components/Controls';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { C } from '../../lib/palette';
import { BOX, cx, WELL } from '../../lib/ui';
import { useZooModels, useZooReport } from './hooks';
import { Markdown } from './markdown';
import { resolveModelKey } from './route';

/**
 * One lane's report, rendered from the Markdown the API serves.
 *
 * The report is generated from stored JSON — sections 1–5 and 7 change only when a number
 * changes — with exactly one written section: the interpretation. The generator marks it in
 * the source with an `<!-- interpretation: … -->` comment, and this view keys off that
 * comment rather than off a section number, so a report template that renumbers its sections
 * still gets the mark in the right place. That distinction is the point: everything else on
 * this page is a measurement, and the one paragraph that is a human's reading of the
 * measurements says so on its face.
 */

/** The generator's own marker for the written section. */
const INTERPRETATION = /<!--\s*interpretation:([^>]*)-->/;

interface Part {
  heading: string;
  body: string;
  /** The marker's payload (`hand-written 2026-09-19 | llm:none`), when this is the written one. */
  written: string | null;
}

/** Split a report into its `## ` sections, flagging the one carrying the written marker. */
function sections(markdown: string): Part[] {
  const chunks = markdown.split(/\n(?=## )/);
  return chunks.map((chunk) => {
    const marker = INTERPRETATION.exec(chunk);
    const [first, ...rest] = chunk.split('\n');
    return {
      heading: first.startsWith('## ') ? first.slice(3).trim() : '',
      body: first.startsWith('## ') ? rest.join('\n') : chunk,
      written: marker ? marker[1].trim() : null,
    };
  });
}

/** The figure the report points at. The route names it; it does not serve its bytes. */
function Figure({ path, alt }: { path: string; alt: string }) {
  const name = path.split('/').pop() ?? path;
  return (
    <p className={cx(WELL, 'text-micro text-chrome-400')}>
      Figure <span className="text-chrome-200">{alt || name}</span> — <code>{path}</code>. The
      reports route names the figures a report references and does not serve their pixels, so the
      page cites the file rather than drawing a broken image.
    </p>
  );
}

export function ModelReport({
  modelKey,
  onModelKey,
}: {
  modelKey: string;
  onModelKey: (key: string) => void;
}) {
  const models = useZooModels();
  const roster: ZooModel[] = models.data?.data ?? [];
  const selected = resolveModelKey(modelKey, roster) ?? 'merged';
  const q = useZooReport(selected);
  const figures = q.data?.data.figures ?? [];

  const options = [
    { value: 'merged', label: 'merged — every lane' },
    ...roster.filter((m) => m.enabled).map((m) => ({ value: m.key, label: m.name })),
  ];

  return (
    <Exhibit
      title="The generated report"
      controls={
        <Select
          label="report"
          value={options.some((o) => o.value === selected) ? selected : 'merged'}
          options={options}
          onChange={(v) => onModelKey(String(v))}
        />
      }
      legend={
        <>
          The report exactly as the workflow wrote it to disk, rendered rather than quoted.{' '}
          <Chip color={C.machinery}>blue</Chip> = a section rendered from stored JSON: it changes
          only when a number changes · <Chip color={C.decision}>yellow</Chip> = the one{' '}
          <strong>written</strong> section, marked as such by the generator&rsquo;s own{' '}
          <code>interpretation</code> marker and never computed. A figure whose bytes the API did
          not serve is named and pathed instead of drawn.
        </>
      }
      reading={
        <>
          Reading the written section against the computed ones is the check that matters: every
          sentence in it names the section and row it rests on, so a claim with no section behind it
          is visible as one.
        </>
      }
      source={q.data?.source}
      cachedAt={q.data?.cachedAt}
      origin={q.data?.origin}
    >
      <Loaded query={q} height={520}>
        {(report) => (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-micro text-chrome-500">
              <Badge tone="machinery">{report.key}</Badge>
              {report.title && <span className="text-chrome-300">{report.title}</span>}
              {report.path && <code>{report.path}</code>}
              <span>
                {figures.length} figure{figures.length === 1 ? '' : 's'} referenced
              </span>
            </div>

            {sections(report.markdown).map((part, i) => (
              <section
                key={`${part.heading}-${i}`}
                className={cx(
                  'rounded-control border px-3 py-2',
                  part.written ? BOX.decision : 'border-line-soft bg-well',
                )}
              >
                {part.heading && (
                  <h4 className="mb-1 flex flex-wrap items-baseline gap-2 text-xs font-semibold text-chrome-100">
                    {part.heading}
                    {part.written && <Badge tone="decision">written, not computed</Badge>}
                  </h4>
                )}
                {part.written && (
                  <p className="mb-1 text-micro text-decision-300">
                    Generator marker: <code>{part.written}</code>
                  </p>
                )}
                <Markdown
                  markdown={part.body}
                  renderImage={(alt, src) => <Figure alt={alt} path={src} />}
                />
              </section>
            ))}
          </div>
        )}
      </Loaded>
    </Exhibit>
  );
}
