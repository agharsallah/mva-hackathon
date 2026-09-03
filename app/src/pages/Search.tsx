/**
 * Universal search — one box over the whole callset.
 *
 * Every other page in this app starts from a list the server chose. This is the only
 * place a *user-chosen* locus enters the system, and the query lives in the URL
 * (`/search?q=…`) so a result is a link someone can paste into a message.
 *
 * The page is two requests, deliberately: resolve the query, then read the window. The
 * split is what lets it say *what the query resolved to, and by which resolver* before,
 * and independently of, paying for a scan of the five-million-row raw layer.
 */

import { useSearchParams } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useSearch } from '../api/hooks';
import { EmptyState } from '../components';
import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { Skeleton } from '../components/QueryState';
import type { Tone } from '../lib/palette';
import { BOX, cx } from '../lib/ui';
import { RegionResult, Resolution } from './search/Results';
import { SearchBox } from './search/SearchBox';

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q')?.trim() ?? '';
  const search = useSearch(q || null);

  function submit(next: string) {
    // `replace: false` on purpose — the back button should walk a search history.
    setParams(next ? { q: next } : {});
  }

  return (
    <div className="space-y-6">
      <Callout tone="decision" title="Why this page costs a cap and the other pages do not">
        Every chart in this app reads a <em>derived</em> table — a few thousand precomputed rows.
        This page is one of only two things in the service that touch{' '}
        <span className="font-mono">warehouse.variants_raw</span>, the 5,012,204-row all-text layer
        with <strong>no index of any kind</strong>. Measured, that layer answers a 1 kb window and a
        whole chromosome in the same ~2 s — PostgreSQL holds it in memory, so the scan is not the
        cost. What differs is the answer: 6 records and under a kilobyte against 101,130 records and
        11 MB. The 5 Mb cap is therefore a payload and render guard, and it comfortably contains any
        human gene. The reasoning behind serving derived tables everywhere else is the one design
        decision in <span className="font-mono">docs/step-0/viz-api.md</span>.
      </Callout>

      <Explainer
        intro={
          <>
            One box over the whole callset. Type a <strong>gene symbol</strong>, a{' '}
            <strong>region</strong> in either chromosome spelling, or an <strong>rsID</strong> — the
            server works out which of the three it is from the shape alone, resolves it to a window,
            and then reads every record the caller produced inside that window. The query is in the
            URL, so a result is a shareable link.
          </>
        }
        terms={[
          {
            term: 'gene symbol',
            dict: 'gene-symbol',
            plain:
              'the short human-readable name of a gene (BUB1B, TP53). Not a coordinate — it has to be looked up in a gene catalogue before anything can be read',
          },
          {
            term: 'region (contig:start-end)',
            dict: 'region-contig-start-end',
            plain:
              'a coordinate range on one chromosome, 1-based and inclusive at both ends. 15:40100000-40200000 is a 100,001 bp window on chromosome 15',
          },
          {
            term: 'contig / chr prefix',
            dict: 'chr-prefix-contig-naming',
            plain:
              'the chromosome’s name. This callset spells it "15" and the candidate panel spells it "chr15"; both are accepted here and normalised through the repo’s single bridge',
          },
          {
            term: 'rsID (dbSNP)',
            dict: 'rsid',
            plain:
              'a stable public name for one variant *site*, issued by dbSNP — the NCBI registry of known human variation. rs137852899 names a place in the genome plus the change seen there, and stays valid across genome builds where a raw coordinate does not',
          },
          {
            term: 'VCF record',
            dict: 'vcf-variant-call-format',
            plain:
              'one row of the callset: contig, position, reference base(s), alternate base(s), a quality score, a FILTER verdict and the sample’s genotype. The table below is exactly these rows',
          },
          {
            term: 'FILTER / suppressed',
            plain:
              'the caller’s own verdict on a record. PASS means it kept it outright; anything else means it kept the record but flagged it. A flagged record is still data — it is suppressed, not deleted',
          },
          {
            term: 'GT (genotype)',
            dict: 'genotype',
            plain:
              '0/1 = one of the two copies carries the change, 1/1 = both do, 1/2 = the two copies carry two *different* changes — compound heterozygosity proven by the genotype alone',
          },
          {
            term: 'VAF (variant allele fraction)',
            dict: 'vaf-variant-allele-fraction',
            plain:
              'the share of reads at a site that carry the alternate allele. ~0.5 for a healthy heterozygous site, ~1.0 for homozygous; far off either is a mosaic event or an artefact',
          },
          {
            term: 'span cap',
            plain:
              'the widest window this page will read. The raw callset layer has no index, so a whole chromosome costs the same ~2 s as a gene and then weighs 11 MB over 101,130 rows — the cap is a payload guard, not a speed one',
          },
        ]}
        caveat="Positions shown here are the proband's real coordinates whenever the live API is answering. They are never written into this repository; the offline fixture uses an obviously synthetic 1,000,000-based ladder."
      />

      <Section
        title="Search the callset"
        subtitle="a gene symbol, a region, or an rsID — resolved server-side, then read from the raw callset"
      >
        <div className="space-y-4">
          <SearchBox value={q} onSubmit={submit} busy={search.isFetching} />
          {!q && <Idle />}
          {q && search.isPending && <Skeleton height={120} />}
          {q && search.error && <SearchError error={search.error} q={q} />}
          {q && search.data && (
            <>
              <Resolution found={search.data.data} />
              <RegionResult found={search.data.data} />
            </>
          )}
        </div>
      </Section>
    </div>
  );
}

