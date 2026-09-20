# esm1b — model report

**Case:** Mosaic Variegated Aneuploidy — challenge proband 1; confirmed pair gene `BUB1B`.

**Standing:** generated 2026-09-19T23:02:33+00:00 by `mva.zoo.report.render_model_report` from run `it4-2962e3117b5c`, catalogue mode `catalogue-free`.

Every number below is a key of `it4_model_reports.report_json` for this run. Section 6 is the only written section.

## 1. Model card

| field | value |
|---|---|
| name | ESM1b variant effects (Brandes 2023) |
| version | Brandes 2023 ESM1b |
| inference tier | 1 |
| licence | MIT |
| catalogue-adjacent | no |
| reference (PMID) | 37563329 |

The only MVP lane that downloads. Found 2026-09-18 by listing the authors' Hugging Face Space
tree (https://huggingface.co/api/spaces/ntranoslab/esm_variants/tree/main):
`ALL_hum_isoforms_ESM1b_LLR.zip`, 1,335,361,543 bytes (1.24 GiB) — all ~450M missense effects
over 42,336 human protein isoforms, one CSV matrix per isoform (rows = the 20 amino acids,
columns = position + wild-type residue). Licence read from the code repository (MIT); the
Space itself states no separate data licence — verify on fetch.
The score is a log-likelihood ratio, <= 0, more negative = more damaging, so the adapter
negates it (`score_sign = -1`) to keep the zoo's "higher = more damaging" convention.
Join key: UniProt isoform accession + protein change, so this lane needs step 1's `hgvs_p`
and a UniProt mapping; records without either are uncovered, and that is a reportable number.

## 2. Inputs and coverage

Scored **4562 of 39286** allele records (11.6%).

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
| `missense_variant` | 4562 | 15620 | 29.2% |
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

![Score distribution](../../../figures/it4/score-histogram-esm1b.svg)

4562 scored alleles; min -13.619, mean 4.10138, max 17.936.

| quantile | score |
|---|---|
| p01 | -4.06719 |
| p10 | 0.6085 |
| p25 | 2.4545 |
| p50 | 3.76 |
| p75 | 5.56625 |
| p90 | 8.2286 |
| p99 | 13.6305 |

The confirmed pair's two alleles, marked on the histogram:

| allele | half | score | percentile |
|---|---|---|---|
| `addc19de8fa29228` | left | — | — |
| `93e077ae83ac2642` | right | 11.537 | 2.52 % |

## 4. The confirmed pair

This lane did not score both halves of the confirmed pair (`BUB1B`), so it is recorded as having **no opinion** on it — not a bad one. 3673 pairs were ranked here.

| half | percentile among this lane's scored alleles |
|---|---|
| left | — |
| right | 2.52 % |

Percentile is a position from the top: rank 1 of 20 is 5.00 %. The pair score is `(min, max)` of the two allele scores, sorted by `min` first — a pair is only as damaging as its weaker half.

Catalogue mode: `catalogue-free`.

## 5. What the clinical terms say

Against the child's 8 HPO terms, `BUB1B` ranks #14 of 5267 genes considered (phenotype score 0.36093, term set `with-parental`, `warehouse.hpo_gene_scores`). `esm1b` scores the molecular change only and never sees the phenotype, so this line is context for the reader, not an input to the score above.

## 6. Interpretation

This section exists in more than one version — the numbers above are identical for all of them. Each version carries a badge saying who wrote it, in which mode, and how many of its sentences resolve to a row of sections 2-5 (`mva.zoo.narrate_check`).

### 6.1 Generated — mode `claude-code`, model `claude-opus-5[1m]`, 13/13 sentences cited

<!-- interpretation: generated 2026-09-19 | llm:claude-code | model:claude-opus-5[1m] | cited 13/13 -->

This lane scored 4562 of 39286 allele records, or 11.6% of the set [cov.scored][cov.total][cov.fraction]. Every scored record is a missense_variant, covering 29.2% of that class [cov.missense_variant]. It scored none of the 12036 synonymous, 5490 intron, 2455 splice_region, 564 frameshift, 555 3_prime_UTR, or 423 splice_donor_region records [cov.synonymous_variant][cov.intron_variant][cov.splice_region_variant][cov.frameshift_variant][cov.3_prime_UTR_variant][cov.splice_donor_region_variant]. So the lane can say nothing about those classes, and its silence there is an absence of opinion, not evidence of harmlessness [cov.frameshift_variant][cov.intron_variant]. Across the 4562 scored alleles, scores run from -13.619 to 17.936 with a mean of 4.10138 [dist.n][dist.min][dist.max][dist.mean]. Half fall below 3.76, with 8.2286 at p90 and 13.6305 at p99 [dist.p50][dist.p90][dist.p99]. The confirmed pair sits in the gene BUB1B [pair.gene]. Its right half scores 11.537, at 2.52% from the top [dist.mark.right][pair.right_percentile]. The left half was not scored, so it has no percentile [dist.mark.left][pair.left_percentile]. Because one half is missing, the pair is excluded from the 3673 ranked pairs and has no rank, recorded as no opinion rather than a bad one [pair.n_ranked][pair.rank]. The run was catalogue-free, which nulls every field a ClinVar-trained model could have learned from [pair.mode]. BUB1B ranks #14 of 5267 genes against the child's 8 HPO terms, but esm1b never sees phenotype, so that line is context only [hpo.rank]. Overall the lane characterises missense change alone, not the pair as a whole [cov.missense_variant][pair.rank].

### 6.2 Hand-written

<!-- interpretation: hand-written 2026-09-19 | llm:none -->

**Citation rule:** every sentence names the section and row it rests on.

The thinnest lane in the zoo: 4,562 of 39,286 records, 29.2 % of missense (§2),
because it is keyed on a protein namespace the record set does not carry and is
reached through the publisher's own accession-to-gene map. On what it does reach
it agrees with the others about the confirmed pair's missense half — 11.537, the
**top 2.52 %** of its scored alleles, on a scale whose observed range here is
−13.619 to 17.936 (§3). Like every missense model it is silent on the
`stop_gained` partner (§3, marks, left = —), so its 3,673 ranked pairs exclude
the confirmed one and the lane has **no opinion** on it (§4). Its thinness is
worth stating twice: a lane that ranks 3,673 of 63,347 pairs still casts a full
first-place vote in a rank fusion, so its weight in §3 of the merged report is
out of proportion to what it saw. The phenotype ranking is independent of it
(§5).

_hand-written 2026-09-19_

Only this section is written rather than computed. Sections 1-5 and 7 are rendered from the stored JSON and change only when a number changes.

## 7. Limitations, licence, runtime, cost

| field | value |
|---|---|
| licence | MIT |
| venue | laptop |
| wall-clock (s) | 0 |
| cost (USD) | 0 |
| run id | `it4-2962e3117b5c` |

- Scored 11.6% of the record set; the unscored remainder is this lane's blind spot and its pairs are excluded from the ranking, not scored zero.
- 59674 biallelic pairs had an unscored half and left this ranking.
- Ran on `laptop` at zero marginal cost.
