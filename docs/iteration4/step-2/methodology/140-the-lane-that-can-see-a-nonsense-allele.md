# 140 — The lane that can see a nonsense allele

**Written:** 2026-09-20. **Step:** `step-2` (iteration 4). **Run:** G1/A2 of wave 4 (opt-A).
**Hypotheses tested:** H068.

The promotion that has been owed since [entry 114](../../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md):
`BUB1B` carries exactly one `missense_variant` and one `stop_gained`, three of the four MVP
lanes are missense-only and the fourth is splice, so **no MVP lane can score half the
confirmed answer**. Plan §10 R9 pre-registered the fix — promote GPN-MSA — and open question
O7 recorded it as due. This is that run.

## Question

Can a lane that keys on the genomic change itself be fetched, joined and scored on this
laptop without downloading a 37 GB file, without a coordinate ever entering Python, and with
enough coverage to give the zoo its first opinion on a nonsense allele?

## Hypothesis and prediction

*Written before the fetch. Filed as H068 before the run
(`mva-science hypothesis-add --iteration iteration4 --step step-2`).*

| | |
|---|---|
| **Statement** | GPN-MSA's published all-possible-SNV table covers the iteration-4 record set's SNV alleles, including both confirmed `BUB1B` alleles, so the zoo gains its first lane that can score a nonsense allele. |
| **Prediction** | A tabix subset of `songlab/gpn-msa-hg38-scores` joined to the record set scores **at least 99 %** of the single-nucleotide alleles, and both confirmed `BUB1B` alleles — the missense one and the `stop_gained` one — carry a score. |

## What would refute it

*Written before the run.*

> SNV coverage below **90 %**, or either confirmed `BUB1B` allele missing from the subset.

Coverage of the *whole* record set is not the test and was never predicted: an
all-possible-**SNV** table has no row for an insertion or a deletion, and reporting that gap
as a failure would be measuring the wrong thing. The number it is judged on is coverage of
the alleles the table could in principle answer for.

## Inputs

| input | what it is |
|---|---|
| `build/it4/records.parquet` | 39,286 allele records (entry 114), of which **35,917 are SNVs** at **35,881 distinct positions** |
| `https://huggingface.co/datasets/songlab/gpn-msa-hg38-scores` | `scores.tsv.bgz`, **37,274,961,495 bytes**, ETag `eb0b78fc…f32f60d`; `scores.tsv.bgz.tbi`, 2,782,844 bytes, sha256 `6b5241c207be318d…`. Sizes and ids read from the HF tree API before the fetch, never from the dataset page's prose |
| licence | **MIT**, from the dataset card's own YAML front-matter. The shared roster said "check on fetch"; this is the check, and `models.d/gpnmsa.toml` overrides the placeholder |
| tool | `tabix` (htslib) on the PATH; `tools/fetch_zoo_tables.py --subset-from`; `mva.zoo.tabix_plan` + `mva.zoo.tabix_subset`; lane `mva.zoo.adapters.coordinate_table` |

## Why this is not a download

Plan §10 R7 forbids pulling whole genome-scale tables. The record set asks about 35,881
positions — 0.001 % of the file's rows. A **bgzipped TSV** (a text table compressed in
independently-decompressable blocks) with a **tabix index** (a side file mapping genomic
position → byte range) is exactly the shape that allows HTTP range reads instead.

Two numbers decided the shape of the fetch, both measured before it ran:

- **one remote seek costs ~0.3 s whatever it returns** — 300 single-position regions took
  96 s serially, 300 regions merged at a 1,000-base gap took 131 s for 107,268 rows. The
  cost is the seek, not the bytes;
- **merging neighbours is therefore almost free**: 35,881 positions collapse to **21,722
  regions spanning 3,105,436 bases**, 0.1 % of the genome. 39 % fewer seeks.

Four parallel workers measured **1.8×** one worker, so the fan-out is 6–8 wide.

## Commands

```bash
uv run python tools/fetch_zoo_tables.py --fetch gpnmsa \
    --subset-from build/it4/records.parquet          # dry run: prints the plan
uv run python tools/fetch_zoo_tables.py --fetch gpnmsa \
    --subset-from build/it4/records.parquet --execute --jobs 6 --rounds 12
uv run mva-zoo coverage --model gpnmsa
uv run mva-zoo score --model gpnmsa --config src/mva/zoo/zoo.example.toml
```

## What happened — three attempts, and why the first two ended

| attempt | wall clock | rows | how it ended |
|---|---|---|---|
| 1 (`--jobs 8`) | 3 h 13 m 23 s | 3,400,074 | **all eight workers dead at once**: `Operation timed out` |
| 2 (`--jobs 8`) | ~4 min | +2,065,680 | same, plus `Failed to read BGZF header at offset …` |
| 3 (`--jobs 6 --rounds 12`) | round 1 **4,521 s**, round 2 **6 s** | **9,316,308** | round 2 found **0 regions left** — complete |

