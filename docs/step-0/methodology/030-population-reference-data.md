# 030 — What does normal look like? Three public reference tables

**A step-0 platform entry, so it carries no hypothesis.** It records what was acquired,
what was measured in it, and the five properties of the data that the warehouse-staging
step has to know before it writes a schema.

## Question

The dashboard can show that the proband's callset holds 5,012,204 variants and that BUB1B
holds 80 of them. Neither number means anything without a comparison set. Can three
**public, non-patient** reference tables — gene intolerance, prior clinical
classifications, and expected whole-genome QC ranges — be acquired, subsetted small enough
to commit, and made join-ready against the existing warehouse?

Constraint: nothing patient-derived may be committed, and the two upstream files are 95 MB
and 193 MB, which is too large for the tree regardless.

## Inputs

| Input | Version / shape |
|---|---|
| gnomAD v4.1 constraint metrics | `gnomad.v4.1.constraint_metrics.tsv`, 95,546,041 bytes, upstream `Last-Modified: 2024-04-18`, SHA-256 `68d8abdb7fc48f570869b02dfaa74b9fecaece7fcc5f301ddca40ec1ce12da00` |
| ClinVar GRCh38 VCF | `clinvar.vcf.gz`, 193,427,450 bytes, header `##fileDate=2026-08-29`, `##reference=GRCh38`, `##fileformat=VCFv4.1` |
| ClinVar index | `clinvar.vcf.gz.tbi`, 610,396 bytes |
| Panel BED | `ressources/data-profile/mva_panel_grch38.bed`, 8 genes, 6 columns, chr-prefixed, ±20 kb padding |
| bcftools / htslib | 1.24 (Homebrew, `/opt/homebrew/bin/bcftools`) — **not previously present on this machine**, installed for this run |
| Python | 3.13, project venv via `uv` |
| Date of run | 2026-08-31 |

Source URLs:

- `https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/constraint/gnomad.v4.1.constraint_metrics.tsv`
- `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz` (+ `.tbi`)

## Commands run

Version discovery first — the release list was enumerated rather than assumed, because a
wrong version number is a silent error (it 404s, or worse, returns an older release):

```bash
curl -sL "https://storage.googleapis.com/storage/v1/b/gcp-public-data--gnomad/o?prefix=release/&delimiter=/&fields=prefixes"
# release/2.1.1 2.1 3.0.1 3.0 3.1.1 3.1.2 3.1.3 3.1 4.0 4.1.1 4.1
```

`4.1` is the highest release carrying a `constraint/` directory. Both URLs were probed
with `curl -sIL` before downloading, then fetched:

```bash
curl -sIL <gnomad-url>   # HTTP/2 200, content-length: 95546041,  last-modified: 2024-04-18
curl -sIL <clinvar-url>  # HTTP/1.1 200, Content-Length: 193427450
curl -L -o gnomad.v4.1.constraint_metrics.tsv <gnomad-url>
curl -L -o clinvar_GRCh38.vcf.gz <clinvar-url>
curl -L -o clinvar_GRCh38.vcf.gz.tbi <clinvar-url>.tbi
shasum -a 256 gnomad.v4.1.constraint_metrics.tsv
```

Both landed in `build/reference-scratch/`, confirmed gitignored:

```bash
git check-ignore -v build/reference-scratch/gnomad.v4.1.constraint_metrics.tsv
# .gitignore:53:build/   build/reference-scratch/gnomad.v4.1.constraint_metrics.tsv
```

Profiling before subsetting:

```bash
wc -l gnomad.v4.1.constraint_metrics.tsv                       # 211524 (211,523 data rows)
head -1 … | tr '\t' '\n' | wc -l                               # 55 columns
awk -F'\t' 'NR>1{c[$51]++}END{…}'   # level:           1→6844  2→89443  3→4680  NA→110556
awk -F'\t' 'NR>1{c[$4]++}END{…}'    # canonical:       true→36315   false→175208
awk -F'\t' 'NR>1{c[$5]++}END{…}'    # mane_select:     true→34962   false→176561
awk -F'\t' 'NR>1{c[$52]++}END{…}'   # transcript_type: protein_coding→82270  NMD→18550  NA→110556

bcftools view -h clinvar_GRCh38.vcf.gz | grep -E '^##(fileDate|reference|contig)' | head
bcftools index -n clinvar_GRCh38.vcf.gz                        # 4468152
```

