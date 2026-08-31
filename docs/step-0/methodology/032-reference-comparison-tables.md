# 032 — The comparison tables: staging the public reference into the warehouse

**A step-0 platform entry, so it carries no hypothesis.** It records how the three public
reference tables from [030](030-population-reference-data.md) were staged, what three
derivations joined them to the delivery, and the numbers those joins produced. The
biological readings at the end are stated as observations, not verdicts — the register
owns verdicts.

## Question

[030](030-population-reference-data.md) put three public tables on disk and
[031](031-vep-rest-panel-annotation.md) put 874 VEP answers in the warehouse. Neither is
yet joined to anything. Can the reference tables be staged and ingested through the
**existing** catalog → stage → `pg-ingest` path, and can three derivations turn them into
comparison tables the browser can read without a whole-genome scan at request time?

## Inputs

| Input | Version / shape |
|---|---|
| `ressources/reference/gnomad_constraint.tsv` | 18,314 rows, 26 columns, `chr`-prefixed contigs, `NA` as null |
| `ressources/reference/clinvar_panel.tsv` | 17,832 rows, 10 columns, bare contigs, `''` as absent |
| `ressources/reference/qc_norms.tsv` | 20 rows, 8 columns, hand-curated, every row cited |
| `pg.warehouse.panel_annotations` | 874 rows, one per (site, ALT), from [031](031-vep-rest-panel-annotation.md) |
| `pg.warehouse.variants_raw` | 5,012,204 rows, every column TEXT, no index |
| `pg.warehouse.mva_panel_grch38`, `panel_variant_counts`, `stats_summary`, `filter_gt_counts`, `profile_scalars` | as ingested |
| Server | PostgreSQL 18.4 (Debian), database 1330 MB before the run |

## What was built

Three code decisions, all made to avoid a second staging path.

1. **`Dataset` gained `root` and `transform`** (`src/mva/warehouse/catalog.py`). `root`
   pins a spec to its own directory, so one staging run draws from the profile directory
   *and* from `ressources/reference/`. `transform` is a SQL select list applied before
   Parquet is written; when set, the file is read **all-VARCHAR** and every cast is
   written down. That is the only way to say "`NA` here is a null" and "strip the `chr`
   prefix" — a CSV sniffer cannot know either, and reading `NA` as text silently turns
   every constraint metric into a string.
2. **`src/mva/warehouse/reference.py`** holds the three specs, their transforms and their
   lineage edges together, so a table cannot reach the database without the upstream URL
   and release that produced it. `pg-ingest` appends the edges itself.
3. **The derivation registry was split** into `analysis.py` (the delivery) and
   `analysis_reference.py` (the comparisons), over a shared `derivation.py`, keeping every
   module under the 400-line rule and the registry single. The new derivations read the
   **ingest schema only** — `qc_observed_expected` therefore re-parses `stats_summary`
   itself rather than reading `results.stats_sn`, because `pg-derive` has no ordering
   guarantee between derivations.

## Commands run

```bash
uv run mva-warehouse stage
#   gnomad_constraint          18,314 rows  26 cols  1,184,944 B
#   clinvar_panel              17,832 rows  10 cols    215,252 B
#   qc_norms                       20 rows   8 cols      5,810 B
#   staged 18 tables total into build/warehouse

uv run mva-warehouse pg-ingest --tables gnomad_constraint clinvar_panel qc_norms \
                               warehouse_catalog
#   clinvar_panel       17,832 rows
#   gnomad_constraint   18,314 rows
#   qc_norms                20 rows
#   lineage edges appended to warehouse.data_lineage for
#   clinvar_panel, gnomad_constraint, qc_norms

time uv run mva-warehouse pg-derive --only panel_gene_constraint   #    8 rows,  3.7 s
time uv run mva-warehouse pg-derive --only panel_candidates        #  874 rows,  3 m 52 s
time uv run mva-warehouse pg-derive --only qc_observed_expected    #   12 rows,   60 s
```

Then the service, from the repository root:

```bash
uv run mva-viz-api --port 8911
curl -s http://127.0.0.1:8911/api/panel/constraint            # 200, 0.54 s
curl -s http://127.0.0.1:8911/api/callset/observed-expected   # 200, 0.51 s
curl -s http://127.0.0.1:8911/api/panel/annotations           # 200, 0.57 s, 874 rows
curl -s "http://127.0.0.1:8911/api/panel/annotations?gene=BUB1B"    # 200, 17 rows
curl -s "http://127.0.0.1:8911/api/panel/annotations?gene=NOTAGENE" # 404
uv run pytest -q   # 702 passed, 11 failed (all pre-existing, tests/test_reads_api.py)
```

## Observed output

### Staging typed the files the way the file actually is

