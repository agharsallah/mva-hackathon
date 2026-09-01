import { Section } from '../components/Controls';
import { Callout, Explainer } from '../components/Explainer';
import { DeliveryInventory } from './catalog/DeliveryInventory';
import { ReadStoreCard } from './catalog/ReadStoreCard';
import { TableCatalog } from './catalog/TableCatalog';
import { TableExplainer } from './catalog/TableExplainer';

/**
 * Catalog — the index over the data itself.
 *
 * Every other page reads *through* the platform to the biology. This one reads the
 * platform: what exists, what it holds, when it landed, where it sits. It is the page a
 * reviewer opens first to decide whether anything downstream is worth reading.
 */
export default function CatalogPage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            A data catalogue answers four questions about every piece of data in the platform:{' '}
            <strong>what is it</strong>, <strong>what does it contain</strong>,{' '}
            <strong>when did it arrive</strong>, and <strong>where does it live</strong>. There are
            only two kinds of answer here. The <strong>raw delivery</strong> is what the publisher
            gave us: immutable — written once, never rewritten — and hash-verified, so we can prove
            our copy is byte-for-byte theirs. Everything else is <strong>derived</strong>: produced
            by a transform over some input, and carrying a <strong>lineage edge</strong> recording
            which input, which transform, which tool. If a derived table cannot name its edge, it
            cannot be re-derived or invalidated, and this page says so in yellow rather than leaving
            the cell blank.
          </>
        }
        terms={[
          {
            term: 'object store',
            plain:
              'a flat key→bytes store (S3 here). No directories, just keys that look like paths; an object is written whole and read whole, never patched in place',
          },
          {
            term: 'object key / location',
            plain:
              'the key is the address inside the bucket (`source/WGS_….vcf.gz`); the location is that key fully qualified — `s3://mva/source/WGS_….vcf.gz`',
          },
          {
            term: 'SHA-256 (checksum, digest)',
            plain:
              'a 64-hex-character fingerprint of a file’s bytes. Recompute it on your copy, compare it to the one the publisher published: equal means not one bit differs. It is the byte-level equivalent of a git commit hash',
          },
          {
            term: 'hash source',
            plain:
              '`publisher` = matched against the manifest the publisher signed, so the bytes are theirs. `own-upload` = matched against a digest we computed ourselves, which proves only that our own upload round-tripped intact',
          },
          {
            term: 'immutable delivery',
            plain:
              'the raw objects are never edited or replaced. Every correction is a new derived artefact, so the thing every result traces back to cannot silently change under it',
          },
          {
            term: 'lineage edge',
            plain:
              'one recorded arrow: this output table came from that input, by that transform, with that tool, at that time. A directed graph of these is what makes a number re-derivable',
          },
          {
            term: 'warehouse vs results schema',
            plain:
              '`warehouse` holds faithful transcriptions of the source data (a VCF as rows); `results` holds aggregates computed for a question. The split keeps "the data" separate from "our reading of it"',
          },
          {
            term: 'row count / estimate',
            plain:
              'the catalogue’s count for a table, taken when the catalogue was refreshed rather than when you looked. For a table of millions of rows it can be an estimate, because an exact count means a full scan — read the magnitude first',
          },
          {
            term: 'ingest ledger',
            plain:
              'our own record of when each object first landed. Objects that predate it have no first-upload time, so the store’s last-modified stamp is shown instead — an upper bound, not the arrival',
          },
          {
            term: 'schema (namespace)',
            plain:
              'a named group of tables inside one database, the way a package groups modules. Two schemas here: `warehouse` for ingested data and the hand-written ledgers, `results` for everything computed from them',
          },
          {
            term: 'replaced vs appended vs rebuilt',
            plain:
              'three things a re-run can do to a table. `CREATE OR REPLACE` throws the old contents away (an ingest); an append-only ledger only ever gains rows, so history survives; a derivation rebuilds its output from scratch, which is safe precisely because it is a pure function of its inputs',
          },
          {
            term: 'partition / shard',
            plain:
              'a partition is a slice of a dataset addressable on its own (here: one lane × read direction); a shard is one physical file inside it. Sharding is what lets a query read part of a store instead of all of it',
          },
        ]}
        caveat="A catalogue records what we hold and where it came from. It does not certify that a derived table is correct — only that it is traceable. A green hash and a lineage edge together mean a number can be audited back to bytes the publisher signed; they say nothing about whether the transform in between was the right one."
      />

      <Callout tone="decision" title="What to look for on this page">
        Two colours carry the whole reading. <strong>Green</strong> in the first exhibit means a
        checksum matched, which is the precondition for every number in the app being about the
        right patient&apos;s data. <strong>Yellow</strong> anywhere is an honest gap — an object
        with no recorded arrival time, or a table with no lineage edge. Neither is fatal; both are
        things a reviewer is entitled to ask about, so they are shown rather than smoothed over.
      </Callout>

      <Section
        title="What were we given?"
        subtitle="the immutable raw delivery — one card per object, with its checksum verdict and arrival time"
      >
        <DeliveryInventory />
      </Section>

      <Section
        title="What did we build from it?"
        subtitle="every warehouse and results table, with the lineage edge that produced it — filterable by name or description"
      >
        <TableCatalog />
      </Section>

      <Section
        title="What is actually in each table?"
        subtitle="one expandable card per table: why it exists, which command writes it, and what every column means"
      >
        <TableExplainer />
      </Section>

      <Section
        title="The one derived artefact that is not a table"
        subtitle="the read store: the same delivered reads, rewritten columnar so they can be queried"
      >
        <ReadStoreCard />
      </Section>
    </div>
  );
}
