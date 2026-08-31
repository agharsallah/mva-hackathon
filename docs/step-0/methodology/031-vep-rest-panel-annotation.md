# 031 — The annotator port, wired: Ensembl VEP REST over the candidate panel

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
format facts that were probed live before any batch code was written, and what the first
real run measured. The one biological observation it produced is stated as an observation,
not a verdict — the register owns verdicts.

## Question

[`docs/notes/annotation-as-a-port.md`](../../notes/annotation-as-a-port.md) left the
annotation backend deliberately open: the port exists, `DictAnnotator` fakes it, nothing
real is behind it. The callset itself cannot fill the gap — its `INFO/AF` is *within-sample*
(0.5 or 1.0 for one person), so reading it as a population frequency is a silent, serious
error.

Can a REST-backed annotator satisfy the existing `Annotator` protocol, annotate every
allele in the candidate panel, and land the answer in the warehouse with lineage — without
a multi-gigabyte offline VEP cache, and without any test depending on the network?

## Inputs

| Input | Version / shape |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 rows, every column TEXT, no index |
| `pg.warehouse.mva_panel_grch38` | 8 intervals, `chr`-prefixed, 20 kbp padding per gene |
| `pg.warehouse.panel_variant_counts` | 8 rows, the count this run has to agree with |
| `https://rest.ensembl.org` | Ensembl release **116**, assembly **GRCh38**, `GCA_000001405.29` |
| `src/mva/pipeline/annotation.py` | the pre-existing `Annotator` protocol, unchanged |
| httpx 0.28 | already a dependency; `MockTransport` is what makes the tests hermetic |

## What was built

| File | Concern |
|---|---|
| `src/mva/pipeline/vep_response.py` | pure parsing: one JSON result object → one `VepRecord` |
| `src/mva/pipeline/annotate_vep.py` | `VepRestAnnotator` — transport, batching, retry policy |
| `src/mva/warehouse/annotate.py` | which alleles to ask about, and where the answers land |
| `src/mva/warehouse/cli_annotate.py` | the `annotate-panel` verb, with `--dry-run` |
| `tests/test_annotate_vep.py` | 50 tests, no network |

The parse is split from the transport so the whole meaning-extraction path is testable
against a decoded dict — no mock server, no recorded cassette, no fixture replay harness.

## The live format probe, run before any batch code

Three `curl` calls against the real service. Each one settled a question that a guess would
have got wrong.

```bash
curl -s 'https://rest.ensembl.org/info/assembly/homo_sapiens?content-type=application/json'
# default_coord_system_version: GRCh38   assembly_accession: GCA_000001405.29
# karyotype: ["1", ... ,"22","X","Y","MT"]   <- BARE contigs, no chr prefix

curl -s 'https://rest.ensembl.org/info/software?content-type=application/json'
# {"release":116}

curl -s -X POST 'https://rest.ensembl.org/vep/homo_sapiens/region' \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -d '{"variants":["17 7676154 . G C . . ."],"af_gnomadg":1,"af_gnomade":1}'
```

Five facts came out of it, all of which shaped the code:

1. **The accepted line is VCF-shaped and 8 fields long**: `<chrom> <pos> <id> <ref> <alt>
   <qual> <filter> <info>`. The contig is **bare** — the same convention as the proband
   callset, and the opposite of the panel BED.
2. **Results come back unordered**, but every object echoes the exact query line in
   `input`. That string, not the list index, is the join key. Matching by position would
   have silently mis-assigned annotations.
3. **Without `af_gnomadg`/`af_gnomade` there are no frequencies at all** — the
   `colocated_variants` block carries identifiers and clinical calls but no numbers. The
   rarity signal the ranker needs would have come back uniformly empty.
4. **Frequencies are keyed by VEP's own allele spelling, not the VCF ALT.** A `CTT>C`
   deletion is keyed `"-"`. `vep_allele()` reproduces that spelling; without it every
   indel would report "absent from gnomAD", which is exactly the signal a rare-disease
   ranker is most sensitive to.
5. **`clin_sig` is per *variant*; `clin_sig_allele` is per *allele*.** At one probed site
   the list reads `[uncertain_significance, benign, likely_benign, pathogenic]` while the
   per-allele field assigns *benign* to the allele actually queried. Reporting the site
   list against every allele would manufacture pathogenic calls.

A sixth was checked and then designed around: a comma-packed ALT (`G` → `A,C`) is accepted
as **one** query and returns **one** merged consequence belonging to neither allele. So the
warehouse splits ALT before querying — one request line per allele.

