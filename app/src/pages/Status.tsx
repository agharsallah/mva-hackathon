import { Link } from 'react-router-dom';

import { HEALTH_POLL_MS } from '../api/hooks';
import { Explainer, Section } from '../components';
import { AdvancedPanel } from './status/AdvancedPanel';
import { DependencyBoard } from './status/DependencyBoard';
import { OverallVerdict } from './status/OverallVerdict';
import { useStatusDebugUnlocked } from './status/statusDebug';
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
/** Derived from the constant the hook actually polls on, so the sentence cannot drift
 * from the cadence again — it already had, after the interval was raised. */
const POLL_MINUTES = Math.round(HEALTH_POLL_MS / 60_000);

export default function StatusPage() {
  const forced = useRefreshRequested();
  const debugUnlocked = useStatusDebugUnlocked();
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            This app is a thin read layer over five dependencies that can each fail on their own: a{' '}
            <strong>Postgres warehouse</strong>, a <strong>MinIO object store</strong>, a{' '}
            <strong>parquet read-store</strong>, a <strong>raw-reads API</strong> and{' '}
            <strong>Ensembl REST</strong>. When one is down, this page names it, what it costs, and
            the exact command to fix it.
          </>
        }
        terms={[
          {
            term: 'Postgres warehouse',
            plain:
              'a relational database — the same kind of thing as MySQL — holding the ingested VCF rows and every computed table',
          },
          {
            term: 'MinIO object store',
            plain:
              'a key→bytes store speaking the S3 protocol, an on-prem stand-in for Amazon S3. It holds the raw delivered files',
          },
          {
            term: 'parquet read-store',
            plain: (
              <>
                a columnar file format — rows rewritten as columns on disk, the way a spreadsheet
                column scan beats a row scan. It backs the{' '}
                <Link
                  to="/reads"
                  className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
                >
                  Reads
                </Link>{' '}
                page&apos;s flowcell and quality charts
              </>
            ),
          },
          {
            term: 'raw-reads API',
            plain: (
              <>
                a separate process serving the k-mer probe console on the{' '}
                <Link
                  to="/probes"
                  className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
                >
                  Probes
                </Link>{' '}
                page
              </>
            ),
          },
          {
            term: 'Ensembl REST',
            plain:
              'a public, third-party HTTP API this app calls for gene coordinates — the only dependency this app does not own or run',
          },
          {
            term: 'liveness check / probe',
            dict: 'liveness-probe',
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
          {
            term: 'budget (timeout)',
            dict: 'timeout-budget',
            plain:
              'how long that check is allowed to take before it is reported down — per check, because a Postgres greet over the network is not a ping to this process. Raise one with MVA_HEALTH_TIMEOUTS=<check>=<seconds>, or raise the floor for all of them with MVA_HEALTH_TIMEOUT',
          },
          {
            term: 'masked address',
            plain:
              'hosts and ports render as •••• until you reveal them, per card or for the whole board. Presentation hygiene for a screenshot, not a secret: the values are in the response either way',
          },
        ]}
        caveat={`This page reads a health endpoint like any other — the states shown are whatever it reports at the moment you loaded the page, then re-checked every ${POLL_MINUTES} minutes. Probing costs real round trips to Postgres, MinIO and Ensembl, so it is deliberately quiet: after restarting one service use that card's own re-probe, which measures only that dependency and leaves the other six as last measured (each card says how old its own answer is). Re-probe now re-measures all seven. In fixture mode (no backend running) every state below is illustrative, not measured — the fixture's source string says so, and the per-card re-probe is disabled because there is nothing to probe.`}
      />

      <div className="flex flex-wrap items-baseline justify-between gap-2 text-micro text-chrome-400">
        <span>
          Probed on load, then every {POLL_MINUTES} minutes. The API caches each check&apos;s result
          for ~10 s.
        </span>
        {forced ? (
          <span className="text-decision-300">
            forced re-probe — the API&apos;s cache is bypassed ·{' '}
            <Link to="/status" className="underline hover:text-chrome-200">
              back to the normal cadence
            </Link>
          </span>
        ) : (
          <Link to="/status?refresh" className="underline hover:text-chrome-200">
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

      {debugUnlocked && <AdvancedPanel />}
    </div>
  );
}
