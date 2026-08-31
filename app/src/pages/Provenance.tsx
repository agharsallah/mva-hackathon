import { Callout, Explainer } from '../components/Explainer';
import { Section } from '../components/Controls';
import { LineageGraph } from './provenance/LineageGraph';
import { Derivations, LineageTable } from './provenance/Derivations';

export default function ProvenancePage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            A clinical claim is only as good as the chain behind it. This page is that chain: which bytes were
            delivered, what checksum proved they arrived intact, which table was computed from which, by what
            transform, and what question each table was built to answer. Think of it as a build graph with
            content hashes on the inputs — the same discipline, applied to data instead of artefacts.
          </>
        }
        terms={[
          {
            term: 'provenance',
            plain: 'the record of where a number came from and every step that shaped it',
          },
          {
            term: 'lineage',
            plain: 'the edges of that record: this table was produced from that source by this transform',
          },
          {
            term: 'sha256',
            plain: 'a content hash. Recompute it on the received bytes and compare — if it matches, nothing was lost or altered in transit',
          },
          {
            term: 'derivation',
            plain: 'a computed table, stored so the app never re-scans 5 million records to draw a chart',
          },
          {
            term: 'append-only',
            plain: 'records are added, never edited. A changed belief becomes a new row, so the old reasoning stays visible',
          },
          {
            term: 'raw vs results schema',
            plain: 'raw holds the delivered records verbatim; results holds only things computed from raw, so the two can never be confused',
          },
        ]}
        caveat="A verified hash proves the bytes we hold are the bytes that were sent. It says nothing about whether the vendor's pipeline that produced them was correct — that is what the Callset page's sanity checks are for."
      />

      <Callout tone="good" title="What this page guarantees">
        Every figure in this app resolves to a delivered object whose sha256 was recomputed locally and matched.
        No chart reads a hand-edited file, and no derived table exists without a recorded question. The graph
        below is the proof, and it is short by design — two hops from bytes to chart.
      </Callout>

      <Section title="The data flow">
        <LineageGraph />
      </Section>

      <Section title="Why each table exists">
        <Derivations />
      </Section>

      <Section title="The full lineage record" subtitle="the same rows as the graph, flat, for auditing">
        <LineageTable />
      </Section>
    </div>
  );
}
