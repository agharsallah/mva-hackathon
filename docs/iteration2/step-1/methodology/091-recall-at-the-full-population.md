# 091 — Does H012's recall@300 hold at the full population?

**Written:** 2026-09-12, before the run. **Run:** 2026-09-12. **Step:** `step-1` (iteration 2).
**Hypothesis re-tested:** H012 (verdict **refuted** in [084](084-the-blind-target-set.md); this
entry tests whether that verdict survives removing the sampling).
**Verified:** against HPO release `hp/releases/2026-06-23`, the same release 084 ran on.

Entry 084 measured the symptom-only ranker's held-out recall on **200 of 3,240** eligible
recessive diseases and recorded the sampling as its first stated limitation. That limitation
is now removable: one run over the whole eligible population costs only wall-clock time. The
question is not whether H012 flips — 0.360 is nowhere near 0.90 and no re-test moves it there
— but whether the *number itself* is a property of the corpus or of the 200 diseases the seed
happened to draw. Everything downstream quotes it: the target set is described as an
enrichment with "measured recall ≈ 0.36", and that phrase must be defensible without the word
"sample" beside it.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| public | `hp.obo` — the ontology graph (ancestor closure, term labels, the noise vocabulary) | `hp/releases/2026-06-23`, sha256 `a5092cbd…` |
| public | `genes_to_phenotype.txt` — the curation corpus that is ranked, and the disease list the population is drawn from | same release, sha256 `26cb7ee0…` |
| clinical | none read by the benchmark itself. The benchmark ranks *held-out diseases*, not this child: the proband's terms (`ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md`, 7 + 8 terms) fix only the **query size** (7 terms) and the **inheritance filter** (recessive), so the curve measures the ranker under this case's conditions rather than ideal ones | via `mva.phenotype.benchmark.QUERY_TERMS` and `RECESSIVE` |

**No genomic data of this child was read.** No iteration-1 table was read — no candidate
gene, rank or tier appears in this entry, and `mva-science check --blind iteration2` is the
gate. No table produced by iteration 1 or by step 2 is an input here.

## Hypothesis and prediction — written before the run

- **H012 (re-test).** Held-out recall@300 over the **full** eligible population falls inside
  the 200-sample's own 95 % bootstrap interval, **[0.295, 0.420]**.
- The point estimate is expected near 0.360, and the full-population interval is expected to
  be **narrower** than the sample's, because a bootstrap interval's width falls roughly as
  1/√n and n rises from 200 to the full eligible count.
- The verdict of H012 in the register — **refuted** — is expected to stand either way: the
  prediction it was tested against was 0.90.

## What would refute it

- Full-population recall@300 **outside [0.295, 0.420]**. That would mean the sampled run was
  not representative and the quoted 0.36 is an artefact of the draw. The remedy, fixed in
  advance: file an evidence row citing this entry, add a **new revision** of H012 carrying the
  full-population number and the reason, and correct every downstream page and doc that quotes
  0.36 to the full-population value.
- Secondary (does not by itself refute): a full-population interval **wider** than the
  sample's would mean the bootstrap is not behaving as resampling theory says and the interval
  arithmetic needs checking before any further recall is quoted.
- A run that changes the *eligible population* count away from 3,240 would mean the two runs
  were not drawn from the same corpus, and the comparison would be void rather than informative.

## Commands

```
uv run mva-phenotype benchmark --sample 3240 --seed 20260910 \
  --out build/it2/step-1/benchmark-full.json
```

`--sample` has no "all" spelling: it caps the draw, and `run()` takes the whole population
when the cap is not smaller than it (`sample < len(chosen)` is false), so 3,240 — the eligible
count 084 reported — runs every eligible disease. The seed is 084's, so the two runs share the
degradation draws for the diseases they have in common.

## Observed

Ran 2026-09-12, 2h16m of one core on the laptop; the eligible population came out at
**3,240**, the same count 084 reported, so the two runs are drawn from the same corpus.

### The curve, both runs side by side

