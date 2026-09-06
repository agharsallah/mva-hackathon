import type { MethodsFormAnswer, SubmissionIteration } from '../../api/types';
import { Chip, Exhibit } from '../../components/Exhibit';
import { C } from '../../lib/palette';
import { cx, WELL } from '../../lib/ui';
import { blobUrl } from './iteration';

/**
 * The prose half of the submission: the organisers' methods form, and the report.
 *
 * Both are long, and both are collapsed by default — a reader who wants to check a number
 * opens one row, not a wall of text. The report is shown as its own Markdown source rather
 * than rendered: it is what `tools/md_to_pdf.mjs` turns into the uploaded PDF, so the bytes
 * on this page and the bytes in the PDF are the same bytes, which is the point of showing
 * it at all. (The app has no Markdown renderer, and adding a dependency to pretty-print a
 * file nobody edits here would cost more than it is worth.)
 */
export function Paperwork({
  iteration,
  source,
}: {
  iteration: SubmissionIteration;
  source?: string;
}) {
  return (
    <Exhibit
      title="Methods form and report"
      legend={
        <>
          <Chip color={C.machinery}>blue = neutral machinery</Chip> — the row numbers are the
          organisers&rsquo; own template rows, so the answers can be checked against the spreadsheet
          they were filled into. Both sections are collapsed by default; nothing here is generated
          for this page, both are read verbatim from the iteration folder.
        </>
      }
      reading="The form is the only place the method is stated in the organisers' own vocabulary, and the report is the only place every number is joined to the run that produced it. They are on this page so that the dossier is complete without leaving the app."
      data={iteration.methods_form}
      source={source}
    >
      <div className="space-y-3">
        <details className={cx(WELL, 'group')}>
          <summary className="cursor-pointer text-xs font-semibold text-chrome-200 hover:text-chrome-50">
            Methods form — {iteration.methods_form.length} answers
          </summary>
          <dl className="mt-3 space-y-3">
            {iteration.methods_form.map((a: MethodsFormAnswer) => (
              <div key={a.row} className="grid gap-1 sm:grid-cols-[4rem_1fr]">
                <dt className="font-mono text-micro text-chrome-400">row {a.row}</dt>
                <dd className="max-w-[100ch] text-xs leading-relaxed text-chrome-300">
                  {a.answer}
                </dd>
              </div>
            ))}
          </dl>
        </details>

        <details className={cx(WELL, 'group')}>
          <summary className="cursor-pointer text-xs font-semibold text-chrome-200 hover:text-chrome-50">
            Report source — <span className="font-mono">{iteration.report.path}</span>
          </summary>
          <p className="mt-2 text-micro text-chrome-400">
            The Markdown the uploaded PDF was rendered from.{' '}
            <a
              href={blobUrl(iteration.report.path)}
              className="text-machinery-300 underline decoration-machinery-700 underline-offset-2 hover:text-machinery-200"
            >
              open on GitHub
            </a>
          </p>
          <pre className="mt-2 max-h-[28rem] overflow-auto rounded-control border border-line-soft bg-chrome-950/60 p-3 font-mono text-micro leading-relaxed whitespace-pre-wrap text-chrome-300">
            {iteration.report.markdown}
          </pre>
        </details>
      </div>
    </Exhibit>
  );
}