function Idle() {
  return (
    <EmptyState>
      Nothing searched yet. Pick one of the examples above, or type a gene, a region or an rsID.
    </EmptyState>
  );
}

/**
 * The four failure modes, told apart.
 *
 * Collapsing them is what makes a search box feel broken: "I mistyped", "no such gene",
 * "too wide" and "the upstream is down" call for four different next actions, so each
 * gets its own sentence and its own colour.
 */
function SearchError({ error, q }: { error: Error; q: string }) {
  const status = error instanceof ApiError ? error.status : 0;
  const tone: Tone = status === 502 ? 'broken' : status === 404 ? 'neutral' : 'decision';

  const title =
    status === 422
      ? 'That is not one of the three forms — or the window is too wide'
      : status === 404
        ? 'Valid shape, but nothing knows that name'
        : status === 502
          ? 'Ensembl could not be reached'
          : 'The search API did not answer';

  return (
    <div className={cx('rounded-card border p-4', BOX[tone])}>
      <div className="text-xs font-semibold text-chrome-300">{title}</div>
      <p className="mt-2 font-mono text-xs leading-relaxed text-chrome-400">{error.message}</p>
      <p className="mt-2 max-w-3xl text-xs leading-relaxed text-chrome-500">
        {status === 422 && (
          <>
            <span className="font-mono text-chrome-300">{q}</span> was refused before anything was
            looked up. The three accepted forms are a gene symbol, a{' '}
            <span className="font-mono">contig:start-end</span> region, and an{' '}
            <span className="font-mono">rs</span>-number. A region wider than the span cap is
            refused the same way, and the message above carries the cap.
          </>
        )}
        {status === 404 && (
          <>
            The shape was fine, so the query reached a resolver — the candidate panel, then the
            callset’s own rsID column, then Ensembl — and none of them placed it. This is
            deliberately <em>not</em> the same answer as an empty table: a name nothing knows and a
            place with no records are different facts.
          </>
        )}
        {status === 502 && (
          <>
            Off-panel gene symbols and rsIDs absent from the callset are resolved against the public
            Ensembl REST service, and it is unreachable or refusing. Nothing is guessed in its place
            — an invented coordinate would be worse than no answer. Panel genes, regions and rsIDs
            the callset already names still resolve, because none of those touches Ensembl.
          </>
        )}
        {status !== 422 && status !== 404 && status !== 502 && (
          <>
            Start the viz API (<span className="font-mono">uv run mva-viz-api</span>), or browse the
            committed fixtures — the offline fixture answers the example queries and deliberately
            answers nothing else, so a made-up result can never be mistaken for a real one.
          </>
        )}
      </p>
    </div>
  );
}
