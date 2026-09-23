# esm2 — model report

**Case:** Mosaic Variegated Aneuploidy — challenge proband 1; confirmed pair gene `BUB1B`.

**Standing:** generated 2026-09-23T23:02:25+00:00 by `mva.zoo.report.render_model_report` from run `it4-81ec74fb9f9a`, catalogue mode `catalogue-free`.

Every number below is a key of `it4_model_reports.report_json` for this run. Section 6 is the only written section.

## 1. Model card

| field | value |
|---|---|
| name | ESM2 650M |
| version | esm2_t33_650M_UR50D |
| inference tier | 2 |
| licence | MIT |
| catalogue-adjacent | no |
| reference (PMID) | 36927031 |

The first genuinely zero-shot lane: nothing is looked up, the model scores the substitution
from sequence alone. Laptop CPU, hours for the callset's missense set. Needs the protein
windows, which the MVP record does not build.

## 2. Inputs and coverage

Scored **15592 of 39286** allele records (39.7%).

| consequence class | scored | records | fraction |
|---|---|---|---|
| `3_prime_UTR_variant` | 0 | 555 | 0.0% |
| `5_prime_UTR_variant` | 0 | 235 | 0.0% |
| `coding_sequence_variant` | 0 | 4 | 0.0% |
| `downstream_gene_variant` | 0 | 5 | 0.0% |
| `frameshift_variant` | 0 | 564 | 0.0% |
| `incomplete_terminal_codon_variant` | 0 | 2 | 0.0% |
| `inframe_deletion` | 0 | 277 | 0.0% |
| `inframe_insertion` | 0 | 211 | 0.0% |
| `intergenic_variant` | 0 | 1 | 0.0% |
| `intron_variant` | 0 | 5490 | 0.0% |
| `mature_miRNA_variant` | 0 | 2 | 0.0% |
| `missense_variant` | 15592 | 15620 | 99.8% |
| `non_coding_transcript_exon_variant` | 0 | 129 | 0.0% |
| `protein_altering_variant` | 0 | 5 | 0.0% |
| `splice_acceptor_variant` | 0 | 128 | 0.0% |
| `splice_donor_5th_base_variant` | 0 | 121 | 0.0% |
| `splice_donor_region_variant` | 0 | 423 | 0.0% |
| `splice_donor_variant` | 0 | 122 | 0.0% |
| `splice_polypyrimidine_tract_variant` | 0 | 385 | 0.0% |
| `splice_region_variant` | 0 | 2455 | 0.0% |
| `start_lost` | 0 | 51 | 0.0% |
| `stop_gained` | 0 | 289 | 0.0% |
| `stop_lost` | 0 | 131 | 0.0% |
| `stop_retained_variant` | 0 | 35 | 0.0% |
| `synonymous_variant` | 0 | 12036 | 0.0% |
| `upstream_gene_variant` | 0 | 10 | 0.0% |

A class with a low fraction is this lane's blind spot, stated rather than averaged away: a pair with an unscored half is excluded from this lane's ranking, never scored zero.

## 3. Score distribution

![Score distribution](../../../figures/it4/score-histogram-esm2.svg)

15592 scored alleles; min -12.3246, mean 0.236909, max 12.6267.

| quantile | score |
|---|---|
| p01 | -6.08802 |
| p10 | -2.02299 |
| p25 | -0.785766 |
| p50 | 0.134342 |
| p75 | 1.12374 |
| p90 | 2.76292 |
| p99 | 7.16931 |

The confirmed pair's two alleles, marked on the histogram:

| allele | half | score | percentile |
|---|---|---|---|
| `addc19de8fa29228` | left | — | — |
| `93e077ae83ac2642` | right | 4.23406 | 4.84 % |

## 4. The confirmed pair

This lane did not score both halves of the confirmed pair (`BUB1B`), so it is recorded as having **no opinion** on it — not a bad one. 15749 pairs were ranked here.

| half | percentile among this lane's scored alleles |
|---|---|
| left | — |
| right | 4.84 % |

Percentile is a position from the top: rank 1 of 20 is 5.00 %. The pair score is `(min, max)` of the two allele scores, sorted by `min` first — a pair is only as damaging as its weaker half.

Catalogue mode: `catalogue-free`.

## 5. What the clinical terms say

Against the child's 8 HPO terms, `BUB1B` ranks #14 of 5267 genes considered (phenotype score 0.36093, term set `with-parental`, `warehouse.hpo_gene_scores`). `esm2` scores the molecular change only and never sees the phenotype, so this line is context for the reader, not an input to the score above.

## 6. Interpretation

<!-- interpretation: hand-written 2026-09-23 | llm:none -->

_Placeholder. This is the one section prose may enter._

Only this section is written rather than computed. Sections 1-5 and 7 are rendered from the stored JSON and change only when a number changes.

## 7. Limitations, licence, runtime, cost

| field | value |
|---|---|
| licence | MIT |
| venue | laptop |
| wall-clock (s) | 0 |
| cost (USD) | 0 |
| run id | `it4-81ec74fb9f9a` |

- Scored 39.7% of the record set; the unscored remainder is this lane's blind spot and its pairs are excluded from the ranking, not scored zero.
- 47598 biallelic pairs had an unscored half and left this ranking.
- Ran on `laptop` at zero marginal cost.