Rate-limit headers observed on every reply: `x-ratelimit-limit: 55000`,
`x-ratelimit-period: 3600`, `x-ratelimit-remaining` counting down. A 5-request run is not
close to that ceiling, but the client honours `Retry-After` on 429 regardless.

## Commands run

```bash
uv run mva-warehouse pg-check
# connected. PostgreSQL 18.4 (Debian 18.4-1.pgdg12+1), size 1330 MB

uv run pytest -q
# 643 passed, 11 failed  (the 11 are pre-existing failures in tests/test_reads_api.py,
#  reproduced on a clean tree with `git stash`; none are in this work)

time uv run mva-warehouse annotate-panel --dry-run
time uv run mva-warehouse annotate-panel
```

## Observed output

### The dry run

```
panel    8 intervals
  BUB1B   15:40,140,984-40,241,137  (100,154 bp)
  CENPE    4:103,085,349-103,218,463  (133,115 bp)
  CEP192  18:12,971,283-13,145,053  (173,771 bp)
  CEP57   11:95,769,965-95,857,070  (87,106 bp)
  DICER1  14:95,066,228-95,178,010  (111,783 bp)
  SMC5     9:70,238,270-70,374,874  (136,605 bp)
  TP53    17:7,641,779-7,707,546  (65,768 bp)
  TRIP13   5:872,849-939,357  (66,509 bp)

alleles  874 distinct, after splitting multi-allelic ALT
batches  5 request(s) of up to 200
```

Wall clock **51.9 s**, all of it the single `variants_raw` scan.

The 874 reconciles with `panel_variant_counts`, which is what makes it trustworthy: that
table's `n_all` sums to **861 sites**, and 874 − 861 = **13 extra ALT alleles** contributed
by multi-allelic sites. Every contig in the plan is printed bare, which is the visible
proof the BED's `chr` prefix was stripped on the way in.

### The live run

```
source   ensembl-vep-rest release=116 assembly=GRCh38 (GCA_000001405.29)
wrote    874 rows into warehouse.panel_annotations
  with a consequence   874
  with a gnomAD AF     863
  with a grpmax AF     863
  with a ClinVar call  56
  with an rsID         863
  distinct genes       18
```

| Measure | Value |
|---|---|
| Alleles sent | 874 |
| Alleles annotated (non-null consequence) | 874 — **100%** |
| HTTP requests | 7 (5 VEP batches + 2 version lookups) |
| Retries / 429s / 5xx | 0 |
| Wall clock, end to end | **2 min 44 s** (≈ 52 s of it the warehouse scan) |
| Rows with a gnomAD AF | 863 |
| Rows with a gnomAD grpmax AF | 863 |
| Rows with a ClinVar significance | 56 |
| Rows with an rsID | 863 |
| Rows with **no** gnomAD entry (novel) | 11 |

### Consequence and impact distribution

| Impact | n | | Consequence (top) | n |
|---|---|---|---|---|
| MODIFIER | 850 | | `intron_variant` | 542 |
| MODERATE | 13 | | `intergenic_variant` | 91 |
| LOW | 9 | | `upstream_gene_variant` | 85 |
| HIGH | **2** | | `downstream_gene_variant` | 39 |
| | | | `3_prime_UTR_variant` | 37 |
| | | | `non_coding_transcript_exon_variant` | 34 |
| | | | `5_prime_UTR_variant` | 19 |
| | | | `missense_variant` | 13 |
| | | | `synonymous_variant` | 6 |
| | | | `stop_gained` | **1** |

### 18 genes from an 8-gene panel — expected, not a bug

