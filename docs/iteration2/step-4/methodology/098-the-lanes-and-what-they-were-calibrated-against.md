# 098 — Which tool speaks for which allele, what each rung is worth, and what could not be read

**Written:** 2026-09-18. **Step:** `step-4` (iteration 2).
**Hypotheses:** H030–H035, all six filed **before** this entry's first command ran. This is
an *input and calibration* entry: it fixes the numbers the ranking will use and builds the
annotation table it reads. The claims are settled in
[099](099-every-gene-ordered-with-nothing-filtered-out.md),
[100](100-two-nulls-and-an-ablation.md) and [101](101-the-phase-that-cannot-be-measured.md).
Precedent for an input entry with no verdict of its own:
[093](../../step-3/methodology/093-where-the-aligner-was-unsure.md) and
[095](../../step-3/methodology/095-the-probes-and-the-counting-kernel.md).

**Supersedes nothing.** It records four deviations from [`plan.md` §3 step 4](../../plan.md)
and the reason for each.

## Hypothesis and prediction

The six claims, as filed (`uv run mva-science show H030` … `H035`):

| Id | Plan label | Claim |
|---|---|---|
| H030 | plan H020 | the top-posterior pair genome-wide sits in a gene of the step-1 target set |
| H031 | plan H021 | the runner-up **gene**'s posterior is ≥ 1 order of magnitude below the leader's |
| H032 | *substitute* | no gene entering only through the network-proximity lane reaches the top 20 |
| H033 | plan H032 | < 1 in 1,000 permuted seven-term sets produce a top posterior ≥ the observed one |
| H034 | new (F4) | target genes separate from matched decoys — the bootstrap AUC interval excludes 0.5 |
| H035 | new (goal) | the lead pair's P(trans) is `undetermined` — ≥ 1 allele absent from gnomAD v2 |

H032 replaces the plan's H022 (Exomiser human-only ranks the same top gene in its top 5).
No amd64 VM was provisioned, so no reference run exists;
[plan §11.9 limitation (iii)](../../plan.md#119-cuts-re-decided) already pre-recorded this,
and the substitute tests the §11.5 network lane instead.

## What would refute the calibration itself

Not a hypothesis — a gate. The annotation pass fails if the table lands with fewer rows than
`results.coding_alleles` has distinct alleles, or if any allele is silently dropped. A
rejected allele must be **named and counted**, never absent.

## The lanes, fixed before any score was seen

One calibrated tool per consequence class, which is Pejaver 2022's own recommendation and
the reason these constants live in `src/mva/pipeline/genotype_lr.py` rather than in a tuning
script.

| Class | Tool | Rungs |
|---|---|---|
| protein-truncating | LOFTEE-style rules over the transcript (Karczewski 2020) | very strong in the NMD-competent body; strong in the penultimate exon or with no exon numbering; moderate in the last exon or a single-exon transcript |
| missense | AlphaMissense's own three-class call (Cheng 2023) | `likely_pathogenic` → moderate; `ambiguous` → 1; `likely_benign` → supporting benign |
| splice window | SpliceAI Δ = max(DS_AG, DS_AL, DS_DG, DS_DL) (Jaganathan 2019) | ≥ 0.8 → moderate; ≥ 0.5 → supporting; ≥ 0.2 → 1; < 0.2 → supporting benign |
| synonymous / other | the consequence class alone | silent and outside the splice window → supporting benign |
| any | ClinVar | P/LP → strong; B/LB → strong benign; conflicting → **1, in neither direction** |
| any | gnomAD frequency | absent or < 1e-4 → supporting; ≥ 1e-3 → moderate benign; ≥ 5e-3 → strong benign |
| any | the caller's FILTER | non-PASS → ×⅓, a **down-weight and never a cut** |

The ladder itself is Tavtigian 2018's: prior 0.10, and 350 / 18.7 / 4.33 / 2.08 for very
strong / strong / moderate / supporting — each rung the square root of the one above it.
Benign evidence divides where pathogenic evidence multiplies.

**Every lane above shares one correlation group.** A missense predictor trained on ClinVar
and ClinVar itself are not independent, and nor are a canonical splice-site consequence and
a SpliceAI score for the same base. Exactly one of them contributes — the strongest — and
the rest are kept in the record, damped and named. Frequency and FILTER are separate,
because neither was trained on the others.

### Two calibrations that could not be read, and what was done instead

The plan said "strength from its published calibration" for AlphaMissense and SpliceAI.
**Neither paper's ACMG mapping could be read during this step**: `science.org` returned 403
and PMC's SpliceAI copy returned a CAPTCHA page. Rather than invent a rung:

* the **Δ cutoffs** are taken from SpliceAI's own documentation (0.2 high recall, 0.5
  recommended, 0.8 high precision), which is the tool authors' own statement;
