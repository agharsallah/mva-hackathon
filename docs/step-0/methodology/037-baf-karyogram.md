# 037 — The BAF karyogram: allele balance re-asked one megabase at a time

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, what
the live derivation measured, and the negative that measurement produced.

## Question

`results.allele_balance_flags` averages every heterozygous call on a chromosome into one
mean B-allele fraction. That grain answers "is a whole chromosome present in the wrong
number of copies". It cannot answer the question mosaic variegated aneuploidy actually
poses, where the event may be a **segment** rather than a whole contig and is carried by
only a fraction of cells: a shifted 20 Mb arm inside a 250 Mb chromosome moves the
chromosome mean by almost nothing.

So: **at 1 Mb resolution, does any region's allele balance leave 0.5, or any arm step in
depth?** And if not — is that a real absence, or is the aneuploid fraction simply below
the floor a VCF can resolve (roadmap §2b)?

## What the number is

A **heterozygous** call is a position where the two inherited copies of a chromosome
differ. On two intact copies the sequencer should see the variant allele in roughly half
the reads, so the **B-allele fraction** (BAF — here the variant allele fraction of a
heterozygous call, `alt_reads / (ref_reads + alt_reads)`) sits at ≈ 0.5. A mosaic gain
makes the alleles unequally represented and raises depth; a mosaic loss does the opposite.
Both traces scale with the fraction of cells carrying the event.

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 rows, every column text |
| Filter applied | `filter = 'PASS'` and `length(chrom) <= 2` (the 25 canonical contigs) |
| Genotype kept | `GT = '0/1'` only, located by `list_position` on each record's own FORMAT keys |
| Depth kept | the record's `DP`, falling back to `AD` ref+alt when the caller wrote no DP |
| Rows skipped | any record whose `AD` is absent, unparsable, or not exactly two values (a multi-allelic `1/2` site has no single ALT to attribute reads to) |
| Code | `src/mva/warehouse/analysis_karyogram.py`, registered in `src/mva/warehouse/analysis.py` |

Comparator for scale: `pg.warehouse.filter_gt_counts` reports **3,047,077** `0/1` calls in
the callset across all FILTER values.

## Commands run

```bash
uv run mva-warehouse pg-check                       # PostgreSQL 18.4, 1338 MB
time uv run mva-warehouse pg-derive --only baf_bins
uv run mva-warehouse pg-query "SELECT … FROM pg.results.baf_bins WHERE n_het >= 50
                               ORDER BY abs(vaf_deviation) DESC LIMIT 12"
uv run mva-warehouse pg-query "SELECT chrom, count(*), median(mean_vaf), … GROUP BY chrom"
uv run mva-viz-api --port 8941
curl -s -w '%{time_total}' 'http://127.0.0.1:8941/api/genome/baf-bins'
uv run pytest -q
cd app && npm run typecheck && npm run build
```

## Observed output

### Cost of the derivation

| Measure | Value |
|---|---|
| Wall time, `pg-derive --only baf_bins` | **392 s (6 m 32 s)** |
| Rows written to `pg.results.baf_bins` | **2,951** |
| Heterozygous calls that survived every filter | **2,778,844** (91.2 % of the 3,047,077 `0/1` calls) |
| Bins under 20 heterozygous calls (low confidence) | **157** |

A whole-genome scan, as expected and as `variant_density_bins` already pays. It is ~6.5×
that one's ~60 s because this reads the two widest text columns (`format`, `sample_call`)
and splits both per row, rather than reading `pos`/`qual` alone. `variant_density_bins`
produces 2,961 bins to this one's 2,951: ten bins hold variants but no usable heterozygous
call, MT among them (a haploid contig — it produces no bin at all here).

### Endpoint latency

`GET /api/genome/baf-bins`, live (no cache — the derivation already did the scan), against
the hosted database, own instance on port 8941:

| Request | Rows | Payload | Time |
|---|---|---|---|
| whole genome | 2,951 | 507,921 B | 3.8 / 4.9 / 4.9 / 6.8 s |
| one contig (`?chrom=7`) | 160 | 27,561 B | 1.4 / 2.3 / 2.9 s |

Dominated by the `ATTACH` plus a ten-column round trip to a remote server, not by any
computation. `chrom=chr7` and `chrom=7` return the same rows, through the existing
`to_vcf_contig` bridge.

### The result: every autosome is flat

Per-chromosome summary over the 2,951 bins — the **median of the per-bin mean BAF**, its
5th/95th percentiles, and the median per-bin depth:

| chrom | bins | thin | median bin BAF | p05 | p95 | median depth |
|---|---|---|---|---|---|---|
| 1 | 232 | 0 | 0.4969 | 0.4588 | 0.5035 | 42.3 |
| 2 | 243 | 0 | 0.4972 | 0.4625 | 0.5056 | 42.3 |
| 3 | 199 | 0 | 0.4974 | 0.4827 | 0.5043 | 42.4 |
| 4 | 191 | 0 | 0.4969 | 0.4835 | 0.5033 | 42.2 |
| 5 | 181 | 0 | 0.4976 | 0.4856 | 0.5039 | 42.2 |
| 6 | 171 | 0 | 0.4981 | 0.4840 | 0.5043 | 42.2 |
| 7 | 160 | 1 | 0.4974 | 0.4698 | 0.5059 | 42.3 |
| 8 | 146 | 2 | 0.4984 | 0.4873 | 0.5057 | 42.4 |
| 9 | 125 | 1 | 0.4972 | 0.3709 | 0.5039 | 42.7 |
| 10 | 134 | 0 | 0.4977 | 0.4648 | 0.5053 | 42.4 |
| 11 | 136 | 2 | 0.4977 | 0.4839 | 0.5053 | 42.2 |
| 12 | 134 | 0 | 0.4969 | 0.4774 | 0.5044 | 42.2 |
| 13 | 99 | 0 | 0.4980 | 0.4703 | 0.5045 | 42.4 |
| 14 | 90 | 0 | 0.4983 | 0.4705 | 0.5050 | 42.4 |
| 15 | 85 | 0 | 0.4972 | 0.4550 | 0.5040 | 42.6 |
| 16 | 84 | 1 | 0.4955 | 0.3368 | 0.5056 | 43.1 |
| 17 | 84 | 2 | 0.4978 | 0.4744 | 0.5107 | 42.8 |
| 18 | 81 | 2 | 0.4980 | 0.4555 | 0.5054 | 42.6 |
| 19 | 57 | 0 | 0.4954 | 0.4833 | 0.5048 | 42.7 |
| 20 | 65 | 0 | 0.4969 | 0.4019 | 0.5049 | 42.6 |
| 21 | 41 | 0 | 0.4971 | 0.3752 | 0.5021 | 43.1 |
| 22 | 39 | 0 | 0.4955 | 0.3675 | 0.5042 | 43.4 |
| X | 150 | 132 | 0.4899 | 0.2351 | 0.8806 | 16.4 |
| Y | 24 | 14 | 0.4047 | 0.3009 | 0.5932 | 25.2 |

Every autosome's median bin sits in **0.4954–0.4984**, a band 0.003 wide. Every autosome's
median bin depth sits in **42.2–43.4×**, a band 1.2× wide. There is no arm-scale step in
either. X and Y are single-copy in a male sample — 132 of 150 X bins and 14 of 24 Y bins
fall under the confidence floor, and their apparent heterozygous calls are mapping
artefacts, exactly as `allele_balance_flags` already reports at chromosome grain.

### The outliers are one-sided, and that is the tell

Restricting to autosomal bins with ≥ 50 heterozygous calls (2,752 of them):

| Measure | Value |
|---|---|
| Bins outside 0.45–0.55 | **107** (3.89 %) |
| Bins **above** 0.55 | **0** |
| Median bin BAF | 0.4974 |
| SD of the bin means | 0.0234 |
| Depth p05 / median / p95 | 40.5 / 42.4 / 44.6 × |

**Not one autosomal bin in the whole genome reads above 0.55.** Every deviant bin deviates
downward. A real mosaic aneuploidy cannot look like this: at a heterozygous site either
allele can be the gained or the lost one, so a copy-number event splits the BAF
distribution in **both** directions around 0.5. A purely one-sided downward pull is the
signature of reference bias — extra reference-matching reads mismapping in from elsewhere
and diluting the variant fraction.

The depth confirms it. Comparing the 107 deviant bins against the other 2,645:

| Bin group | n | median depth | 90th-pct depth | median per-bin BAF spread | median % of calls inside 0.40–0.60 |
|---|---|---|---|---|---|
| within 0.45–0.55 | 2,645 | 42.4× | 43.6× | 0.0922 | 77.0 % |
| outside | 107 | **52.7×** | **102.9×** | 0.1671 | 35.1 % |

