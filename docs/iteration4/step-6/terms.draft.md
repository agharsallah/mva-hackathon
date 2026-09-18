# Step 6 — dictionary terms, draft

**Standing:** drafted 2026-09-18 by the wave-1 *rank + report + merge* agent, against
`fixtures/it4/` only. Not merged: the one dictionary is
[`docs/dictionary.md`](../../dictionary.md) and the wave-3 *docs* agent merges these entries in
dependency order. Nothing here is a result.

Source for every entry: [`docs/iteration4/plan.md`](../plan.md) §5 (step 6),
`src/mva/zoo/merge.py`, `merge_render.py`, `tools/render_it4_figures.py`.

Insert in the order below — each entry only uses words defined above it. They depend on
[step 4's draft](../step-4/terms.draft.md) (pair score, unscored pair, percentile).

---

**Spearman ρ (rank correlation)** — a number between −1 and +1 saying whether two lists put the
same items in the same *order*, ignoring the scales they use. +1 = identical order, 0 = no
relation, −1 = exactly reversed.
*Example: two fixture lanes over their 22 shared alleles give ρ = −0.079 — they order those
alleles almost independently of each other.*
*Context: computed with `scipy.stats.spearmanr` in `mva.zoo.merge.agreement_matrix`; the right
statistic here because two models' scores are on unrelated scales (one is a probability, one a
log-likelihood ratio) and only their ordering is comparable · source: src/mva/zoo/merge.py ·
related: agreement matrix · first seen 2026-09-18*

**agreement matrix** — the table of Spearman ρ between every pair of lanes, computed over the
alleles both lanes scored, with that shared count `n` printed in every cell.
*Example: `figures/it4/agreement-matrix.svg`; a cell with fewer than three shared alleles, or
with no variance on one side, is left blank rather than filled with a zero.*
*Context: `mva.zoo.merge.agreement_matrix` returns it symmetric by construction with a diagonal
of 1.0; `n` is printed because ρ over nine alleles is not the same claim as ρ over thirty
thousand · source: src/mva/zoo/merge.py · related: Spearman ρ, disagreement table ·
first seen 2026-09-18*

**reciprocal rank fusion (RRF)** — merging several ranked lists by giving each item
`1 / (k + rank)` from every list that ranked it and summing. No weights to fit, and robust to
lists on different scales.
*Example: a pair placed 1st by one lane and 2nd by another scores `1/61 + 1/62 = 0.032522`
with `k = 60`.*
*Context: `mva.zoo.merge.rrf`; the transparent default of plan decision D10. Cited as Cormack
GV, Clarke CLA, Buettcher S, *Reciprocal rank fusion outperforms Condorcet and individual rank
learning methods*, SIGIR 2009, pp. 758-759 — **DOI to verify**, deliberately not asserted here ·
source: src/mva/zoo/merge.py · related: consensus rank, thin-lane effect ·
first seen 2026-09-18*

**k (the RRF constant)** — the damping number in `1 / (k + rank)`. Larger k flattens the
advantage of being first in any single list; the original paper used 60, and so does this repo.
*Example: with `k = 0` a first place is worth 1.0; with `k = 60` it is worth 0.0164, only
1.6 % more than second place.*
*Context: `[merge] rrf_k = 60` in `src/mva/zoo/zoo.example.toml`, asserted in
`tests/test_zoo_merge.py::test_k_damps_the_top_of_a_single_list` · source:
src/mva/zoo/zoo.example.toml · related: reciprocal rank fusion · first seen 2026-09-18*

**consensus rank** — where RRF puts the confirmed pair once every lane has voted, printed twice:
once with catalogue-adjacent lanes excluded, once with every lane.
*Example: the merged report's section 3 prints both rows, each naming the lanes that voted and
the lanes that were silenced.*
*Context: `mva.zoo.merge.consensus(..., exclude_adjacent=True|False)`; the catalogue-free number
is the one plan claim `P4-8` is filed on, because a ClinVar-trained lane may be recalling the
published answer rather than predicting it · source: src/mva/zoo/merge.py · related:
reciprocal rank fusion, catalogue-adjacent · first seen 2026-09-18*

**thin-lane effect** — a lane that could rank only a few pairs still hands its best one a full
first-place vote, so fusing lists of very different lengths is not neutral.
*Example: a lane that ranks one pair gives it `1/61`, the same contribution a lane that ranked
1,200 pairs gives its winner — enough to move the fused order
(`tests/test_zoo_workflow.py::test_a_thin_lane_hands_its_one_ranked_pair_a_full_top_rank_vote`).*
*Context: why the merged report prints `n_ranked` and `unscored_pairs` beside every lane's rank
instead of the rank alone · source: src/mva/zoo/merge.py · related: reciprocal rank fusion,
unscored pair · first seen 2026-09-18*

**disagreement table** — the alleles one lane places in its top 1 % while another places them in
its worse-scoring half. Ordered pairs, so "A loves what B hates" and its converse are two
separate rows.
*Example: on a 10-allele toy lane pair, `x9` (up's best, down's worst) and `x0` (the mirror
image) are both listed with percentiles 10 % and 100 %.*
*Context: `mva.zoo.merge.disagreements`; both cut-offs are on *positions*, not raw scores,
because the lanes are on unrelated scales. Plan §5 step 6 calls this "a finding to explain, not
to hide" · source: src/mva/zoo/merge.py · related: agreement matrix, percentile ·
first seen 2026-09-18*

**merge method** — which of three ways the lanes are combined, selected by one config key:
`fusion` (deterministic layer only, narrative written by hand), `fusion+synthesis` (an LLM
writes the narrative from the per-model interpretations, cited), `judge` (an LLM ranks the
models and its ranking is printed beside RRF, flagged non-reproducible).
*Example: `[merge] method = "fusion"` — the MVP, which needs no LLM to reach a result.*
*Context: plan decision D10; the deterministic layer is computed under all three, so the method
only decides who writes the words · source: src/mva/zoo/zoo.example.toml · related: consensus
rank, LLM-as-judge · first seen 2026-09-18*

**LLM-as-judge** — using a language model as the scorer of other methods' output: here, asking
it to read the per-model reports and rank the lanes by evidential value.
*Example: plan claim `P4-9` — the judge is informative if its ranking correlates with the lanes'
catalogue-free pair rank at Spearman ρ ≥ 0.5, uninformative below 0.2.*
*Context: plan §5 step 6's opt-B substep, not built in the MVP; when it runs, its output is
printed *beside* the RRF rank and flagged non-reproducible, never in place of it · source:
docs/iteration4/plan.md · related: merge method, consensus rank, Spearman ρ ·
first seen 2026-09-18*

**narrative slot** — the marked place in the merged report where the hand-written paragraph
lives, so a later LLM run can replace exactly that paragraph and nothing else.
*Example: `<!-- narrative: hand-written 2026-09-18 -->` in `docs/iteration4/report.md`; a
re-render reads the existing paragraph back out and keeps it
(`tests/test_zoo_workflow.py::test_a_hand_written_narrative_survives_a_re_render`).*
*Context: `mva.zoo.merge_render.render_merged` plus `workflow_stages._existing_narrative`; the
same device as the per-model report's interpretation marker · source:
src/mva/zoo/merge_render.py · related: interpretation section, merge method ·
first seen 2026-09-18*