Then the build, via a new parameterized tool, `tools/build_reference_data.py`:

```bash
uv run tools/build_reference_data.py gnomad
uv run tools/build_reference_data.py clinvar
```

## Observed output

### The download and subset

```
panel   8 genes from ressources/data-profile/mva_panel_grch38.bed
gnomad  18,314 rows -> ressources/reference/gnomad_constraint.tsv  (3,250,168 bytes)
gnomad  panel genes present: 8/8

clinvar release (##fileDate): 2026-08-29
clinvar 17,832 rows -> ressources/reference/clinvar_panel.tsv  (2,690,034 bytes)
```

211,523 rows → **18,314**, and 95 MB → **3.2 MB**. The subset rule is Ensembl `canonical ==
true` **and** `transcript_type == protein_coding`. The alternatives were measured before
choosing: `canonical` alone gives 18,623; `mane_select` alone gives 17,481. The two extra
namespaces in the file (`NM_`/`XM_` RefSeq rows, 59,265 of them) carry `NA` for
chromosome, level and transcript type, so keeping them would have meant 40% of the table
having no chromosome. 18,314 rows cover **18,035 distinct gene symbols**.

ClinVar 4,468,152 records → **17,832** over the 8 padded regions, 2.6 MB.

### The panel, measured

All 8 symbols found in the gnomAD subset (the tool asserts this and prints `8/8`):

| gene | LoF obs/exp | oe_lof | LOEUF | decile | pLI | mis_z | syn_z |
|---|---|---|---|---|---|---|---|
| DICER1 | 41 / 193.23 | 0.21219 | 0.275 | 0 | 1 | 6.1513 | 0.60706 |
| TP53 | 12 / 43.319 | 0.27701 | 0.449 | 1 | 0.99798 | 1.1539 | 0.95837 |
| CENPE | 75 / 201.37 | 0.37245 | 0.451 | 1 | 0.99958 | 1.8159 | 0.28117 |
| TRIP13 | 23 / 55.054 | 0.41777 | 0.592 | 2 | 0.19213 | 2.6712 | 0.12328 |
| CEP192 | 92 / 179.22 | 0.51335 | 0.610 | 2 | 3.2978e-11 | 1.622 | 2.1581 |
| BUB1B | 81 / 137.83 | 0.58767 | 0.707 | 2 | 2.5766e-14 | 1.7805 | 0.5878 |
| SMC5 | 60 / 103.87 | 0.57765 | 0.716 | 2 | 1.7399e-10 | 1.6524 | 0.4547 |
| CEP57 | 34 / 61.144 | 0.55606 | 0.740 | 3 | 6.8356e-06 | 0.050453 | -0.41337 |

Genome-wide in the subset: 3,162 of 18,131 rows with a pLI (**17.4%**) reach pLI ≥ 0.9;
1,397 (**7.7%**) reach LOEUF < 0.35.

### ClinVar over the panel

Rows per contig: `4`→633, `5`→342, `9`→159, `11`→1,438, `14`→7,787, `15`→2,474, `17`→4,536,
`18`→463. Total 17,832.

| gene | rows | P / LP | VUS | benign | conflicting | no germline classification |
|---|---|---|---|---|---|---|
| DICER1 | 7,785 | 860 | 3,872 | 2,707 | 317 | 28 |
| TP53 | 3,908 | 1,147 | 958 | 1,165 | 534 | 99 |
| BUB1B | 2,471 | 84 | 1,486 | 844 | 42 | 11 |
| CEP57 | 972 | 19 | 623 | 305 | 13 | 12 |
| CENPE | 592 | 5 | 302 | 245 | 10 | 30 |
| WRAP53 | 575 | 6 | 285 | 251 | 23 | 10 |
| CEP192 | 418 | 0 | 316 | 42 | 0 | 60 |
| MTMR2 | 417 | 46 | 174 | 169 | 16 | 12 |
| TRIP13 | 242 | 9 | 84 | 136 | 2 | 11 |
| SMC5 | 159 | 5 | 119 | 12 | 0 | 23 |
| BRD9 | 100 | 0 | 65 | 8 | 0 | 27 |
| FAM76B | 49 | 0 | 34 | 1 | 0 | 14 |
| ATP1B2 | 47 | 0 | 41 | 0 | 0 | 6 |
| SEH1L | 45 | 0 | 31 | 1 | 0 | 13 |
| BDH2 | 41 | 0 | 28 | 1 | 0 | 12 |
| EFNB3 | 6 | 0 | 6 | 0 | 0 | 0 |
| PAK6 | 3 | 0 | 0 | 0 | 0 | 3 |
| DICER1-AS1 | 2 | 0 | 0 | 0 | 0 | 2 |

