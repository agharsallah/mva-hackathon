import { Link } from 'react-router-dom';

import { Callout } from '../../components/Explainer';
import { Loaded } from '../../components/QueryState';
import { StatTile } from '../../components/StatTile';
import { int, pct } from '../../lib/format';
import { useZooCase, useZooModels, useZooRanks } from './hooks';

/**
 * The case banner and the beginner walkthrough — both built from the payload, not typed.
 *
 * Every noun in the paragraph below that a reader could fail to know is a link into the
 * dictionary, and every number in it comes from `/api/zoo/ranks` or `/api/zoo/models`. That
 * is the rule this page is written to: a reader who has never seen a variant-effect model
 * should be able to read this page without a second document, and a reader who changes the
 * case (a different gene, a different illness) should see the page change with it.
 */

/** A dictionary link, so the walkthrough teaches the word instead of assuming it. */
function D({ slug, children }: { slug: string; children: React.ReactNode }) {
  return (
    <Link
      to={`/learn#${slug}`}
      className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
    >
      {children}
    </Link>
  );
}

export function CaseBanner() {
  const ranks = useZooRanks();
  const models = useZooModels();
  const zooCase = useZooCase().data?.data;
  const roster = models.data?.data ?? [];
  const ran = roster.filter((m) => m.enabled);
  const adjacent = ran.filter((m) => m.catalogue_adjacent);

  return (
    <Loaded query={ranks} height={220} variant="tiles">
      {(data) => {
        const configured = zooCase ?? data.case;
        const label = configured?.case?.label;
        const iteration = configured?.case?.iteration;
        const opinions = data.per_model.filter((m) => m.confirmed?.rank != null);
        const silent = data.per_model.filter((m) => m.confirmed?.rank == null);
        return (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile
                label="Case gene"
                value={configured?.gene ?? '—'}
                tone="raw"
                sub={
                  configured
                    ? `${iteration ?? 'iteration unstated'} · mode ${configured.mode ?? 'unstated'}`
                    : 'the API named no case'
                }
                hint={
                  configured?.gene_source
                    ? `read by the API from ${configured.gene_source}`
                    : "read by the API from the zoo's configuration, never typed into this page"
                }
              />
              <StatTile
                label="Lanes that ran"
                value={ran.length || data.per_model.length}
                sub={`${adjacent.length} catalogue-adjacent · ${roster.length} on the roster`}
              />
              <StatTile
                label="Pairs considered"
                value={int(data.pairs_total)}
                sub={`${int(Math.max(...data.per_model.map((m) => m.n_ranked)))} ranked by the widest lane`}
              />
              <StatTile
                label="Lanes with an opinion"
                value={`${opinions.length} of ${data.per_model.length}`}
                tone={opinions.length === 0 ? 'broken' : 'good'}
                sub={
                  silent.length
                    ? `${silent.map((m) => m.model).join(', ')} scored only one half`
                    : 'every lane scored both halves'
                }
              />
            </div>

            <Callout tone="machinery" title="Read this first, if the words are new">
              A <D slug="model-zoo">model zoo</D> is a set of independent programs asked the same
              question, kept apart on purpose. The question here is: of the {int(data.pairs_total)}{' '}
              candidate <D slug="compound-heterozygous-comp-het">pairs</D> of broken gene copies in
              this child&rsquo;s genome, how damaging is each one? Each lane answers with a number
              per <D slug="allele-id">allele</D>; a pair is scored by its <em>weaker</em> half, so
              one unscored half means the lane has <strong>no opinion</strong> on that pair rather
              than a bad one — which is why {silent.length} of {data.per_model.length} lanes below
              report no <D slug="rank">rank</D> for the case pair at all. One lane,{' '}
              {adjacent.map((m) => m.name).join(', ') || 'none here'}, is{' '}
              <D slug="catalogue-adjacent">catalogue-adjacent</D> — it was trained on curated
              verdicts about known variants, so the consensus is always printed twice, once with it
              and once without.
              {configured && (
                <>
                  {' '}
                  The case is <strong>{label ?? 'unnamed'}</strong>: the gene the run was configured
                  to check, <strong>{configured.gene}</strong>, and the folder its reports were
                  written to, <code>{iteration ?? 'unstated'}</code>, are values the API read from{' '}
                  <code>{configured.gene_source ?? configured.config_path}</code> — point them at
                  another illness and this page follows.
                </>
              )}
            </Callout>

            {opinions.length > 0 && (
              <p className="text-xs text-chrome-400">
                The lanes that did rank the case pair put it at{' '}
                {opinions.map((m) => `${m.model} ${pct(m.confirmed?.percentile, 2)}`).join(' · ')} —
                a percentile counted from the top, so smaller is more damaging.
              </p>
            )}
          </div>
        );
      }}
    </Loaded>
  );
}
