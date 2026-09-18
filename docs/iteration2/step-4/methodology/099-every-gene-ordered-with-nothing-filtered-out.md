# 099 — Over every protein-coding gene in the VCF, with no hard filter, which biallelic pair leads?

**Written:** 2026-09-18. **Step:** `step-4` (iteration 2).
**Hypotheses:** **H030 supported**, **H031 refuted**, **H032 refuted**. All three were filed
before [098](098-the-lanes-and-what-they-were-calibrated-against.md) ran; the lanes, the
rungs and the caps were fixed there and are not touched here.

**Supersedes nothing.** It is the first genome-wide ordering of this case that drops no gene.

## Hypothesis and prediction

* **H030** — the top-posterior pair genome-wide sits in a gene of the step-1 target set.
  *Predicted:* the rank-1 gene carries tier `core`, `mechanism-term` or `net` in
  `results.it2_targets`.
* **H031** — the runner-up **gene**'s best ratio is at least an order of magnitude below the
  leader's. *Predicted:* `leader / runner-up ≥ 10`.
* **H032** — no gene entering only through the network-proximity lane reaches the top 20.
  *Predicted:* every top-20 gene carries a phenotype score, and the count entering solely
  via STRING proximity is zero.

## What would refute them

* H030: the rank-1 gene is absent from `it2_targets` — the symptom-derived target set was
  too small, and step 2's discovery is re-run on that gene.
* H031: the ratio is under 10× — the ranking does not separate a single lead, and **two**
  leads go to step 6.
* H032: a top-20 gene has no phenotype score and entered through the network lane alone —
  the lane is promoted from tie-break to evidence and the report says so.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| derived | `results.coding_alleles` — 38,437 rows, every FILTER and every zygosity kept | `analysis_coding.py` |
| warehouse | `coding_annotations` (38,087) ∪ `it2_insilico_annotations` (38,087) | [098](098-the-lanes-and-what-they-were-calibrated-against.md) |
| warehouse | `hpo_gene_scores`, term set `proband-only` — 5,259 genes ranked | entry 067 / [084](../../step-1/methodology/084-the-blind-target-set.md) |
| derived | `results.it2_targets` (404) · `results.it2_decoys` (396) | [084](../../step-1/methodology/084-the-blind-target-set.md) |
| derived | `results.it2_kmer_pairs` — the read route's confirmation triple, carried, **no rank** | [096](../../step-3/methodology/096-the-alleles-at-their-multiplicity.md) |
| derived | `build/it2/step-4/network.tsv` — 569 uncurated neighbours | [098](098-the-lanes-and-what-they-were-calibrated-against.md) |
| reference | `warehouse.gnomad_constraint` — LOEUF, carried as a **column, not a lane** | gnomAD v4.1 |
| clinical | the seven proband terms, through the phenotype lane | `Challenge_Clinical_Phenotype_1.md` |

## Commands

```
uv run python tools/rank_it2_pairs.py
uv run mva-warehouse pg-load-it2-step4
uv run mva-warehouse pg-derive --only it2_lr_top_pairs
uv run mva-warehouse pg-derive --only it2_lr_target_decoy
uv run mva-warehouse pg-derive --only it2_lr_uncurated
uv run mva-warehouse pg-derive --only it2_lr_lane_coverage
```

## Observed — what was scored

| | |
|---|---|
| allele rows carried | **38,437** |
| genes with at least one carried allele | **11,465** |
| biallelic hypotheses scored | **51,920** |
| prior per gene | 1 / 19,723 = 5.070 × 10⁻⁵ |
| genes with **no** curated phenotype, scored anyway | **8,252** (72.0 % of the genes scored) |
| genes whose ratio exceeds 1 | 208 |
| genes whose ratio exceeds 100 | 34 |

| Shape | Hypotheses | Genes | Median ratio | Largest |
|---|---|---|---|---|
| compound | 35,120 | 4,398 | 0.0003 | 341,019 |
| homozygous | 14,130 | 6,070 | 0.0098 | 13,134 |
| **single** | 2,670 | 2,670 | 0.0987 | 59.6 |

The `single` row is the shape iteration 1's funnel deleted outright: one damaging allele and
nothing on the other copy. It is kept at the square root of its evidence (Robinson 2020), and
nothing in it reached the top 20 — which is the outcome that makes keeping it cheap.

144 genes carry more than 12 heterozygous alleles and had their pairs enumerated over the 12
strongest rather than exhaustively. The count is recorded on the run; a gene with 60 carried
alleles is a mapping artefact and 1,770 pairs of it would swamp the table.

## Observed — the ordering

