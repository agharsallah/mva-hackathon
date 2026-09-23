# ntv2 — model report

**Case:** Mosaic Variegated Aneuploidy — challenge proband 1; confirmed pair gene `BUB1B`.

**Standing:** generated 2026-09-23T23:02:25+00:00 by `mva.zoo.report.render_model_report` from run `it4-81ec74fb9f9a`, catalogue mode `catalogue-free`.

Every number below is a key of `it4_model_reports.report_json` for this run. Section 6 is the only written section.

## 1. Model card

| field | value |
|---|---|
| name | Nucleotide Transformer v2 500M |
| version | InstaDeepAI/nucleotide-transformer-v2-500m-multi-species |
| inference tier | 3 |
| licence | CC-BY-NC-SA-4.0 |
| catalogue-adjacent | no |
| reference (PMID) | 39609566 |

Runs through HF `transformers` on any GPU — the cheap tier-3 lane, and the fallback if Evo 2 will not fit.

## 2. Inputs and coverage

Scored **39286 of 39286** allele records (100.0%).

| consequence class | scored | records | fraction |
|---|---|---|---|
| `3_prime_UTR_variant` | 555 | 555 | 100.0% |
| `5_prime_UTR_variant` | 235 | 235 | 100.0% |
| `coding_sequence_variant` | 4 | 4 | 100.0% |
| `downstream_gene_variant` | 5 | 5 | 100.0% |
| `frameshift_variant` | 564 | 564 | 100.0% |
| `incomplete_terminal_codon_variant` | 2 | 2 | 100.0% |
| `inframe_deletion` | 277 | 277 | 100.0% |
| `inframe_insertion` | 211 | 211 | 100.0% |
| `intergenic_variant` | 1 | 1 | 100.0% |
| `intron_variant` | 5490 | 5490 | 100.0% |
| `mature_miRNA_variant` | 2 | 2 | 100.0% |
| `missense_variant` | 15620 | 15620 | 100.0% |
| `non_coding_transcript_exon_variant` | 129 | 129 | 100.0% |
| `protein_altering_variant` | 5 | 5 | 100.0% |
| `splice_acceptor_variant` | 128 | 128 | 100.0% |
| `splice_donor_5th_base_variant` | 121 | 121 | 100.0% |
| `splice_donor_region_variant` | 423 | 423 | 100.0% |
| `splice_donor_variant` | 122 | 122 | 100.0% |
| `splice_polypyrimidine_tract_variant` | 385 | 385 | 100.0% |
| `splice_region_variant` | 2455 | 2455 | 100.0% |
| `start_lost` | 51 | 51 | 100.0% |
| `stop_gained` | 289 | 289 | 100.0% |
| `stop_lost` | 131 | 131 | 100.0% |
| `stop_retained_variant` | 35 | 35 | 100.0% |
| `synonymous_variant` | 12036 | 12036 | 100.0% |
| `upstream_gene_variant` | 10 | 10 | 100.0% |

A class with a low fraction is this lane's blind spot, stated rather than averaged away: a pair with an unscored half is excluded from this lane's ranking, never scored zero.

## 3. Score distribution

![Score distribution](../../../figures/it4/score-histogram-ntv2.svg)

39286 scored alleles; min 6.05585e-07, mean 0.000262, max 0.198727.

| quantile | score |
|---|---|
| p01 | 1e-06 |
| p10 | 2e-06 |
| p25 | 3e-06 |
| p50 | 5e-06 |
| p75 | 1.1e-05 |
| p90 | 3.8e-05 |
| p99 | 0.003549 |

The confirmed pair's two alleles, marked on the histogram:

| allele | half | score | percentile |
|---|---|---|---|
| `addc19de8fa29228` | left | 1.67843e-05 | 16.52 % |
| `93e077ae83ac2642` | right | 5.52859e-06 | 47.75 % |

## 4. The confirmed pair

| gene | rank | of pairs | percentile | min score | max score |
|---|---|---|---|---|---|
| `BUB1B` | 15157 | 63347 | 23.93 % | 5.52859e-06 | 1.67843e-05 |

| half | percentile among this lane's scored alleles |
|---|---|
| left | 16.52 % |
| right | 47.75 % |

Percentile is a position from the top: rank 1 of 20 is 5.00 %. The pair score is `(min, max)` of the two allele scores, sorted by `min` first — a pair is only as damaging as its weaker half.

Catalogue mode: `catalogue-free`.

## 5. What the clinical terms say

Against the child's 8 HPO terms, `BUB1B` ranks #14 of 5267 genes considered (phenotype score 0.36093, term set `with-parental`, `warehouse.hpo_gene_scores`). `ntv2` scores the molecular change only and never sees the phenotype, so this line is context for the reader, not an input to the score above.

## 6. Interpretation

<!-- interpretation: hand-written 2026-09-23 | llm:none -->

_Placeholder. This is the one section prose may enter._

Only this section is written rather than computed. Sections 1-5 and 7 are rendered from the stored JSON and change only when a number changes.

## 7. Limitations, licence, runtime, cost

| field | value |
|---|---|
| licence | CC-BY-NC-SA-4.0 |
| venue | modal:L4 |
| wall-clock (s) | 0 |
| cost (USD) | 0 |
| run id | `it4-81ec74fb9f9a` |

- Ran on `modal:L4` at zero marginal cost.
