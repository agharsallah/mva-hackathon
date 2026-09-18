import { Link } from 'react-router-dom';

import { useStep1 } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { Chip, Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { int, pct } from '../lib/format';
import { C } from '../lib/palette';
import { DecoyCard } from './steps/step1/DecoyCard';
import { Gates } from './steps/step1/Gates';
import { Overlap } from './steps/step1/Overlap';
import { RecallCurve } from './steps/step1/RecallCurve';
import { Sources } from './steps/step1/Sources';
import { Tiers } from './steps/step1/Tiers';

/**
 * Step 1 — which genes the child's symptoms alone nominate, with the DNA never opened.
 *
 * The page of this app with the smallest input: eight ontology codes a doctor wrote down,
 * ranked against public curation of what every gene is known to cause. Everything the read
 * route and the k-mer route later look at is chosen here, so the honest question is not
 * "what did it nominate" but "how much does a list like this actually cover" — and that
 * question has a measured, uncomfortable answer.
 *
 * No gene symbol appears on this page. Step 1 ran blind against iteration 1's candidate,
 * and a symbol list here is exactly the comparison step 6 exists to make on purpose.
 */
export default function Step1Page() {
  const q = useStep1();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            The child arrived with <strong>eight symptoms</strong> written as ontology codes. This
            step turns them into a <strong>target set</strong> — the genes every later route is
            allowed to read DNA for — and then measures the one thing a gene list is usually allowed
            to skip: <strong>how often a list like this contains the right gene at all</strong>.
          </>
        }
        terms={[
          {
            term: 'held-out recall',
            dict: 'held-out',
            plain:
              'Take a disease whose answer is known, delete that disease’s own contribution to the gene’s curation, rank, and see where the gene lands. Doing it for thousands of diseases turns "does this work" into a number.',
          },
          {
            term: 'Zemojtel-style degradation',
            dict: 'zemojtel-style-degradation',
            plain:
              'Real clinics do not record textbook term lists. Before ranking, a couple of terms are blurred to their parent and a couple of unrelated ones are added, so the benchmark measures the ranker under clinic conditions instead of ideal ones.',
          },
          {
            term: 'bootstrap interval',
            dict: 'bootstrap-interval',
            plain:
              'Resample the results with replacement a thousand times and read off the middle 95% of the answers. It says how much of the number is the method and how much is the particular diseases that happened to be drawn.',
          },
          {
            term: 'decoy set',
            dict: 'decoy-set',
            plain:
              'Genes matched to the targets on shape but carrying none of the symptoms. Running the same rules over them measures how often the method nominates a gene by chance.',
          },
          {
            term: 'mechanism term',
            plain:
              'A gene admitted because the ontology annotates it under a chromosome-instability root, whatever it scored. That is prior knowledge, not evidence, so those rows are tagged and carry their pure-score rank beside them.',
          },
        ]}
      />

      <Loaded query={q} height={420}>
        {(data) => {
          const full = data.benchmark_full ?? data.benchmark;
          const atTarget = full?.curve.find((p) => p.n === data.target_n) ?? null;
          const promised = data.gates.find((g) => g.claim === 'H012')?.predicted ?? 0.9;

          return (
            <div className="space-y-6">
              <Callout tone="broken" title="The result this step is actually for">
                No cutoff of a symptom-only ranker reaches the coverage this step promised. At the{' '}
                {data.target_n} genes the target set is taken at, held-out recall is{' '}
                <strong>
                  {atTarget ? atTarget.recall.toFixed(3) : '—'}
                  {atTarget
                    ? ` [${atTarget.interval[0].toFixed(3)}, ${atTarget.interval[1].toFixed(3)}]`
                    : ''}
                </strong>{' '}
                against a pre-registered {promised.toFixed(2)} — and {int(full?.unrankable)} of{' '}
                {int(full?.diseases_run)} held-out genes cannot be placed at <em>any</em> N, because
                the disease being withheld is the only one that ever curated them. So the target set
                is an <strong>enrichment, never coverage</strong>: a gene missing from it is not
                thereby excluded, and the safety net is the genome-wide ranking that applies no
                target set at all.
              </Callout>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile
                  label="genes nominated"
                  value={int(data.set_sizes.targets)}
                  sub={`${int(data.set_sizes.earned_by_score)} earned their rank, ${int(data.set_sizes.by_mechanism_rule)} by the mechanism rule`}
                />
                <StatTile
                  label={`recall at N = ${data.target_n}`}
                  value={atTarget ? atTarget.recall.toFixed(3) : '—'}
                  tone="broken"
                  sub={
                    atTarget
                      ? `95% bootstrap [${atTarget.interval[0].toFixed(3)}, ${atTarget.interval[1].toFixed(3)}] over ${int(full?.diseases_run)} diseases`
                      : 'not run'
                  }
                  hint="an internal consistency check — ground truth and scoring database share curators"
                />
                <StatTile
                  label="protein-coding genes it cannot see"
                  value={pct(data.curation.fraction, 1)}
                  tone="broken"
                  sub={`${int(data.curation.uncurated)} of ${int(data.curation.protein_coding)} have no HPO curation at all`}
                />
                <StatTile
                  label="decoy null"
                  value={int(data.decoys.genes)}
                  tone="decision"
                  sub="shape-matched genes carrying none of the features, drawn from a recorded seed"
                />
              </div>

              <Section title="How far does a symptom-only list reach?">
                <Exhibit
                  title="Held-out recall against the cutoff, with the promise it missed"
                  legend={
                    <>
                      <Chip color={C.machinery}>blue</Chip> = the sampled run ·{' '}
                      <Chip color={C.good}>green</Chip> = the full eligible population · the shaded
                      band is each run&rsquo;s 95% bootstrap interval ·{' '}
                      <Chip color={C.decision}>amber dashes</Chip> = the cutoff actually taken ·{' '}
                      <Chip color={C.broken}>red dots</Chip> = the recall promised before the run.
                    </>
                  }
                  reading={
                    <>
                      The curve never approaches the red line, and it is still climbing at the right
                      edge — raising the cutoff to a thousand genes triples the work for about a
                      fifth more recall and still misses two genes in five. That is why the cutoff
                      stayed where it was and the wording changed instead. The two runs sit on top
                      of one another, which is the point of drawing them together: the number is a
                      property of the corpus, not of which diseases were sampled.
                    </>
                  }
                  source={q.data?.source}
                  cachedAt={q.data?.cachedAt}
                  origin={q.data?.origin}
                  data={{ sample: data.benchmark, full: data.benchmark_full }}
                >
                  <RecallCurve
                    sample={data.benchmark}
                    full={data.benchmark_full}
                    targetN={data.target_n}
                    promised={promised}
                  />
                </Exhibit>

                <Exhibit
                  title="The pre-registered gates, including the three that failed"
                  legend={
                    <>
                      One row per promise made <em>before</em> the run.{' '}
                      <Chip color={C.good}>green</Chip> = the measurement kept it ·{' '}
                      <Chip color={C.broken}>red</Chip> = it did not, and the gate stays on the page
                      anyway.
                    </>
                  }
                  reading={
                    <>
                      One of four held, and it is the weakest of the four: the mechanism rule
                      guarantees a chromosome-instability gene a seat, so that claim is close to
                      true by construction and is reported as a sanity check on the rule, not as a
                      discovery. The verdict column is computed from the served numbers, so it
                      cannot go stale.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.gates}
                >
                  <Gates rows={data.gates} />
                </Exhibit>
              </Section>

              <Section title="What the target set is made of">
                <Exhibit
                  title="Tiers, and how many rows earned their rank"
                  legend={
                    <>
                      <Chip color={C.good}>green</Chip> = the top of the symptom score, where human
                      review starts · <Chip color={C.machinery}>blue</Chip> = the rest of the window
                      · <Chip color={C.decision}>amber</Chip> = admitted by the mechanism rule
                      rather than by score — prior knowledge, tagged as such.
                    </>
                  }
                  reading={
                    <>
                      A tier says where review starts, not what is looked at: every later step reads
                      all of them. The amber rows matter for one reason — a rediscovery claim may
                      only be made on a gene that earned its rank, because the mechanism rule
                      pre-loads exactly the gene class this disease&rsquo;s name points at.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.tiers}
                >
                  <Tiers payload={data} />
                </Exhibit>

                <Exhibit
                  title="The decoy set — the null every later step is measured against"
                  legend={
                    <>
                      <Chip color={C.broken}>red</Chip> = the genes that should find nothing ·{' '}
                      <Chip color={C.decision}>amber</Chip> = genes excluded before the draw because
                      the child&rsquo;s features are curated for them, which would make them a
                      contaminated null.
                    </>
                  }
                  reading={
                    <>
                      Without this set, &ldquo;we found a biallelic candidate in a target
                      gene&rdquo; has no denominator — almost every gene carries two differences in
                      almost everyone. Step 2 ran its whole enumeration over these genes too, and
                      the answer it got back is why this set exists.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.decoys}
                >
                  <DecoyCard payload={data} />
                </Exhibit>
              </Section>

              <Section title="Does a second opinion agree?">
                <Exhibit
                  title="Two hosted rankers against ours, over the window each filled"
                  legend={
                    <>
                      <Chip color={C.good}>green</Chip> = genes both rankers put in the window ·{' '}
                      <Chip color={C.broken}>red</Chip> = genes only that ranker nominated ·{' '}
                      <Chip color={C.decision}>amber dashes</Chip> = the 50% agreement promised
                      before the run.
                    </>
                  }
                  reading={
                    <>
                      Neither reaches the line. The denominator is each service&rsquo;s own window
                      rather than the {data.target_n} we asked for — one of the two returns fifty
                      rows however many are requested, and dividing that truncation by{' '}
                      {data.target_n} would print a service limit as scientific disagreement. Low
                      agreement is not proof that either is wrong; it is proof that a single ranker
                      is not a second opinion.
                      {data.agreement_retrieved_on
                        ? ` Both were queried live on ${data.agreement_retrieved_on}, which is a retrieval date rather than a pinned version.`
                        : ''}
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.overlap}
                >
                  <Overlap rows={data.overlap} />
                </Exhibit>
              </Section>

              <Section title="Where this list is blind">
                <Exhibit
                  title="The share of protein-coding genes with no curation at all"
                  legend={
                    <>
                      <Chip color={C.broken}>red</Chip> = genes this ranker cannot score, because
                      nobody has curated a phenotype for them ·{' '}
                      <Chip color={C.machinery}>blue</Chip> = the genes it can see.
                    </>
                  }
                  reading={
                    <>
                      {pct(data.curation.fraction, 1)} of the protein-coding genome is invisible to
                      any curation-driven ranker, ours included — against a fifth predicted before
                      the run. This is the larger blind spot, and it is the reason the later steps
                      keep a genome-wide route that applies no gene list at all.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.curation}
                >
                  <div className="space-y-3">
                    <div className="flex h-8 w-full overflow-hidden rounded-sm">
                      <div
                        className="h-full"
                        style={{
                          width: `${(data.curation.fraction ?? 0) * 100}%`,
                          background: C.broken,
                        }}
                      />
                      <div className="h-full flex-1" style={{ background: C.machinery }} />
                    </div>
                    <div className="grid gap-3 sm:grid-cols-3">
                      <StatTile
                        label="uncurated"
                        value={int(data.curation.uncurated)}
                        tone="broken"
                        sub={pct(data.curation.fraction, 1)}
                      />
                      <StatTile
                        label="protein-coding total"
                        value={int(data.curation.protein_coding)}
                        sub="the denominator, from the reference gene model"
                      />
                      <StatTile
                        label="chromosome-instability genes in the corpus"
                        value={int(data.mechanism_term_genes)}
                        tone="decision"
                        sub="every gene the ontology annotates under the two mechanism roots"
                      />
                    </div>
                  </div>
                </Exhibit>
              </Section>

              <Sources payload={data} query={q} />

              <Callout tone="decision" title="What this number is, and what it is not">
                Ground truth and scoring database come from the same curators, so the recall curve
                is an <strong>internal consistency check, not an external validation</strong>, and
                it carries no genomic background — every gene here is a candidate, where a real case
                has a whole exome of them. It is also stricter than published top-10 figures in one
                respect (the disease&rsquo;s own curation of its gene is deleted first) and weaker
                in another (there is no variant evidence to break ties). The ranking itself, term by
                term, is on{' '}
                <Link to="/phenotype" className="underline underline-offset-2">
                  the phenotype page
                </Link>
                ; what the reads then found in these genes is on{' '}
                <Link to="/steps/step-2" className="underline underline-offset-2">
                  step 2
                </Link>
                .
              </Callout>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
