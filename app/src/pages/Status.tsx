import { Link } from 'react-router-dom';

import { Explainer, Section } from '../components';
import { DependencyBoard } from './status/DependencyBoard';
import { OverallVerdict } from './status/OverallVerdict';
import { useRefreshRequested } from './status/useRefresh';

/**
 * Status — is anything broken, and if so, what do I run to fix it?
 *
 * Every other page assumes its data arrived. This one is about the plumbing underneath
 * all of them: the app talks to a Postgres database, an S3-shaped object store, a
 * columnar read-store on disk, a second internal service for raw reads, and Ensembl's
 * public REST API — any one of which can be down while the others are fine. A red dot
 * only tells a developer *that* something is broken; this page's job is to also say
 * *what* to run next, inline, on the card itself.
 */
export default function StatusPage() {
  const forced = useRefreshRequested();
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            This app is a thin read layer over five things that can each fail on their own. A{' '}
            <strong>Postgres warehouse</strong> (a relational database — the same kind of thing as
            MySQL) holds the ingested VCF rows and every computed table. A{' '}
            <strong>MinIO object store</strong> (a key→bytes store speaking the S3 protocol — think
            an on-prem stand-in for Amazon S3) holds the raw delivered files. A{' '}
            <strong>parquet read-store</strong> (a columnar file format — rows rewritten as columns
            on disk, the way a spreadsheet column scan beats a row scan) backs the Reads page's
            flowcell and quality charts. A separate <strong>raw-reads API</strong> process serves
            the k-mer probe console. And <strong>Ensembl REST</strong> is a public, third-party HTTP
            API this app calls for gene coordinates — the only dependency this app does not own or
            run. If any of these is down, this page names which one, what it costs, and the exact
            command to run.
          </>
        }
        terms={[
          {
            term: 'liveness check / probe',
            plain:
              'a request the server makes to a dependency right before answering — "can I actually reach Postgres right now", not "did it work once at startup"',
          },
          {
            term: 'internal / upstream / third-party / snapshot',
            plain:
              "four kinds of dependency: internal is ours and required; upstream is ours but optional (a feature-scoped service); third-party is someone else's live service (Ensembl); snapshot is ingested reference data with nothing to probe",
          },
          {
            term: 'degraded',
            plain: 'answering, but slowly or only partially — worse than up, not yet down',
          },
          {
            term: 'skipped ("not configured")',
            plain:
              'a dependency deliberately not wired up in this environment (e.g. no S3 credentials) — a choice, not a failure',
          },
          {
            term: 'remedy',
            plain:
              'the actionable text a down or degraded check carries: the shell commands a developer would run to fix it',
          },
          {
            term: 'latency',
            plain: 'how long the probe itself took to answer, in milliseconds',
          },
        ]}
        caveat="This page reads a health endpoint like any other — the states shown are whatever it reports at the moment you loaded the page, then re-checked every 10 minutes. Probing costs real round trips to Postgres, MinIO and Ensembl, so it is deliberately quiet; use Re-probe now when you have just restarted something. In fixture mode (no backend running) every state below is illustrative, not measured — the fixture's source string says so."
      />

      <div className="flex flex-wrap items-baseline justify-between gap-2 text-[11px] text-zinc-500">
        <span>
          Probed on load, then every 10 minutes. The API caches one probe round for ~10 s.
        </span>
        {forced ? (
          <span className="text-amber-400">
            forced re-probe — the API&apos;s cache is bypassed ·{' '}
            <Link to="/status" className="underline hover:text-zinc-200">
              back to the normal cadence
            </Link>
          </span>
        ) : (
          <Link to="/status?refresh" className="underline hover:text-zinc-200">
            Re-probe now
          </Link>
        )}
      </div>

      <Section
        title="What works right now"
        subtitle="the overall verdict, and what a broken dependency costs — derived from which pages it powers"
      >
        <OverallVerdict />
      </Section>

      <Section
        title="Every dependency, probed"
        subtitle="one card per check — status, latency, what it powers, and the remedy when it isn't clean"
      >
        <DependencyBoard />
      </Section>
    </div>
  );
}
