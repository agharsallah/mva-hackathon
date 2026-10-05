/**
 * The overview — the map of the app rather than a stop on the journey.
 *
 * It owns no data of its own: the section cards come from the module manifest through the
 * journey context, so adding a page in `src/app/modules/index.ts` puts it on this page too.
 */

import { Card, Explainer, JourneyMap, Section } from '../components';

export default function Overview() {
  return (
    <div className="space-y-8">
      <Explainer
        intro={
          <>
            This dashboard is an <strong>understanding tool</strong>: every figure carries the
            legend that decodes it, the provenance line that says where its rows came from, and a
            one-click export of both for an AI chat. Nothing is shown without saying how it was
            produced.
          </>
        }
        terms={[
          {
            term: 'exhibit',
            plain:
              'The one wrapper a figure may enter the app through. It requires a legend, so no chart can ship without one.',
          },
          {
            term: 'provenance',
            plain:
              'The string the API returns beside every payload, naming the table, object or file the rows came from.',
          },
          {
            term: 'module manifest',
            plain:
              'The single array that declares every page: its route, its nav label, its section and its lazily-loaded chunk.',
          },
        ]}
      />

      <Section
        title="The questions this app answers"
        subtitle="One card per section, each a reading list in journey order."
      >
        <JourneyMap />
      </Section>

      <Section title="How a page is built" subtitle="The contract every new page inherits.">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Card>
            <h3 className="text-sm font-semibold tracking-tight text-chrome-100">
              Declare it once
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-chrome-400">
              A page is one entry in <code>src/app/modules/index.ts</code>. The router, the header
              rows, the page heading and the previous/next links all read that entry, so none of
              them can drift apart.
            </p>
          </Card>
          <Card>
            <h3 className="text-sm font-semibold tracking-tight text-chrome-100">
              Fetch through one door
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-chrome-400">
              Every request goes through <code>src/api/client.ts</code> and a hook in{' '}
              <code>src/api/hooks.ts</code>. One envelope, one retry policy, one place a failure
              becomes a sentence the reader can act on.
            </p>
          </Card>
          <Card>
            <h3 className="text-sm font-semibold tracking-tight text-chrome-100">
              Show, then say how
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-chrome-400">
              A chart enters through <code>Exhibit</code>, which requires a legend and registers the
              figure for export. The design tokens behind it are on the Style page.
            </p>
          </Card>
        </div>
      </Section>
    </div>
  );
}
