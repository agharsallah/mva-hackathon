"""Column semantics for the result schema: what ``pg-derive`` computes and writes.

The other half of :mod:`mva.viz.catalog_columns`. A derived column is where the reading
happens — ``balance_call``, ``verdict``, ``is_rare_recessive`` are judgements, not
measurements — so these sentences say what the judgement is and where its threshold came
from, not merely what the number is.
"""

#: ``(table, column) -> meaning`` for every table in the result schema.
RESULT_COLUMNS: dict[tuple[str, str], str] = {
    # ── results: the derivation log ───────────────────────────────────────────────────
    ("derivation_runs", "run_at"): "When the derivation ran, in UTC. Appended, so every "
                                   "previous run stays visible.",
    ("derivation_runs", "derivation"): "Name of the derivation, which is also the name of "
                                       "the table it wrote.",
    ("derivation_runs", "question"): "The one question the derivation exists to answer, "
                                     "declared beside its SQL.",
    # ── results: the derived tables ───────────────────────────────────────────────────
    ("panel_gene_density", "n_filtered"): "Records the caller suppressed inside the gene "
                                          "— `n_all` minus `n_pass`.",
    ("panel_gene_density", "span_bp"): "Length of the gene's interval in bases.",
    ("panel_gene_density", "pct_pass"): "Share of the gene's records that passed the "
                                        "caller's filters.",
    ("contig_density", "length"): "Length of the contig in bases.",
    ("contig_density", "n_records"): "Variant records called on this contig.",
    ("contig_density", "pct_of_callset"): "Share of the whole callset's records that sit "
                                          "on this contig.",
    ("allele_balance_flags", "vaf_deviation"): "How far the contig's mean allele fraction "
                                               "sits from 0.50. A copy-number change "
                                               "pushes it off the line.",
    ("allele_balance_flags", "balance_call"): "`flagged` when the mean allele fraction "
                                              "leaves 0.45–0.55, `balanced` otherwise. A "
                                              "screen, not a diagnosis.",
    ("allele_balance_flags", "dp_vs_autosomal"): "The contig's mean depth over the "
                                                 "autosomal average. Near 0.5 is one "
                                                 "copy, near 1.0 two.",
    ("filter_impact", "filter_value"): "The FILTER label being counted, e.g. `PASS` or "
                                       "`LowQual`.",
    ("filter_impact", "pct_of_section"): "Share of all filtered records carrying this "
                                         "label.",
    ("filter_impact", "impact_rank"): "Rank by record count, 1 being the label that "
                                      "removes the most.",
    ("variant_density_bins", "mb"): "Which 1-megabase window of the contig this row "
                                    "covers, counted from the start.",
    ("variant_density_bins", "n"): "Variant records in the window.",
    ("variant_density_bins", "pass_n"): "Of those, how many carry `FILTER=PASS`.",
    ("variant_density_bins", "low_qual_n"): "Of those, how many have QUAL below 30.",
    ("variant_density_bins", "mean_qual"): "Mean QUAL over the window's records.",
    ("stats_sn", "metric"): "Name of the headline counter, as `bcftools stats` spells it "
                            "in its SN section, e.g. `number of SNPs`.",
    ("stats_sn", "value"): "That counter's value for this callset.",
    ("stats_tstv", "ts"): "Transitions: substitutions between two purines or two "
                          "pyrimidines (A↔G, C↔T). Chemistry makes these common.",
    ("stats_tstv", "tv"): "Transversions: substitutions between a purine and a "
                          "pyrimidine. Rarer in real data.",
    ("stats_tstv", "ratio"): "Transitions over transversions. A random error process "
                             "gives ~0.5; a real human genome gives ~2.0, which makes "
                             "this the cheapest sanity check on a callset.",
    ("stats_dp", "bin"): "Read depth, in reads, this histogram bar counts.",
    ("stats_dp", "count"): "Sites covered at that depth.",
    ("stats_dp", "pct"): "Share of all sites covered at that depth.",
    ("stats_st", "sub_type"): "The substitution, written `REF>ALT`, e.g. `A>G`.",
    ("stats_st", "count"): "How many records carry that substitution.",
    ("stats_st", "is_transition"): "Whether the substitution is a transition (A>G, G>A, "
                                   "C>T, T>C) rather than a transversion.",
    ("stats_idd", "length"): "Length of the insertion or deletion in bases — negative is "
                             "a deletion, positive an insertion.",
    ("stats_idd", "count"): "How many indels of that length the callset carries.",
    ("stats_af", "af_bin"): "The non-reference allele-frequency bin `bcftools stats` "
                            "labelled this row with. With one sample AN is always 2, so "
                            "only two bins exist: `0.0` is its singleton (AC=1) row and "
                            "`0.99` its AC=2 row. **Not** a population frequency.",
    ("stats_af", "zygosity"): "What the bin means for a single-sample callset: "
                              "`heterozygous` (one copy carries the allele) or "
                              "`homozygous alternate` (both do). Null on any callset with "
                              "more than one sample, where the bins really are allele "
                              "frequencies and neither word applies.",
    ("stats_af", "n_snps"): "Single-base substitutions in the bin.",
    ("stats_af", "n_ts"): "Of those, transitions — A↔G or C↔T, the chemically easy swaps.",
    ("stats_af", "n_tv"): "Of those, transversions — a purine swapped for a pyrimidine or "
                          "the reverse. Rarer in real data.",
    ("stats_af", "n_indels"): "Insertions and deletions in the bin.",
    ("stats_af", "n_alleles"): "Every allele in the bin — SNPs plus indels. Counted per "
                               "allele, so a multi-allelic record contributes more than "
                               "one and the column exceeds the record count.",
    ("stats_af", "ts_tv"): "Transitions over transversions inside this bin alone. A "
                           "random error process drags it toward 0.5, so a het bin "
                           "sitting well below the hom bin is false positives "
                           "concentrating where they are expected to.",
    ("stats_af", "pct_of_alleles"): "The bin's share of every allele the AF section "
                                    "counts.",
    ("sequencing_yield", "gigabytes"): "Compressed bytes delivered for the lane, in "
                                       "billions.",
    ("sequencing_yield", "n_files"): "FASTQ files the lane contributed — two per lane for "
                                     "paired-end reads.",
    ("panel_gene_constraint", "gnomad_transcript"): "Which gnomAD transcript the "
                                                    "constraint metrics on this row came "
                                                    "from. A symbol can carry several, so "
                                                    "MANE Select is preferred and the "
                                                    "choice recorded.",
    ("panel_gene_constraint", "clinvar_plp"): "ClinVar records in the gene classified "
                                              "pathogenic or likely pathogenic, excluding "
                                              "conflicting ones.",
    ("panel_gene_constraint", "clinvar_vus"): "ClinVar records of uncertain significance "
                                              "— known variants nobody has called either "
                                              "way.",
    ("panel_gene_constraint", "clinvar_benign"): "ClinVar records classified benign or "
                                                 "likely benign, excluding conflicting "
                                                 "ones.",
    ("panel_gene_background", "span_bp"): "Length of the gene's interval in bases.",
    ("panel_gene_background", "gene_variants_per_mb"): "The gene's own variant density: "
                                                       "records divided by its span in "
                                                       "megabases.",
    ("panel_gene_background", "gene_pct_pass"): "Share of the gene's records that passed "
                                                "the caller's filters.",
    ("panel_gene_background", "contig_variants_per_mb"): "The whole contig's density, "
                                                         "records over its reference "
                                                         "length in megabases.",
    ("panel_gene_background", "contig_pct_pass"): "Share of the contig's records that "
                                                  "passed, over every 1 Mb window of it.",
    ("panel_gene_background", "genome_variants_per_mb"): "The whole callset's density, "
                                                         "records over the canonical "
                                                         "contigs' length in megabases.",
    ("panel_gene_background", "genome_pct_pass"): "Share of the whole callset's records "
                                                  "that passed.",
    ("panel_gene_background", "contig_n_bins"): "How many 1 Mb windows of this contig the "
                                                "background distribution is built from.",
    ("panel_gene_background", "contig_bin_mean_density"): "Mean records per 1 Mb window on "
                                                          "this contig — the background "
                                                          "the density z is measured "
                                                          "against.",
    ("panel_gene_background", "contig_bin_sd_density"): "Standard deviation of that "
                                                        "window distribution. Null where "
                                                        "one window cannot show a spread.",
    ("panel_gene_background", "contig_bin_mean_pct_pass"): "Mean PASS share across this "
                                                           "contig's well-covered "
                                                           "windows.",
    ("panel_gene_background", "contig_bin_sd_pct_pass"): "Standard deviation of that PASS "
                                                         "share across the same windows.",
    ("panel_gene_background", "genome_n_bins"): "How many 1 Mb windows of the whole "
                                                "callset the genome background is built "
                                                "from.",
    ("panel_gene_background", "genome_bin_mean_density"): "Mean records per 1 Mb window "
                                                          "genome-wide.",
    ("panel_gene_background", "genome_bin_sd_density"): "Standard deviation of the "
                                                        "genome-wide window density.",
    ("panel_gene_background", "genome_bin_mean_pct_pass"): "Mean PASS share across every "
                                                           "well-covered window "
                                                           "genome-wide.",
    ("panel_gene_background", "genome_bin_sd_pct_pass"): "Standard deviation of that "
                                                         "genome-wide PASS share.",
    ("panel_gene_background", "z_density_vs_contig"): "How many standard deviations the "
                                                      "gene's density sits from its "
                                                      "contig's 1 Mb windows. Null where "
                                                      "the windows had no spread.",
    ("panel_gene_background", "z_density_vs_genome"): "The same distance measured against "
                                                      "every 1 Mb window of the callset.",
    ("panel_gene_background", "z_pass_vs_contig"): "How many standard deviations the "
                                                   "gene's PASS share sits from its "
                                                   "contig's windows. A callability "
                                                   "reading — mappability, repeats — "
                                                   "never a pathogenicity one.",
    ("panel_gene_background", "z_pass_vs_genome"): "The same PASS-share distance measured "
                                                   "against the whole callset's windows.",
    ("panel_candidates", "gt"): "The sample's genotype call, read out of the record's own "
                                "FORMAT keys: `0/1` is heterozygous, `1/1` homozygous "
                                "alternate, `1/2` two different alternate alleles.",
    ("panel_candidates", "dp"): "Reads covering the site for this sample.",
    ("panel_candidates", "vaf"): "Fraction of those reads carrying the alternate allele. "
                                 "Null at a `1/2` site, where no single alternate owns "
                                 "the reads.",
    ("panel_candidates", "is_rare_recessive"): "Whether the allele is rare enough to "
                                               "survive a recessive search: gnomAD "
                                               "frequency under 0.01, or absent "
                                               "altogether.",
    ("panel_candidates", "is_protein_altering"): "Whether VEP's impact is HIGH or "
                                                 "MODERATE, i.e. the allele changes the "
                                                 "protein.",
    ("panel_suppressed", "gt"): "The sample's genotype call, read out of the record's own "
                                "FORMAT keys. A suppressed `0/1` is the interesting case: "
                                "a second broken copy the caller saw but did not trust.",
    ("panel_suppressed", "dp"): "Reads covering the site for this sample. Low depth is a "
                                "common reason the record was flagged in the first place.",
    ("panel_suppressed", "gq"): "The caller's Phred-scaled confidence in the genotype it "
                                "chose, capped at 99. Distinct from QUAL, which is "
                                "confidence that the site varies at all.",
    ("panel_suppressed", "ad_ref"): "Reads supporting the reference allele.",
    ("panel_suppressed", "ad_alt"): "Reads supporting the alternate allele.",
    ("panel_suppressed", "vaf"): "Alternate reads over total reads. Null at a `1/2` site, "
                                 "where no single alternate owns the reads.",
    ("panel_suppressed", "is_het"): "Whether the genotype puts one copy of an alternate "
                                    "allele on one chromosome — the shape a compound "
                                    "heterozygote's hidden second allele would take.",
    ("panel_suppressed", "annotated_alt"): "Which of the record's alternate alleles the "
                                           "annotation columns describe. A comma-packed "
                                           "record joins to its most severe annotated "
                                           "allele, so the row stays one per record.",
    ("panel_suppressed", "annotated"): "Whether VEP was asked about any alternate allele "
                                       "of this record. False leaves every annotation "
                                       "column null — absent, never `not damaging`.",
    ("panel_filter_census", "filter"): "The FILTER value verbatim, as GATK wrote it. A "
                                       "`;`-joined value such as `LowQual;QD2` is one "
                                       "record that tripped two thresholds, counted once.",
    ("panel_filter_census", "is_pass"): "Whether this row is the gene's PASS bar. PASS is "
                                        "a row like any other here, so a gene's rows stack "
                                        "to its whole record count.",
    ("panel_filter_census", "n"): "Records in the gene carrying that FILTER value.",
    ("panel_filter_census", "n_gene_all"): "Records in the gene at every FILTER value — the "
                                           "denominator, repeated on each of its rows.",
    ("panel_filter_census", "pct_of_gene"): "`n` as a percentage of `n_gene_all`. A gene's "
                                            "percentages sum to 100.",
    ("qc_observed_expected", "metric"): "Name of the QC norm being tested.",
    ("qc_observed_expected", "label"): "The metric in plain words, for a chart axis.",
    ("qc_observed_expected", "observed"): "What this callset actually measures for the "
                                          "metric.",
    ("qc_observed_expected", "verdict"): "`within`, `below` or `above` the published "
                                         "range — the whole point of the join.",
    ("qc_observed_expected", "source"): "The publication the range came from.",
    ("qc_observed_expected", "observed_from"): "Which table and section the observation "
                                               "was measured from, so the number is "
                                               "traceable.",
    ("candidate_funnel", "stage_no"): "Position of the stage in the waterfall, 1 first. "
                                      "Also the sort key.",
    ("candidate_funnel", "stage"): "The filter this stage applies, in plain words.",
    ("candidate_funnel", "scope"): "`genome` for a stage measured over the whole callset, "
                                   "`panel` for one measurable only inside the eight-gene "
                                   "candidate panel — the only region annotation exists "
                                   "for.",
    ("candidate_funnel", "n"): "How many survive the stage. The unit changes down the "
                               "table: records, then alleles, then pairs — the note says "
                               "which.",
    ("candidate_funnel", "of_previous_pct"): "`n` as a percentage of the row above. Null "
                                             "wherever this row is not a subset of that "
                                             "one, rather than dividing two different "
                                             "populations.",
    ("candidate_funnel", "note"): "Why the filter is justified and what it does to the "
                                  "unit being counted.",
    ("panel_het_pairs", "allele_ix"): "Which alternate allele of the record this row is: 1 "
                                      "always, 2 for the second allele of a `1/2` site. It "
                                      "is what keeps the two halves of a multi-allelic "
                                      "record distinguishable in the pair grid.",
    ("panel_het_pairs", "gt"): "The sample's genotype call, read out of the record's own "
                               "FORMAT keys. Only heterozygous calls are kept: `0/1`, or "
                               "`1/2` for two different alternate alleles.",
    ("panel_het_pairs", "dp"): "Reads covering the site for this sample.",
    ("panel_het_pairs", "vaf"): "Fraction of the record's reads carrying *this* allele. "
                                "Defined at a `1/2` site too, because the row is one "
                                "allele rather than the whole record.",
    ("panel_het_pairs", "pgt"): "Which haplotype the allele sits on inside its phase set, "
                                "e.g. `0|1`. Null wherever the caller could not phase, "
                                "which is the common case.",
    ("panel_het_pairs", "pid"): "Phase-set identifier: two variants sharing it were seen "
                                "on the same reads, so their relative phase is measured. "
                                "Reach is about 300 bp. Null means unphased.",
    ("panel_het_pairs", "annotated"): "Whether VEP was asked about this exact allele. "
                                      "False leaves every annotation-derived column null "
                                      "rather than false.",
    ("panel_het_pairs", "is_rare_recessive"): "Whether the allele is rare enough to survive "
                                              "a recessive search: gnomAD frequency under "
                                              "0.01, or absent altogether. Null when the "
                                              "allele was never annotated.",
    ("panel_het_pairs", "is_protein_altering"): "Whether VEP's impact is HIGH or MODERATE, "
                                                "i.e. the allele changes the protein. Null "
                                                "when the allele was never annotated.",
    ("clinvar_presence", "variation_id"): "ClinVar's own stable identifier for the "
                                          "variant record. The key to use: 4,442 rows of "
                                          "the extract have no rsID.",
    ("clinvar_presence", "clnsig"): "ClinVar's germline classification, verbatim. Every "
                                    "row here is pathogenic or likely pathogenic, so the "
                                    "column distinguishes which combined form was "
                                    "asserted, not whether it was.",
    ("clinvar_presence", "clnrevstat"): "ClinVar's review status: how the assertion was "
                                        "arrived at, not how confident it is. Ranges from "
                                        "`practice_guideline` down to "
                                        "`no_assertion_criteria_provided`.",
    ("clinvar_presence", "review_stars"): "That review status as NCBI's gold-star count, "
                                          "4 (practice guideline) down to 0 (no assertion "
                                          "criteria). Null where ClinVar states no status "
                                          "— which is not the same as zero stars.",
    ("clinvar_presence", "condition"): "The disease name(s) ClinVar attaches to the "
                                       "record, `|`-joined. Routinely twenty of them in "
                                       "one cell.",
    ("clinvar_presence", "comparable"): "Whether the ClinVar row states an alternate "
                                        "allele a VCF record could equal. False where it "
                                        "is `.`, a placeholder that matches nothing by "
                                        "construction.",
    ("clinvar_presence", "present"): "Whether the callset contains a record for this exact "
                                     "allele. A **lower bound**: matching is exact on "
                                     "contig, position and reference plus ALT list "
                                     "membership, with no left-alignment on either side, "
                                     "so an indel spelled differently in the two sources "
                                     "reads as absent. Null — never false — where the row "
                                     "is not comparable.",
    ("clinvar_presence", "gt"): "The sample's genotype call at the matched record, read "
                                "out of its own FORMAT keys. Null where the site is "
                                "absent.",
    ("clinvar_presence", "dp"): "Reads covering the matched record for this sample.",
    ("clinvar_presence", "allele_ix"): "Which alternate of the matched record the ClinVar "
                                       "allele is: 1 on a biallelic site, 2 for the "
                                       "second allele of a comma-packed one.",
    ("clinvar_presence", "vaf"): "Fraction of the record's reads carrying *this* allele — "
                                 "its own AD entry over the record's total, so it is "
                                 "defined at a multi-allelic site too.",
    ("clinvar_presence", "carries_alt"): "Whether the genotype actually contains this "
                                         "allele. A record can list an alternate the "
                                         "sample does not carry: `0/1` on a `G -> A,C` "
                                         "record carries `A` and not `C`. Null where the "
                                         "site is absent.",
    ("clinvar_presence", "is_het"): "Whether the sample carries exactly one copy of this "
                                    "allele — the shape a recessive candidate has to have. "
                                    "True at a `1/2` site for both of its alleles. Null "
                                    "where the site is absent.",
}
