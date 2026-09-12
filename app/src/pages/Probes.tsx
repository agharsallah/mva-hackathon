import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { JobsMonitor } from './probes/JobsMonitor';
import { ProbeBuilder } from './probes/ProbeBuilder';
import { ProbeConsole } from './probes/ProbeConsole';
import { ProbeLedger } from './probes/ProbeLedger';

export default function ProbesPage() {
  return (
    <div className="space-y-6">
      <Callout tone="decision" title="Two budgets, do not confuse them">
        A <strong>local k-mer count</strong> over our own read store costs about 5.6 minutes of
        compute for 20 probes and nothing else — run as many as you like. An{' '}
        <strong>oracle probe</strong> is one of eighteen irreversible questions to the challenge
        organisers. The console below spends the first kind. The ledger at the bottom tracks the
        second, and it currently stands at 0 of 18.
      </Callout>

      <Explainer
        intro={
          <>
            Every other page reads a summary. This page asks the raw reads a new question. A{' '}
            <strong>k-mer probe</strong> is a literal string search: give it a 30-letter sequence
            and it reports how many of the 1.07 billion reads contain it, on either strand, in how
            many lanes. That is the cheapest possible independent check on a variant call — it
            bypasses the aligner and the caller entirely and goes back to the measurement.
          </>
        }
        terms={[
          {
            term: 'k-mer',
            dict: 'k-mer',
            plain:
              'a short fixed-length DNA sequence used as an exact search string (k = its length)',
          },
          {
            term: 'reverse complement',
            dict: 'reverse-complement',
            plain:
              'DNA is double-stranded, so the same sequence can appear reversed and letter-swapped. A real match shows up on both strands',
          },
          {
            term: 'expected read count',
            plain:
              'at ~44× depth a sequence on one of two chromosome copies should be seen by roughly 35 reads. Far fewer means noise',
          },
          {
            term: 'noise floor',
            plain:
              'sequencing errors produce a handful of spurious matches for almost any sequence. A count near it proves nothing',
          },
          {
            term: 'lane support',
            plain:
              'a real allele appears in all 4 lanes. A one-lane hit is a red flag for an instrument artefact',
          },
          {
            term: 'job',
            plain:
              'the count takes minutes, so the API accepts the request, returns an id, and the browser follows it',
          },
          {
            term: 'long-poll',
            plain:
              'the browser calls /wait?timeout=60 and the server holds the connection until the state changes — fewer requests, lower latency than polling',
          },
          {
            term: 'oracle probe',
            dict: 'oracle',
            plain:
              'a different thing entirely: one of 18 allowed questions to the challenge organisers. Irreversible, and tracked in the ledger below',
          },
        ]}
        caveat="An exact-match count is a strong negative test and a weak positive one. Zero reads is close to proof of absence; a healthy count proves the sequence exists somewhere in the sample, not that it exists at the locus you had in mind."
      />

      <Section
        title="Probe console"
        subtitle="submit one or more sequences; the count runs one pass over all 272 shards"
      >
        <ProbeConsole />
      </Section>

      <Section
        title="Jobs"
        subtitle="every read-store query the API has been asked to run, including from the CLI"
      >
        <JobsMonitor />
      </Section>

      <Section
        title="Submission builder"
        subtitle="turn candidates into the Track 1 CSV without typing a coordinate — building is free, uploading spends 1 of 18"
      >
        <ProbeBuilder />
      </Section>

      <Section title="Oracle probe ledger">
        <ProbeLedger />
      </Section>
    </div>
  );
}
