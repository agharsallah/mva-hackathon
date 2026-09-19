# Iteration 4 — the merged report

**Standing:** generated 2026-09-19T16:50:24+00:00 by `mva.zoo.merge.render_merged` from run `it4-dcda40a4df2c`; merge method `fusion`.

Every number below is a key of the run's merged JSON; this page computes nothing.

## 1. The lanes

| lane | version | tier | catalogue-adjacent | pairs ranked | pairs unscored | alleles scored | confirmed rank | percentile |
|---|---|---|---|---|---|---|---|---|
| `alphamissense` | AlphaMissense hg38 2023 | 1 | no | 10333 | 53014 | 10601 | — | — |
| `esm1b` | Brandes 2023 ESM1b | 1 | no | 3673 | 59674 | 4562 | — | — |
| `revel` | REVEL 1.3 via VEP REST | 1 | yes | 10456 | 52891 | 10783 | — | — |
| `spliceai` | SpliceAI via VEP plugin (iteration 2 annotation pass) | 1 | no | 50696 | 12651 | 32534 | 11980 | 23.63 % |

> Percentile is the pair's position from the top, in percent: rank 1 of 20 is 5.0 %.
> A lane with no rank scored fewer than both alleles of the confirmed pair, and is recorded as having no opinion rather than a bad one.

## 2. Agreement between lanes

Spearman ρ (rank correlation) over the alleles both lanes scored, with the shared-allele count. An empty cell had too few shared alleles or no variance.

| ρ (n) | `alphamissense` | `esm1b` | `revel` | `spliceai` |
|---|---|---|---|---|
| `alphamissense` | +1.000 (10601) | +0.580 (3943) | +0.186 (9365) | +0.033 (9532) |
| `esm1b` | +0.580 (3943) | +1.000 (4562) | +0.168 (3997) | +0.043 (4051) |
| `revel` | +0.186 (9365) | +0.168 (3997) | +1.000 (10783) | +0.021 (9816) |
| `spliceai` | +0.033 (9532) | +0.043 (4051) | +0.021 (9816) | +1.000 (32534) |

## 3. Consensus — reciprocal rank fusion

Cormack GV, Clarke CLA, Buettcher S. Reciprocal rank fusion outperforms Condorcet and individual rank learning methods. SIGIR 2009, pp. 758-759. doi:10.1145/1571941.1572114 (verified against Crossref 2026-09-19)

| run | lanes | excluded | k | confirmed pair's RRF rank | of pairs | fused score |
|---|---|---|---|---|---|---|
| catalogue-free | alphamissense, esm1b, spliceai | revel | 60 | 20639 | 52012 | 0.000083 |
| all lanes | alphamissense, esm1b, revel, spliceai | — | 60 | 21497 | 52219 | 0.000083 |

## 4. Where the lanes disagree

Alleles in the top 1 % of one lane and the bottom half of another. A disagreement is a finding about the models, not an error in the data.

| allele | high lane | its percentile | low lane | its percentile |
|---|---|---|---|---|
| `6000716b21e7d701` | `spliceai` | 0.03 % | `alphamissense` | 89.88 % |
| `c982f5420cb3855e` | `spliceai` | 0.06 % | `revel` | 93.16 % |
| `7afc3f053087423b` | `spliceai` | 0.08 % | `alphamissense` | 87.39 % |
| `1ed22b12dcc50ba6` | `spliceai` | 0.14 % | `alphamissense` | 92.46 % |
| `1ed22b12dcc50ba6` | `spliceai` | 0.14 % | `revel` | 84.14 % |
| `1ed22b12dcc50ba6` | `spliceai` | 0.14 % | `esm1b` | 64.12 % |
| `017771f599a78157` | `spliceai` | 0.16 % | `revel` | 71.71 % |
| `017771f599a78157` | `spliceai` | 0.16 % | `alphamissense` | 60.05 % |
| `32b403b9ff4ab9cb` | `spliceai` | 0.18 % | `revel` | 90.53 % |
| `8f1f3081060a323b` | `spliceai` | 0.18 % | `esm1b` | 83.30 % |
| `8f1f3081060a323b` | `spliceai` | 0.18 % | `alphamissense` | 64.47 % |
| `32b403b9ff4ab9cb` | `spliceai` | 0.18 % | `alphamissense` | 55.74 % |
| `5d4ab3fe0cdf2a22` | `spliceai` | 0.20 % | `revel` | 92.33 % |
| `6ae8c742aa03d3a5` | `spliceai` | 0.21 % | `revel` | 77.70 % |
| `6ae8c742aa03d3a5` | `spliceai` | 0.21 % | `esm1b` | 73.54 % |
| `6ae8c742aa03d3a5` | `spliceai` | 0.21 % | `alphamissense` | 61.15 % |
| `d5518a598a7733c3` | `spliceai` | 0.22 % | `revel` | 56.22 % |
| `6bfe100cf1f416d4` | `spliceai` | 0.23 % | `esm1b` | 82.24 % |
| `ce668b09edd7c83b` | `spliceai` | 0.23 % | `revel` | 73.30 % |
| `e732f429250a61f5` | `spliceai` | 0.25 % | `revel` | 77.70 % |