| # | Gene | Shape | Origin | Symptom rank | Ratio | Behind leader | Phase |
|---|---|---|---|---|---|---|---|
| 1 | **BUB1B** | compound | core target | 6 | **341,019** | — | unknown |
| 2 | ADAMTS1 | compound | uncurated | — | 201,029 | 1.70× | **cis** |
| 3 | HLA-DRB1 | compound | curated | 523 | 143,934 | 2.37× | unknown |
| 4 | PEX5 | homozygous | net target | 220 | 13,134 | 25.97× | — |
| 5 | HLA-DQA1 | compound | curated | 1,547 | 6,474 | 52.68× | unknown |
| 6 | RAI1 | compound | mechanism-term | 290 | 3,158 | 108× | **cis** |
| 7 | POU6F2 | compound | curated | 400 | 855 | 399× | **cis** |
| 8 | SLC67A1 | homozygous | core target | 24 | 726 | 470× | — |

### H030 — supported

`BUB1B` carries tier **core** in `results.it2_targets`. The gene the child's symptoms
nominated at rank 6, with the DNA never read, is also the gene a genome-wide likelihood ratio
puts first with no filter anywhere.

**The two routes are not independent, and the ablation says how much that matters.** With the
phenotype lane set to 1 for every gene — what the DNA alone would have nominated — the
ordering is:

| # | Gene | Genotype-only ratio |
|---|---|---|
| 1 | ADAMTS1 | 529,850 |
| 2 | HLA-DRB1 | 29,451 |
| 3 | **BUB1B** | **6,548** |
| 3= | HLA-DQA1 | 6,548 |

**The DNA alone does not nominate BUB1B first; it puts it joint third behind an uncurated
gene and two HLA loci.** The symptoms are doing real work, and H030 is support for the
*combination* of the two routes rather than for either one. Stated here because the opposite
reading — "the genome-wide scan found it independently" — is the one a reader would otherwise
take, and it is not what happened. The full ablation is in [100](100-two-nulls-and-an-ablation.md).

**The decomposition reproduces the published mechanism.** BUB1B's arithmetic, printed:

| Lane | × | What it is |
|---|---|---|
| phenotype | 52.08 | rank 6 of 5,259, read off the measured recall curve |
| left:consequence | **350** | truncating, in the NMD-competent body of the transcript |
| left:frequency | 2.08 | absent from gnomAD |
| right:alphamissense | **4.325** | `likely_pathogenic`, capped at moderate |
| right:frequency | 2.08 | absent from gnomAD |
| everything else | 1 | said nothing, or lost its correlation group |

A null allele beside a missense allele is exactly the **null + hypomorph** model Hanks 2004
(PMID 15475955) describes for MVA1. Nothing in the scoring was told that; the two lanes
that fired are the two the published mechanism predicts.

### H031 — refuted

`341,019 / 201,029 = 1.70×`, well inside one order of magnitude. **Two leads go to step 6**,
as the refutation clause pre-registered.

The honest qualification, and it is a large one: **ADAMTS1's pair is phased `cis` by the
caller's own physical phasing.** Both alleles sit on the same copy of the chromosome, so one
copy of the gene is intact and it is not a compound-heterozygote hypothesis at all. The
ranking does not use phase — by design, since phase is unknown for 97 % of pairs and a filter
on it would delete the true answer — so it is carried on the row and not scored.

| Phase | Hypotheses | Of which compound |
|---|---|---|
| unknown | 50,545 | 33,745 |
| **cis** | 1,191 | 1,191 |
| trans | 184 | 184 |

Four of the top twelve compound pairs are `cis` (ADAMTS1, RAI1, POU6F2, CIROP). Recorded
rather than filtered: the claim is refuted on the number it was filed against, and step 6
receives both the number and the reason the runner-up is not a diagnosis.

### H032 — refuted, but not in the way the refutation clause described

The prediction was that **every** top-20 gene carries a phenotype score. ADAMTS1 does not:
it is one of the 14,523 genes nobody has curated, and it came second genome-wide.

The refutation clause said such a gene would "enter through the network lane alone".
**It did not.** `entered_by_network` is false for every uncurated gene in the top 25 — the
STRING lane fired for none of them. ADAMTS1 entered through the phenotype lane's *unranked*
bucket, which costs ×0.379, and overcame it on genotype evidence alone.

So the claim is **refuted on its prediction and not by its stated mechanism**, and both halves
are worth carrying: the uncurated population really can reach the top of a genome-wide
ranking, and the lane built to let it do so contributed nothing. The lane's own value is
settled in [100](100-two-nulls-and-an-ablation.md) with the decoy null beside it.

## Observed — which tool actually spoke

The top of `it2_lr_lane_coverage`, over 87,050 allele slots (one per allele per hypothesis
side):

