# Architecture — the map

How the pieces fit, what each seam guarantees, and where to plug the next thing in.
Vocabulary is defined in [`../CONTEXT.md`](../CONTEXT.md); the reasoning behind the shape
is in [`notes/`](notes/).

## The shape of the problem

One proband. Five million variants. An answer key of exactly two of them, in one gene, one
on each chromosome copy. Eighteen chances to ask whether we are right.

That framing sets the whole design: the ranked unit is a **pair**, not a variant
([why pairs](notes/ranking-pairs-not-variants.md)), and a submission is a
**measurement** to be designed before it is spent
([why a replica](notes/local-scorer-replica.md)).

## Flow

```
  ~/ubuntu/data/*.vcf.gz          the gated callset, never entering git
          │
          │  bcftools: index, normalize, region-query        tools/profile-genomic-data.sh
          ▼
  ┌───────────────┐
  │    vcf.py     │  read_calls() → one Call per ALT allele
  └───────┬───────┘  keeps non-PASS, never rewrites alleles
          │
          │  Call(variant, genotype, depths, phase_set, phase_gt, filters)
          ▼
  ┌───────────────┐
  │compound_het.py│  candidate_pairs() → every het pair, classified
  └───────┬───────┘  CIS rejected · TRANS confirmed · UNKNOWN kept
          │
          │  VariantPair(left, right, phase)
          ▼
  ┌───────────────┐        ┌──────────────────┐
  │  ranking.py   │◄───────│  annotation.py   │  the port: gene, consequence, gnomAD AF
  └───────┬───────┘        └──────────────────┘  DictAnnotator today, VEP later
          │                                       see notes/
          │  RankedPair(left, right, gene, score)
          ▼
  ┌───────────────┐
  │ submission.py │  write_submission() → the 12-column Track 1 CSV
  └───────┬───────┘  validates: PROBAND01 · ≤10 rows · epcr ∈ (0,1] distinct
          │
          ├──────────────► the real leaderboard          (spends one of 18)
          │
          ▼
  ┌───────────────┐
  │   scorer.py   │  score(rows, hypothesis) → rank_points, f_max, match ranks
  └───────────────┘  a local replica — rehearse the probe before spending it
```

`variant.py` sits under all of it: every module speaks `Variant`, and it is the only place
allowed to build a chromosome string.

## The seams, and what each one guarantees

| Module | Guarantee | Test module |
|---|---|---|
| `variant.py` | A variant is always in the scorer's representation. The `chr` prefix is added exactly once, here. | `test_variant.py` |
| `vcf.py` | Every ALT allele becomes its own `Call`. Nothing is filtered, nothing is rewritten. | `test_vcf.py` |
| `compound_het.py` | Cis pairs never reach ranking. Unknown-phase pairs always do. | `test_compound_het.py` |
| `annotation.py` | An unseen variant is unknown, never an exception. | (exercised via ranking) |
| `ranking.py` | Pairs come back best-first, and only same-gene pairs come back at all. | `test_ranking.py` |
| `submission.py` | Nothing the scorer would reject or rank ambiguously can be written. | `test_submission.py` |
| `scorer.py` | Faithful to the published evaluation code, including its tie-breaking. | `test_scorer.py` |
| the whole chain | A VCF in, a scored CSV out. | `test_pipeline_end_to_end.py` |

69 tests, running in 0.15 s on synthetic fixtures with no dataset present.

## Where the sharp edges are

**The `chr` prefix.** The VCF says `15`; the scorer demands `chr15` and compares strings
verbatim. `Variant.from_vcf()` is the bridge. Region queries go the other way — `bcftools`
needs the bare contig — so the panel BED is stripped on the way in and prefixed on the way
out. Building a chromosome string anywhere else is the single easiest way to score zero
while looking correct.

**Normalization is not done yet.** 66,860 multiallelic sites and 930k indels face a scorer
that does exact string matching with no left-alignment. `bcftools norm -m -both -f <no-chr
GRCh38>` must run before candidate extraction, against the *no-chr* reference to match the
VCF. This is the highest-value unimplemented step after annotation.

**`INFO/AF` is a trap.** It is within-sample. With one sample it is 0.5 or 1.0 and carries
no population information. Population frequency comes only from the annotation port.

**Unknown phase is not a rejection.** It is the verdict on 99.7% of pairs.

## Extension points

- **A real annotator.** Implement `annotate(variant) -> Annotation`. Nothing else changes.
- **A different ranking model.** `rank_pairs()` takes pairs and an annotator and returns
  scored pairs; the scoring function inside is deliberately simple and inspectable, because
  with one proband and no training data a transparent additive score is defensible in the
  methods form and a tuned black box is not.
- **Variant sources beyond the delivered VCF.** Anything that can produce `Call` objects —
  a DeepVariant re-call, an SV caller, a non-PASS rescue pass — feeds the same pipeline.
  This is how the structural-variant path attaches when it is built.

## What is not here yet

No alignment, no re-calling, no SV detection, no normalization step, no real annotator, and
no CLI. See [`roadmap.md`](roadmap.md).
