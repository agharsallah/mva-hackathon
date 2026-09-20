# Iteration 4 — the merged report

**Standing:** generated 2026-09-20T13:25:46+00:00 by `mva.zoo.merge.render_merged` from run `it4-5e25dd45eee2`; merge method `fusion`.

Every number below is a key of the run's merged JSON; this page computes nothing.

## 1. The lanes

| lane | version | tier | catalogue-adjacent | pairs ranked | pairs unscored | alleles scored | confirmed rank | percentile |
|---|---|---|---|---|---|---|---|---|
| `alphamissense` | AlphaMissense hg38 2023 | 1 | no | 10333 | 53014 | 10601 | — | — |
| `esm1b` | Brandes 2023 ESM1b | 1 | no | 3673 | 59674 | 4562 | — | — |
| `esm2` | esm2_t33_650M_UR50D | 2 | no | 15749 | 47598 | 15592 | — | — |
| `gpnmsa` | GPN-MSA hg38 precomputed scores (songlab) | 1 | no | 54865 | 8482 | 35917 | 508 | 0.93 % |
| `revel` | REVEL 1.3 via VEP REST | 1 | yes | 10456 | 52891 | 10783 | — | — |
| `spliceai` | SpliceAI via VEP plugin (iteration 2 annotation pass) | 1 | no | 50696 | 12651 | 32534 | 11980 | 23.63 % |

> Percentile is the pair's position from the top, in percent: rank 1 of 20 is 5.0 %.
> A lane with no rank scored fewer than both alleles of the confirmed pair, and is recorded as having no opinion rather than a bad one.

## 2. Agreement between lanes

Spearman ρ (rank correlation) over the alleles both lanes scored, with the shared-allele count. An empty cell had too few shared alleles or no variance.

| ρ (n) | `alphamissense` | `esm1b` | `esm2` | `gpnmsa` | `revel` | `spliceai` |
|---|---|---|---|---|---|---|
| `alphamissense` | +1.000 (10601) | +0.580 (3943) | +0.546 (10601) | +0.704 (10601) | +0.186 (9365) | +0.033 (9532) |
| `esm1b` | +0.580 (3943) | +1.000 (4562) | +0.751 (4562) | +0.562 (4542) | +0.168 (3997) | +0.043 (4051) |
| `esm2` | +0.546 (10601) | +0.751 (4562) | +1.000 (15592) | +0.479 (15547) | +0.157 (10778) | +0.026 (13163) |
| `gpnmsa` | +0.704 (10601) | +0.562 (4542) | +0.479 (15547) | +1.000 (35917) | +0.221 (10783) | +0.058 (30836) |
| `revel` | +0.186 (9365) | +0.168 (3997) | +0.157 (10778) | +0.221 (10783) | +1.000 (10783) | +0.021 (9816) |
| `spliceai` | +0.033 (9532) | +0.043 (4051) | +0.026 (13163) | +0.058 (30836) | +0.021 (9816) | +1.000 (32534) |

## 3. Consensus — reciprocal rank fusion

Cormack GV, Clarke CLA, Buettcher S. Reciprocal rank fusion outperforms Condorcet and individual rank learning methods. SIGIR 2009, pp. 758-759. doi:10.1145/1571941.1572114 (verified against Crossref 2026-09-19)

| run | lanes | excluded | k | confirmed pair's RRF rank | of pairs | fused score |
|---|---|---|---|---|---|---|
| catalogue-free | alphamissense, esm1b, esm2, gpnmsa, spliceai | revel | 60 | 2734 | 59474 | 0.001844 |
| all lanes | alphamissense, esm1b, esm2, gpnmsa, revel, spliceai | — | 60 | 3482 | 59474 | 0.001844 |

## 4. Where the lanes disagree

Alleles in the top 1 % of one lane and the bottom half of another. A disagreement is a finding about the models, not an error in the data.

