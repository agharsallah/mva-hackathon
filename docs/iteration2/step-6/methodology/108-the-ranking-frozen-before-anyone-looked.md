# 108 — One ranking out of three, hashed before anybody compared it to anything

**Written:** 2026-09-18. **Step:** `step-6` (iteration 2).
**Hypotheses:** **H042 refuted**, **H043 supported**. Both were filed before
[107](107-the-routes-and-which-of-them-earned-a-rank.md) ran. H041 and H044 need the
comparison and are settled in [109](109-what-the-mirror-found.md).

**Supersedes nothing.** It takes the four routes
[107](107-the-routes-and-which-of-them-earned-a-rank.md) admitted and produces the one
artifact the blind protocol is built around: a fused ranking whose digest is written down
**here**, before any iteration-1 table exists in this step's inputs.

## Hypothesis and prediction

* **H042** — no single route carries the fused result. *Predicted:* in the
  leave-one-route-out table, every single-route removal reproduces the same rank-1 pair as
  the all-routes fusion.
* **H043** — the fused leader is spoken for by at least two disjoint inputs once routes
  sharing an input are collapsed. *Predicted:* its independent-evidence count is ≥ 2 of
  `{reads, VCF, HPO, literature}`.

## What would refute them

* H042: any single-route removal changes which pair holds fused rank 1. The route whose
  removal changes it is then the route carrying the result, and the fusion is that route
  wearing three coats.
* H043: the count is 1 — every route speaking for the leader traces back to one input, and
  the leader is one witness repeated, not four.

## Inputs

Identical to [107](107-the-routes-and-which-of-them-earned-a-rank.md): `results.it2_targets`,
`build/it2/step-1/benchmark-full.json`, `results.it2_lr_pairs`, `results.it2_lr_nulls`,
`results.it2_knowledge_ranks`, `results.it2_kmer_pairs`, `results.it2_kmer_genotypes`,
`results.it2_exon_cn`, `results.it2_decoys`, and the eight clinical terms by way of the two
routes that ranked on them. One stage, one command, one seed — the routes and the fusion are
the same run.

**No iteration-1 candidate table was read** — not its biallelic table, not its filtered
candidate table, not its decode file. `uv run python tools/check_blind.py` was green before
and after this entry was filed.

## Commands

```
uv run python tools/fuse_it2_routes.py
shasum -a 256 build/it2/step-6/fused-ranking.tsv
```

## The frozen artifact

| | |
|---|---|
| file | `build/it2/step-6/fused-ranking.tsv` (gitignored: it names alleles) |
| **sha256** | **`a596abf85a618a0b4baa40c630ae4ff58c5c25634fda7243111b07a399fb53ea`** |
| rows | **274** |
| frozen at | **2026-09-18T17:06:43Z** |
| constants | k = **60**, top **50** per route, absent = rank **51**, seed **20260918** |

Two consecutive runs of the command produced **byte-identical** files and therefore the same
digest. That is what makes the number above a commitment rather than a label: the ranking
cannot be quietly re-run until it agrees with the answer, because a re-run that agreed would
have to have a different hash, and this one is already written down.

**Why 274 rows and not 51,410.** Each route contributes its top 50, so the fused universe is
the union of what some route actually listed: 95 pairs from `phenotype` (50 genes fanned out),
50 from `likelihood`, 161 from `knowledge` (50 genes fanned out), 274 distinct. Everything
else is absent from every route — a score of nothing, which is not a row.

## Observed — the head of the ranking

| Fused rank | Pair | Tier | Evidence | phenotype | likelihood | knowledge | Confirmation |
|---|---|---|---|---|---|---|---|
| **1** | `BUB1B \| truncating:rs759242053 \| missense:` | core | **3** — hpo, reads, vcf | 9 | **1** | 51 | read-confirmed · single-copy · no CN loss |
| 2 (×11) | `CLCNKB \| …` — eleven pairs of one gene | core | 4 | 8 | 51 | 18 | all three |
| 13 (×8) | `DDX11 \| …` — eight pairs of one **decoy** gene | — | 2 | 51 | 51 | 1 | — |

The leader is a compound pair in a `core` target gene, ranked **1 by the likelihood route,
9 by the symptom route, and not listed at all by the knowledge route**. Its confirmation
triple is complete: the raw reads carry the allele, at single copy, in a gene with no exon
below the copy-number null band.

### H043 — supported

The leader's independent-evidence count is **3**: `hpo`, `vcf` and `reads`. Two ranking
routes and one confirmation instrument speak for it across three disjoint sources, so it is
not one witness in three coats. **`literature` is missing** — the knowledge route placed the
gene outside its top 50 — and that absence is the honest shape of the result: 3 of 4, not 4
of 4. Across the whole exported table the counts run 1 (12 pairs), 2 (86), 3 (72), 4 (30).