* the **class boundaries** for AlphaMissense are not hard-coded at all — the tool's own
  `am_class` field is used, so the threshold is whatever its authors published;
* the **mapping from a cutoff to an ACMG rung is a choice this entry pre-registers**, and
  both lanes are therefore **capped at moderate**. They may argue, but never at full
  strength.

This is stated wherever either lane is quoted. It is the step's largest soft spot.

## Four deviations from the plan, recorded now

| Plan said | What happened | Consequence |
|---|---|---|
| CADD as a tie-break outside the calibrated lanes | `?CADD=1` on Ensembl REST returns **HTTP 500** — the plugin is not served, and no local file exists | the lane does not exist in this iteration; the plan had already demoted it, so no calibrated lane is lost |
| LOFTEE for the truncating lane | `?LoF=1` also returns **HTTP 500** | rules reimplemented from Karczewski 2020 over VEP's own fields; this is *LOFTEE-style* reasoning and never claims the tool's benchmark |
| P(trans) fallback = "the paper's rare-pair base rate" | Guo 2024's number could not be read | the **uninformative prior 0.5** is used instead — two heterozygous variants in one gene are, with no information, equally likely cis as trans — and `base_rate()` measures an empirical rate from whatever pairs did resolve |
| IHW over depth and LOEUF for multiple testing | not run | the **number of hypotheses tested** is printed beside every ratio, and the permutation null gives an empirical p-value; LOEUF is carried as a column and deliberately **not** made a lane, because it is a dominant-disease constraint signal and this is a recessive hypothesis |

## The phenotype lane is measured, not asserted

The plan said "converted per LIRICAL's formulation". LIRICAL's phenotype LR is per-term
against a disease; what exists here is a per-gene similarity score in 0–1, and any
conversion between the two would be invented. So the ratio *is* the ranker's own measured
performance:

* `P(rank = r | causal)` comes from step 1's held-out benchmark — 3,240 recessive diseases,
  each with its own disease's contribution removed from the corpus and its terms degraded
  Zemojtel-style ([084](../../step-1/methodology/084-the-blind-target-set.md),
  [091](../../step-1/methodology/091-recall-at-the-full-population.md));
* `P(rank = r | not causal)` is flat at `1 / 19,723`, the protein-coding gene count.

`src/mva/pipeline/rank_lr.py` divides the two per rank band:

| Symptom rank | Causal mass | Null mass | Likelihood ratio |
|---|---|---|---|
| 1 | 0.00340 | 0.00005 | **66.96** |
| 2–10 | 0.02377 | 0.00046 | 52.08 |
| 11–50 | 0.07870 | 0.00203 | 38.81 |
| 51–300 | 0.22870 | 0.01268 | 18.04 |
| 301–1000 | 0.17346 | 0.03549 | 4.89 |
| 1001–5267 | 0.21389 | 0.21635 | **0.99** |
| no rank at all | 0.27809 | 0.73304 | **0.379** |

Both columns sum to 1, so the arithmetic closes over the whole genome. The last row is the
reason this step can see the 73.6 % of genes nobody has curated: they are **down-weighted by
2.6×, not deleted**.

## The network lane, and a defect it exposed in step 1

