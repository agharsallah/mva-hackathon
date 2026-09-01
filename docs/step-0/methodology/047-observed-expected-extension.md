# 047 — Seven more norms, four more verdicts, and three metrics that stay ungraded

**A step-0 platform entry, so it carries no hypothesis.** It records what was added to the
observed-vs-expected comparison, the executed numbers, and — the part that took the most
work — the metrics that are measurable but have **no citable range**, with the sources that
say why.

Supersedes nothing. Extends [032](032-reference-comparison-tables.md) (which built
`results.qc_observed_expected`) and [033](033-compare-page.md) (which drew it).

## Question

`ressources/reference/qc_norms.tsv` held 20 cited rows and 12 of them were comparable
against this callset. Two follow-ups:

1. **Can the table be widened without inventing a number?** Which further WGS QC metrics
   that this warehouse can actually measure have a PMID/DOI-citable range?
2. **Does the verdict have to live on the Compare page?** The Overview page states eight
   raw figures. A reader looking at "5.01 M variants" has no way to know it is high without
   navigating away.

## Inputs

| Input | Shape as read |
|---|---|
| `ressources/reference/qc_norms.tsv` | 20 rows before, **27 after** |
| `pg.warehouse.stats_summary` | 200 lines: 9 `SN`, 1 `TSTV`, 120 `IDD`, 55 `DP`, 12 `ST`, 2 `AF`, 1 `SiS` |
| `pg.warehouse.filter_gt_counts` | 38 rows; genotype counts `0/1` 3,047,077 · `1/1` 1,898,267 · `1/2` 66,860 |
| `pg.warehouse.variants_raw` | 5,012,204 records, the only place the rsID column lives |
| `pg.warehouse.contig_counts` | 1,690 contigs with length and record count |
| Code | `src/mva/warehouse/analysis_reference_qc.py` (new), spliced into `analysis_reference.QC_OBSERVED_EXPECTED` at two anchors |
| App | `app/src/components/NormChip.tsx` (new), one optional `chip` prop on `StatTile`, three call sites in `Overview.tsx` |

## Commands run

```bash
# measurements, before deciding what to add
uv run mva-warehouse pg-query "SELECT … FROM pg.warehouse.stats_summary WHERE line LIKE 'SN'…"
uv run mva-warehouse pg-query "SELECT … FROM pg.warehouse.variants_raw"          # dbSNP rates
uv run mva-warehouse pg-query "SELECT … FROM pg.warehouse.contig_counts"          # X/Y density

# the round trip
uv run mva-warehouse stage --reference ressources/reference --stagedir build/stage-d1
uv run mva-warehouse pg-ingest --stagedir build/stage-d1 --tables qc_norms
uv run mva-warehouse pg-derive --only qc_observed_expected
curl -s 'http://127.0.0.1:8961/api/callset/observed-expected?refresh=true'

uv run pytest -q
cd app && npm run typecheck && npm run build
```

## Observed output

### Before and after

| | before | after |
|---|---|---|
| `qc_norms.tsv` rows | 20 | **27** |
| `results.qc_observed_expected` rows | 12 | **16** |
| observations computed in the derivation | 12 | **18** |

Eighteen observations, sixteen rows: two are measured and deliberately ungraded (below).

`pg-derive --only qc_observed_expected` ran in **17.7 s** wall clock with the new
second scan of `variants_raw`, against the **60 s** recorded in
[032](032-reference-comparison-tables.md) with one scan. That is not evidence the extra
scan is free — it is PostgreSQL's buffer cache holding the raw layer after the day's other
queries. Both numbers are what was measured, on different cache states.

### The seven rows added to `qc_norms.tsv`

