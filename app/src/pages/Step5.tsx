import { useStep5 } from '../api/hooksSteps';
import { Section } from '../components/Controls';
import { Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Plot } from '../components/Plot';
import { Loaded } from '../components/QueryState';
import { StatTile } from '../components/StatTile';
import { C } from '../lib/palette';
import { Anchors } from './steps/step5/Anchors';
import { Catalogue } from './steps/step5/Catalogue';
import { Citations } from './steps/step5/Citations';
import { conditions, count, movement, share, stat } from './steps/step5/metrics';
import { ProteinTrack } from './steps/step5/Protein';

/**
 * Step 5 — what public knowledge says about the candidate set, and what that is worth.
 *
 * The page is arranged so the knowledge result cannot be read on its own. A literature
 * route is the easiest route in this pipeline to fool yourself with — the gene at the top
 * of any search is the gene most has been written about — so the two things that could
 * explain the ordering away, a matched decoy set and a raw publication count, are on the
 * same screen as the ordering itself.
 */
export default function Step5Page() {
  const q = useStep5();

  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Three questions to public knowledge, and a fourth that judges them. Has anyone{' '}
            <strong>published</strong> about the alleles this child carries? Does any single{' '}
            <strong>paper</strong> discuss a candidate gene alongside several of the child&rsquo;s
            features? Does a leading missense allele land in an annotated protein{' '}
            <strong>domain</strong>? And then: does any of that order anything a raw publication
            count does not? If not, the route has measured fame rather than biology, and the step
            says so.
          </>
        }
        terms={[
          {
            term: 'LitVar 2.0',
            dict: 'pubmed-europe-pmc-pubtator3-litvar2-openalex-semantic-scholar',
            plain:
              "NCBI's index of which publications mention which variant, keyed on dbSNP identifiers — so it can be asked about this child's own alleles rather than about a gene.",
          },
          {
            term: 'PubTator 3.0',
            dict: 'pubmed-europe-pmc-pubtator3-litvar2-openalex-semantic-scholar',
            plain:
              'A search over PubMed and PMC with genes, diseases and chemicals already annotated in the text, so a gene-plus-symptom query is an entity query rather than a string match.',
          },
          {
            term: 'case-report anchor',
            dict: 'case-report-anchor',
            plain:
              "A published paper that discusses a candidate gene alongside several of the patient's own clinical features. Derived here by script, never chosen by hand.",
          },
          {
            term: 'InterPro domain',
            dict: 'domain-database-pfam-smart-prosite-gene3d-superfamily-cdd-prints',
            plain:
              'A curated stretch of a protein that folds and works as a unit. A swap inside one is more likely to break something than a swap in a linker between them.',
          },
          {
            term: 'pLDDT',
            dict: 'plddt',
            plain:
              "AlphaFold's own per-residue confidence, 0–100. Not a pathogenicity score: below 70 it means the model has no confident opinion about the shape there.",
          },
          {
            term: 'citation-volume baseline',
            dict: 'citation-volume-baseline',
            plain:
              'Ranking the same genes by how many papers mention them at all. If the knowledge ordering agrees with it, the knowledge ordering is it.',
          },
          {
            term: 'decoy null',
            dict: 'decoy-null',
            plain:
              'Size-matched control genes run through the identical queries. Matching on coding length matters here: a bigger gene carries more alleles and attracts more papers.',
          },
        ]}
      />

      <Loaded query={q} height={480}>
        {(data) => {
          const coverage = data.coverage;
          const anchors = data.anchor_summary;
          const protein = data.protein_summary;
          const separation = data.baselines.separation;
          const agreement = data.baselines.agreement;
          const route = data.baselines.route;
          const leader = protein.leader ?? null;
          const moved = movement(data.citations);
          const reaching = anchors.genes_reaching_five_terms ?? [];

          return (
            <div className="space-y-6">
              <Callout
                tone={route?.ranking_route ? 'good' : 'decision'}
                title={
                  route?.ranking_route
                    ? 'The literature carries information the citation count does not'
                    : 'What this route is allowed to do in the fusion'
                }
              >
                Two conditions were filed before the run, and a route has to meet both before it may
                rank anything: it must separate the symptom-nominated genes from their matched
                decoys, and it must reorder a ranking built from publication counts alone.{' '}
                {separation && (
                  <>
                    The decoy null gives <strong>AUC {stat(separation.auc)}</strong> [
                    {stat(separation.low)}, {stat(separation.high)}] over{' '}
                    {count(separation.targets)} targets and {count(separation.decoys)} decoys.{' '}
                  </>
                )}
                {agreement && (
                  <>
                    Against the citation baseline, <strong>rho = {stat(agreement.rho)}</strong> and
                    the two top-{agreement.k} sets share {agreement.overlap} genes
                    {(agreement.tied_at_k ?? 0) > agreement.k
                      ? ` — with ${agreement.tied_at_k} genes tied on the score that decides entry to the top ${agreement.k}, so that overlap is partly alphabetical`
                      : ''}
                    .{' '}
                  </>
                )}
                <strong>{route?.verdict}</strong>
              </Callout>

              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatTile
                  label="alleles asked about"
                  value={count(coverage.queryable)}
                  sub={`${count(coverage.unqueryable)} had no dbSNP identifier and could not be asked`}
                  hint="the denominator: an allele nobody indexed is not an allele nobody published about"
                />
                <StatTile
                  label="of those, published about"
                  value={count(coverage.described)}
                  tone="machinery"
                  sub={`${share(coverage.described, coverage.queryable)} — nearly saturated, so this column barely discriminates`}
                  hint="LitVar holds at least one paper for almost any variant carrying an rsID"
                />
                <StatTile
                  label="ClinVar pathogenic alleles the child carries"
                  value={count(coverage.clinvar_carried)}
                  tone="good"
                  sub="typed by k-mer count in the raw reads — no aligner, no caller (step 3)"
                  hint="the only column on this page that is evidence about the patient"
                />
                <StatTile
                  label="genes with a five-feature paper"
                  value={count(reaching.length)}
                  tone={reaching.length > 0 ? 'good' : 'decision'}
                  sub={`out of ${count(anchors.genes)} genes and ${count(anchors.searches)} searches`}
                  hint="a paper returned by five of the seven per-term searches"
                />
              </div>

              <Section title="The ordering, and the two things that could explain it away">
                <Exhibit
                  title="Knowledge rank against citation rank, gene by gene"
                  legend={
                    <>
                      <strong style={{ color: C.good }}>green</strong> = a gene the child&rsquo;s
                      symptoms nominated · <strong style={{ color: C.broken }}>red</strong> = a
                      matched decoy · <strong style={{ color: C.machinery }}>blue</strong> = neither
                      · <strong style={{ color: C.absent }}>grey dotted</strong> = the line of no
                      reordering. {moved.promoted} genes were promoted above their citation rank,{' '}
                      {moved.demoted} demoted and {moved.still} left where they were.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.citations}
                >
                  <Plot
                    height={420}
                    data={[
                      {
                        type: 'scatter',
                        mode: 'markers',
                        x: data.citations.map((row) => row.citation_rank),
                        y: data.citations.map((row) => row.knowledge_rank),
                        text: data.citations.map(
                          (row) => `${row.gene} — ${row.pubmed_count.toLocaleString()} papers`,
                        ),
                        marker: {
                          size: 10,
                          color: data.citations.map((row) =>
                            row.is_decoy ? C.broken : row.is_target ? C.good : C.machinery,
                          ),
                        },
                      },
                    ]}
                    layout={{
                      xaxis: { title: 'rank by PubMed hit count alone' },
                      yaxis: { title: 'rank by the knowledge score' },
                      showlegend: false,
                    }}
                  />
                </Exhibit>

                <Exhibit
                  title="The same rows, with what moved and why"
                  legend={
                    <>
                      <strong>moved</strong> is citation rank minus knowledge rank: positive means
                      the literature promoted the gene above where its publication volume would have
                      put it. <strong>rank by DNA</strong> is where step 4&rsquo;s genome-wide
                      likelihood ratio put the same gene, carried so the two routes can be read
                      against each other before step 6 fuses anything.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.citations}
                >
                  <Citations rows={data.citations} />
                </Exhibit>

                {data.groups.length > 0 && (
                  <Exhibit
                    title="Targets, decoys and the rest of the genome, scored identically"
                    legend={
                      <>
                        The decoys are matched to the targets on coding length and exon count, which
                        matters more here than anywhere else in the iteration: a bigger gene carries
                        more alleles and attracts more papers, so an unmatched control set would
                        measure gene size. {separation?.verdict}
                      </>
                    }
                    source={q.data?.source}
                    origin={q.data?.origin}
                    data={data.groups}
                  >
                    <Plot
                      height={320}
                      data={[
                        {
                          type: 'bar',
                          x: data.groups.map((row) => row.grouping),
                          y: data.groups.map((row) => row.mean_score),
                          text: data.groups.map(
                            (row) => `${row.genes_with_anchor} of ${row.genes} with an anchor`,
                          ),
                          textposition: 'outside',
                          marker: {
                            color: data.groups.map((row) =>
                              row.grouping === 'decoy'
                                ? C.broken
                                : row.grouping === 'target'
                                  ? C.good
                                  : row.grouping === 'curated-other'
                                    ? C.machinery
                                    : C.raw,
                            ),
                          },
                        },
                      ]}
                      layout={{ yaxis: { title: 'mean knowledge score' }, showlegend: false }}
                    />
                  </Exhibit>
                )}
              </Section>

              <Section title="What the literature was asked, and what it answered">
                <Exhibit
                  title="Of the alleles this child carries, which has anyone published about?"
                  legend={
                    <>
                      <strong>askable</strong> = the allele carries a dbSNP identifier, so an index
                      keyed on dbSNP could have an opinion · <strong>never askable</strong> = it
                      does not, and that is an absence of the instrument, not of the literature ·{' '}
                      <strong style={{ color: C.good }}>carries</strong> = a public ClinVar
                      pathogenic allele step 3 found present in the raw reads. Only the last column
                      is about this child.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.catalogue}
                >
                  <Catalogue rows={data.catalogue} />
                </Exhibit>

                <Exhibit
                  title="Papers that discuss a gene alongside the child's own features"
                  legend={
                    <>
                      Every row was produced by {count(anchors.searches)} scripted searches — each
                      gene against each of the {anchors.terms?.length ?? 0} proband terms — and not
                      by a reader choosing citations. A decoy row here is not an error: it is the
                      measurement. Papers matching fewer than {anchors.min_terms_written ?? 2} terms
                      are not written out.
                    </>
                  }
                  source={q.data?.source}
                  origin={q.data?.origin}
                  data={data.anchors}
                >
                  <Anchors rows={data.anchors} />
                </Exhibit>
              </Section>

              {data.protein.length > 0 && (
                <Section title="Where the leading missense alleles sit in their proteins">
                  <Exhibit
                    title="Domain map and structure confidence, per leading gene"
                    legend={
                      <>
                        <strong style={{ color: C.decision }}>amber</strong> = an InterPro entry
                        typed as a <em>domain</em>, the only kind the claim counts ·{' '}
                        <strong style={{ color: C.machinery }}>blue</strong> = a family or
                        superfamily, drawn thinner and excluded because it spans most of a protein ·{' '}
                        <strong style={{ color: C.good }}>green tick</strong> = the allele falls
                        inside a domain · <strong style={{ color: C.broken }}>red tick</strong> = it
                        does not. Positions are fractions of each protein&rsquo;s own length; no
                        residue number is served.
                      </>
                    }
                    source={q.data?.source}
                    origin={q.data?.origin}
                    data={data.protein}
                  >
                    <div className="space-y-4">
                      {data.protein
                        .filter((row) => row.fraction !== null)
                        .slice(0, 12)
                        .map((row) => (
                          <ProteinTrack
                            key={`${row.gene}-${row.rsid}-${row.fraction}`}
                            residue={row}
                            domains={data.domains}
                          />
                        ))}
                    </div>
                  </Exhibit>

                  {leader && (
                    <Exhibit
                      title={`The three conditions, for the leading allele in ${leader.gene}`}
                      legend={
                        <>
                          The claim was filed as three separate conditions so a refutation can name
                          which one failed. {protein.esm1b}
                        </>
                      }
                      source={q.data?.source}
                      origin={q.data?.origin}
                      data={[leader]}
                    >
                      <ul className="space-y-1 text-sm">
                        {conditions(leader).map((condition) => (
                          <li key={condition.label}>
                            <span style={{ color: condition.met ? C.good : C.broken }}>
                              {condition.met ? '✓' : '✗'}
                            </span>{' '}
                            {condition.label}
                            {condition.label.startsWith('inside') && !condition.met && (
                              <span className="text-chrome-400">
                                {' '}
                                — and {leader.in_superfamily ? 'inside' : 'outside'} every family
                                and superfamily entry too
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </Exhibit>
                  )}
                </Section>
              )}

              <Callout tone="broken" title="What this step cannot tell you">
                <strong>A publication is not evidence about this child.</strong>{' '}
                {share(coverage.described, coverage.queryable)} of the askable alleles carry at
                least one paper, which means the column is near-saturated and separates almost
                nothing on its own — LitVar holds a citation for nearly any variant with an rsID.
                The one column on this page that is about the patient comes from a different
                instrument entirely: {count(coverage.clinvar_carried)} public ClinVar pathogenic
                alleles that step 3 typed as present in the raw reads by k-mer count.{' '}
                <strong>ESM1b was cut</strong> — it needs a 2.5 GB checkpoint to score a handful of
                residues, and AlphaMissense is the calibrated missense score the ranking already
                used, so the second opinion here is structural context rather than a second model.
              </Callout>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}