70 further rows are in the run's merged JSON.

## 5. What this means

<!-- narrative: hand-written 2026-09-19 -->

**Every sentence below names the section and row it rests on. Nothing here is computed; §1–§4
are rendered from `build/it4/merged.json` and this section is the only prose in the file.**

### The headline, and it is a negative one

The zoo's consensus puts the confirmed `BUB1B` pair at **rank 20,639 of 52,012** biallelic pairs
with the catalogue-adjacent lane excluded, and **21,497 of 52,219** with it included (§3) — the
39.7th and 41.2nd percentiles. Pre-registered claim `P4-8` predicted rank 1 and named "outside
the top 5" as refuting it. **It is refuted, by four orders of magnitude.**

### Why, in one number

Read §1 rather than §3. Three of the four lanes have **no rank at all** for this pair:
AlphaMissense ranked 10,333 pairs, ESM1b 3,673, REVEL 10,456 — and the confirmed pair is in none
of those sets, because each lane scored one of its two alleles and a pair with an unscored half
is excluded rather than scored zero. Only SpliceAI ranks it, at 11,980 of 50,696. A reciprocal
rank fusion over lanes that decline to vote is not a consensus; it is one lane's opinion divided
by four. The fused score in §3, 0.000083, is exactly `1/(60 + 11980)` — SpliceAI's vote, alone,
with no other term in the sum.

### The lane gap, named

The confirmed pair is one `stop_gained` allele and one `missense_variant`. Three of the four MVP
lanes are missense-only; the fourth is a splice model. **No lane in this roster can score a
nonsense allele**, so no lane can price the pair's weaker half, and the pair score `(min, max)`
has no `min` to take. This was not discovered here: entry 114 read the two consequence classes
off the record set on day one and recorded GPN-MSA's promotion as due; entry 119 confirmed it
with coverage; entries 128 and 129 measured it as an absent rank. Four entries, one cause.

### What the lanes do say, and it is not nothing

Step 5 measured the pair one unit down, at the allele. AlphaMissense puts the missense half in
the **top 0.47 %** of the 10,601 alleles it scored, ESM1b in the **top 2.52 %** of 4,562, REVEL
in the **top 2.59 %** of 10,783. Three models of different provenance — structure-aware,
protein-language, ClinVar-trained ensemble — converge on one allele without conferring. Had
`P4-8` been written about alleles rather than pairs, this report would read the other way.

### The catalogue ablation changes nothing, which is itself a result

§3's two rows differ by 858 ranks out of ~52,000 and share an identical fused score. REVEL is
the one lane whose training set included ClinVar and therefore the one that might already know
the answer; excluding it moves the consensus by 1.5 percentile points, because it too has no
rank for this pair. **The leak a reviewer checks first is not load-bearing here.** Note also
§2: REVEL correlates with AlphaMissense at only ρ = +0.186 (n = 9,365) and with ESM1b at
+0.168 (n = 3,997) — weaker than the two catalogue-free missense lanes agree with each other
(ρ = +0.580, n = 3,943). The catalogue-trained lane is the *least* typical missense lane here.

### The agreement matrix, read honestly

§2 has two blocks. The three missense lanes agree weakly-to-moderately with one another
(+0.168 to +0.580). SpliceAI agrees with none of them — ρ = +0.021 to +0.043 over 4,051 to 9,816
shared alleles. That is not a defect: splice disruption and amino-acid damage are different
mechanisms, and a splice model that tracked a missense model would be the surprising result.
It does mean the zoo contains **one opinion about protein damage, sampled three times, and one
about splicing** — which is a thin basis for a fusion, and why §3's number should not be read as
four independent votes.

### The disagreement table is all one shape

All 20 printed rows (90 in the JSON) have SpliceAI in the top 1 % against a missense lane in the
bottom half (§4). Every one is the same event: an allele in a splice window whose amino-acid
change is unremarkable. There is not a single row of the opposite kind — no allele a missense
lane calls extreme that SpliceAI calls benign — because SpliceAI's distribution is degenerate
(median 0, p90 0.03), so almost no allele is in *its* bottom half by a meaningful margin.

### What the clinical terms say

Independently of every number above, the child's eight HPO terms rank `BUB1B` **#14 of 5,267**
genes considered (phenotype score 0.36093, term set `with-parental`; §5 of each per-model
report). No lane in this zoo sees a phenotype. The gene the models cannot collectively rank is
the gene the symptoms nominate fourteenth out of five thousand — and that disagreement between
two independent sources is the most informative line in this report.

### What to change

One lane that scores a nonsense allele. GPN-MSA (tier 1, precomputed, any SNV) is the
pre-registered answer (plan §10 R9) and its promotion has been due since entry 114. With it,
every lane can price both halves, the pair re-enters three rankings, and `P4-8` gets the revision
it is owed. Nothing else in the zoo needs to change.

_hand-written 2026-09-19_

## 6. Lineage

- run id: `it4-dcda40a4df2c`
- merge method: `fusion`, RRF k = 60
- source tables: `results.it4_model_ranks`, `warehouse.allele_scores`, `results.coding_alleles`
- built by: `mva.zoo.merge.merged_report`
