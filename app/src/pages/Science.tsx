import { Callout, Explainer } from '../components/Explainer';
import { Section } from '../components/Controls';
import { LoopDiagram } from './science/LoopDiagram';
import { HypothesisBoard } from './science/HypothesisBoard';
import { EvidenceLedger } from './science/EvidenceLedger';
import { ProbeBudget } from './science/ProbeBudget';
import { CONFIDENCE_CAVEAT } from './science/register';

/**
 * The science register: what is believed, how strongly, and on what basis.
 *
 * Every other page in this app answers "what does the data say". This one answers the
 * different question a reviewer asks next, and it is the only page whose subject is the
 * project's own reasoning rather than the child's genome.
 */
export default function SciencePage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Provenance says where a byte came from. It says nothing about <strong>what we believe</strong>. The
            research register is the other half: a machine-readable record of every claim, the observation
            that would kill it, the evidence for and against, and the verdict — kept in two append-only
            tables so a belief cannot be quietly rewritten to match whatever the data turned out to say. The
            report and the submission rows are generated from it, not transcribed by hand.
          </>
        }
        terms={[
          {
            term: 'hypothesis',
            plain: (
              <>
                a falsifiable claim with its prediction <em>and</em> its refutation condition, both written
                before the run. Think of the refutation as the failing assertion you commit before the fix
              </>
            ),
          },
          {
            term: 'refuted_by',
            plain: 'the observation that would kill the claim. A claim nothing could disprove is refused at the constructor, not flagged in review',
          },
          {
            term: 'evidence',
            plain: 'one observation, tagged supports / refutes / neutral, weighted, and carrying its source. An unsourced observation is refused',
          },
          {
            term: 'source_ref',
            plain: 'where the observation can be checked: a methodology entry, a table, a PMID, a ClinVar id, or an oracle reply',
          },
          {
            term: 'revision',
            plain: 'both tables are append-only. A changed belief appends a new revision row of the same hypothesis id — never an edit, so the record of the belief moving survives',
          },
          {
            term: 'verdict',
            plain: 'the evidence accumulated in log-odds into a status and a confidence, with every term printed and a stated reason',
          },
          {
            term: 'step',
            plain: 'one research goal, declared in code (src/mva/science/steps.py). Every claim names one, so the record reads by question rather than by date',
          },
          {
            term: 'step-0',
            plain: 'platform machinery. "PostgreSQL is the right database" is a decision judged by whether it works, not a claim about the patient — so the register refuses a hypothesis filed under it',
          },
          {
            term: 'oracle probe',
            plain: 'one of 18 irreversible submissions to the challenge scorer. A reply is recorded twice: in the probe ledger as what happened, in the evidence ledger as what it means',
          },
        ]}
        caveat={`Every confidence number on this page is ${CONFIDENCE_CAVEAT}. Strengths are human judgements, and rows drawn from the same underlying data are not independent the way the sum treats them. It exists so a suggested number can be argued with — never quote it as a probability.`}
      />

      <Callout tone="good" title="The register is empty on purpose">
        No hypothesis has been proposed and no probe has been spent. That is the honest state of a project
        that has finished its platform step and not yet made a claim about the child — and it is exactly what
        this page is built to show. The two register tables are created on first write by{' '}
        <span className="font-mono">mva-science</span>, so until then they do not exist in the database at
        all; the endpoints report that as a flag rather than inventing an empty table. Nothing on this page
        writes.
      </Callout>

      <LoopDiagram />

      <Section
        title="What do we claim, and what would kill it?"
        subtitle="one card per registered claim, current revision first, history one click away"
      >
        <HypothesisBoard />
      </Section>

      <Section
        title="What have we observed, for and against?"
        subtitle="every observation, bound to the claim it moves and to the source it came from"
      >
        <EvidenceLedger />
      </Section>

      <Section
        title="What have we spent to find out?"
        subtitle="the same ledger the Probes page operates, read here as part of the research narrative"
      >
        <ProbeBudget />
      </Section>

      <p className="text-[11px] leading-relaxed text-zinc-600">
        The method this page renders is owned by <span className="font-mono text-zinc-500">docs/method.md</span>;
        the steps are declared in <span className="font-mono text-zinc-500">src/mva/science/steps.py</span>; the
        register lives in <span className="font-mono text-zinc-500">warehouse.hypotheses</span> and{' '}
        <span className="font-mono text-zinc-500">warehouse.evidence</span>. This page is read-only — only the{' '}
        <span className="font-mono text-zinc-500">mva-science</span> verbs write. No genomic position appears
        in a statement or a claim; the register refuses one on the way in.
      </p>
    </div>
  );
}