**8 panel genes: 16,547 rows, 2,129 pathogenic/likely-pathogenic.** The other 1,285 rows
are in genes caught by the BED's 20 kb padding.

Review status across all 17,832 rows: 373 `reviewed_by_expert_panel`, 5,174
`criteria_provided,_multiple_submitters,_no_conflicts`, 10,691
`criteria_provided,_single_submitter`, 955 `criteria_provided,_conflicting_classifications`,
257 `no_assertion_criteria_provided`, 9 `no_classification_provided`, 373 empty.

### Two correctness checks, both run

**The chr-prefix bridge actually fired.** The panel BED is `chr15`; the ClinVar VCF header
declares `##contig=<ID=1>` — bare. A query built from the unmodified BED returns zero rows,
which is indistinguishable from "this gene has no ClinVar entries". Independent
cross-check of the stripped BUB1B region:

```bash
printf "15\t40140983\t40241137\n" > _chk.bed
bcftools view -H -R _chk.bed clinvar_GRCh38.vcf.gz | wc -l     # 2474
awk -F'\t' 'NR>1 && $1=="15" && $2>40140983 && $2<=40241137' clinvar_panel.tsv | wc -l
                                                               # 2474
```

Exact agreement, which also confirms the BED 0-based → bcftools 1-based `start+1`
conversion is right.

**Positive controls found where they must be.** TP53 R175H (`17:7675088 C>T`) is present as
`Pathogenic`, `reviewed_by_expert_panel`, with `Li-Fraumeni_syndrome` among its conditions;
the `C>A` allele at the same site is `Likely_pathogenic`. BUB1B carries pathogenic entries
annotated `Mosaic_variegated_aneuploidy_syndrome_1`. These are public ClinVar coordinates,
not patient positions.

### The third table: `qc_norms.tsv`

No machine-readable upstream exists, so this one was assembled by reading sources. Method:
search, fetch the full text, and copy the number **only** from a sentence actually read.
Every PMID was resolved through NCBI eutils rather than recalled:

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id=25741868,26432245,32461654,38057664,29165669"
# 25741868 | Richards S  | 2015 | Genet Med | Standards and guidelines for the interpretation…
# 26432245 | Auton A     | 2015 | Nature    | A global reference for human genetic variation.
# 32461654 | Karczewski  | 2020 | Nature    | The mutational constraint spectrum…141,456 humans
# 38057664 | Chen S      | 2024 | Nature    | A genomic mutational constraint map…76,156 genomes
# 29165669 | Landrum MJ  | 2018 | Nucleic Acids Res | ClinVar: improving access…
curl -s ".../esearch.fcgi?db=pubmed&retmode=json&term=10.1002/bimj.202300278"   # ['38988195']
curl -s ".../esearch.fcgi?db=pmc&retmode=json&term=10.1038/s41525-021-00227-3"  # ['8282602'] → PMID 34267211
```

Result: **20 rows, 8 columns** (`metric`, `expected_low`, `expected_high`, `unit`,
`applies_to`, `source`, `url`, `basis`), 8,192 bytes, from six sources:

| Source | PMID | Rows it supplies |
|---|---|---|
| Betschart et al. 2024, *Biometrical Journal* | 38988195 | Ts/Tv genome-wide **2.0–2.1** and coding **3–4**; het/hom **1.5–1.6** EUR, **1.9–2.0** AFR, **1.3–1.7** AMR; cross-publication dbSNP concordance **70–100%**; median coverage **35×** |
| 1000 Genomes Consortium 2015, *Nature* | 26432245 | variant sites/genome **4.1M–5.0M**; SNPs/genome **3.53M (EUR) – 4.31M (AFR)**; indels/genome **546k – 625k**; SVs/genome **2,100–2,500** — all low-coverage |
| Byrska-Bishop et al. 2022, *Cell* | 36055201 | **30× per-sample**: SNVs **3,818,951 (EUR) – 4,653,521 (AFR)**; indels **826,238 – 969,792**; ins/del **0.924–0.936** |
| Taliun et al. 2021, *Nature* (TOPMed) | 33568819 | dbSNP membership per genome **99.2%** |
| Pedersen et al. 2021, *npj Genomic Medicine* | 34267211 | AF < **0.01** recessive/comp-het, AF < **0.001** de novo/dominant; **~70** de novo SNV+indel genome-wide; **13.1–18.3** candidates per WGS trio of which **9.2** compound heterozygous |
| Whiffin et al. 2017, *Genetics in Medicine* | 28518168 | corroborates the 1% / 0.1% convention |

Two of the six were found by a delegated literature agent and then **re-verified against
the primary source in this session before being written**. Nature and medRxiv return 303
or 403 to automated fetches, so the TOPMed sentence was read from the Europe PMC full-text
XML instead of the publisher page:

```bash
curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7875770/fullTextXML" \
  | tr '>' '>\n' | grep -iE 'novel|dbSNP|in each genome'
