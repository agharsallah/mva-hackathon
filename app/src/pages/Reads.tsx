import { Callout, Explainer } from '../components/Explainer';
import { Section } from '../components/Controls';
import { LaneYield } from './reads/LaneYield';
import { DeliveredYield } from './reads/DeliveredYield';
import { StoreShape } from './reads/StoreShape';
import { Flowcell } from './reads/Flowcell';
import { CycleQuality } from './reads/CycleQuality';
import { QualityLevels } from './reads/QualityLevels';

export default function ReadsPage() {
  return (
    <div className="space-y-6">
      <Explainer
        intro={
          <>
            Underneath the callset sit 1.07 billion raw reads — the actual measurement. Everything on the other
            pages is a summary somebody else computed from these. Having them locally, in a queryable columnar
            store, is what makes it possible to go back and ask a question the caller never answered: does this
            exact 30-letter sequence appear in the raw data, and how many times? That is the k-mer probe on the
            Probes page, and this page is the ground it stands on.
          </>
        }
        terms={[
          {
            term: 'read',
            plain: 'one sequenced fragment of DNA, 149 letters here. A genome is reconstructed by piling up a billion of them',
          },
          {
            term: 'paired-end (R1 / R2)',
            plain: 'each fragment is read from both ends. R1 and R2 therefore come in exactly equal counts',
          },
          {
            term: 'FASTQ',
            plain: 'the raw read format: four lines per read — id, sequence, separator, one quality letter per base',
          },
          {
            term: 'lane',
            plain: 'a physical channel on the sequencer’s flowcell. This sample ran across 4 lanes',
          },
          {
            term: 'tile / x / y',
            plain: 'a read’s physical address on the flowcell glass. Instrument defects are spatial, so this address is diagnostic',
          },
          {
            term: 'cycle',
            plain: 'one round of the sequencing chemistry = one letter of the read. Quality decays as cycles accumulate',
          },
          {
            term: 'phred quality',
            plain: 'log-scale error probability per base. Q30 = 1 error in 1000, Q37 = about 1 in 5000',
          },
          {
            term: 'parquet',
            plain: 'a columnar file format. Unlike gzipped FASTQ, a query can read one column of one shard instead of the whole stream',
          },
          {
            term: 'shard / partition',
            plain: 'the store is split into 8 partitions (lane × read) of 34 files each, so scans parallelise and prune',
          },
          {
            term: 'k-mer',
            plain: 'a short fixed-length sequence used as a literal search string against the reads',
          },
        ]}
        caveat="Every read-level figure here is sampled, not exhaustive: flowcell maps come from one shard, quality curves from a 100k-row sample per partition. They characterise the run; they are not a census."
      />

      <Callout tone="decision" title="The one real finding on this page">
        <strong>R2 degrades measurably more than R1.</strong> Q30 share is 92.9 % for R1 against 90.0 % for R2,
        and the per-cycle curves show where it happens — the back half of the read. It is normal instrument
        behaviour, not a defect, but it matters for interpretation: a variant supported mainly by the tail of R2
        reads has weaker evidence behind it than the read count alone suggests.
      </Callout>

      <Section title="What was delivered">
        <div className="grid gap-4 xl:grid-cols-2">
          <LaneYield />
          <StoreShape />
        </div>
      </Section>

      <Section
        title="How good was the guess before we counted?"
        subtitle="Reads were estimated from the delivered bytes long before anything decompressed them. The parquet census makes that estimate's error measurable."
      >
        <DeliveredYield />
      </Section>

      <Section title="Where the reads came from, physically">
        <Flowcell />
      </Section>

      <Section title="How good are the letters?">
        <div className="space-y-4">
          <CycleQuality />
          <QualityLevels />
        </div>
      </Section>
    </div>
  );
}