The BED carries **20 kbp of padding** per gene, and that padding reaches the neighbours.
The extra symbols are `ATP1B2`, `BDH2`, `BRD9`, `DICER1-AS1`, `FAM76B`, `MAMDC2-AS1`,
`MTMR2`, `PAK6`, `SEH1L`, `WRAP53` — every one of them a real gene adjacent to a panel
gene (`WRAP53` and `ATP1B2` flank `TP53`; `DICER1-AS1` is `DICER1`'s antisense partner).
A further **145 rows carry no gene at all**: they are intergenic or regulatory hits inside
the padding, and reporting the nearest gene there would be a guess the ranker could not
distinguish from a fact.

The panel-gene tie-break did its job where it applies: at a position covered by both a
panel transcript and a neighbour's, the panel gene is the one reported.

## One observation worth carrying into step 1

Filtering the table to *protein-altering and rare* — `impact IN ('HIGH','MODERATE')` and
`gnomad_af IS NULL OR gnomad_af < 0.01` — reduces 874 alleles to **two rows, both in
`BUB1B`**:

| Gene | Consequence | Impact | gnomAD AF | grpmax | ClinVar | Genotype | FILTER |
|---|---|---|---|---|---|---|---|
| BUB1B | `stop_gained` | HIGH | 3.286e-05 | 7.35e-05 | `pathogenic;likely_pathogenic` | `0/1` | PASS |
| BUB1B | `missense_variant` | MODERATE | *absent from gnomAD* | — | none | `0/1` | PASS |

(The genotype and FILTER columns come from a join back to `variants_raw`, run after the
annotation, not from VEP.)

`BUB1B` is the MVA1 gene. Two rare protein-altering alleles in it, **both heterozygous,
both PASS** — one a ClinVar-classified nonsense allele, one absent from gnomAD entirely —
is exactly the shape a compound heterozygote makes. **This entry does not claim it is the
answer.** Phase is not established: `0/1` at two sites is consistent with *trans* (one
allele from each parent, causal) and with *cis* (both on the same chromosome, not causal),
and only read-level phasing or a parental sample separates them. The claim belongs in the
hypothesis register with a prediction and a refutation condition before it is tested. It is
recorded here because it is what the run measured.

No genomic position appears anywhere in this entry, per the repository rule. The positions
are in `warehouse.panel_annotations`, which is private.

## The table as created

`warehouse.panel_annotations`, 874 rows, `CREATE OR REPLACE` like every other ingest:

| Column | Type | Note |
|---|---|---|
| `chrom` | `character varying` | **bare** contig — joins to `variants_raw` with no conversion |
| `pos` | `bigint` | typed here; the raw layer keeps it text |
| `ref` | `character varying` | |
| `alt` | `character varying` | one row per ALT allele, never comma-packed |
| `rsid` | `character varying` | dbSNP only, filtered out of a mixed identifier list |
| `gene` | `character varying` | null where the hit is intergenic |
| `consequence` | `character varying` | VEP's `most_severe_consequence` |
| `impact` | `character varying` | HIGH / MODERATE / LOW / MODIFIER, from the picked transcript |
| `gnomad_af` | `double precision` | gnomAD **genomes**, exomes as fallback |
| `gnomad_af_grpmax` | `double precision` | max over afr/amr/eas/nfe/sas |
| `clin_sig` | `character varying` | `;`-joined; null, not `''`, when absent |
| `annotated_at` | `timestamp without time zone` | one instant for the whole run |
| `source` | `character varying` | `ensembl-vep-rest release=116 assembly=GRCh38` |

Lineage edge appended to `warehouse.data_lineage`:

```
target_table   panel_annotations          target_rows  874
source_kind    api
source_ref     https://rest.ensembl.org/vep/homo_sapiens/region
source_version ensembl-vep-rest release=116 assembly=GRCh38
transform      annotate-panel: distinct ALT-split alleles inside the 8 panel intervals,
               annotated by Ensembl VEP REST
tool           mva-warehouse annotate-panel
notes          genes: BUB1B, CENPE, CEP192, CEP57, DICER1, SMC5, TP53, TRIP13; requests: 7
```

## Conclusions

1. **The port survived contact with a real backend.** `VepRestAnnotator` satisfies the
   protocol as written — no change to `annotation.py`, so every ranking test that runs
   against `DictAnnotator` runs against this unchanged. The wider record (`VepRecord`) is a
   *separate* type the warehouse consumes, precisely so the ranker's contract stays narrow.
2. **Probe the format, do not assume it.** Four of the five facts in the probe section
   would have produced a plausible-looking, silently wrong table: results matched by
   position, indels reported as novel, every allele tagged with the site's worst clinical
   call, and no frequencies at all. None of them would have raised an exception.
3. **A REST backend is the right tool at panel scale and the wrong one at genome scale.**
   874 alleles cost 5 requests and under three minutes. 5,012,204 would cost 25,062
   requests against a 55,000/hour budget — feasible only just, and fragile. The offline
   cache is still the answer for a genome-wide run, and the port is why swapping it in is
   a swap.
4. **The scan dominates, not the API.** 52 s of the 164 s was the single `variants_raw`
   pass; VEP answered 874 alleles in the remainder. Any future re-annotation should reuse
   the allele list rather than re-scan.
5. **The chr-prefix bridge held under a third direction of pressure.** BED is `chr15`, the
   callset is `15`, the submission is `chr15`, and Ensembl is `15`. All four conversions go
   through the two functions in `src/mva/pipeline/variant.py`; nothing in the new code
   builds a contig string by hand, and a test asserts the query line comes out bare.