Every property [030](030-population-reference-data.md) measured in the raw TSVs is
reproduced by the staged Parquet, which is the check that the transform matches the file
rather than a guess about it:

| Property 030 measured | Staged Parquet |
|---|---|
| 275 rows with `gene == NA` | 275 rows with `gene IS NULL`, 0 rows with `gene = 'NA'` |
| 445 rows with no `loeuf_decile` | 445 nulls |
| 22 contigs, autosomes only | 22 distinct, **0** matching `chr%` |
| 373 ClinVar rows with empty `clnsig` | 373 nulls, 0 empty strings |
| longest ClinVar `ref` = 7,027 characters | `max(length(ref))` = 7,027, column `VARCHAR` |
| 4,442 ClinVar rows with no rsid | 4,442 nulls |

`loeuf`/`pli` land as `DOUBLE`, `lof_obs`/`cds_length`/`pos`/`variation_id` as `BIGINT`,
`mane_select`/`canonical` as `BOOLEAN`.

### `results.panel_gene_constraint` — 8 rows

| gene | n_all | n_pass | LOEUF | pLI | ClinVar P/LP | VUS | benign |
|---|---|---|---|---|---|---|---|
| DICER1 | 87 | 87 | **0.275** | 1.000 | 860 | 3,872 | 2,707 |
| TP53 | 120 | 118 | **0.449** | 0.998 | 1,147 | 958 | 1,165 |
| CENPE | 169 | 166 | **0.451** | 0.9996 | 5 | 302 | 245 |
| TRIP13 | 12 | 6 | **0.592** | 0.192 | 9 | 84 | 136 |
| CEP192 | 255 | 251 | **0.610** | 3.3e-11 | 0 | 316 | 42 |
| BUB1B | 80 | 76 | **0.707** | 2.6e-14 | 84 | 1,486 | 844 |
| SMC5 | 125 | 124 | **0.716** | 1.7e-10 | 5 | 119 | 12 |
| CEP57 | 13 | 13 | **0.740** | 6.8e-06 | 19 | 623 | 305 |

Every ClinVar count reproduces the per-gene table in
[`ressources/reference/README.md`](../../../ressources/reference/README.md), which was
computed by a different tool on the raw file. That is an independent confirmation of the
significance predicate, which is the part most likely to be wrong: `clnsig LIKE
'%athogenic%' AND clnsig NOT LIKE '%Conflicting%'`. It has to be a substring test, because
the assertion arrives as `Pathogenic`, `Likely_pathogenic`,
`Pathogenic/Likely_pathogenic`, `Pathogenic|Affects` and
`Pathogenic/Likely_pathogenic/Pathogenic,_low_penetrance`; and the exclusion has to be
there, because `Conflicting_classifications_of_pathogenicity` contains the same substring
and is the opposite of an assertion. All 13 distinct values in the extract are covered by
a parametrised test.

Gene symbol is not a key in gnomAD, so the derivation picks the **MANE Select** transcript
per symbol and falls back to the lowest transcript id. All 8 panel genes resolved to the
transcript 030 recorded.

### `results.panel_candidates` — 874 rows

Every one of the 874 annotations matched a callset record: **0 rows with a null genotype**.
That is the check that the ALT join is right. `variants_raw` keeps a multi-allelic site
comma-packed in one row while the annotations are one row per ALT, so the join tests
`list_contains(str_split(alt, ','), a.alt)` — element membership, not substring, which
would match `A` against `AT`. GT and DP are located with `list_position` over the record's
own `FORMAT` keys, never by position: the callset carries at least `GT:AD:DP:GQ:PL`, and a
record whose FORMAT is ordered differently would otherwise yield the depth as the genotype.

| Measure | Value |
|---|---|
| rows | 874 |
| rows with no matching callset record | **0** |
| distinct genes | 18 (8 panel + 10 flanking, from the 20 kb padding VEP annotates into) |
| rows with `gene IS NULL` | 145 — VEP returned no symbol; intergenic inside the padding |
| `vaf IS NULL` (multi-allelic `1/2` sites) | 26 |
| `is_rare_recessive` (AF null or < 0.01) | 35 |
| `is_protein_altering` (impact HIGH or MODERATE) | 15 |

The rarity flag uses **1e-2**, from `qc_norms.rare_af_threshold_recessive`, not 1e-3.
Both rows are in the norms table and they are different models: 1e-3 is the *de novo /
autosomal-dominant* cutoff, and applying it to a compound-heterozygous search can drop a
real allele (Pedersen 2021, PMID 34267211).

### `results.qc_observed_expected` — 12 rows

