import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { useReferenceProvenance } from '../api/hooks';
import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { Derivations, LineageTable } from './provenance/Derivations';
import { LineageGraph } from './provenance/LineageGraph';
import { ReferenceData } from './provenance/ReferenceData';

/**
 * Scroll to `#reference` when another page deep-links here.
 *
 * The router does not restore a hash on its own, and this page is a lazy chunk, so the
 * target does not exist at navigation time — hence the effect rather than a plain anchor.
 *
 * Two things the deps carry beyond `hash`, both of them bugs that were visible:
 *
 * - **`key`** — the router's per-navigation id. Following `/provenance#reference` while
 *   *already* on `/provenance#reference` leaves `hash` unchanged, so the effect never re-ran
 *   and the link did nothing.
 * - **`settled`** — the reference table's rows arrive after this effect's first pass, so the
 *   section still had its collapsed height and the scroll landed short. Re-running once the
 *   rows are in puts the heading at the top of the viewport.
 */
function useHashScroll(settled: boolean) {
  const { hash, key } = useLocation();
  useEffect(() => {
    if (!hash) return;
    document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'start' });
  }, [hash, key, settled]);
}

export default function ProvenancePage() {
  const reference = useReferenceProvenance();
  useHashScroll(!reference.isLoading);
  return (
    <div className="space-y-6">
      <Callout tone="good" title="What this page guarantees">
        Every figure in this app resolves to a{' '}
        <Link
          to="/catalog"
          className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
        >
          delivered object
        </Link>{' '}
        whose sha256 was recomputed locally and matched. No chart reads a hand-edited file, and no
        derived table exists without a recorded question. The graph below is the proof, and it is
        short by design — two hops from bytes to chart.
      </Callout>

      <Explainer
        intro={
          <>
            A clinical claim is only as good as the chain behind it. This page is that chain: which
            bytes were delivered, what checksum proved they arrived intact, which table was computed
            from which, by what transform, and what question each table was built to answer. Think
            of it as a build graph with content hashes on the inputs — the same discipline, applied
            to data instead of artefacts.
          </>
        }
        terms={[
          {
            term: 'provenance',
            dict: 'provenance',
            plain: 'the record of where a number came from and every step that shaped it',
          },
          {
            term: 'lineage',
            dict: 'data-lineage',
            plain:
              'the edges of that record: this table was produced from that source by this transform',
          },
          {
            term: 'sha256',
            dict: 'checksum-sha-256',
            plain:
              'a content hash. Recompute it on the received bytes and compare — if it matches, nothing was lost or altered in transit',
          },
          {
            term: 'derivation',
            plain:
              'a computed table, stored so the app never re-scans 5 million records to draw a chart',
          },
          {
            term: 'append-only',
            dict: 'append-only',
            plain:
              'records are added, never edited. A changed belief becomes a new row, so the old reasoning stays visible',
          },
          {
            term: 'provenance manifest',
            dict: 'provenance-manifest',
            plain:
              'a lockfile for data: URL + version + hash, committed beside the file, so the same bytes can be re-fetched and checked',
          },
          {
            term: 'raw vs results schema',
            plain:
              'raw holds the delivered records verbatim; results holds only things computed from raw, so the two can never be confused',
          },
        ]}
        caveat={
          <>
            A verified hash proves the bytes we hold are the bytes that were sent. It says nothing
            about whether the vendor&apos;s pipeline that produced them was correct — that is what
            the{' '}
            <Link
              to="/callset"
              className="underline decoration-chrome-600 underline-offset-2 hover:text-chrome-50"
            >
              Callset
            </Link>{' '}
            page&apos;s sanity checks are for.
          </>
        }
      />

      <Section title="The data flow">
        <LineageGraph />
      </Section>

      <Section
        id="reference"
        title="The public inputs"
        subtitle="reference tables and offline fixtures — fetched, not computed, so each carries a manifest instead of a lineage edge"
      >
        <ReferenceData />
      </Section>

      <Section title="Why each table exists">
        <Derivations />
      </Section>

      <Section
        title="The full lineage record"
        subtitle="the same rows as the graph, flat, for auditing"
      >
        <LineageTable />
      </Section>
    </div>
  );
}
