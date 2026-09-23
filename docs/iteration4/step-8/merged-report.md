# Iteration 4 — the merged report

**Standing:** generated 2026-09-23T23:02:28+00:00 by `mva.zoo.merge.render_merged` from run `it4-81ec74fb9f9a`; merge method `fusion`.

Every number below is a key of the run's merged JSON; this page computes nothing.

## 1. The lanes

| lane | version | tier | catalogue-adjacent | pairs ranked | pairs unscored | alleles scored | confirmed rank | percentile |
|---|---|---|---|---|---|---|---|---|
| `alphamissense` | AlphaMissense hg38 2023 | 1 | no | 10333 | 53014 | 10601 | — | — |
| `esm1b` | Brandes 2023 ESM1b | 1 | no | 3673 | 59674 | 4562 | — | — |
| `esm2` | esm2_t33_650M_UR50D | 2 | no | 15749 | 47598 | 15592 | — | — |
| `esmc` | esmc_600m esm==3.1.1 hf:biohub/esmc-600m-2024-12@e4d83bc7e10f | 3 | no | 15749 | 47598 | 15592 | — | — |
| `evo2` | evo2_1b_base | 3 | no | 63347 | 0 | 39286 | 10362 | 16.36 % |
| `gpnmsa` | GPN-MSA hg38 precomputed scores (songlab) | 1 | no | 54865 | 8482 | 35917 | 508 | 0.93 % |
| `ntv2` | InstaDeepAI/nucleotide-transformer-v2-500m-multi-species | 3 | no | 63347 | 0 | 39286 | 15157 | 23.93 % |
| `revel` | REVEL 1.3 via VEP REST | 1 | yes | 10456 | 52891 | 10783 | — | — |
| `spliceai` | SpliceAI via VEP plugin (iteration 2 annotation pass) | 1 | no | 50696 | 12651 | 32534 | 11980 | 23.63 % |

> Percentile is the pair's position from the top, in percent: rank 1 of 20 is 5.0 %.
> A lane with no rank scored fewer than both alleles of the confirmed pair, and is recorded as having no opinion rather than a bad one.

## 2. Agreement between lanes

Spearman ρ (rank correlation) over the alleles both lanes scored, with the shared-allele count. An empty cell had too few shared alleles or no variance.

| ρ (n) | `alphamissense` | `esm1b` | `esm2` | `esmc` | `evo2` | `gpnmsa` | `ntv2` | `revel` | `spliceai` |
|---|---|---|---|---|---|---|---|---|---|
| `alphamissense` | +1.000 (10601) | +0.580 (3943) | +0.546 (10601) | +0.539 (10601) | +0.544 (10601) | +0.704 (10601) | -0.017 (10601) | +0.186 (9365) | +0.033 (9532) |
| `esm1b` | +0.580 (3943) | +1.000 (4562) | +0.751 (4562) | +0.743 (4562) | +0.555 (4562) | +0.562 (4542) | -0.025 (4562) | +0.168 (3997) | +0.043 (4051) |
| `esm2` | +0.546 (10601) | +0.751 (4562) | +1.000 (15592) | +0.855 (15592) | +0.467 (15592) | +0.479 (15547) | -0.002 (15592) | +0.157 (10778) | +0.026 (13163) |
| `esmc` | +0.539 (10601) | +0.743 (4562) | +0.855 (15592) | +1.000 (15592) | +0.481 (15592) | +0.473 (15547) | -0.006 (15592) | +0.160 (10778) | +0.034 (13163) |
| `evo2` | +0.544 (10601) | +0.555 (4562) | +0.467 (15592) | +0.481 (15592) | +1.000 (39286) | +0.530 (35917) | +0.015 (39286) | +0.160 (10783) | +0.059 (32534) |
| `gpnmsa` | +0.704 (10601) | +0.562 (4542) | +0.479 (15547) | +0.473 (15547) | +0.530 (35917) | +1.000 (35917) | +0.012 (35917) | +0.221 (10783) | +0.058 (30836) |
| `ntv2` | -0.017 (10601) | -0.025 (4562) | -0.002 (15592) | -0.006 (15592) | +0.015 (39286) | +0.012 (35917) | +1.000 (39286) | -0.051 (10783) | +0.047 (32534) |
| `revel` | +0.186 (9365) | +0.168 (3997) | +0.157 (10778) | +0.160 (10778) | +0.160 (10783) | +0.221 (10783) | -0.051 (10783) | +1.000 (10783) | +0.021 (9816) |
| `spliceai` | +0.033 (9532) | +0.043 (4051) | +0.026 (13163) | +0.034 (13163) | +0.059 (32534) | +0.058 (30836) | +0.047 (32534) | +0.021 (9816) | +1.000 (32534) |