| allele | high lane | its percentile | low lane | its percentile |
|---|---|---|---|---|
| `379ec0d38c461aab` | `spliceai` | 0.03 % | `gpnmsa` | 91.99 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `alphamissense` | 89.88 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `gpnmsa` | 73.84 % |
| `6000716b21e7d701` | `spliceai` | 0.03 % | `esm2` | 73.38 % |
| `3d6d7940d354625a` | `gpnmsa` | 0.06 % | `esm2` | 61.98 % |
| `c982f5420cb3855e` | `spliceai` | 0.06 % | `revel` | 93.16 % |
| `626ea376c2169581` | `spliceai` | 0.08 % | `gpnmsa` | 98.29 % |
| `fa84e49f41619fe5` | `spliceai` | 0.08 % | `gpnmsa` | 99.37 % |
| `7afc3f053087423b` | `spliceai` | 0.08 % | `alphamissense` | 87.39 % |
| `fa84e49f41619fe5` | `spliceai` | 0.08 % | `esm2` | 62.27 % |
| `7afc3f053087423b` | `spliceai` | 0.08 % | `gpnmsa` | 54.02 % |
| `dbcf9e1e277868f4` | `spliceai` | 0.09 % | `esm2` | 76.03 % |
| `fe5f9f335c5feeee` | `spliceai` | 0.10 % | `gpnmsa` | 68.58 % |
| `043dd14c63f399d3` | `spliceai` | 0.10 % | `gpnmsa` | 66.88 % |
| `043dd14c63f399d3` | `spliceai` | 0.10 % | `esm2` | 58.25 % |
| `5f7ef0dce74aa311` | `gpnmsa` | 0.11 % | `esm1b` | 61.03 % |
| `5f7ef0dce74aa311` | `gpnmsa` | 0.11 % | `esm2` | 56.40 % |
| `0e2cac5237e3170f` | `spliceai` | 0.12 % | `gpnmsa` | 70.09 % |
| `221b12b9e9d0fd70` | `spliceai` | 0.13 % | `esm2` | 63.77 % |
| `86e40af3fcaf3da5` | `gpnmsa` | 0.13 % | `esm2` | 91.77 % |

180 further rows are in the run's merged JSON.

## 5. What this means

This section exists in more than one version — the numbers above are identical for all of them. Each version carries a badge saying who wrote it, in which mode, and how many of its sentences resolve to a row of sections 1-4 (`mva.zoo.narrate_check`).

### 5.1 Synthesised — mode `claude-code`, model `claude-opus-5[1m]`, 8/8 sentences cited

<!-- narrative: synthesised 2026-09-20 | llm:claude-code | model:claude-opus-5[1m] | cited 8/8 -->

The lanes were merged by reciprocal rank fusion with k = 60; a lane that never ranks a pair contributes nothing to it [method]. Four of the six — alphamissense, esm1b, esm2 and revel — have no rank for the confirmed pair: each scored only one of its two alleles, so the pair left their rankings [lane.alphamissense.rank][lane.esm1b.rank][lane.esm2.rank][lane.revel.rank]. That is abstention, not disagreement: esm2's report says an unscored half leaves the lane with no opinion rather than a bad one, and gpnmsa's calls such silence missing measurement, not evidence of absence [interp.esm2][interp.gpnmsa]. Only two lanes rank the pair — gpnmsa at 508 of 54865, 0.93% from the top, and spliceai at 11980 of 50696, 23.63% [lane.gpnmsa.rank][lane.spliceai.rank]. The fused positions, 2734 of 59474 excluding revel and 3482 including it, therefore rest on those two [rrf.free.rank][rrf.all.rank]. One lane, revel, is catalogue-adjacent, since ClinVar was in its training data [lane.revel.rank]. Where lanes do overlap they may order alleles similarly, +0.751 for esm1b and esm2, or almost independently, +0.021 for revel and spliceai, and 200 alleles sit in the top 1% of one lane and the bottom half of another [rho.esm1b.esm2][rho.revel.spliceai][disagree.n]. The consensus cannot claim the lanes agree here, only that most never weighed in [method].

### 5.2 Hand-written

<!-- narrative: hand-written 2026-09-19 -->

**Every sentence below names the section and row it rests on. Nothing here is computed; §1–§4
are rendered from `build/it4/merged.json` and this section is the only prose in the file.**

**The headline, and it is a negative one.** The zoo's consensus puts the confirmed `BUB1B` pair at **rank 20,639 of 52,012** biallelic pairs
with the catalogue-adjacent lane excluded, and **21,497 of 52,219** with it included (§3) — the
39.7th and 41.2nd percentiles. Pre-registered claim `P4-8` predicted rank 1 and named "outside
the top 5" as refuting it. **It is refuted, by four orders of magnitude.**

