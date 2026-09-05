import { usePhenotypeTerms } from '../../api/hooks';
import type { LineageSource, SubmissionIteration } from '../../api/types';
import { Badge } from '../../components/Badge';
import { EmptyState } from '../../components/EmptyState';
import { Chip, Exhibit } from '../../components/Exhibit';
import { Loaded } from '../../components/QueryState';
import { C } from '../../lib/palette';
import { cx, WELL } from '../../lib/ui';
import { shortSha } from './iteration';

/**
 * The standing rule of this project, drawn as a panel: **two** data sources were delivered,
 * and every conclusion has to be cross-referenced against both.
 *
 * Left is the clinical picture — eight HPO terms and nothing else, no age, sex, karyotype
 * or parental DNA. Right is the raw dataset — one gzipped VCF whose sha256 was recomputed
 * on arrival. A candidate that satisfies one and not the other is not an answer; the
 * decode table on this page only means anything because both halves agree on the gene.
 */
export function TwoInputs({
  iteration,
  source,
}: {
  iteration: SubmissionIteration;
  source?: string;
}) {
  const terms = usePhenotypeTerms();
  const raw = iteration.lineage.sources.filter((s) => s.kind === 'raw');
  const clinical = iteration.lineage.sources.filter((s) => s.kind === 'clinical');

  return (
    <Exhibit
      title="Two inputs, one answer"
      legend={
        <>
          <Chip color={C.raw}>purple = the raw input</Chip> — both panels, because both were
          delivered by the challenge and neither was computed here. The left panel is the{' '}
          <strong>clinical dataset</strong> (HPO terms), the right the <strong>raw dataset</strong>{' '}
          (the callset and its checksum). A <Badge tone="decision">parental</Badge> tag marks the
          one delivered term that describes the parents, not the child — it is excluded from the
          child&rsquo;s ranking. A <Badge tone="good">sha256 ✓</Badge> tag means the digest was
          recomputed locally and matched.
        </>
      }
      reading="Neither half alone identifies a gene. The symptoms rank thousands of genes without reading any DNA; the callset holds five million records with no clinical meaning. Every claim in this submission is the intersection, which is why both roots appear on the lineage graph below."
      source={source}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={cx(WELL, 'space-y-2')}>
          <div className="flex items-baseline justify-between gap-2">
            <h4 className="text-xs font-semibold text-chrome-200">
              Clinical dataset — the child&rsquo;s features
            </h4>
            <span className="font-mono text-micro text-chrome-600">HPO</span>
          </div>
          <Loaded query={terms} height={180} variant="table" rows={4}>
            {(data) => (
              <ul className="space-y-1">
                {data.terms.map((t) => (
                  <li key={t.hpo_id} className="flex flex-wrap items-baseline gap-2 text-xs">
                    <span className="font-mono text-chrome-500">{t.hpo_id}</span>
                    <span className="text-chrome-200">{t.label}</span>
                    {!t.proband && <Badge tone="decision">parental — not the child</Badge>}
                  </li>
                ))}
              </ul>
            )}
          </Loaded>
          {clinical.map((s) => (
            <SourceLine key={s.ref} source={s} />
          ))}
        </div>

        <div className={cx(WELL, 'space-y-2')}>
          <div className="flex items-baseline justify-between gap-2">
            <h4 className="text-xs font-semibold text-chrome-200">
              Raw dataset — the delivered callset
            </h4>
            <span className="font-mono text-micro text-chrome-600">VCF</span>
          </div>
          {raw.length === 0 ? (
            <EmptyState>
              No <span className="font-mono">raw</span> lineage root recorded for this iteration.
            </EmptyState>
          ) : (
            raw.map((s) => (
              <div key={s.ref} className="space-y-1">
                <div className="font-mono text-xs break-all text-chrome-100">{s.ref}</div>
                <div className="flex flex-wrap items-center gap-2 text-micro text-chrome-500">
                  <span className="font-mono">version {s.version || '—'}</span>
                  <Badge tone={s.sha256 ? 'good' : 'neutral'}>
                    sha256 {s.sha256 ? `${shortSha(s.sha256)} ✓` : 'not recorded'}
                  </Badge>
                </div>
                <p className="text-xs leading-relaxed text-chrome-400">{s.note}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </Exhibit>
  );
}

function SourceLine({ source }: { source: LineageSource }) {
  return (
    <div className="border-t border-line-soft pt-2 text-micro text-chrome-500">
      <span className="font-mono break-all text-chrome-400">{source.ref}</span>
      <span className="mx-1">·</span>
      <span className="font-mono">{source.version}</span>
      <span className="mx-1">·</span>
      <span className="font-mono" title={source.sha256}>
        sha256 {shortSha(source.sha256)}
      </span>
    </div>
  );
}
