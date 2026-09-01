# 048 — Gene versus genome: z-scoring each panel gene against its 1 Mb-window background

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
measured per-gene table, and the two things the numbers do *not* say.

## Question

`results.panel_gene_density` says TRIP13 carries 180.4 variants/Mb and passes 50 % of its
records. Neither figure is interpretable alone: 180/Mb is either unremarkable or a hole in
the data depending entirely on what the surrounding sequence does, and a 50 % PASS share
is only alarming next to a chromosome that passes at 96 %.

**Is each panel gene's variant density and PASS share normal for its chromosome and for
the genome, or an outlier?**

## Design decisions

**The background is the per-megabase window distribution, not a contig average.** A contig
mean is one number with no spread attached, so "two above the mean" is meaningless against
it. The comparison population is therefore every 1 Mb window of the callset — the same
windows `variant_density_bins` computes. One window is one megabase, so a window's record
count *is* a density in variants/Mb and is directly comparable to a gene's
`variants_per_mb` with no unit conversion.

**The statistic is a z-score** — how many standard deviations from the background mean a
value sits. Two backgrounds per gene: its own contig's windows, and every window in the
callset.

**The window aggregate is recomputed, not read from `results`.** A derivation may not read
the result schema, because `pg-derive` has no ordering guarantee between derivations. So
this one re-runs the bin aggregate over `variants_raw` exactly the way
`variant_density_bins` does, the same duplication `qc_observed_expected` pays when it
re-parses `stats_summary`. `TestRegistry::test_it_bins_the_same_way_variant_density_bins_does`
asserts the two binning expressions agree.

**A thin window is kept in the density background and dropped from the PASS-share one.**
An empty stretch is a real property of the reference and belongs in the density
distribution. A PASS *share* computed over three records is 0 %, 33 %, 67 % or 100 % and
is noise, so windows under `MIN_BIN_N_FOR_PASS = 100` records are excluded from the
PASS-share background only.

**Zero spread yields NULL, never zero.** `stddev_samp` of one window is undefined and an
identical-window contig would divide by zero. Both are guarded; the z comes back null and
is rendered as a gap.

**The `chr` bridge.** Windows come from `variants_raw` (bare contigs), gene rows from
`mva_panel_grch38` (`chr`-prefixed). The join strips with `replace(chrom, 'chr', '')`, the
repo's sanctioned expression. The emitted `chrom` stays `chr`-prefixed, matching
`panel_gene_density` and `/api/panel/genes`.

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 rows, all text — aggregated to 2,961 canonical 1 Mb windows |
| `pg.warehouse.contig_counts` | 25 canonical contigs, `length` + `n_records` |
| `pg.warehouse.panel_variant_counts` | 8 panel genes, `n_all` + `n_pass` |
| `pg.warehouse.mva_panel_grch38` | the panel BED, `chr`-prefixed intervals |
| Code | `src/mva/warehouse/analysis_background.py`, `queries.panel_background`, `routes_warehouse.TABLES` |

## Commands run

```bash
uv run mva-warehouse pg-derive --only panel_gene_background     # 12.5 s, 8 rows
uv run mva-warehouse pg-query "SELECT gene, chrom, … FROM pg.results.panel_gene_background"
uv run mva-viz-api --port 8962
curl -s -w '%{time_total}' http://127.0.0.1:8962/api/panel/background
uv run pytest -q                       # 1205 passed, 11 pre-existing test_reads_api failures
cd app && npm run typecheck && npm run build
```

## Observed output

### The per-gene z table, as measured

Ordered by PASS-share z, most suppressed first — the derivation's own order.

