# Architecture — the map

**Standing:** a map, not a manual. Module names and seam guarantees checked against the
tree 2026-08-29. Counts, provisioned state and gaps live in
[`current-state.md`](current-state.md); vocabulary in [`../CONTEXT.md`](../CONTEXT.md);
the reasoning behind each choice in [`decisions.md`](decisions.md).

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
  │pipeline/vcf.py│  read_calls() → one Call per ALT allele
  └───────┬───────┘  keeps non-PASS, never rewrites alleles
          │
          │  Call(variant, genotype, depths, phase_set, phase_gt, filters)
          ▼
  ┌───────────────┐
  │  compound_het │  candidate_pairs() → every het pair, classified
  └───────┬───────┘  CIS rejected · TRANS confirmed · UNKNOWN kept
          │
          │  VariantPair(left, right, phase)
          ▼
  ┌───────────────┐        ┌──────────────────┐
  │    ranking    │◄───────│   annotation     │  the port: gene, consequence, gnomAD AF
  └───────┬───────┘        └──────────────────┘  DictAnnotator today, VEP later
          │                                       see notes/
          │  RankedPair(left, right, gene, score)
          ▼
  ┌───────────────┐
  │   submission  │  write_submission() → the 12-column Track 1 CSV
  └───────┬───────┘  validates: PROBAND01 · ≤10 rows · epcr ∈ (0,1] distinct
          │
          ├──────────────► the real leaderboard          (spends one of 18)
          │
          ▼
  ┌───────────────┐
  │     scorer    │  score(rows, hypothesis) → rank_points, f_max, match ranks
  └───────────────┘  a local replica — rehearse the probe before spending it
```

Every module above is `src/mva/pipeline/`. `variant.py` sits under all of it: every module speaks `Variant`, and it is the only place
allowed to build a chromosome string ([the chr-prefix bridge](notes/chr-prefix-bridge.md)).

## The second branch: exploration

The pipeline above answers *which two variants*. A second package answers *what is in this
data at all*, and it reads the committed profile rather than the gated dataset:

```
  ressources/data-profile/       ~600 KB of tallies, committable
          │
          ▼
  ┌───────────────┐
  │  explore/     │  readers → profile → checks → views → report
  └───────┬───────┘  one interactive HTML page, 20 exhibits
          │
          ├──────────────► figures/explore-report.html
          │
          └──────────────► uv run mva-explore checks   (graded table, terminal)
```

It also has a locus branch that reads real calls through `vcf.py` and classifies pairs
through `compound_het.py`, which is how the pair matrix and phase map are drawn. Nothing
in the pipeline depends on `explore/`; the dependency runs one way only, so a change to a
chart can never affect a submission.

Full documentation in [`exploration.md`](exploration.md).

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
| `io/readers.py` | A malformed or truncated artifact is a gap, never an exception. | `test_explore_readers.py` |
| `explore/profile.py` | Every section is optional, and the filename mapping is a parameter. | `test_explore_profile.py` |
| `explore/checks.py` | Every verdict states its band and the reasoning behind it. | `test_explore_checks.py` |
| `explore/views/` | A figure never travels without its caption and its legend. | `test_explore_views.py` |
| `explore/report.py` | Every exhibit is rendered, reachable, and drawn exactly once. | `test_explore_report.py` |

All of it runs on synthetic fixtures with no dataset and no services present — the
current test count is in [`current-state.md`](current-state.md).

## Where the sharp edges are

**The `chr` prefix.** The VCF says `15`; the scorer demands `chr15` and compares strings
verbatim. `pipeline/variant.py` owns the conversion and nothing else may build a chromosome
string — [the chr-prefix bridge](notes/chr-prefix-bridge.md).

**Normalization is not done yet.** Multiallelic sites and indels
([counts](../ideation/data-findings.md)) face a scorer that does exact string matching with
no left-alignment. `bcftools norm -m -both -f <no-chr GRCh38>` must run before candidate
extraction, against the *no-chr* reference to match the VCF. This is the highest-value
unimplemented step after annotation.

**`INFO/AF` is a trap.** It is within-sample. With one sample it is 0.5 or 1.0 and carries
no population information. Population frequency comes only from the annotation port.

**Unknown phase is not a rejection.** It is the verdict on the overwhelming majority of
pairs; phasing is a tiebreaker, not the discriminator
([measured](../ideation/data-findings.md)).

**`pg-query` addresses tables as `pg.<schema>.<table>`.** It runs in DuckDB, which reaches
Postgres through `ATTACH`. A bare `warehouse.foo` is a "table does not exist" error, not a
permissions problem — [`infrastructure.md`](infrastructure.md).

## Extension points

- **A real annotator.** Implement `annotate(variant) -> Annotation`. Nothing else changes.
- **A different ranking model.** `rank_pairs()` takes pairs and an annotator and returns
  scored pairs; the scoring function inside is deliberately simple and inspectable, because
  with one proband and no training data a transparent additive score is defensible in the
  methods form and a tuned black box is not.
- **Variant sources beyond the delivered VCF.** Anything that can produce `Call` objects —
  a DeepVariant re-call, an SV caller, a non-PASS rescue pass — feeds the same pipeline.
  This is how the structural-variant path attaches when it is built.

## The third branch: storage

`warehouse/` is the infrastructure half — how the delivered bytes and the derived tables
get somewhere the team can query them. It has no opinion about variants.

| Module group | Modules | What it does |
|---|---|---|
| **CLI** | `cli.py`, `cli_objects.py`, `cli_source.py`, `cli_vcf.py` | `mva-warehouse`, split so one verb family lives in one module rather than one 1,000-line entry point |
| **Postgres path (live)** | `settings.py`, `catalog.py`, `stage.py`, `postgres.py`, `analysis.py`, `vcfstage.py` | profile → typed Parquet → the `warehouse` schema → derivations into `results` |
| **Object store** | `objects.py`, `source.py` | the bucket, and the delivery inside it |
| **Guarantees** | `integrity.py`, `lineage.py` | fingerprints and provenance edges |

**Path A vs Path B.** The first warehouse was a `.duckdb` file on a box reached over SSH
(Path A). It never ran against a real host: DuckDB's file lock excludes readers as well as
writers, so a shared warehouse needs a real server, and the tooling moved to hosted
PostgreSQL with MinIO alongside for bulk files (Path B). Path A's SSH verbs and `remote.py`
were **deleted 2026-08-29**; `catalog.py` and `stage.py` survive because `pg-ingest`
consumes their Parquet. One paragraph, one link:
[postgres for shared state](notes/postgres-for-shared-state.md).

What the guarantee modules buy:

| Module | Guarantee |
|---|---|
| `integrity.py` | A hop either reproduces the source exactly or fails loudly — row counts, per-column checksums, and NULL vs empty-string accounting, so DuckDB's one lossy case cannot pass silently |
| `lineage.py` | An append-only edge list saying which input produced which output. **Currently a stub** — see [`current-state.md` §5](current-state.md#5-known-gaps) |
| `objects.py` | An object is written once, hashed, and never rewritten in place; the bucket is versioned |
| `source.py` | The delivery is stored as the publisher shipped it and verified against the publisher's own SHA-256 — [delivery is immutable](notes/delivery-is-immutable.md) |

## What is not here yet

No alignment, no re-calling, no SV detection, no normalization step, no real annotator, and
no probe ledger. Two CLIs exist — `mva-explore` and `mva-warehouse` — but the *pipeline*
has none: it is still library-only. See [`roadmap.md`](roadmap.md).