| metric | band | source | graded? |
|---|---|---|---|
| `snv_to_indel_ratio` | 4.611 – 4.798 | Byrska-Bishop 2022, PMID 36055201 (derived from Table 1) | **yes** |
| `snv_to_indel_ratio_across_callers` | 4.744 – 6.201 | Supernat 2018, PMID 30552369 (derived from Table 1) | no — context |
| `het_count_per_genome` | 2,657,943 – 2,819,897 | Supernat 2018, PMID 30552369 | **yes** |
| `dbsnp_membership_rate_pass_only` | 99.2 (point) | Taliun 2021, PMID 33568819 | **yes** |
| `dbsnp_membership_rate_pass_snv` | 89.89 (point) | DePristo 2011, PMID 21478889 | **yes** |
| `dbsnp_novel_allele_rate_cohort_b155` | 5.9 (point) | Byrska-Bishop 2022, PMID 36055201 | no — context |
| `multiallelic_locus_fraction_cohort` | 6.6 (point) | Byrska-Bishop 2022, PMID 36055201 | no — context |

The three *context* rows carry a metric id that **deliberately does not match any
observation**, so they can never be joined. They exist for the same reason `tstv_coding`
does: to make the wrong comparison impossible to make by accident. A one-sample multiallelic
fraction graded against a 3,202-sample one would be pure noise, and now nobody can.

### The four new verdicts, as measured

| metric | observed | expected | verdict |
|---|---|---|---|
| `snv_to_indel_ratio` | **4.3934** | 4.611 – 4.798 | **below** |
| `het_count_per_genome` | **3,113,937** | 2,657,943 – 2,819,897 | **above** |
| `dbsnp_membership_rate_pass_only` | **91.07 %** | 99.2 % | **below** |
| `dbsnp_membership_rate_pass_snv` | **93.89 %** | 89.89 % | **above** |

The full table is now 16 rows: **4 within, 12 outside, 0 unknown** (was 4 within, 8
outside of 12). Every one of the four new comparisons lands outside its band — see the two
readings below before treating that as four defects.

### The dbSNP ladder — the diagnostic the wave was asked for

Membership was 87.96 % over every delivered record, 11.2 points under the published 99.2 %.
Narrowing the population, one restriction at a time, each measured by its own executed
query:

| population | records | carry an rsID |
|---|---|---|
| every delivered record | 5,012,204 | **87.96 %** |
| canonical contigs only (1–22, X, Y) | 4,895,706 | 90.05 % |
| PASS only | 4,740,790 | **91.07 %** |
| canonical **and** PASS | 4,661,862 | 92.61 % |
| PASS biallelic SNVs only | 3,835,251 | **93.89 %** |

So: filtering buys ≈ 3.1 points, dropping the decoy and alternate-haplotype contigs buys
≈ 2.1, and dropping indels and multi-allelic sites buys ≈ 2.8 more. Together they close
roughly half the gap to 99.2 % and **the other half does not close**. Two readings, both
consistent with the numbers and neither yet tested:

* the delivered callset is genuinely novel-rich — plausible on a 51.9× genome where rare
  and low-quality alleles survive that a 30× consortium pipeline would drop; or
* the delivery's `ID` column was populated against an older dbSNP build than the one behind
  the 99.2 %. **The VCF header does not name a dbSNP build**, so this cannot be settled
  from the delivery.

Only two rows are committed and graded (all-record and PASS-only, plus the SNV-only row
against the 2011 figure); the canonical-contig rows above are measurements recorded here,
not warehouse rows.

Placing 93.89 % between the two published figures is the honest summary: **above**
DePristo's 89.89 % for a VQSR-passing 2011 call set, **below** Taliun's 99.2 % for a modern
one. Those two are not in conflict — the dbSNP denominator grew by orders of magnitude
between them, and each row's `applies_to` says which era it describes.

### Why `snv_to_indel_ratio` fires, and how much to make of it

4.393 observed against 4.611–4.798. The band is real and derived from stated table cells,
but the metric is **strongly pipeline-dependent** — that is why the second, wider row was
added rather than left out:

| source | pipeline | SNV/indel |
|---|---|---|
| Supernat 2018, DeepVariant | one genome, 34× | 4.745 |
| Byrska-Bishop 2022 | 3,202 genomes, 30×, GATK joint | 4.611 – 4.798 |
| Supernat 2018, SpeedSeq | same reads as above | 5.997 |
| Supernat 2018, GATK 4.0 | same reads as above | 6.201 |
| Taliun 2021, TOPMed | 40,722 genomes | 18.21 |
| **this callset** | 1 genome, 51.9×, GATK hard filters | **4.393** |