Deviant bins are **piled up, not depleted** — median depth 24 % above the rest and a 90th
percentile 2.4× above it, with the deepest autosomal bin at 1,062×. That is collapsed
repetitive sequence: reads from several genomic copies stacking on one reference locus.
And they cluster where that is known to happen — the most deviant bins fall in the
pericentromeric and acrocentric stretches of chromosomes 1, 2, 7, 15, 16 and 21, the same
regions where `variant_density_bins` already shows the caller going quiet.

A mosaic **loss** would show the opposite pairing: BAF off 0.5 *with depth below* the
autosomal median. No bin in this callset shows that combination.

## Conclusions

1. **The map is flat, and the flatness is the finding.** Every autosome's median 1 Mb bin
   sits within 0.005 of 0.5 and within 1.2× of the genome-wide depth. At megabase
   resolution this callset carries no segmental allele-balance shift and no arm-scale depth
   step. The chromosome-level negative in `allele_balance_flags` survives being asked 2,951
   times instead of 25.
2. **The 107 outliers are mapping artefacts, and the asymmetry proves it.** Zero bins above
   0.55, all deviation downward, deviant bins 24 % *deeper* than the rest with a 90th
   percentile 2.4× higher, concentrated in pericentromeric and acrocentric sequence. A copy
   -number event is symmetric about 0.5 and a loss is shallower, not deeper. Neither holds.
3. **This is an upper bound on the mosaic fraction, not a proof of absence.** The
   derivation reads the VCF, so it sees only what the caller wrote down: one already
   thresholded genotype and one allele-depth pair per site. A clone present in too few
   cells never crosses that threshold and leaves no row to bin. The honest statement is
   *"no mosaic aneuploidy is visible at the resolution a VCF can resolve"*. Answering
   roadmap §2b properly needs the read-level path, which is the lower floor; this entry
   does not answer it.
4. **A thin bin must be rendered as unmeasured, never as signal.** 157 of 2,951 bins hold
   fewer than 20 heterozygous calls — centromeres, acrocentric arms, and most of X and Y.
   Their means are arithmetic, not measurement. The flag travels in the table, through the
   endpoint, and into the chart as a separate flat-grey layer with no place on the colour
   scale, so a 6-call bin cannot be read as a finding.
5. **Consequence for the case, unchanged and now better bounded.** MVA is defined by
   aneuploidy, and this genome shows none the callset can resolve — at whole-chromosome
   *or* megabase grain. The causal mechanism has to be a coding change in a
   chromosome-segregation gene rather than a detectable copy-number event, which is what a
   recessive compound-heterozygous MVA gene predicts.

## What was built

| Artefact | Path |
|---|---|
| Derivation `baf_bins` | `src/mva/warehouse/analysis_karyogram.py` |
| Registry entry | `src/mva/warehouse/analysis.py` (`KARYOGRAM_DERIVATIONS`) |
| Query | `src/mva/viz/queries.py` (`baf_bins`) |
| Endpoint `GET /api/genome/baf-bins?chrom=` | `src/mva/viz/routes_warehouse.py` |
| Exhibit | `app/src/pages/genome/BafKaryogram.tsx`, on the Genome page |
| Diverging + depth colour scales | `app/src/lib/palette.ts` (`DIVERGING_SCALE`, `DEPTH_SCALE`) |
| Offline fixture | `app/src/fixtures/karyogram.ts` — **shape, not measurement**, and it carries one deliberately planted shifted arm so the diverging scale and the hover are exercisable with the API down. No such segment exists in the callset. |

## Tests

* `tests/test_warehouse_karyogram.py`, 19 tests, hermetic: the real SQL against a
  miniature DuckDB warehouse, in the style of `tests/test_warehouse_reference.py`. Covers
  the PASS / genotype / canonical-contig selection, integer megabase binning, BAF as
  alt over ref+alt, the signed deviation, the in-band percentage, the median, a
  single-call bin reporting **no** spread rather than 0.0, depth preferring the record's
  own DP and falling back to the allele depths, the low-confidence flag, FORMAT parsed by
  key rather than by position (`DP:GT:AD`), the deliberate exclusion of the phased
  spelling, and the registry wiring.
* `tests/test_viz_karyogram.py`, 10 tests, hermetic in the style of
  `tests/test_viz_api.py`: envelope, live-not-cached, the source string, the optional
  contig in both spellings, the contig as a bound parameter rather than interpolation,
  every contract column selected, position ordering, and a thin bin served flagged rather
  than withheld.
* `uv run pytest -q` → **879 passed**, 11 failures, all pre-existing in
  `tests/test_reads_api.py` and unrelated to this change.
* `cd app && npm run typecheck && npm run build` → clean.
