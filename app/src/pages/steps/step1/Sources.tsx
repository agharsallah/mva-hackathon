import type { Step1Payload } from '../../../api/types';
import { Section } from '../../../components/Controls';
import { Chip, Exhibit } from '../../../components/Exhibit';
import { C } from '../../../lib/palette';

/** The envelope fields every Exhibit on the page stamps its provenance line from. */
interface Envelope {
  data?: { source: string; cachedAt: string | null; origin: 'api' | 'fixture' };
}

/**
 * Both of the case's inputs, named beside the step's own numbers.
 *
 * The standing rule is that every result states the sources it came from. Step 1 has two —
 * the clinic's eight ontology codes and three public reference files — and the receipt for
 * each public one is the sha256 of the exact bytes that were read, so a re-run on a newer
 * HPO release is visible as a changed digest rather than as a silently different curve.
 */
export function Sources({ payload: data, query: q }: { payload: Step1Payload; query: Envelope }) {
  return (
    <Section title="What this was built from">
      <Exhibit
        title="Both sources, named, with the receipts"
        legend={
          <>
            <Chip color={C.raw}>purple</Chip> = the clinical input ·{' '}
            <Chip color={C.machinery}>blue</Chip> = the public reference files, each with the sha256
            of the exact bytes that were read.
          </>
        }
        reading={
          <>
            {data.provenance.genomic_data_read ??
              'No genomic data of this child was read at this step.'}
          </>
        }
        source={q.data?.source}
        origin={q.data?.origin}
        data={data.provenance}
      >
        <div className="space-y-3 text-sm">
          <div className="border-l-2 border-raw-500 py-1 pl-3">
            <div className="text-xs text-chrome-400">clinical input</div>
            <div>
              <code>{data.provenance.clinical_source ?? '—'}</code>
            </div>
            <div className="text-xs text-chrome-400">
              {Object.entries(data.provenance.clinical_term_counts)
                .map(([name, n]) => `${name}: ${n} terms`)
                .join(' · ')}
            </div>
          </div>
          {data.provenance.inputs.map((row) => (
            <div key={row.name} className="border-l-2 border-machinery-500 py-1 pl-3">
              <div className="text-xs text-chrome-400">{row.role}</div>
              <div>
                <code>{row.name}</code>
              </div>
              <div className="text-micro break-all text-chrome-500">
                sha256 {row.sha256.slice(0, 16)}…
              </div>
            </div>
          ))}
          <div className="text-xs text-chrome-400">
            HPO release <code>{data.provenance.hpo_release ?? '—'}</code> · built by{' '}
            <code>{data.provenance.built_by ?? '—'}</code> at{' '}
            <code>{data.provenance.code_version ?? '—'}</code>
          </div>
        </div>
      </Exhibit>
    </Section>
  );
}