# We identified an average of 3.78 million variants in each genome. Among
# these, an average of 30,207 (0.8%) were novel and 3,510 (0.1%) were singletons.
# …
# Novel variants are taken as variants that were not present in dbSNP
# build 149, the most recent dbSNP version without TOPMed submissions.
```

So dbSNP membership per genome = 100 − 0.8 = **99.2%**, and against any post-TOPMed dbSNP
build it can only be higher. This replaces Betschart's 70–100% as the row to grade against;
the wide row is kept, renamed `dbsnp_concordance_across_publications`, to show how much
published practice varies.

The insertion/deletion ratio is **derived arithmetic, not a quoted range**, and the row
says so. From Byrska-Bishop 2022 Table 1 per-sample averages:

```
ALL 420,646 / 451,277 = 0.9321      AFR 465,797 / 503,995 = 0.9242   (low)
EUR 399,298 / 426,940 = 0.9353      EAS 406,064 / 433,635 = 0.9364   (high)
SAS 400,873 / 428,078 = 0.9364      AMR 407,428 / 435,976 = 0.9345
```

Deletions exceed insertions in every superpopulation. A callset at ins/del ≈ 1.0 is the
anomaly.

**One negative result and one correction, recorded because they matter more than the
positives.**

**1. `AF < 1e-3` is the dominant threshold, not the recessive one.** The brief for this work
assumed *gnomAD AF < 1e-3 for recessive-disease filtering*. Two independent sources say
otherwise, and neither was cherry-picked — they were the first two consulted. Pedersen 2021
methods: *Under de novo and autosomal dominant models of inheritance, we required candidate
variants to have an AF < 0.001 in each of the eight gnomAD populations*, and *for all
others, we required a frequency < 0.01*. Whiffin 2017: *the lenient values of 1 and 0.1%
often invoked as conservative frequency cutoffs for recessive and dominant diseases
respectively*. The literature-backed recessive cutoff is **1e-2**. Both thresholds are in
the table as separate rows so that filtering at 1e-3 for a compound-het search is visible
as a deliberate tightening rather than an inherited assumption. It is a real risk: at 1e-3
a genuine recessive allele that happens to sit between 1e-3 and 1e-2 is silently dropped.

**2. The GATK reference article was never read, so none of its numbers are here.**
"Evaluating the quality of a germline short variant callset" and "Hard-filtering germline
short variants" both return **HTTP 403** to automated fetches. Their figures (Ts/Tv 2.0–2.1
WGS, 3.0–3.3 WES) circulate widely in secondary sources and search summaries, and were
deliberately *not* copied from there. The table's Ts/Tv rows come from Betschart 2024,
which was read in full. Anyone with browser access should add the GATK rows.

**3. Direct-quote discipline caught one bad row before it was written.** The first pass had
no insertion/deletion row at all, because four search rounds produced only prose about
deletions being under stronger purifying selection and no number. The row exists now only
because a source with per-sample counts (Byrska-Bishop 2022 Table 1) turned up and the
division could be shown. The intermediate state — an honest gap — was the correct state.

## What the data actually looks like — five things a schema has to handle

1. **gnomAD v4.1 constraint is autosome-only.** 22 contigs, `chr1`–`chr22`. Grepping the
   gene column for `DMD`, `F8`, `AR`, `MECP2`, `XIST`, `SRY`, `RPS4Y1` returns **0 for
   every one**; `TP53` and `BUB1B` return 1 each. There is no chrX/chrY row to miss — the
   file has none. A null constraint row for an X-linked gene must render as *unknown*, not
   as *unconstrained*.
2. **`NA` is the null literal, not the empty string.** 183 rows are `NA` across every LoF
   column, 275 rows have `gene == NA`, 445 have no `loeuf_decile`, 16 have no missense
   columns, 21 no synonymous. `NULLIF(col,'NA')` on ingest.
3. **`constraint_flags` arrives as a JSON-ish list with embedded double quotes**
   (`["outlier_mis","outlier_syn"]`). Written straight through, a TSV writer quotes the
   field and the file stops being loadable by a plain `COPY … FORMAT text`. The tool
   flattens it to `outlier_mis,outlier_syn` and `[]` to empty. Verified: **zero `"`
   characters in either output file**, 26 fields on every `gnomad_constraint.tsv` line,
   10 on every `clinvar_panel.tsv` line.
