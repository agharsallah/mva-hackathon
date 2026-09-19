# 123 — The denominator that assumes nothing, read back

**Written:** 2026-09-19. **Step:** `step-8` (iteration 2).
**Hypotheses:** **H054** — one evidence row added; the verdict of
[121](121-the-second-instrument-and-the-shards-it-did-not-need.md) stands.

**Supersedes nothing; completes 121 on one point.** Entry 121 announced *two denominators,
deliberately* — the autosomal median (assumes most autosomes are normal) and the absolute
k-mer mass (assumes nothing about chromosomes) — and then reported every table against the
median only. The plan named the absolute denominator as defence (c) against the failure mode
the disease is named for: several chromosomes abnormal at once, which is exactly when a
median divisor lies ([plan §3 step 8](../../plan.md)). The audit that prepared the iteration-2
Track 1 report found the column computed but never read. This entry reads it.

## Hypothesis and prediction

- **H054** (defence c) — the absolute denominator names no chromosome the median denominator
  does not. *Predicted:* on every contig the ratio `absolute / relative` equals one constant
  (the autosomal median count divided by the calibration set's mean), to within the
  composition-corrected residual spread of 121 (0.802 %).

## What would refute it

- Any contig whose `absolute / relative` ratio departs from the common constant by more than
  0.8 %. That would mean the two divisors disagree *about that chromosome*, and 121's "no
  autosome beyond its null" would rest on the median assumption alone.

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| derived | `build/it2/step-8/dosage.json` — per contig `relative`, `absolute`, `disagreement`; written by `tools/run_it2_dosage_pass.py` | [121](121-the-second-instrument-and-the-shards-it-did-not-need.md); `mva.kmer.dosage` |
| clinical | none read here; 121's statement stands (no karyotype, no predictive term) | — |

`relative` = a contig's mean probe count ÷ the autosomal median of those means.
`absolute` = the same mean ÷ the genome-wide calibration set's mean (`mva.kmer.dosage.absolute_scale`).
`disagreement` = `relative − absolute`.

## Commands

```bash
uv run python - <<'PY'
import json, statistics
d = json.load(open("build/it2/step-8/dosage.json"))
rows = [(r["chrom"], r["relative"], r["absolute"], r["absolute"] / r["relative"], r["disagreement"]) for r in d["dosage"]]
ratios = [r[3] for r in rows]
print("ratio min/max", min(ratios), max(ratios))
aut = [r for r in rows if r[0] not in ("X", "Y")]
print("autosomal disagreement min/max", min(r[4] for r in aut), max(r[4] for r in aut))
print("autosomal median absolute", statistics.median(r[2] for r in aut))
PY
```

## Observed

| Contig | relative (÷ autosomal median) | absolute (÷ calibration mean) | absolute / relative |
|---|---|---|---|
| chr1 | 1.0012 | 1.0289 | 1.0277 |
| chr2 | 0.9984 | 1.0262 | 1.0278 |
| chr3 | 0.9915 | 1.0190 | 1.0277 |
| chr4 | 0.9886 | 1.0160 | 1.0277 |
| chr5 | 0.9988 | 1.0266 | 1.0278 |
| chr6 | 0.9816 | 1.0088 | 1.0277 |
| chr7 | 0.9902 | 1.0177 | 1.0278 |
| chr8 | 1.0078 | 1.0358 | 1.0278 |
| chr9 | 0.9920 | 1.0195 | 1.0277 |
| chr10 | 1.0098 | 1.0378 | 1.0277 |
| chr11 | 0.9968 | 1.0245 | 1.0278 |
| chr12 | 0.9885 | 1.0160 | 1.0278 |
| chr13 | 0.9780 | 1.0051 | 1.0277 |
| chr14 | 1.0070 | 1.0350 | 1.0278 |
| chr15 | 1.0039 | 1.0318 | 1.0278 |
| chr16 | 1.0183 | 1.0466 | 1.0278 |
| chr17 | 1.0319 | 1.0605 | 1.0277 |
| chr18 | 0.9922 | 1.0197 | 1.0277 |
| chr19 | 1.0431 | 1.0721 | 1.0278 |
| chr20 | 1.0263 | 1.0548 | 1.0278 |
| chr21 | 1.0199 | 1.0482 | 1.0277 |
| chr22 | 1.0451 | 1.0741 | 1.0277 |
| chrX | 0.4873 | 0.5008 | 1.0277 |
| chrY | 0.5083 | 0.5224 | 1.0277 |

- ratio `absolute / relative`: **min 1.02767, max 1.02784** over all 24 contigs — a spread of
  **0.017 %**, forty-seven times inside the 0.8 % refutation margin;
- `disagreement` on the autosomes: −0.0271 … −0.0290; on X and Y −0.0135 and −0.0141, i.e. the
  same constant scaled by their single copy;
- autosomal median `absolute`: **1.0278** — the constant is the autosomal median count
  divided by the calibration set's mean, a property of the two divisors, not of any chromosome.

## Assumptions, limitations and quality checks

- The absolute denominator is the calibration set's mean, drawn from the same 32 shards as the
  chromosome probes; a shard subset that was not a uniform sample would bias both divisors
  the same way, so this comparison cannot detect *that* failure. 121's thinning argument covers it.
- The two divisors sharing one constant proves the median assumption did not distort any
  contig **in this sample**. It does not raise the detection floor's power: the floor stays
  at 121's 1.6 % of cells, from the residual spread.
- No new pass, no new figure: this is a readback of a file 121 wrote. The dashboard's step-8
  dosage table carries the `absolute` column already (`results.it2_chrom_dosage`).

## Verdict

**H054 — supported, unchanged (0.85).** Defence (c) now has its number: the divisor that
assumes nothing about chromosomes agrees with the divisor that assumes most are normal on
every contig to 0.017 %. One evidence row added (`methodology/123`); the committed confidence
is not revised, because the row measures the divisor, not the chromosomes.