| metric | observed | expected | verdict |
|---|---|---|---|
| `tstv_genome_wide` | 1.94 | 2.0 – 2.1 | **below** |
| `variant_sites_per_genome` | 5,012,204 | 4.10 M – 5.00 M | **above** |
| `snv_per_genome` | 4,086,641 | 3.53 M – 4.31 M | within |
| `snv_per_genome_30x` | 4,086,641 | 3.82 M – 4.65 M | within |
| `indel_per_genome` | 930,181 | 546 k – 625 k | **above** |
| `indel_per_genome_30x` | 930,181 | 826 k – 970 k | within |
| `insertion_deletion_ratio` | 0.977 | 0.924 – 0.936 | **above** |
| `het_hom_ratio_eur` | 1.605 | 1.5 – 1.6 | **above** |
| `het_hom_ratio_afr` | 1.605 | 1.9 – 2.0 | **below** |
| `het_hom_ratio_amr` | 1.605 | 1.3 – 1.7 | within |
| `dbsnp_membership_rate_per_genome` | 87.96 % | 99.2 % | **below** |
| `mean_coverage_wgs` | 51.9 × | 35 × | **above** |

**8 of the 20 norms were skipped**, each because the callset carries no counterpart, and
each skipped rather than guessed: `tstv_coding` (no exonic subset has been computed),
`structural_variants_per_genome` (a short-variant VCF has no SV calls),
`dbsnp_concordance_across_publications` (a cross-study spread, not a property of one
callset), `de_novo_snv_indel_per_genome` and `candidate_variants_per_wgs_trio` and
`candidate_comp_het_per_wgs_trio` (all trio metrics; this is a singleton), and
`rare_af_threshold_recessive` / `rare_af_threshold_dominant` (filter parameters, not
measurements — they are *consumed* by `panel_candidates` instead).

Two rows need their caveat carried with them. `mean_coverage_wgs` is measured from
`profile_scalars.est_raw_coverage_x`, which is a **yield-based, pre-alignment** estimate
(total FASTQ bases over genome size), not aligned mean depth; against a project-median
norm it reads high partly for that reason. The three `het_hom_ratio_*` rows share one
observation compared against three ancestry-specific ranges, because the proband's genetic
ancestry has not been inferred — the row that applies is not yet known, so all three are
shown.

### Lineage

Six new edges in `warehouse.data_lineage`: three `source_kind = 'file'` naming the
`ressources/reference/*.tsv` path, the upstream URL and release in `notes`, and the gnomAD
SHA-256 in `source_sha256`; three `source_kind = 'table'` written by `pg-derive`, each
naming its ingest-schema inputs and its `derivation_runs.run_at`.

### API

Three endpoints, all live (no cache), all in the standard `{data, cached_at, source}`
envelope, all under 0.6 s against the hosted database:
`/api/panel/constraint` (8 rows, with `ensembl_id`/`note` merged from the panel BED),
`/api/panel/annotations?gene=` (874 rows, or 17 for BUB1B; unknown gene → 404), and
`/api/callset/observed-expected` (12 rows). Contract detail in
[`../viz-api.md`](../viz-api.md).

## Conclusion

The existing staging path absorbs the public reference with two additions to the dataset
record — `root` and `transform` — and no second code path. Six new tables are live: three
ingested (18,314 / 17,832 / 20 rows) and three derived (8 / 874 / 12 rows), each with a
lineage edge.

The joins are checked against something other than themselves. The per-gene ClinVar counts
reproduce a table computed by a different tool on the raw file, and all 874 annotations
found their callset record, which means the ALT-membership join and the FORMAT-key lookup
are both correct.

Three things this makes true that were not true before, all as **observations**:

- **BUB1B and CEP57, the two established MVA genes, have pLI ≈ 0** and LOEUF 0.707 / 0.740.
  Read correctly this is expected: MVA is recessive, carriers are healthy, gnomAD is full
  of them, and pLI measures *dominant* intolerance. A ranking that weights pLI would
  demote the right answer.
- **CEP192 has 0 ClinVar P/LP records** across 418 records in the region. It is a candidate
  gene, not an established disease gene; absence of evidence is expected there.
- **The callset's Ts/Tv is 1.94 against an expected 2.0–2.1, and its dbSNP membership is
  88 % against an expected 99.2 %.** Both point the same way — an unfiltered callset
  carrying more novel/error calls than a filtered one — and both are consistent with
  `variant_sites_per_genome` and `indel_per_genome` reading above range. This is a
  quality-of-callset observation, not a verdict about the proband.

## Cost, for whoever runs this next

`panel_candidates` is **3 m 52 s** and `qc_observed_expected` **60 s**, both because they
scan `variants_raw`. That is paid once, at `pg-derive` time, and is exactly why the three
endpoints answer in half a second. Neither may be moved into a request.
