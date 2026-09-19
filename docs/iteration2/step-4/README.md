# Step 4 — likelihood-ratio ranking over the VCF

**Standing:** **complete, 2026-09-18.** Six claims filed before the run, six settled:
**three supported (H030, H034, H035), three refuted (H031, H032, H033).** The refutations are
the useful half. Hands over to [step 5](../step-5/README.md) and
[step 6](../step-6/README.md). Iteration 2, `step-4`.

**Goal** (from `src/mva/science/steps.py`):

> Over every protein-coding gene in the VCF, with no hard filter, which biallelic pair has
> the highest posterior, and what is its P(trans)?

Design: [`plan.md`](../plan.md) §3 step 4, as expanded by
[§11.5](../plan.md#115-step-4-expanded--the-only-discriminating-and-genome-wide-route).

## What this step is for

Iteration 1 used a **funnel**: rare AND protein-altering AND biallelic AND PASS, and a gene
was in or out. Steps 1–3 then measured what that costs. The symptom ranking's held-out recall
is 0.335; 73.6 % of protein-coding genes carry no curated phenotype at all; and the read
route's measured discrimination is zero. Every one of those findings says the same thing: a
cut applied early deletes evidence nobody can get back.

So this step replaces every cut with a multiplier. A common allele is divided down, a
filtered call is down-weighted, a gene nobody has curated keeps a ratio below 1, and a gene
with one damaging allele and no partner is scored at the square root of its evidence.
**Nothing is removed**, so "which gene leads" has an answer for all 11,465 of them — and
because nothing is removed, the nulls beside it are interpretable.

## Results

| | |
|---|---|
| biallelic hypotheses scored | **51,920** over **11,465** genes |
| of those, genes with **no** curated phenotype | **8,252** — 72 % of everything scored |
| shapes | 35,120 compound · 14,130 homozygous · **2,670 single** (the shape a funnel deletes) |
| alleles re-annotated for the in-silico lanes | **38,087**, with **0** refused |
| AlphaMissense coverage | 10,601 alleles; it won **22.2 %** of all allele slots, the largest single lane |
| **leader** | **`BUB1B`**, compound, ratio **341,019** |
| runner-up | `ADAMTS1` at 201,029 — **1.70× behind**, and phased **cis** |
| target vs matched decoy | **AUC 0.706 [0.655, 0.751]** — separates |
| permutation null | **55 of 1,000** random symptom sets reach the leader; p = **0.056** |
| DNA alone, phenotype lane ablated | `BUB1B` is **joint third** behind ADAMTS1 and HLA-DRB1 |
| P(trans) for the leading pair | **undetermined** — 5 of 50 alleles reach gnomAD v2 at all |

## Claims — all six resolved

| Id | Verdict | Conf. | Claim |
|---|---|---|---|
| H030 | **supported** | 0.75 | the top pair genome-wide sits in a step-1 target gene — `BUB1B`, tier core |
| H031 | **refuted** | 0.14 | the runner-up is ≥ 10× behind — it is 1.70× behind |
| H032 | **refuted** | 0.25 | no uncurated gene reaches the top 20 — `ADAMTS1` reached rank 2 |
| H033 | **refuted** | 0.15 | < 1 in 1,000 permuted term sets reach the leader — 55 do |
| H034 | **supported** | 0.95 | targets separate from matched decoys — AUC 0.706, interval excludes 0.5 |
| H035 | **supported** | 0.86 | the lead pair's P(trans) is undetermined — it is, for all 25 leading pairs |

### The three refutations, which is where the step earns its place

**H031 — the margin is 1.70×, not 10×.** Two leads go to step 6, as the refutation clause
pre-registered. The qualification is large and is carried rather than used to rescue the
claim: `ADAMTS1`'s pair is phased **cis** by the caller's own physical phasing, so both
alleles sit on one copy and it is not a compound-heterozygote hypothesis at all. 1,191 of
35,120 compound hypotheses are cis; the ranking does not filter on phase, because phase is
unknown for 97 % of pairs and a filter on it would delete the true answer.

**H032 — an uncurated gene reached rank 2, and not through the lane built for uncurated
genes.** The prediction said every top-20 gene would carry a phenotype score; `ADAMTS1` does
not. The refutation clause said such a gene would enter through the network-proximity lane;
it did not — the STRING lane fired for no gene in the top 25. `ADAMTS1` entered through the
phenotype lane's *unranked* bucket, paid its ×0.379, and overcame it on genotype evidence
alone. Both halves are recorded: the uncurated population really can reach the top, and the
lane built to let it do so contributed nothing.

**H033 — 55 of 1,000, not fewer than 1.** And the interesting part is *why*. A thousand
draws produced **four distinct top values**: 945 of them are the same number, produced by
`ADAMTS1`, which no term permutation can move because it has no rank to change. Only four
genes in the whole callset can exceed the observed value under any term set at all, and one
of them is `BUB1B` itself. Every draw that beat the leader is `HLA-DRB1` promoted into a
better rank band. The null is measuring HLA hyperpolymorphism as much as it is measuring
phenotype specificity, and `p = 0.056` quoted without that sentence would be the wrong
number ([100](methodology/100-two-nulls-and-an-ablation.md)).

### The result the step is most confident about

**H034.** Targets separate from their matched decoys at AUC **0.706 [0.655, 0.751]** — and
step 2 had already measured the same two sets as *indistinguishable* before any filter (10 of
396 each, Fisher one-sided p = 0.589, which is what refuted H020). The gene list was never an
instrument; the separation here was produced by the scoring and by nothing else. That is the
F4 measurement the plan asked for, and it is the strongest single statement in the step.

### The mechanism, reproduced without being told it

`BUB1B`'s arithmetic, printed in full:

| Lane | × | What it is |
|---|---|---|
| phenotype | 52.08 | rank 6 of 5,259, read off step 1's own measured recall curve |
| left:consequence | **350** | truncating, in the NMD-competent body of the transcript |
| left:frequency | 2.08 | absent from gnomAD |
| right:alphamissense | **4.33** | `likely_pathogenic`, capped at moderate |
| right:frequency | 2.08 | absent from gnomAD |
| the other nine lanes | 1 | said nothing, or lost their correlation group |

A null allele beside a missense allele is exactly the **null + hypomorph** model Hanks 2004
(PMID 15475955) describes for MVA1. Nothing in the scoring knew that.

## What went wrong, and was caught

| What | How it surfaced | Consequence |
|---|---|---|
| a 60 s client timeout against a request that now costs three lookups per allele | the whole annotation pass died with `ReadTimeout` after five retries | the timeout is now the caller's argument — the *options* decide it — and the pass runs at 100 alleles with 600 s |
| one allele Ensembl would not parse killed a 100-allele batch, and the batch killed the run | `400 … "G is not a supported structural variant type"`, naming one line, losing 99 answers with it | a 4xx is now `VepRejectedError`, distinct from a transport failure; a rejected batch is halved and retried down to the single allele, which is recorded and skipped. **0 alleles were skipped on the final pass** |
| a claim written into entry 099 that the genotype half alone still led | the ablation was run instead of assumed | it does not — `BUB1B` is joint third on DNA alone. The entry says so, and an evidence row against H030 records it |
| a figure clipped its own leader's number and every gene label | rendering the figure and reading it | margins set from the longest label actually drawn — the step-3 lesson, applied |

## Limitations, stated beside the results

* **The leader depends on a calibration that could not be read.** No published ACMG mapping
  for AlphaMissense or SpliceAI was reachable during the step (`science.org` 403, PMC
  CAPTCHA), so both lanes are **capped at moderate** as a pre-registered choice. The
  sensitivity run says what that costs: lowering the cap to *supporting* moves `BUB1B` to
  rank 2. This is the step's most load-bearing assumption.
* **CADD and LOFTEE contributed nothing** — Ensembl REST serves neither plugin (HTTP 500).
  The truncating lane is *LOFTEE-style* reasoning over VEP's fields and never claims the
  tool's benchmark.
* **Two HLA loci sit at ranks 3 and 5**, and they dominate the permutation null. The most
  polymorphic loci in the genome collect compound hypotheses whatever the scoring. They are
  reported, not removed — removing them would be a hard filter.
* **The phenotype lane and the target set are not independent.** Both come from one ranking,
  so H030's support is for the two routes combined; the ablation is what separates them.
* **P(trans) is a population statistic, not this child's haplotype**, and for this case it
  does not exist at all: 5 of 50 leading alleles are in gnomAD v2.
* **LOEUF is carried as a column and deliberately not a lane** — gene constraint is a
  dominant-disease signal, and making it a lane would penalise the recessive class under test.
* **A ratio orders hypotheses. It is not a calibrated probability that a gene is causal**,
  and every place that quotes one says so.
* **144 genes with more than 12 heterozygous alleles** had their pairs enumerated over the 12
  strongest. Recorded on every run; affects no gene in the top 200.

## The tools this step needed

| Thing | What it is |
|---|---|
| `src/mva/pipeline/acmg.py` | the Tavtigian ladder — four rungs, one prior, benign as the reciprocal |
| `src/mva/pipeline/likelihood.py` | `Lane`, `combine`, correlation-group damping, the printable arithmetic |
| `src/mva/pipeline/genotype_lr.py` | one calibrated tool per consequence class, LOFTEE-style NMD rules, the frequency ladder, the non-PASS down-weight, LIRICAL's degradation |
| `src/mva/pipeline/rank_lr.py` | a **measured** recall curve read as a likelihood ratio per rank |
| `src/mva/pipeline/pair_lr.py` | the three shapes, phase carried not scored, and the exact re-score the null needs |
| `src/mva/pipeline/ptrans.py` | the gnomAD co-occurrence adapter, its three states and its prior |
| `src/mva/pipeline/nulls.py` | AUC with a bootstrap interval, and the empirical p that cannot print zero |
| `src/mva/phenotype/lanes.py` · `modes.py` | the three gene-level lanes, and inheritance read from the corpus step 1 ranked on |
| `src/mva/phenotype/network.py` | `partners_url` — the endpoint step 1's network tier needed and did not call |
| `src/mva/warehouse/annotate_insilico.py` + `it2_lr_inputs.py` | the sibling annotation table, and the two queries the ranker reads |
| `src/mva/warehouse/it2_step4_tables.py` + `cli_it2.py` | three tables, three lineage rows each |
| `src/mva/warehouse/analysis_it2_lr.py` | the four derivations that answer a claim |
| `src/mva/viz/steps_it2_step4.py` + `app/src/pages/Step4.tsx` | `GET /api/steps/step-4` and the deep page |
| `tools/build_it2_network_lane.py` · `annotate_it2_insilico.py` · `rank_it2_pairs.py` · `lookup_it2_ptrans.py` · `run_it2_lr_nulls.py` | the five stages |
| `tools/export_it2_step4_analysis.py` · `it2_step4_charts.py` · `render_it2_step4_figures.py` | the one source of numbers and the eight exhibits |
| `tools/capture_step_fixture.py` | the offline dashboard fixture, rebuilt from the route's own `payload()` rather than by hand |

Every module under `src/mva/pipeline/` here is **case-agnostic**: no gene, no disease, no
coordinate. They transfer to any N-of-1 recessive problem with a VCF and a term set, which
is the second deliverable this project is built for.

## Methodology

| Entry | Question |
|---|---|
| [098](methodology/098-the-lanes-and-what-they-were-calibrated-against.md) | Which tool speaks for which allele, what is each rung worth, and what could not be read? |
| [099](methodology/099-every-gene-ordered-with-nothing-filtered-out.md) | Over every protein-coding gene in the VCF, with no hard filter, which biallelic pair leads? |
| [100](methodology/100-two-nulls-and-an-ablation.md) | How high would the leader have come out by chance, and does the scoring discriminate at all? |
| [101](methodology/101-the-phase-that-cannot-be-measured.md) | What is the leading pair's P(trans), when phase cannot be measured at all? |

Design note: [`notes/why-no-filter-anywhere.md`](notes/why-no-filter-anywhere.md).

## Exhibits

`/track1/iteration2/step-4` on the dashboard, and `figures/track1/iteration2/step-4/` (each as `.png`, plus an
`index.html` with captions and legends), rendered by `tools/render_it2_step4_figures.py` from
`build/it2/step-4/analysis.json`: `leaders`, `decomposition`, `groups`, `permutation-null`, `genotype-only`, `phenotype-bins`, `lane-coverage`, `shapes`.

## What this hands to steps 5 and 6

* **Two leads, not one** — `BUB1B` at 341,019 and `ADAMTS1` at 201,029 — with the reason the
  second is not a diagnosis (phased cis) attached to the row rather than applied as a filter.
* **A measured separation**: AUC 0.706 [0.655, 0.751] between symptom-nominated genes and
  matched controls, produced by the scoring and not by the gene list.
* **A measured non-specificity**: p = 0.056 on the permutation null, with the reason
  (two HLA loci and one unrankable gene) rather than the number alone.
* **The top-20 gene list** for step 5's knowledge engine.
* **P(trans) undetermined** for every leading pair, so the lead pair enters step 6 in failure
  category **(v) unphaseable** — both alleles real, both single-copy, no fragment spanning
  them, no parental DNA.