Same reads and same reference move the ratio by a third across callers, so a `below`
verdict here says *this callset is indel-rich relative to every published reference*, not
*this callset is broken*. It is corroborated from the other side by two existing rows:
`indel_per_genome` is above its phase-3 band and `insertion_deletion_ratio` is 0.977 where
every 1000G superpopulation sits at 0.924–0.936.

### Measurable, unnormed — three metrics that were **not** given a band

**1. Multi-allelic site fraction — measured 1.3339 %** (66,860 of 5,012,204 records).
Ungraded. A locus is multi-allelic only when two different ALT alleles are seen across the
samples called *together*, so the fraction is a property of the joint callset and scales
with cohort size; it has no cohort-independent value. No source was found stating one for a
single-sample human WGS VCF. The one citable figure — 6.6 % of small-variant loci across
3,202 samples (Byrska-Bishop 2022) — is committed as a context row precisely so it is never
used as the expectation. The same paper adds that 74.8 % of multi-allelic loci fall in GIAB
"difficult regions" (20 % of the genome), so even the cohort figure is not a genome-wide
constant.

**2. Indel length 1–2 bp share — measured 63.735 %** (631,259 of 990,438 indel alleles in
the `IDD` histogram; 45.84 % are 1 bp alone). Ungraded. No primary source states a 1–2 bp
share or gives a table it can be derived from. Checked and rejected as sources: Montgomery
2013 (PMID 23478400 — length appears only in Fig. 1B/3C, no numbers in the text),
Byrska-Bishop 2022 (Fig. S4A only), 1000G Auton 2015 (no length distribution at all),
Mullaney 2010 and Mills 2011 (not open access, abstracts carry no breakdown). The closest
verified adjacent sentence is Jiang 2015 NAR (PMID 26130710): *small indels of length
1–20 bp make up 98.5 % of all indel events* — a different bucket, and itself a secondary
citation.

Note the denominator: `IDD` totals **990,438 indel alleles** while `SN` reports **930,181
indel records**. They are not the same population — `IDD` counts alleles, so a
multi-allelic site contributes more than once. The share is computed against `IDD`'s own
total and a test asserts it.

**3. X/Y depth ratio for sex confirmation — deliberately not attempted as a graded row.**
Two independent reasons, one about the norm and one about our instrument.

*The norm does not exist.* Webster et al. 2019, *GigaScience* 8(7):giz074, PMID 31289836,
DOI 10.1093/gigascience/giz074 examined exome, low-coverage WGS and high-coverage WGS and
found XX and XY separate cleanly **within** a dataset while the relative depths vary
**between** datasets — from which they conclude that a general threshold for assigning
genetic sex across sequencing experiments would be difficult to implement. Their numeric
ratios exist only as a plot. `somalier` (PMID 32664994) and `seGMM`
(DOI 10.3389/fgene.2022.850804) both infer sex from X/Y signal and both use cohort-derived
gates rather than a fixed ratio. The gnomAD/Hail definition (`2 × mean chrX depth / mean
autosomal depth`) is documented but carries no DOI, and its expected 0.5×/1.0× follows from
copy number by definition — it is arithmetic, not a measured norm.

*Our instrument is the wrong one anyway.* The only per-contig depth this warehouse holds,
`vcf_chrom_allele_balance.mean_dp`, is mean depth **at heterozygous sites**, and on a
hemizygous X the heterozygous sites are largely mismapping — so its 41.4× for X against
44.1× for the autosomes measures the artefact, not the ploidy.

What *is* measurable, and was measured, is variant **density**:

| scope | records | length | per kb |
|---|---|---|---|
| autosomes 1–22 | 4,764,641 | 2,875,001,522 | 1.657 |
| X | 117,225 | 156,040,895 | 0.751 |
| Y | 13,840 | 57,227,415 | 0.242 |

X:autosome = **0.453**, consistent with a hemizygous X, and chrY present at real density.
That agrees with [004](004-sex-and-aneuploidy-from-allele-balance.md), which called the
proband male from 4,858 chrX heterozygous SNVs. It is recorded here as a corroborating
measurement, **not** as a norm, because there is no published band to put it against.

### The Overview chips

