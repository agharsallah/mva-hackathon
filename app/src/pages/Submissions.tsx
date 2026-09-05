import { Link } from 'react-router-dom';

import { useSubmissions } from '../api/hooks';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { Dossier } from './submissions/Dossier';

/**
 * The submissions page: the dossier for every upload-ready iteration.
 *
 * Every other page in this app answers a question about the child's data. This one answers
 * the question a judge asks last — *what exactly would you send, and why should anyone
 * believe it?* — by putting the four things that usually live in four different places side
 * by side: the file's identity (a sha256, because the file itself must never be committed),
 * the reasoning behind every row (selectors, not coordinates), the chain back to the
 * delivered bytes, and the ledger of what the answer has cost.
 *
 * Cumulative: one entry per iteration, newest first. A folder is frozen the moment it is
 * uploaded and is never edited again, so the page grows rather than changing.
 */
export default function SubmissionsPage() {
  const q = useSubmissions();

  return (
    <div className="space-y-6">
      <Callout tone="decision" title="A submission is a measurement, not a guess">
        The oracle budget is <strong>6 irreversible uploads</strong>, and nothing renews it. So a
        submission is designed the way an experiment is: the hypothesis space is written down with
        its priors, every possible reply is simulated against a transcribed replica of the published
        scorer, and the file is only sent when the reply would be informative{' '}
        <em>whatever it says</em>. The decode table below is that design, and the{' '}
        <Link
          to="/probes"
          className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
        >
          Probes
        </Link>{' '}
        page is where the budget is actually spent.
      </Callout>

      <Explainer
        intro={
          <>
            An <strong>iteration</strong> is one folder — the report, the methods form, the decode
            table and the coordinate-free spec — and it is everything the organisers would receive
            plus the material a reviewer needs to check it. The predictions file itself is the one
            artefact of this project that carries genomic positions, so it is{' '}
            <strong>never committed</strong>: this page identifies it by its content hash and shows
            the reasoning behind every row instead of the row.
          </>
        }
        terms={[
          {
            term: 'decode table',
            dict: 'decode-table',
            plain:
              'every reply the scorer can give, with what each one would leave standing. Written before the upload, so the answer is read rather than reacted to',
          },
          {
            term: 'expected information gain',
            dict: 'expected-information-gain',
            plain:
              'how many bits of uncertainty the reply is expected to remove — the price/benefit calculation for spending one of six irreversible probes',
          },
          {
            term: 'F-max',
            dict: 'f-max',
            plain:
              'the challenge scorer’s per-case score: how well the submitted variant set overlaps the answer key at the best threshold. 1.0 is exact',
          },
          {
            term: 'rank points',
            dict: 'rank-points',
            plain:
              'the other half of the score: points for how high in the submitted list the right answer sits, so ordering the rows is itself a decision',
          },
          {
            term: 'epcr',
            dict: 'epcr',
            plain:
              'estimated probability of causal relationship — the confidence column of the submission template. Must strictly descend down the file',
          },
          {
            term: 'secondary finding',
            dict: 'secondary-incidental-finding',
            plain:
              'a pathogenic variant unrelated to the question asked, reported because a clinician would want to know. Marked as such so it cannot compete with the primary answer',
          },
          {
            term: 'selector',
            dict: 'selector-submission',
            plain:
              'a WHERE clause over a warehouse result table that must match exactly one row. It names what an allele is — gene, consequence, rarity — instead of where it sits, which is what makes this folder committable',
          },
          {
            term: 'sha256',
            dict: 'checksum-sha-256',
            plain:
              'a content hash. It names bytes without carrying them, which is how this page can talk about a file that is deliberately outside the repository',
          },
          {
            term: 'lineage',
            dict: 'data-lineage',
            plain:
              'the recorded edges behind a result: this table was produced from that source by this transform',
          },
          {
            term: 'oracle',
            dict: 'oracle',
            plain:
              'the challenge scorer, reachable only by uploading. Six replies exist for this whole project and each one is permanent',
          },
        ]}
        caveat="Confidence numbers in the register below are a transparent triage heuristic with their arithmetic printed — never quote one as a probability. The decode table's priors are stated judgements too; what is measured is the scorer's behaviour, which was rehearsed byte-for-byte on a replica."
      />

      <Loaded query={q} height={420} label="Loading the submission dossier">
        {(_data, meta) => <Dossier result={meta} />}
      </Loaded>
    </div>
  );
}
