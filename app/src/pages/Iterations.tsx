import { Link } from 'react-router-dom';

import { useIterations, useSubmissions } from '../api/hooks';
import type { IterationsOverview } from '../api/types';
import { Section } from '../components/Controls';
import { Chip, Exhibit } from '../components/Exhibit';
import { Callout, Explainer } from '../components/Explainer';
import { Loaded } from '../components/QueryState';
import { C, TONE_MARK } from '../lib/palette';
import { CatalogExplorer } from './iterations/CatalogExplorer';
import { FlowDiagram } from './iterations/FlowDiagram';
import { FoldersTable } from './iterations/FoldersTable';
import { LineageHealth } from './iterations/LineageHealth';
import { Matrix } from './iterations/Matrix';
import { catalogOptions, headline, ORACLE_BUDGET } from './iterations/model';
import { iterationLabel } from './steps/route';

/**
 * The iterations hub: both numberings on one page.
 *
 * A **research iteration** (`/track1/iteration2`) is a route through the case; a
 * **submission folder** (`/submissions?it=track2/iteration-4`) is what the organisers would
 * receive. Their numbers do not line up, and every other page shows one axis at a time. This
 * page is the join — which route fed which folder, what state each folder is in — and the
 * catalogue of the datasets each one rests on, with the lineage record that explains them.
 *
 * Nothing here is typed by hand: `GET /api/iterations` derives it from the step maps, the
 * register, the methodology entries, the folders, the ledger and the manifests.
 */