**Why, in one number.** Read §1 rather than §3. Three of the four lanes have **no rank at all** for this pair:
AlphaMissense ranked 10,333 pairs, ESM1b 3,673, REVEL 10,456 — and the confirmed pair is in none
of those sets, because each lane scored one of its two alleles and a pair with an unscored half
is excluded rather than scored zero. Only SpliceAI ranks it, at 11,980 of 50,696. A reciprocal
rank fusion over lanes that decline to vote is not a consensus; it is one lane's opinion divided
by four. The fused score in §3, 0.000083, is exactly `1/(60 + 11980)` — SpliceAI's vote, alone,
with no other term in the sum.

**The lane gap, named.** The confirmed pair is one `stop_gained` allele and one `missense_variant`. Three of the four MVP
lanes are missense-only; the fourth is a splice model. **No lane in this roster can score a
nonsense allele**, so no lane can price the pair's weaker half, and the pair score `(min, max)`
has no `min` to take. This was not discovered here: entry 114 read the two consequence classes
off the record set on day one and recorded GPN-MSA's promotion as due; entry 119 confirmed it
with coverage; entries 128 and 129 measured it as an absent rank. Four entries, one cause.

**What the lanes do say, and it is not nothing.** Step 5 measured the pair one unit down, at the allele. AlphaMissense puts the missense half in
the **top 0.47 %** of the 10,601 alleles it scored, ESM1b in the **top 2.52 %** of 4,562, REVEL
in the **top 2.59 %** of 10,783. Three models of different provenance — structure-aware,
protein-language, ClinVar-trained ensemble — converge on one allele without conferring. Had
`P4-8` been written about alleles rather than pairs, this report would read the other way.

**The catalogue ablation changes nothing, which is itself a result.** §3's two rows differ by 858 ranks out of ~52,000 and share an identical fused score. REVEL is
the one lane whose training set included ClinVar and therefore the one that might already know
the answer; excluding it moves the consensus by 1.5 percentile points, because it too has no
rank for this pair. **The leak a reviewer checks first is not load-bearing here.** Note also
§2: REVEL correlates with AlphaMissense at only ρ = +0.186 (n = 9,365) and with ESM1b at
+0.168 (n = 3,997) — weaker than the two catalogue-free missense lanes agree with each other
(ρ = +0.580, n = 3,943). The catalogue-trained lane is the *least* typical missense lane here.

**The agreement matrix, read honestly.** §2 has two blocks. The three missense lanes agree weakly-to-moderately with one another
(+0.168 to +0.580). SpliceAI agrees with none of them — ρ = +0.021 to +0.043 over 4,051 to 9,816
shared alleles. That is not a defect: splice disruption and amino-acid damage are different
mechanisms, and a splice model that tracked a missense model would be the surprising result.
It does mean the zoo contains **one opinion about protein damage, sampled three times, and one
about splicing** — which is a thin basis for a fusion, and why §3's number should not be read as
four independent votes.

**The disagreement table is all one shape.** All 20 printed rows (90 in the JSON) have SpliceAI in the top 1 % against a missense lane in the
bottom half (§4). Every one is the same event: an allele in a splice window whose amino-acid
change is unremarkable. There is not a single row of the opposite kind — no allele a missense
lane calls extreme that SpliceAI calls benign — because SpliceAI's distribution is degenerate
(median 0, p90 0.03), so almost no allele is in *its* bottom half by a meaningful margin.

**What the clinical terms say.** Independently of every number above, the child's eight HPO terms rank `BUB1B` **#14 of 5,267**
genes considered (phenotype score 0.36093, term set `with-parental`; §5 of each per-model
report). No lane in this zoo sees a phenotype. The gene the models cannot collectively rank is
the gene the symptoms nominate fourteenth out of five thousand — and that disagreement between
two independent sources is the most informative line in this report.

**What to change.** One lane that scores a nonsense allele. GPN-MSA (tier 1, precomputed, any SNV) is the
pre-registered answer (plan §10 R9) and its promotion has been due since entry 114. With it,
every lane can price both halves, the pair re-enters three rankings, and `P4-8` gets the revision
it is owed. Nothing else in the zoo needs to change.

_hand-written 2026-09-19_

## 6. Lineage

- run id: `it4-5e25dd45eee2`
- merge method: `fusion`, RRF k = 60
- source tables: `results.it4_model_ranks`, `warehouse.allele_scores`, `results.coding_alleles`
- built by: `mva.zoo.merge.merged_report`