[Plan §11.5](../../plan.md#115-step-4-expanded--the-only-discriminating-and-genome-wide-route)
asks that `mva.phenotype.network` be reused here to score uncurated genes by STRING
proximity to the top-50. Step 1 ran it and got **zero rows**, and the reason turns out to be
the endpoint:

* `GET /api/json/network?identifiers=…` returns only the edges **among** the identifiers
  given. By construction it can never name a gene that was not already a seed.
* `GET /api/json/interaction_partners?identifiers=…` returns the edges that **leave** the
  seed set, which is the only way an uncurated gene can enter.

With the second endpoint, the top-50 ranked genes at STRING's own high-confidence cut (700)
return **1,575 edges** and **569 uncurated neighbours**. `network_url` is kept with a
docstring saying what it is for; `partners_url` is new.

The lane is capped at *supporting*: a neighbour has no phenotype evidence of its own, only a
neighbour that has some. Its ratio is `2.08 ** (proximity / best proximity)`, so it runs
from 1 to 2.08 and no further, and it fires **only** for a gene with no phenotype rank — it
subdivides the unranked bucket rather than offering a second opinion about a gene that
already has one.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `results.coding_alleles` — 38,437 rows, **38,087 distinct alleles**, 11,465 genes, every FILTER kept | `analysis_coding.py`, built in iteration 1 |
| api | Ensembl VEP REST, release **116**, assembly **GRCh38** (`GCA_000001405.29`) | read from `/info/software` and `/info/assembly`, not assumed |
| api | STRING `interaction_partners`, species 9606, `required_score=700` | URL recorded in `build/it2/step-4/network.json` |
| derived | `build/it2/step-1/benchmark-full.json` — the measured recall curve | [091](../../step-1/methodology/091-recall-at-the-full-population.md) |
| clinical | the proband's seven terms, through the phenotype lane and the seed list | `Challenge_Clinical_Phenotype_1.md`, via [084](../../step-1/methodology/084-the-blind-target-set.md) |

## Commands

```
uv run mva-science hypothesis-add --step step-4 …      # H030-H035, before anything else
uv run python tools/build_it2_network_lane.py --seeds 50
uv run python tools/annotate_it2_insilico.py --batch-size 100 --workers 12 --timeout 600
```

## Observed — the annotation pass

| | |
|---|---|
| alleles asked about | **38,087** |
| rows landed in `warehouse.it2_insilico_annotations` | **38,087** |
| alleles the server refused to parse | **0** |
| with a consequence | 38,087 |
| with an **AlphaMissense** score | **10,601** |
| with a **SpliceAI** delta | **32,534** |
| with exon numbering (`n/m`) | 29,806 |
| with a gnomAD frequency | 37,904 |
| with a ClinVar assertion | 9,506 |
| distinct genes | 11,313 |

The table is a **sibling** of `coding_annotations` on the same four-key join, exactly as
`it2_read_annotations` is. The platform table is not altered, so iteration 1's derivations
read byte-identical rows.

### Two defects found while the pass ran

**A 60-second client timeout against a request that now costs three lookups per allele.**
Asking for AlphaMissense and SpliceAI makes VEP do two extra lookups per allele, and a
200-allele batch stopped answering inside the client's timeout. Five retries later the whole
pass died with `ReadTimeout`. Fixed by making the timeout a caller's argument — the options
decide it — and running at 100 alleles with 600 s.

**One unparseable allele killed a whole batch, and the batch killed the run.** Ensembl
answered a 100-allele POST with
`400 … "G is not a supported structural variant type"`, naming one line. The other 99
answers went with it. Fixed properly rather than worked around:

* a 4xx is now `VepRejectedError`, distinct from a transport `VepError` — one means "ask
  again", the other means "this payload will never be accepted";
* a rejected batch is **halved and retried** down to the single allele, which is recorded in
  `annotator.skipped` with its reason and left out.

On the final pass **zero alleles were skipped**, so the mechanism cost nothing and the gate
above is met. Both behaviours have regression tests
(`tests/test_annotate_vep.py::TestRetries`).

## Conclusion

The lanes, the rungs, the caps and the four deviations are fixed and written down before any
ranking exists. The annotation table is complete at 38,087 of 38,087 alleles with nothing
dropped. The phenotype lane is the one number in the step that is **measured on this
project's own held-out benchmark** rather than taken from a paper, and the network lane
exists at all only because step 1's endpoint choice was wrong.

Next: [099](099-every-gene-ordered-with-nothing-filtered-out.md).