export default function IterationsPage() {
  const q = useIterations();
  const dossiers = useSubmissions();

  return (
    <div className="space-y-6">
      {q.data ? (
        <Headline data={q.data.data} />
      ) : (
        <Callout tone="machinery" title="Counting the iterations…">
          The headline is computed from the payload, so it waits for it.
        </Callout>
      )}

      <Explainer
        intro={
          <>
            The word <strong>iteration</strong> means two things here. A{' '}
            <strong>research iteration</strong> is one route through the case — its own steps,
            claims and methodology entries. A <strong>submission iteration</strong> is one folder
            the organisers receive. A folder <em>cites</em> the research iterations whose entries
            its README links, so the matrix below is the join between the two, and the catalogue
            says which datasets each one rests on and whether a record explains where each came
            from.
          </>
        }
        terms={[
          {
            term: 'research iteration',
            dict: 'research-iteration',
            plain:
              'one whole route through the case: its own plan, steps and claims — docs/iteration<n>/, routes /track1/iteration<n>',
          },
          {
            term: 'submission iteration',
            dict: 'submission-iteration',
            plain:
              'one folder the organisers receive — submissions/<track>/iteration-<n>/, frozen once uploaded',
          },
          {
            term: 'data lineage',
            dict: 'data-lineage',
            plain:
              'recorded edges: this table was produced from that input by that transform, one warehouse row per edge',
          },
          {
            term: 'provenance manifest',
            dict: 'provenance-manifest',
            plain:
              'a file beside a data file naming its upstream, digests and tool — for fetched data, which has nothing to derive',
          },
          {
            term: 'iteration data catalog',
            dict: 'iteration-data-catalog',
            plain:
              'every dataset an iteration’s methodology entries name, joined to the ledger and to the manifests — derived, never typed',
          },
          {
            term: 'lineage attribution',
            dict: 'lineage-attribution',
            plain:
              'whether a ledger edge names the methodology entry that wrote it — the link from a table back to the reasoning that made it',
          },
        ]}
        caveat="“Cited” is not “used”: a dataset an entry names may have been read, written, or only mentioned. Only an edge or manifest that names the entry makes it “produced”."
      />

      <Loaded query={q} height={480} label="Loading the iterations overview">
        {(data, meta) => {
          const options = catalogOptions(data, dossiers.data?.data.iterations);
          const fallback = data.research.find((r) => r.current)?.iteration ?? options[0]?.key ?? '';
          return (
            <div className="space-y-8">
              <Section
                title="Research iterations × tracks"
                subtitle="which route through the case fed which track, and which submission folders cite it"
              >
                <Exhibit
                  title="The matrix — routes down, tracks across"
                  legend={
                    <>
                      A row is a research iteration; a{' '}
                      <span className="text-chrome-300">dashed</span> row is a plan with no steps. A
                      cell links the iteration’s page on that track, lists the folders{' '}
                      <em>built from</em> it (the newest iteration a folder cites) with their state
                      badge, and the folders that only quote it. Claims bar:{' '}
                      <Chip color={TONE_MARK.good}>green supported</Chip> ·{' '}
                      <Chip color={TONE_MARK.broken}>red refuted</Chip> ·{' '}
                      <Chip color={TONE_MARK.decision}>yellow testing</Chip> ·{' '}
                      <Chip color={TONE_MARK.machinery}>blue proposed</Chip> ·{' '}
                      <Chip color={C.absent}>grey superseded</Chip> — each claim at its latest
                      status.
                    </>
                  }
                  reading="Read across a row to see what one route did for each deliverable; read down a column to see every route that argues one deliverable."
                  data={data.research.map(({ catalog: _catalog, ...r }) => r)}
                  source={meta.source}
                  origin={meta.origin}
                >
                  <Matrix data={data} />
                </Exhibit>

                <Exhibit
                  title="Which research iterations each folder cites"
                  legend={
                    <>
                      Left: research iterations — <Chip color={C.machinery}>blue</Chip> = declared
                      steps (neutral machinery), <Chip color={C.absent}>grey dashed</Chip> = plan
                      only. Right: submission folders by state —{' '}
                      <Chip color={TONE_MARK.good}>green frozen</Chip> (uploaded) ·{' '}
                      <Chip color={TONE_MARK.decision}>yellow ready</Chip> ·{' '}
                      <Chip color={TONE_MARK.machinery}>blue draft</Chip>. A{' '}
                      <strong>solid line</strong> in the folder’s colour = built from that iteration
                      (the newest one it cites); a <strong>dashed grey line</strong> = the folder
                      only quotes one of its entries (every folder quotes entry 083, the oracle’s
                      reply, so iteration 1 is cited by all). Hover a box to light its lines; a
                      folder box opens its dossier.
                    </>
                  }
                  data={data.submissions.map((s) => ({ key: s.key, research: s.research }))}
                  source={meta.source}
                >
                  <FlowDiagram data={data} />
                </Exhibit>
              </Section>

              <Section
                title="Submission folders"
                subtitle="what the organisers would receive, one row per folder — each row opens its dossier"
              >
                <FoldersTable data={data} source={meta.source} />
              </Section>

              <Section
                title="Lineage health"
                subtitle="how much of the ledger names its entry, and how much of each catalogue a record explains"
              >
                <LineageHealth data={data} options={options} source={meta.source} />
              </Section>

              <Section
                id="data-catalog"
                title="Data catalog"
                subtitle="pick a research iteration or a submission folder: every dataset it names, and what explains it"
              >
                <CatalogExplorer
                  options={options}
                  fallback={fallback}
                  source={meta.source}
                  folderSource={dossiers.data?.source}
                />
              </Section>
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}

/** The headline, stated from the payload: what exists, in which state, and the oracle budget. */
function Headline({ data }: { data: IterationsOverview }) {
  const h = headline(data);
  const states = Object.entries(h.byState)
    .map(([state, n]) => `${n} ${state}`)
    .join(', ');
  return (
    <Callout tone="decision" title="Two numberings, one map">
      <strong>{h.research}</strong> research iterations ({h.declared} with steps
      {h.planOnly.length > 0 ? `; ${h.planOnly.map(iterationLabel).join(', ')} is a plan only` : ''}
      ) feed <strong>{h.folders}</strong> submission folders — {states}. {h.oracleFolders} folders
      are oracle-scored (Track 1) and {h.panelFolders} panel-judged (Track 2).{' '}
      <strong>
        {h.uploaded} of {ORACLE_BUDGET}
      </strong>{' '}
      oracle uploads are spent by a frozen folder; the ledger on{' '}
      <Link
        to="/probes"
        className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
      >
        Probes
      </Link>{' '}
      is the authority on the budget.
    </Callout>
  );
}