## Observed — leave one route out

| Removed | New rank 1 | Where the all-routes leader lands |
|---|---|---|
| `knowledge` | `BUB1B` | **1** — unchanged |
| `phenotype` | `BUB1B`, tied with `DDX11` (a decoy) | **1**, but no longer alone |
| **`likelihood`** | **`CLCNKB`** (eleven tied pairs) | **62** |

### H042 — refuted, on its own pre-registered condition

Removing the likelihood route moves the leader from rank 1 to **rank 62**. One route carries
the result. The consequence the claim named applies and is carried, not argued away:

* **The fusion is not four witnesses agreeing.** It is one discriminating route, and two
  routes that reorder its top without being able to find the leader themselves. Any
  statement that "independent routes converge" must be written as "the genome-wide
  likelihood route nominates, and the symptom route corroborates at rank 9".
* **The symptom route alone is not enough either.** Dropping it leaves the leader tied at
  rank 1 with a *decoy* gene, which is the same finding from the other side.
* It also matches what step 4 already measured: with the phenotype lane ablated the leader
  was joint third on DNA alone ([100](../../step-4/methodology/100-two-nulls-and-an-ablation.md)).
  The routes are correlated exactly where
  [107](107-the-routes-and-which-of-them-earned-a-rank.md)'s graph says they are.

## Observed — the second weighting

Weighting each route by its own measured error rate (phenotype 0.3346, likelihood 0.9441,
knowledge 0.6337) leaves **`BUB1B` at rank 1** and reorders everything behind it:
`ADAMTS1` 2, `HLA-DRB1` 3, `PEX5` 6 — the likelihood route's own order, which is what
up-weighting the only discriminating route does. `CLCNKB` falls from 2 to **49**.

That the leader is rank 1 under both weightings is the one robustness statement this step
can make. It is a weaker statement than H042 asked for, and it is stated at that strength.

## Assumptions, limitations and quality checks

* **Rank inheritance inflates ties, and the top 20 shows it.** A gene-level route gives every
  pair in a gene the same rank, so a gene with eleven scored pairs occupies eleven rows. The
  fused top 20 contains **three genes**: `BUB1B` (1), `CLCNKB` (2–12), `DDX11` (13–20).
  206 of the 233 exported rank rows are inherited rather than stated for a pair. The rule was
  pre-registered in `plan.md` §3 and is kept, but "top 20 pairs" must never be read as
  "top 20 genes" anywhere in this iteration.
* **Decoys reach the fused top 20.** Eight of the top 20 pairs are in `DDX11`, a size-matched
  control gene, put there by the knowledge route's rank 1. A fused ranking that admits a
  decoy at rank 13 is reporting its own resolution, and the decoy set is doing exactly the
  job it was built for.
* **The confirmation triple is gene-level** ([107](107-the-routes-and-which-of-them-earned-a-rank.md)):
  228 pairs over 64 genes are covered, 168 carry all three booleans. A pair inherits its
  gene's confirmation, so "read-confirmed" here means the gene carries a read-confirmed
  heterozygous allele, not that this exact allele was typed.
* **`p_trans` is not in the fusion.** It is undetermined for every leading pair — 5 of 50
  alleles reach gnomAD v2 ([101](../../step-4/methodology/101-the-phase-that-cannot-be-measured.md))
  — so it rides the row as a state, never as a score. The leader enters
  [109](109-what-the-mirror-found.md) in failure category **(v) unphaseable**.
* **The target set is an enrichment, never coverage** (recall@300 0.335). "Absent from the
  fused ranking" is "not nominated by any route", never "excluded".
* **`ranx` was not adopted** as the reference implementation `execution.md` §3 proposed: a
  compiled dependency tree for forty lines of arithmetic. Instead the 33 tests in
  `tests/test_fusion.py` compute every expected sum by hand from the published formula. This
  is a recorded cut, not an omission — the property a cross-check would have given is the one
  the tests assert.

## Conclusion

One ranking, 274 pairs, digest `a596abf8…`, written down before anything was compared.
`BUB1B` leads under both weightings and is confirmed by the reads at single copy with no
copy-number loss, on three disjoint inputs out of four. **But it is carried by one route**:
silence the likelihood ranker and the leader falls to 62. The fusion's honest contribution is
corroboration and resolution, not independent rediscovery — and that is the sentence
[109](109-what-the-mirror-found.md) has to test against what iteration 1 actually found.