| gene | contig | gene /Mb | contig window mean ± sd /Mb | **z density** | gene PASS % | contig window PASS % mean ± sd | **z PASS** | z density (genome) | z PASS (genome) |
|---|---|---|---|---|---|---|---|---|---|
| **TRIP13** | chr5 | 180.4 | 1601.2 ± 463.0 | **−3.07** | 50.0 | 96.28 ± 11.52 | **−4.02** | −1.90 | **−3.54** |
| BUB1B | chr15 | 798.8 | 1651.8 ± 528.8 | −1.61 | 95.0 | 93.35 ± 13.91 | +0.12 | −1.10 | −0.04 |
| CENPE | chr4 | 1269.6 | 1778.0 ± 565.7 | −0.90 | 98.22 | 97.05 ± 10.02 | +0.12 | −0.50 | +0.21 |
| CEP192 | chr18 | 1467.4 | 1652.6 ± 599.4 | −0.31 | 98.43 | 92.75 ± 21.08 | +0.27 | −0.24 | +0.23 |
| CEP57 | chr11 | 149.2 | 1739.6 ± 539.8 | **−2.95** | 100.0 | 96.15 ± 13.69 | +0.28 | −1.94 | +0.35 |
| TP53 | chr17 | 1824.6 | 1691.1 ± 835.0 | +0.16 | 98.33 | 93.64 ± 16.03 | +0.29 | +0.22 | +0.22 |
| DICER1 | chr14 | 778.3 | 1715.0 ± 506.1 | −1.85 | 100.0 | 96.67 ± 9.97 | +0.33 | −1.13 | +0.35 |
| SMC5 | chr9 | 915.0 | 1791.0 ± 678.1 | −1.29 | 99.2 | 90.79 ± 20.99 | +0.40 | −0.95 | +0.29 |

Genome background: 2,961 windows, density 1653.4 ± 774.1 /Mb, PASS share 95.47 ± 12.84 %.
Whole-callset density 1585.3 /Mb, PASS share 95.22 %. No z in the table is null — every
panel contig has enough windows for a spread.

### Cost

| Step | Measured |
|---|---|
| `pg-derive --only panel_gene_background` | **12.5 s** wall (the whole-genome window aggregate), 8 rows written |
| `GET /api/panel/background` | **0.75 s** first request, 0.87 s second — live, no cache |

The derive cost is the `variants_raw` scan, paid once at derive time so the endpoint reads
eight rows. Notably cheaper than the ~60 s the module comments quote for a bare scan,
because the aggregate pushes down to PostgreSQL through the attached connection.

### The TRIP13 verdict

**Confirmed, and only on the PASS axis.** TRIP13 is the sole gene whose PASS share leaves
the |z| < 2 band, and it leaves it by a distance nothing else approaches: **z = −4.02**
against chr5's windows, **−3.54** against the whole callset. Every other panel gene sits
between +0.12 and +0.40. This is the predicted outlier — `ideation/data-findings.md` §3
records 6 of TRIP13's 12 records suppressed, mostly `MQ40`, in telomere-proximal chr5
sequence — so the designed confirmation holds.

**It is a callability statement.** A low PASS-share z says the sequence is hard to map and
the evidence there is thin, in *either* direction. It is not evidence of pathogenicity and
must never be quoted as such.

### The density axis says something else, and it is easy to over-read

Every panel gene sits at or below its chromosome's window mean, and two are past two
sigma: TRIP13 (−3.07) and CEP57 (−2.95). Two reasons, neither of them about these genes:

1. **A 1 Mb window is mostly intergenic.** Gene bodies carry less variation per base than
   the genome average, so a systematic negative density z is expected for *any* gene and
   is not a property of the panel.
2. **The spans are far under a megabase.** TRIP13's interval is 0.067 Mb and CEP57's
   0.087 Mb — the two most negative genes are the two smallest. A per-Mb figure
   extrapolated from 67 kb is noisier than the 1 Mb windows it is compared against, so the
   density comparison is honest about *direction* and not about *magnitude*.

That second point is a limitation of this derivation, recorded here rather than hidden: a
fairer density background would be windows matched to gene span, which this entry does not
build.

## What was built

| Artefact | Path |
|---|---|
| Derivation `panel_gene_background` | `src/mva/warehouse/analysis_background.py` |
| Endpoint `GET /api/panel/background` | `routes_warehouse.TABLES` + `queries.panel_background` |
| Column meanings (24 columns) | `src/mva/viz/catalog_columns_results.py` |
| Exhibit (dot-and-band per gene) | `app/src/pages/panel/GeneBackground.tsx` |
| Fixture (the measured rows, transcribed) | `app/src/fixtures/panel-background.ts` |
| Tests | `tests/test_warehouse_background.py` (24), `tests/test_viz_background.py` (13) |

## Conclusion

The comparison works and it separates the two questions the raw table conflates. On
callability, TRIP13 is a four-sigma outlier and nothing else is close — the expected
result, reproduced from the data rather than restated from the brief. On density, the
whole panel reads low for a reason that has nothing to do with the panel, which is exactly
why the exhibit's legend and callout state it: an unexplained systematic offset in a
figure is a reader's false finding.
