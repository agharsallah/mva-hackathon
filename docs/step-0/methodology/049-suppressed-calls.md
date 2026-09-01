# 049 — Mining the suppressed calls: the panel's non-PASS census, per gene and per reason

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
census it measured, and one observation about the annotation coverage of non-PASS sites.
The one biological reading it produced is stated as an observation; the register owns
verdicts.

## Question

Every panel derivation in this warehouse is PASS-only by construction — `panel_het_pairs`
says so in its docstring, `candidate_funnel` starts from PASS, the locus explorer colours
the rest red and moves on. Genome-wide that discards **271,414 records**, 5.4 % of the
callset, dominated by `MQ40` and `QD2`
([`ideation/data-findings.md`](../../../ideation/data-findings.md) §3).

That is not obviously safe here. A VCF's `FILTER` column is a text field on a record the
caller **kept**: GATK's `VariantFiltration` writes the name of every threshold the record
failed and leaves the row in the file. `MQ40` fires where reads map ambiguously — repeats,
segmental duplications, subtelomeric sequence — which is exactly where a real variant is
hardest to call. A compound heterozygote needs *two* damaging alleles in one gene, so a
second allele sitting behind a flag makes the gene look like it carries one.

So: **inside the eight-gene candidate panel, what exactly did the caller suppress, under
which reason, and is any of it a plausible hidden second allele?**

## Design decisions

**The FILTER value is the census key, verbatim.** GATK packs every threshold a record
tripped into one `;`-joined string. Splitting `LowQual;QD2` into a `LowQual` count and a
`QD2` count would make the census sum to more records than the panel holds. Keeping the
string whole means a gene's rows stack to its record count exactly, and the `;` is
explained in the legend instead of being normalised away.

**PASS is a row of the census, not a separate table.** The question is a comparison — how
much of this gene is suppressed — so the denominator has to travel with the numerator. One
table, one row per `(gene, FILTER value)`, `is_pass` marking which is which.

**One row per record, so a multi-allelic ALT stays comma-packed.** `variants_raw` keeps
`G → A,C` in one row while `panel_annotations` is one row per ALT. A naive join would turn
one suppressed record into two and inflate the very count the table exists to report. The
record therefore joins **once**, to its most severe annotated ALT (HIGH → MODERATE → LOW →
MODIFIER, ties broken by allele so the pick is deterministic), and `annotated_alt` names
which one the annotation columns describe.

**Annotation is a LEFT join even though it turned out to be total.** See the observation
below: VEP did cover every non-PASS panel allele. The derivation must not depend on that,
so an uncovered record gets `annotated = false` and **null** everywhere — never `false`,
which would read as "looked up and harmless".

**`chr`-strip through the sanctioned path.** The panel BED is `chr`-prefixed and the
callset is bare; the strip is the same `replace(chrom, 'chr', '')` CTE
`mva.warehouse.analysis_pairs` uses, factored into one shared `PANEL_CTE` so the interval
test and the contig pushdown cannot drift apart.

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 rows, every column TEXT, no index |
| `pg.warehouse.mva_panel_grch38` | 8 intervals, `chr`-prefixed, 20 kbp padding per gene |
| `pg.warehouse.panel_annotations` | VEP REST, Ensembl 116, one row per panel ALT allele ([`031`](031-vep-rest-panel-annotation.md)) |
| `src/mva/warehouse/analysis_suppressed.py` | the two derivations, new |
| `src/mva/viz/{routes_warehouse,queries}.py` | `GET /api/panel/suppressed` |
| `app/src/pages/panel/SuppressedCalls.tsx` | the exhibit |

## Commands run

```bash
uv run mva-warehouse pg-check                     # PostgreSQL 18.4, 1339 MB
uv run mva-warehouse pg-derive --only panel_suppressed panel_filter_census
uv run mva-warehouse pg-query "SELECT gene, filter, is_pass, n, n_gene_all, pct_of_gene
                               FROM pg.results.panel_filter_census ORDER BY gene, is_pass DESC, n DESC"
uv run mva-warehouse pg-query "SELECT gene, filter, gt, dp, ad_ref, ad_alt, vaf, is_het,
                                      consequence, impact, gnomad_af, annotated, qual
                               FROM pg.results.panel_suppressed ORDER BY gene, pos"
uv run mva-viz-api --port 8963
curl -s -w '%{time_total}' http://127.0.0.1:8963/api/panel/suppressed
uv run pytest -q
cd app && npm run typecheck && npm run build
```

## Observed output

### The census, as measured

One row per `(gene, FILTER value)` over every record in the panel. 20 rows, 8 genes,
4 distinct FILTER values plus PASS.

| Gene | PASS | MQ40 | QD2 | LowQual | LowQual;QD2 | all | suppressed | PASS % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **TRIP13** | 6 | 5 | 1 | — | — | 12 | **6** | **50.00** |
| BUB1B | 76 | 3 | — | — | 1 | 80 | 4 | 95.00 |
| CENPE | 166 | 1 | 1 | — | 1 | 169 | 3 | 98.22 |
| TP53 | 118 | — | — | 1 | 1 | 120 | 2 | 98.33 |
| CEP192 | 251 | 3 | — | 1 | — | 255 | 4 | 98.43 |
| SMC5 | 124 | — | — | 1 | — | 125 | 1 | 99.20 |
| CEP57 | 13 | — | — | — | — | 13 | 0 | 100.00 |
| DICER1 | 87 | — | — | — | — | 87 | 0 | 100.00 |
| **panel** | **841** | **12** | **2** | **3** | **3** | **861** | **20** | **97.68** |

