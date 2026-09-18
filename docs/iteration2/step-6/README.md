# Step 6 — fusion and unblinding

**Standing:** **complete, 2026-09-18.** Four claims filed before the run, four settled:
**two supported (H043, H044), two refuted (H041, H042).** The refutations are again the
useful half. Hands over to [step 7](../step-7/README.md). Iteration 2, `step-6`.

**Goal** (from `src/mva/science/steps.py`):

> Fused across steps 2-5 and then unblinded, does iteration 2 rediscover iteration 1's pair,
> and is a second upload informative?

Design: [`plan.md`](../plan.md) §3 step 6, as pre-registered by
[§11.6](../plan.md#116-step-6-pre-registered-now).

## The headline, both halves

**Starting from the raw reads, the callset and eight clinical terms, with no iteration-1
table read until the last entry, the fused ranking puts the same two `BUB1B` alleles first** —
the truncating allele with dbSNP `rs759242053` and the missense allele with no identifier,
which is exactly what was uploaded and confirmed
([083](../../iteration1/step-6/methodology/083-oracle-reply-submission-1.md)). Rank 1 under
equal weights and rank 1 under measured-error-rate weights.

**And one route carried it.** Silence the genome-wide likelihood ranker and the leader falls
from rank 1 to rank **62**. The symptom route put it at rank 9 of its own list; the literature
route never listed it at all. The honest sentence is *"one route found it, two corroborated it
at a distance, and one instrument confirmed it in the raw reads"* — not "the routes
converged".

## Results

| | |
|---|---|
| routes admitted to the fusion | **3 of 4** — `phenotype`, `likelihood`, `knowledge`; the read route confirms at weight 0 |
| pairs fused | **274**, from a universe of 51,410 coordinate-free keys |
| **frozen ranking** | `build/it2/step-6/fused-ranking.tsv`, sha256 **`a596abf8…`**, recorded in [108](methodology/108-the-ranking-frozen-before-anyone-looked.md) before the comparison |
| **fused rank 1** | `BUB1B` · truncating `rs759242053` + missense (no rsid) — **the confirmed pair** |
| its per-route ranks | likelihood **1** · phenotype **9** · knowledge **not listed** |
| its confirmation triple | read-confirmed · single copy · no CN loss — **all three** |
| its independent-evidence count | **3 of 4** disjoint inputs (HPO, VCF, reads); the literature is missing |
| leave-one-route-out | without `likelihood` the leader falls to **62**; without `knowledge` or `phenotype` it stays at **1** |
| measured-error-rate weights | leader still rank 1; `CLCNKB` falls 2 → 49 |
| decoy reach | a matched control gene reaches fused rank **13**; targets median 109, decoys median 42 |
| expected information gain of a second upload | **0.000 bits** on all three questions |
| oracle budget | **5 of 6 remain**, deliberately |

## Claims — all four resolved

| Id | Verdict | Conf. | Claim |
|---|---|---|---|
| H041 | **refuted** | 0.20 | fused rank 1 **and** no route below rank 3 — rank 1 held, two routes did not |
| H042 | **refuted** | 0.12 | no single route carries the result — the likelihood route does |
| H043 | **supported** | 0.80 | the leader has ≥ 2 disjoint inputs behind it — it has 3 of 4 |
| H044 | **supported** | 0.90 | a second upload is not informative — 0.000 bits on every question |

### The two refutations, which is where the step earns its place

**H042 — one route carries the fusion.** The ablation was pre-registered precisely because
reciprocal rank fusion treats correlated lists as independent witnesses. It does not here:
two routes ranked on the same eight clinical terms, two read the same callset, and the
knowledge route was seeded with the likelihood route's top 20. The route-dependency graph in
[107](methodology/107-the-routes-and-which-of-them-earned-a-rank.md) shows which edges those
are; the independent-evidence count is the arithmetic correction.

**H041 — the first clause held, the second failed on two routes of three.** Rank 1 is the
finding the report leads on. Ranks 9 and "not listed" are the finding about the *instruments*:
a symptom ranker with a measured held-out recall of 0.335 puts the known answer at rank 9 of
its own list, and a literature route misses a gene carrying a ClinVar-pathogenic truncating
allele. Both are measurements of those routes, not footnotes about this case.

### Why no second upload

Three questions a second Track 1 upload could be aimed at, each simulated against the local
replica of the published scorer:

| Question | EIG | Why |
|---|---|---|
| the causal pair | 0.000 bits | the first reply collapsed the space to a single point; its entropy is 0 |
| a second causal pair | 0.000 bits | **not expressible** — the answer key holds one or two alleles, so "both" is not a reply this oracle can give |
| secondary findings | 0.000 bits | simulated with and without three secondary rows: the identical reply |

The runner-up is real — `ADAMTS1`, 1.70× behind on the likelihood ratio, rank 2 under measured
weights — so the plan's fourth decision row is live in fact. It is closed by the **instrument's
limits**, not by the absence of a candidate, and that distinction is the finding.

## What step 6 read from every earlier step

Step 6 is the only step that uses all of it. Nothing below is re-derived here; each number is
read from the table or entry that owns it.

| From | Measured finding | Where step 6 used it |
|---|---|---|
| [1](../step-1/README.md) | recall@300 **0.335** [0.318, 0.350] | weight of the `phenotype` route in the second analysis; quoted with every rediscovery claim |
| 1 | **73.6 %** of protein-coding genes uncurated · 404 targets · 396 matched decoys | the "could not have found" caveat; the decoy column of every exhibit |
| [2](../step-2/README.md) | bait recall **0.905** [0.815, 0.974] | why the read route is admitted as confirmation at all |
| 2 | discrimination **0** — 10/396 vs 10/396, Fisher p = **0.589** | the pre-registered reason it contributes no rank; shown at weight 0, never deleted |
| 2 | **1,199** alleles the vendor never reported · concordance 0.9957 / 0.9927 | the `read_confirmed` flag and the instrument-trust table |
| 2 | **6,823 phase blocks, none reaching the pair's coding span** | phase is *unmeasured*, not absent — failure category (v) |
| [3](../step-3/README.md) | vendor-reported confirmed **96.1 %**, vendor-unreported **35.3 %** | the trust attached to the confirmation triple, per allele origin |
| 3 | CN median **2.00** autosomal, **0.95** on X; null band [1.028, 2.823] | the `no_cn_loss` flag, and the control that licenses it |
| [4](../step-4/README.md) | **51,920** hypotheses over **11,465** genes; leader ratio 341,019 | the `likelihood` route's ordering |
| 4 | AUC **0.706** [0.655, 0.751] · permutation p = **0.056** | the route's admission, recomputed here from the same rows; and its measured weight (0.944) |
| 4 | runner-up **1.70×** behind, phased **cis** · P(trans) **undetermined** | carried on the row, never applied as a filter; failure category (v) |
| [5](../step-5/README.md) | knowledge AUC **0.634** [0.595, 0.672]; ρ vs citations **0.024** | the `knowledge` route's admission, via step 5's own `RouteWeight.ranking_route` |
| 5 | the admission rule itself | called, not restated — a second copy is a second copy able to disagree |

## Methodology

| Entry | What it did | Blind? |
|---|---|---|
| [107](methodology/107-the-routes-and-which-of-them-earned-a-rank.md) | the four routes, their admission measurements, the dependency graph, both weightings | blind |
| [108](methodology/108-the-ranking-frozen-before-anyone-looked.md) | the fusion, the leave-one-out table, the freeze and its sha256 — **H042, H043** | blind |
| [109](methodology/109-what-the-mirror-found.md) | **the unblinding**: the comparison, the decision row, the upload arithmetic — **H041, H044** | unblinds |

## How to reproduce it

```bash
uv run python tools/fuse_it2_routes.py           # prints the sha256 it froze
uv run mva-warehouse pg-load-it2-step6
uv run mva-warehouse pg-derive --only it2_fusion_matrix   # and stability, evidence, reach
uv run python tools/assess_it2_upload.py
uv run python tools/unblind_it2.py               # the only stage that reads iteration 1
uv run python tools/export_it2_step6_analysis.py
uv run python tools/render_it2_step6_figures.py
uv run python tools/check_blind.py               # "unblinded by …/109-…"
```

## What this step cannot tell you

- **A rediscovery is not coverage.** recall@300 is 0.335; the route found *this* pair, and
  says nothing about the next case.
- **The ranking below rank 1 has poor resolution.** Rank inheritance means the fused top 20
  is three genes, not twenty candidates, and a matched decoy gene holds ranks 13–20.
- **The confirmation triple is gene-level**, because the k-mer genotype table carries no
  variant identifier to join a pair's side on.
- **Phase is still unmeasured.** The pair is in *trans* because the oracle's answer key says
  so — the one fact in this step that comes from the reply rather than from the mirror.
- **`ranx` was not adopted** as a cross-check of the fusion arithmetic; the tests compute
  every sum by hand from the published formula instead. Recorded as a cut, not an omission.

## Exhibits

`/steps/step-6` on the dashboard, and `figures/track1/iteration2/step-6/`:
`agreement-matrix`, `leave-one-route-out`, `independent-evidence`, `weight-sensitivity`,
`decoy-reach`, `freeze-receipt`.
