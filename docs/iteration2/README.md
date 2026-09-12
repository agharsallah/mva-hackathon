# Iteration 2 — the research steps behind submission 2

**Standing:** opened 2026-09-09; steps declared in `steps.py` and **step 1 run** on 2026-09-11.
**Plan** in [`plan.md`](plan.md) (eight steps, blind protocol, `step-1` … `step-8`), **gap-reviewed twice on 2026-09-10** against the
eight papers in [`papers/iteration2/`](../../papers/iteration2/README.md) — `plan.md` §9 (five papers)
and §10 (three more, plus a bias pass: term-driven target rows, the family-history term, hand-typed
anchors, missing nulls for the read route, the fusion and Track 2) list every gap and its fix,
§8 G the citations they added. [`execution.md`](execution.md) is the plan's companion: per step,
which published tools to adopt, what `src/mva/` already provides, what to build, and what the
dashboard shows (a `/steps` page for every iteration). Iteration 1 is frozen at
[`../iteration1/`](../iteration1/README.md); step 0 (the platform) stays at
[`../step-0/`](../step-0/README.md).

**Why this iteration exists.** The reply to submission 1 was *full match at rank 1:
stop+missense* (100 rank points, F-max 1.0 — [083](../iteration1/step-6/methodology/083-oracle-reply-submission-1.md)).
The causal pair is settled. Iteration 2 therefore does **not** replay steps 1–8 of
iteration 1: it gets **its own plan, its own methodology and its own steps**, declared
once the plan is agreed, and its output is again a submission
([`submissions/track1/iteration-2/`](../../submissions/track1/iteration-2/README.md)).

## How this folder fills in

1. The plan for iteration 2 is written first (goal, what a second upload should measure or
   deliver, what the report must show).
2. The plan is cut into steps, one goal each, declared in `src/mva/science/steps.py` for
   this iteration — not copied from iteration 1.
3. Each step gets `docs/iteration2/step-<n>/` with a README and an append-only
   `methodology/` log, and this table is filled from `steps.py`.

| Step | Goal | Status for submission 2 |
|---|---|---|
| [1](step-1/README.md) | Which genes do the child's symptoms alone nominate — a target set chosen with the DNA never read? | **run 2026-09-11** — 404-row tiered target set + 396 decoys; H013 supported, H012/H014/H015 refuted ([084](step-1/methodology/084-the-blind-target-set.md)) |
| [2](step-2/README.md) | Which alleles do the raw reads carry in the target set, discovered without the vendor caller? | **run 2026-09-12** — 14.7 M reads recovered from 1.07 B, 131,530 alleles, 98.87 % mapped; H016/H019/H020/H021/H022 supported, H023 refuted ([085](step-2/methodology/085-the-bait-and-where-it-runs.md)–[088](step-2/methodology/088-the-alleles-the-reads-carry.md)) |
| [3](step-3/README.md) | Alignment-free genotype and copy number | open — [handover written](step-3/README.md), claims not yet filed |
| 4 | Likelihood-ratio ranking over the VCF | planned |
| 5 | Knowledge engine | planned |
| 6 | Fusion and unblinding | planned |
| 7 | Track 2 enrichment | planned |
| 8 | The mosaic aneuploidy bound | planned |

**What step 2 added, and the finding that changes how every later step reports a rate.**
A reference k-mer bait recovered 1.36752 % of 1.07 billion reads against a bait covering
1.361 % of the genome, and two callers sharing no code with the vendor's reproduced its
genotypes at 99.57 % and 99.27 %. But enumerating biallelic genes *without* a rarity and
consequence filter makes the **decoys win** — 57.3 % against core's 50.8 % — because
everyone carries about two heterozygous differences per gene. With the filter the ordering
inverts (core 1.69 %, decoy 0.51 %). **The discriminating power is in the filter, not in
the symptom-derived gene list**, and any step quoting a target-versus-decoy rate has to say
which version it means.

**The finding that already changes the plan.** Step 1 measured the phenotype-only ranker
instead of trusting it: held-out recall@300 is **0.36**, not the 0.90 H012 predicted, and
raising N does not fix it (recall@1000 = 0.565; a quarter of held-out genes are unrankable
at any N). The target set is therefore an **enrichment, never coverage**, and step 4's
genome-wide ranking is the safety net. 73.6 % of protein-coding genes have no HPO curation
at all, which makes the `uncurated` tier the iteration's largest blind spot rather than a
footnote.