**The recorded TRIP13 figure reproduces exactly.** `ideation/data-findings.md` §3 and §6
carry "12 variants, 6 of 12 non-PASS, mostly MQ40". Measured here: 12 records, 6
suppressed, 5 of them `MQ40`. No discrepancy.

Two things the table says that the genome-wide numbers do not:

- **The panel is much cleaner than the genome.** 97.68 % PASS inside the panel against
  94.6 % genome-wide. Gene bodies are easier sequence than the genome average.
- **TRIP13 is the whole story.** It carries 30 % of the panel's suppressed records while
  holding 1.4 % of its records, and it is the only gene where the suppressed fraction is
  not a rounding error. That is the same outlier [`048`](048-gene-background.md) measured
  as a −4.02 σ PASS-share z-score, arrived at from the other direction.

### The 20 suppressed records, and what they are

Every one of them is annotated (see below), so the judgement can be made without leaving
the table.

| Reading | Count |
|---|---:|
| Suppressed records in the panel | 20 |
| …heterozygous (`0/1`) | 14 |
| …homozygous ALT (`1/1`) | 6 |
| …VEP impact `MODIFIER` (intronic / non-coding-exon) | 19 |
| …VEP impact `MODERATE` (missense) | 1 |
| …VEP impact `HIGH` | **0** |
| …gnomAD AF below the recessive cut-off (0.01) | 3 |
| …**rare *and* protein-altering** — the candidate shape | **0** |

The single `MODERATE` record is a TRIP13 missense at gnomAD AF **0.324** — a common
polymorphism, not a candidate. All three rare records are intronic `MODIFIER`s. The
remaining 17 sit between AF 0.062 and 0.990.

**Observation, not a verdict: nothing in the panel's suppressed set has the shape of a
hidden causal second allele.** No record is both rare and protein-altering, and none is
`HIGH` impact. TRIP13's six suppressed records are all heterozygous with 2–11 alternate
reads out of 17–48 total (VAF 0.118–0.282), and all six are common in gnomAD — the
signature of reads from a paralogous copy piling onto one locus, which is precisely what
`MQ40` exists to flag. If a second allele is missing from this case, the FILTER column is
not where it is hiding; that pushes the search toward structural variation and re-calling
the FASTQ, which the callset cannot answer either (`data-findings` §2.3).

### VEP did see the suppressed sites

`mva.warehouse.annotate.alleles()` selects `SELECT DISTINCT chrom, pos, ref, alt` over the
panel intervals with **no FILTER predicate** — so [`031`](031-vep-rest-panel-annotation.md)
annotated non-PASS alleles alongside PASS ones. Confirmed against the data rather than
against the code: all **20 of 20** suppressed panel records join to a `panel_annotations`
row. The derivation still carries the LEFT join and the `annotated` flag, because that is a
property of this run, not of the contract.

### Cost

| Operation | Cost |
|---|---|
| `pg-derive --only panel_suppressed panel_filter_census` | **14.4 s** for both, 20 rows each |
| `pg-derive --only panel_filter_census` alone | 11.4 s |
| `GET /api/panel/suppressed` (whole panel) | **0.71–0.75 s**, 9,169 B |
| `GET /api/panel/suppressed?gene=TRIP13` | 1.65 s cold, ~0.7 s after |

Both derivations scan `variants_raw`, which is why they are derivations: the endpoint
reads two 20-row tables and never touches the callset.

## What was built

| File | Concern |
|---|---|
| `src/mva/warehouse/analysis_suppressed.py` | `panel_suppressed` + `panel_filter_census`, registered in `analysis.py` |
| `src/mva/viz/queries.py` | `panel_suppressed()`, `panel_filter_census()` |
| `src/mva/viz/routes_warehouse.py` | `GET /api/panel/suppressed?gene=` |
| `src/mva/viz/catalog_columns_results.py` | column meanings for both new tables |
| `app/src/api/types/panel.ts` | `PanelFilterCensusRow`, `PanelSuppressedRecord`, `PanelSuppressed` |
| `app/src/api/hooks.ts` | `usePanelSuppressed` |
| `app/src/fixtures/panel-suppressed.ts` | measured census, synthetic record positions |
| `app/src/pages/panel/SuppressedCalls.tsx` | the exhibit: two-panel stacked bar + record table |
| `tests/test_warehouse_suppressed.py` | 24 tests, hermetic DuckDB |
| `tests/test_viz_suppressed.py` | 13 tests, `queries.fetch` mocked |

**Test delta:** +37. `uv run pytest -q` green apart from the 11 pre-existing
`tests/test_reads_api.py` failures. `npm run typecheck` and `npm run build` green.

**The record endpoint's payload carries real patient positions**, like `/api/panel/locus`.
The exhibit therefore hands the AI export the **census only**; the record table declares no
`data`, so no coordinate can leave the browser through that channel.

## Conclusion

The suppressed set inside the candidate panel is **20 records**, and it is now a first-class
surface rather than a filtered-out remainder: one derivation per grain, one endpoint, one
exhibit that puts PASS beside every suppression reason per gene.

The measurement it produced is a negative one, and it is worth as much as a positive would
have been. TRIP13's 50 % suppression rate is real and reproduces the recorded figure
exactly — but all six of its suppressed calls are common gnomAD polymorphisms with thin
alternate support in hard-to-map sequence, which is a **callability** statement, not
evidence of a hidden allele. Nothing in the panel's suppressed set is both rare and
protein-altering. Re-running these two derivations is the cheap way to re-check that after
any change to the panel or the annotation.