## 3. Consensus — reciprocal rank fusion

Cormack GV, Clarke CLA, Buettcher S. Reciprocal rank fusion outperforms Condorcet and individual rank learning methods. SIGIR 2009, pp. 758-759. doi:10.1145/1571941.1572114 (verified against Crossref 2026-09-19)

| run | lanes | excluded | k | confirmed pair's RRF rank | of pairs | fused score |
|---|---|---|---|---|---|---|
| catalogue-free | alphamissense, esm1b, esm2, esmc, evo2, gpnmsa, ntv2, spliceai | revel | 60 | 4318 | 63269 | 0.002005 |
| all lanes | alphamissense, esm1b, esm2, esmc, evo2, gpnmsa, ntv2, revel, spliceai | — | 60 | 5005 | 63269 | 0.002005 |

## 4. Where the lanes disagree

Alleles in the top 1 % of one lane and the bottom half of another. A disagreement is a finding about the models, not an error in the data.

| allele | high lane | its percentile | low lane | its percentile |
|---|---|---|---|---|
| `1e6ea7e996fcd2d9` | `ntv2` | 0.00 % | `evo2` | 98.38 % |
| `406fecdb53ecd31c` | `spliceai` | 0.00 % | `ntv2` | 75.06 % |
| `172b125bf2637198` | `esmc` | 0.01 % | `ntv2` | 54.47 % |
| `1933704432136e8a` | `ntv2` | 0.01 % | `evo2` | 90.63 % |
| `25345ab0485eca02` | `gpnmsa` | 0.02 % | `ntv2` | 53.49 % |
| `d93004a0b5f42cb3` | `ntv2` | 0.02 % | `evo2` | 99.70 % |
| `172b125bf2637198` | `esm1b` | 0.02 % | `ntv2` | 54.47 % |
| `e2df2545d4963b07` | `gpnmsa` | 0.03 % | `ntv2` | 86.34 % |
| `8a23c2c4d9d4b08e` | `gpnmsa` | 0.03 % | `ntv2` | 58.73 % |
| `6087882f501315a5` | `esmc` | 0.03 % | `ntv2` | 96.59 % |
| `6087882f501315a5` | `esmc` | 0.03 % | `esm2` | 54.01 % |
| `f7f9757b58947e51` | `revel` | 0.03 % | `ntv2` | 56.28 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `evo2` | 96.95 % |
| `379ec0d38c461aab` | `spliceai` | 0.03 % | `gpnmsa` | 91.99 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `alphamissense` | 89.88 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `esmc` | 85.60 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `gpnmsa` | 73.84 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `esm2` | 73.38 % |
| `30a19418b503df1a` | `esm2` | 0.03 % | `ntv2` | 52.21 % |
| `a7c5e35c07d36374` | `esmc` | 0.03 % | `ntv2` | 50.37 % |

180 further rows are in the run's merged JSON.

## 5. What this means

<!-- narrative: hand-written 2026-09-23 -->

_(narrative not yet written)_

## 6. Lineage

- run id: `it4-81ec74fb9f9a`
- merge method: `fusion`, RRF k = 60
- source tables: `results.it4_model_ranks`, `warehouse.allele_scores`, `results.coding_alleles`
- built by: `mva.zoo.merge.merged_report`