4. **Gene symbol is not a primary key.** 6 symbols appear on more than one canonical
   transcript in the subset. Key on `transcript` or `ensembl_gene_id`.
5. **ClinVar cells are not scalars.** `condition` routinely packs 20+ disease names joined
   by `|` in one cell; `clnsig` can be `Pathogenic|Affects`. 3 rows have `alt == "."`.
   Longest `ref` is 7,027 characters, longest `alt` 319, and one BUB1B insertion contains a
   run of `N`. 4,442 rows have no rsid — `variation_id` is the stable key.

## Conclusions

1. **Both tables are small enough to commit and were committed whole.** 3.2 MB and 2.6 MB
   against a 10 MB target; the fallback of "panel genes plus a genome-wide summary" was
   not needed. The 95 MB and 193 MB upstream files stay in gitignored
   `build/reference-scratch/`, which the tool re-downloads on demand.
2. **Version was enumerated, not assumed.** The gnomAD release list was queried from the
   bucket API; the ClinVar release date was read from the VCF's own `##fileDate` header
   rather than from the FTP mirror's `Last-Modified`, which reflects the mirror, not the
   release.
3. **The chr-prefix bridge is now a third crossing.** `methodology/028` recorded two
   directions inside `src/mva/pipeline/variant.py` for the panel↔callset boundary. This is
   a third, panel↔ClinVar, and it fails the same silent way — zero rows, no error. It is
   handled inside `tools/build_reference_data.py` and cross-checked numerically above
   rather than trusted.
4. **pLI is the wrong instrument for this case, and the data says so.** BUB1B pLI = 2.6e-14
   and CEP57 pLI = 6.8e-06 — the two established MVA genes look *unconstrained* by pLI.
   That is correct behaviour: pLI measures intolerance to losing **one** copy, MVA is
   recessive, and healthy carriers of one broken copy are exactly who gnomAD is made of.
   Any ranking that weights pLI will push the right genes down. LOEUF (decile 2 and 3) and
   the ClinVar prior are the usable signals here. Recorded because it is a trap the
   ranking step must not walk into.
5. **The 20 kb padding leaks neighbouring genes into the ClinVar subset, deliberately.**
   1,285 of 17,832 rows are in WRAP53, MTMR2, BRD9, SEH1L, BDH2, ATP1B2, FAM76B, EFNB3,
   PAK6, DICER1-AS1. They are kept because the padding exists to catch splice and
   regulatory variation, but any per-gene number must filter on `gene` first.
6. **CEP192 has 0 pathogenic ClinVar entries, and SMC5 has 5.** Both are candidate genes,
   not established disease genes. Absence of a ClinVar prior there is expected and must
   not be scored as evidence against a candidate.
7. **The QC-norms table records what it could not source.** Every one of its 20 rows
   carries a PMID, a URL and a `basis` sentence; two rows are marked `DERIVED` and show
   their arithmetic; the GATK figures are absent because the primary source 403s. An
   incomplete table with a provenance column beats a complete one with an invented row.
8. **The brief's recessive AF threshold was wrong and the sources corrected it.** Recorded
   as a conclusion, not a footnote, because the variant-filtering step will inherit
   whichever number this table carries.