| N | full population (3,240) | 95 % bootstrap | sampled run (200), from 084 | 95 % bootstrap |
|---|---|---|---|---|
| 1 | 0.003 | [0.002, 0.006] | 0.000 | [0.000, 0.000] |
| 10 | 0.027 | [0.022, 0.033] | 0.030 | [0.010, 0.055] |
| 50 | 0.106 | [0.095, 0.117] | 0.125 | [0.080, 0.175] |
| **300** | **0.335** | **[0.318, 0.350]** | **0.360** | **[0.295, 0.420]** |
| 1000 | 0.508 | [0.491, 0.524] | 0.565 | [0.495, 0.630] |

- **recall@300 = 0.335**, inside the sampled run's interval [0.295, 0.420] — the
  prediction held.
- The full-population interval is **0.032 wide against the sample's 0.125**, a factor of
  3.9. Resampling theory predicts √(3240/200) = 4.0. The bootstrap is behaving.
- Median rank **363** (sample: 326). **901 of 3,240 genes unrankable** — 27.8 %, against
  24.5 % in the sample: the held-out disease is the only curation those genes have, at
  *any* N.
- Every point of the sampled curve sits at or above the full-population point, and at
  N = 1000 the sampled estimate (0.565) is outside the full-population interval
  [0.491, 0.524]. The 200 diseases the seed drew were, slightly, an easier set than the
  corpus.

Output: `build/it2/step-1/benchmark-full.json`. It is served by `GET /api/steps/step-1`
beside the sampled run, so the page draws both curves and nobody has to take the
comparison on trust.

## Verdict

| Claim | Prediction of this entry | Verdict |
|---|---|---|
| H012 (re-test) | recall@300 inside [0.295, 0.420] | **supported** — 0.335 |
| secondary: narrower interval | width falls ≈ 1/√n | **supported** — 3.9× against 4.0 predicted |
| secondary: same population | 3,240 eligible | **supported** — 3,240 |

**H012's register verdict does not change and no revision is filed.** The claim was
"recall@300 ≥ 0.90"; 0.335 refutes it exactly as 0.360 did, and the refutation condition
this entry pre-registered (a number outside the sampled interval) did not fire. Per the
standing rule, a belief that did not change is not re-revised.

**What does change is the wording downstream.** 084 handed step 2 "measured recall ≈ 0.36",
qualified as a 200-disease sample. The defensible figure is now **0.335 [0.318, 0.350] over
the whole eligible population**, with no sampling caveat attached, and it is slightly
*worse* than the sampled number rather than better. Every page and doc that quotes the
recall should quote the full-population value; the `/steps/step-1` and `/phenotype`
exhibits read it from the served payload rather than from typed prose, so they follow
automatically.

**The enrichment decision stands, and is now firmer.** Recall@1000 is 0.508 — raising N
from 300 to 1000 still buys under +0.18 for 3.3× the bait, and 27.8 % of held-out genes
cannot be placed at any N at all. No cutoff of a phenotype-only ranker reaches coverage on
this corpus. The target set remains an **enrichment**, a gene absent from it is not thereby
excluded, and the safety net remains step 4's genome-wide ranking.

**Assumptions and limitations.** (1) Unchanged from 084: ground truth and scoring database
share curators, so this is an internal consistency check, not an external validation, and it
carries no genomic background. (2) The degradation parameters (1–2 terms blurred to a
parent, 1–2 noise terms) still follow Zemojtel 2014 and are still untuned to this corpus —
this entry removes the *sampling* limitation only. (3) One seed: the queries are one
degradation draw per disease, not an average over draws, so a second seed would move the
curve by an amount this run does not measure. (4) The intervals are bootstrap intervals over
outcomes, which does not account for correlation between diseases that share a gene.

**Quality checks run.** Eligible population re-counted from the same file and matched 084's
3,240; interval width compared against the 1/√n prediction; the JSON the figure and the
endpoint read is the file this run wrote, not a transcription.

## What this changes for the record

- `build/it2/step-1/benchmark-full.json` exists and is the primary recall source.
- No register write: no verdict moved, so both append-only tables are untouched.
- The dictionary gains **Zemojtel-style degradation** and **bootstrap interval**, the two
  terms this entry's argument rests on.