| Class | Lane that won its correlation group | Slots | % |
|---|---|---|---|
| missense | **alphamissense** | 19,353 | 22.2 |
| silent | consequence | 15,821 | 18.2 |
| missense | clinvar | 10,820 | 12.4 |
| silent | clinvar | 9,597 | 11.0 |
| other | spliceai | 8,322 | 9.6 |
| missense | spliceai | 7,204 | 8.3 |
| truncating | consequence | 3,308 | 3.8 |
| splice | spliceai | 3,088 | 3.6 |
| missense | *no lane spoke* | 3,036 | 3.5 |

AlphaMissense is the single largest contributor, which is the retrospective justification for
the extra VEP pass: without it, 22 % of allele slots would have been scored by their
consequence class alone. CADD and LOFTEE contributed nothing because neither is served
([098](098-the-lanes-and-what-they-were-calibrated-against.md)).

## Limitations, stated beside the result

* **Two HLA genes sit at ranks 3 and 5.** `HLA-DRB1` and `HLA-DQA1` are the most polymorphic
  loci in the genome; a gene where every human carries many rare-looking alleles will collect
  compound hypotheses whatever the scoring. They are reported, not removed — removing them
  would be a hard filter, which is the thing this step exists not to have.
* **The missense and splice lanes are capped, and the cap decides the leader.** Measured,
  not assumed — see the sensitivity table below.
* **LOEUF is carried and not scored.** Gene constraint is a dominant-disease signal;
  recessive disease genes are frequently unconstrained, and making it a lane would have
  penalised exactly the class under test.
* **The ratio is not a probability of causation.** It is a transparent product of
  pre-registered terms, and every place that quotes it says so.
* **The phenotype lane and the target set are not independent.** Both come from the same
  ranking, so H030's support is weaker than it looks; the genotype-only ablation in
  [100](100-two-nulls-and-an-ablation.md) is the number that separates them.

## The sensitivity analysis 098 pre-registered

Four constants in the scoring are **choices** rather than measurements: the two lane caps,
the non-PASS down-weight, and the inheritance prior. Each was moved and the whole ranking
re-run with the same code (`--missense-ceiling`, `--splice-ceiling`, `--non-pass-lr`,
`--no-inheritance`), so what follows is five runs of one scorer, not five scorers.

| Run | Top five, by ratio |
|---|---|
| **as pre-registered** | BUB1B 3.41e5 · ADAMTS1 2.01e5 · HLA-DRB1 1.44e5 · PEX5 1.31e4 · HLA-DQA1 6.47e3 |
| caps raised to *strong* | **identical**, including BUB1B's own ratio |
| caps lowered to *supporting* | **ADAMTS1 2.01e5 · BUB1B 1.64e5** · HLA-DRB1 1.44e5 · PEX5 1.31e4 · HLA-DQA1 6.47e3 |
| non-PASS down-weight removed (×1) | identical |
| inheritance prior off | BUB1B 3.41e5 · **HLA-DRB1 2.88e5** · ADAMTS1 2.01e5 · PEX5 1.31e4 · HLA-DQA1 6.47e3 |

Three readings, and one of them is uncomfortable:

1. **Raising the cap changes nothing, by construction.** `cap()` only ever lowers a rung;
   AlphaMissense's `likely_pathogenic` is assigned *moderate* intrinsically, so a ceiling of
   *strong* leaves it there. The run is still worth having — it proves the cap is not
   secretly doing work in the other direction.
2. **Lowering the cap to *supporting* costs BUB1B the lead.** At ×2.08 instead of ×4.33 its
   ratio falls to 1.64e5 and ADAMTS1 takes rank 1. The leader therefore **depends on the
   missense lane being worth at least moderate** — which is precisely the calibration 098
   could not read from a paper. This is the step's most load-bearing assumption and it is
   named here rather than buried.
3. **The inheritance prior is doing visible work on the runner-up.** With it off, HLA-DRB1
   (dominant-only, ×0.5) rises to rank 2 at 2.88e5. BUB1B still leads. The prior was fixed in
   step 1 before any score was seen, and the run with it removed is reported beside the run
   with it applied, which is what `mva.pipeline.inheritance` was built to make possible.

The non-PASS down-weight moves nothing: every allele in the top five is a PASS call.

## Conclusion

Every gene in the callset is ordered and none is dropped. `BUB1B` leads (H030 supported),
the margin claim fails at 1.70× (H031 refuted, and the runner-up is phased *cis*), and an
uncurated gene reached rank 2 without the lane built for uncurated genes (H032 refuted).

Next: [100](100-two-nulls-and-an-ablation.md).