Three of the eight `StatTile`s have a metric with a row in `qc_observed_expected` and now
carry its verdict inline, verified live against the API on port 8961:

| tile | metric | chip |
|---|---|---|
| variants called | `variant_sites_per_genome` | red — **above norm** |
| Ts/Tv | `tstv_genome_wide` | red — **below norm** |
| coverage | `mean_coverage_wgs` | red — **above norm** |

The other five (PASS share, compound-het sites, reads sequenced, samples, probe budget)
have no published norm and render exactly as before — `pickNorm` returns `undefined`,
`NormChip` returns `null`. The chip is a link to `/compare`; its `title` carries the band
and the citation, so the number the tile shows and the number the chip grades are never
two different things.

`pickNorm` takes a *preference list* of metric ids rather than one key, because the live
warehouse spells the Ts/Tv norm `tstv_genome_wide` while `app/src/fixtures/callset.ts`
spells it `tstv`. Listing the live name first and the fixture alias behind it keeps the
chips working in the offline demo without editing a shared fixture.

## Conclusions

1. **Widening the table was mostly refusing to widen it.** Six candidate metrics were
   researched against primary sources; three yielded a citable band, three did not. The
   three that did not are now documented with the sources that say why — including one
   (Webster 2019) whose finding *is* that the threshold should not exist. A norm file's
   value is in what it declines to assert.
2. **An observation without a norm is still worth computing.** Six new observations were
   added to the derivation and four became rows. `multiallelic_site_fraction` and
   `indel_length_1_2bp_share` are computed on every run and emit nothing; the day a citable
   band lands in the TSV they appear, with no SQL change. A test asserts exactly that.
3. **The dbSNP gap is real and only half explained.** Filters, decoy contigs and indels
   together account for ~5.9 of the 11.2 points. The residual needs the delivery's dbSNP
   build, which the VCF header does not state — so it stays an open question rather than a
   conclusion.
4. **Three context rows are the most useful thing in this change.** `tstv_coding` already
   existed to stop a genome-wide Ts/Tv being graded against an exome band. This wave adds
   the same guard for cohort-scale multi-allelic fraction, cohort-scale novel rate, and
   cross-caller SNV/indel spread. Each is cited, each is unjoinable by construction.
5. **The verdict belongs next to the number.** A reader who never opens Compare now sees
   three red chips on the Overview. Zero call sites broke: `chip` is optional and five
   tiles pass nothing.

## Tests

`tests/test_qc_norms_extension.py`, **21 tests**, hermetic — no network, no database.

* *The committed TSV*: every row carries a PMID or a DOI (regex-enforced), every row has a
  URL and a >40-character `basis`, metric ids are unique, no band is inverted, every row
  names its `applies_to` and `unit`.
* *The new observations*: the real derivation SQL runs against a miniature DuckDB
  warehouse whose counts are chosen so a wrong denominator changes the answer — the `IDD`
  histogram totals 100 alleles while `SN` reports 40 indel records, so computing the 1–2 bp
  share against `SN` would give 162 %, not 65 %. Covered: SNVs-per-indel, a `1/2` call
  counting as heterozygous, the multi-allelic fraction being of records, the short-indel
  share counting both signs of the histogram, and the three dbSNP rates being three
  different numbers over three different populations (60 % / 62.5 % / 83.33 % in the
  fixture) with the SNV rate correctly excluding a PASS 1 bp insertion and a PASS
  comma-packed ALT.
* *SQL and TSV agree on spelling*: the metric ids parsed out of `EXTRA_OBSERVED` are
  exactly the six declared, all four graded ones exist in the committed TSV, neither
  ungraded one does, and `multiallelic_locus_fraction_cohort` exists as a norm while
  matching no observation.
* *Nothing regressed*: `tstv_genome_wide`, `mean_coverage_wgs` and `het_hom_ratio_eur`
  still parse from the same places, and the het/hom **ratio** rows still use `0/1` over
  `1/1` while only the new **count** row folds `1/2` in.

`uv run pytest -q` → **1,226 passed**, 11 failures, all pre-existing in
`tests/test_reads_api.py` and unrelated to this change.
`cd app && npm run typecheck && npm run build` → both clean.