The cause of attempt 1 is in the argv the error printed: an `Expires` policy and a
`Signature`. Hugging Face answers `/resolve/main/<file>` with a redirect to a *signed* CDN
URL; the fetch resolved that redirect once because doing so measured ~25 % faster per seek,
and htslib re-opens the file on **every** seek. The signature outlived neither the run nor
its own clock. Two fixes, both committed before attempt 3:

- the workers are handed the **un**-redirected URL and let the redirect re-sign on each open
  (`1639018`);
- the fetch **resumes** — finished shard output is promoted to `scores.part-NNN.tsv`, the
  positions those parts hold are subtracted from the plan, and a part killed mid-write is
  truncated to its last complete line (`1639018`) — and `--rounds N` repeats that until
  nothing is left or a whole round adds no rows (`abf4c7a`).

After attempts 1 and 2 the subset held **20,495 of 35,881 wanted positions (57.1 %)**. Attempt
3 asked for the 9,819 regions still missing and finished them.

## Results

```
9,316,308 rows -> build/it4/tables/gpnmsa.parquet   (39,793,357 bytes)
subset sha256 ce88426b07b2a02bdebcd1a5e43c24cd5c1c3fbcedaf5f6d6b230b9d2bf4a6d4
```

| measurement | value |
|---|---|
| wanted positions covered | **35,881 / 35,881 = 100.0 %** |
| **SNV alleles scored** | **35,917 / 35,917 = 100.0 %** |
| whole record set | 35,917 / 39,286 = **91.4 %** — the 3,369 shortfall is every indel, exactly |
| missense | 15,547 / 15,620 = **99.5 %** |
| `stop_gained` | **278 / 289 = 96.2 %** — *no other lane in the zoo scores any of these* |
| synonymous | 12,034 / 12,036 = 100.0 % |
| intron | 4,274 / 5,490 = 77.9 % |
| frameshift / inframe indels | **0** of 564 / 277 / 211 — an all-SNV table has no such row |
| confirmed missense allele (`p.Asn1002Lys`) | scored, **8.13** after the sign flip |
| confirmed nonsense allele (`p.Leu737Ter`) | scored, **6.04** after the sign flip |
| cached | `inserted 35,917, skipped 0`, run `20260920T103147Z-0397`, mode `catalogue-free` |

Both confirmed alleles are scored by one lane for the first time in this iteration. Iteration
4's earlier finding — "only SpliceAI sees both halves of the confirmed pair" (entries 122,
128) — no longer holds.

## Verdict

**H068 supported** (confidence 0.95, committed with a stated reason).

The prediction asked for ≥ 99 % of SNV alleles and both confirmed alleles; the measurement is
100.0 % and both. The refutation clause — under 90 %, or either confirmed allele missing —
did not fire on either arm.

## Assumptions, limitations and what was checked

- **The digest is of the subset, not of the upstream file.** 37 GB was never downloaded, so
  hashing it is not possible here. What is pinned instead: the index's sha256, the upstream
  size and ETag from a `HEAD`, the subset's own sha256, and the row and region counts — all
  in `build/it4/tables/gpnmsa.subset.provenance.json`. A reader who wants the upstream digest
  must download 37 GB; a reader who wants to know *these* bytes are the bytes that scored has
  everything needed.
- **The subset is patient-derived by its selection**, though every row in it is public data:
  which regions were asked for is a fact about the callset. It therefore lives under
  `build/it4/` with the records, and the provenance file says so.
- **The coordinate never enters Python.** The lane computes `allele_id` in SQL over the
  *published* table's own `chrom/pos/ref/alt` with `adapters.allele_id_sql`, the same
  expression the record set was keyed by, and joins on the id. `tests/test_zoo_adapters.py`
  already asserts that expression equals `types.allele_id` row by row;
  `tests/test_zoo_coordinate_table.py` asserts the lane's scored ids equal
  `allele_id(...)` computed in Python over the table's rows.
- **Score orientation was checked, not assumed.** GPN-MSA publishes a number that is more
  negative for a more deleterious change (the dataset card's own worked example runs −1.12 to
  −1.83 across a conserved exon). `score_sign = -1` flips it into the zoo's one convention,
  higher = more damaging; both confirmed alleles come back positive, as a damaging change
  must under that convention. Entry 119 records the cost of getting this wrong: applying the
  sign twice made a damaging change look benign, silently.
- **Coverage is not accuracy.** A score for every SNV says nothing about whether the ranking
  is right. Where the confirmed pair lands under this lane is step 4's measurement, and the
  RRF consequence is step 6's.
- **A conservation model scores a region, not a consequence.** GPN-MSA is trained on a
  multi-species alignment, so it will score a synonymous change in a conserved exon highly.
  That is a property of the instrument and the reason the merge keeps lanes separate rather
  than averaging them.
