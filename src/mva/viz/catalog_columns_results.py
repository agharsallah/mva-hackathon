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
}
