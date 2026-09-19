# Track 1 — iteration 2 (2026-09-19)

**Standing:** built, rehearsed on two scorers, cross-checked — **not uploaded**, held in
reserve (1 of 6 submissions spent, by iteration 1). Iteration 1 is frozen at
[`../iteration-1/`](../iteration-1/README.md); its upload was answered *full match at rank 1:
stop+missense (100 rank points, F-max 1.0, threshold 0.9963)*
([083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md)).
One folder = one upload-ready iteration. Everything the organisers would receive, plus the
material a judge needs to check it, is here or linked from here.

## Why this iteration exists, and why it is not uploaded

The reply to submission 1 collapsed the Track 1 hypothesis space to a single point. Iteration 2
is therefore **not** a replay of iteration 1's steps: it is a **blind replication** — the same
question asked again from the raw reads, the callset and the eight clinical terms, by routes
that share no code with iteration 1 and read no iteration-1 candidate until a final comparison
([`docs/iteration2/plan.md`](../../../docs/iteration2/plan.md)). The fused, hash-frozen ranking
put the same two `BUB1B` alleles first under both weightings
([109](../../../docs/iteration2/step-6/methodology/109-what-the-mirror-found.md)).

The upload rule ([plan §6](../../../docs/iteration2/plan.md)) spends a submission only when a
pre-registered decode table shows expected information gain above zero on a live hypothesis.
The built file's decode table has **one row** and an expected gain of **0.000 bits**
([124](../../../docs/iteration2/step-6/methodology/124-the-reserve-file-built-and-rehearsed.md);
H044 supported). So the file is real, rehearsed and **held**: **5 of 6 remain**. Timing of any
upload is the team's call; nothing here changes if it is never sent.

## What to upload (the challenge asks for three things)

| Deliverable | File | Notes |
|---|---|---|
| Predictions CSV | `submissions/track1/iteration-2/agharsallah_bub1b-comphet-replication.csv` — **in this folder for the upload, gitignored** (`submissions/**/*.csv`); an identical copy is written to `build/submission/` | sha256 `325205a8abdf53d0dca12080cf29633b27d882316517bc8a4620da0b7afab359`; 4 rows (1 primary pair, 3 secondary); holds real coordinates. Rebuild: see *Regenerate* — the rebuild re-grades the file with our replica **and** the organisers' `evaluation.py` and stops if they disagree |
| Report (PDF or Markdown) | [`agharsallah_track1_report.pdf`](agharsallah_track1_report.pdf) — rendered from [`report.md`](report.md) | filename carries the username as the form asks |
| Methods description form | [`agharsallah_track1_methods_form.xlsx`](agharsallah_track1_methods_form.xlsx) — the organisers' template, column B filled from [`methods-form.json`](methods-form.json) | **model number 2** — the blind mirror; abstract under 500 words |
| GitHub URL | `https://github.com/agharsallah/mva-hackathon` | entered in the submit form |

## How to read this iteration

1. [`report.md`](report.md) — the replication report: what the reply settled → the blind
   protocol → the clinical terms and both inputs → the mirror step by step (1–6) → the two
   alleles re-measured → the mosaic bound (step 8) → the submission as a measurement →
   reproducibility → limitations → methods form → where every claim lives. Every number links
   to the methodology entry that produced it.
2. [`decode-table.md`](decode-table.md) — what the only possible reply would mean (labels only,
   no coordinates): one row, gain 0.000 bits.
3. [`spec.selectors.json`](spec.selectors.json) — **why every row is there, without saying
   where**: each allele is a selector over a warehouse result table (gene, consequence, ClinVar
   flag, dbSNP id) that must match exactly one row. No epcr, no notes, no prior typed. Iteration
   1's alternative pairings are gone: the reply eliminated them.
4. [`derivation.md`](derivation.md) (source [`derivation.json`](derivation.json)) — **where
   every number in the CSV comes from**: the facts each note quotes, read from the selector's
   table; the rank-1 epcr = the register's suggested confidence for H009 after the oracle's
   reply entered its evidence (0.9993 — a triage heuristic, not a calibrated posterior); the
   secondary rows below it by allele score. Arithmetic printed line by line.
5. Figures: one folder per step under
   [`figures/track1/iteration2/`](../../../figures/track1/iteration2/) (`step-1` … `step-8`,
   each with an `index.html`), rendered by `tools/render_it2_step<n>_figures.py` from each
   run's own output files. Iteration 1's figures stay in [`figures/track1/`](../../../figures/track1/).
6. The research record: [`docs/science-register.json`](../../../docs/science-register.json) →
   [`figures/science-report.html`](../../../figures/science-report.html); hypotheses H012–H044
   and H051–H057 (steps 1–6 and 8), H045–H050 and H061 (step 7, Track 2).

**In the app:** `/submissions` (API `GET /api/submissions`) shows this folder with its lineage
graph (three edges appended by the resolver on 2026-09-19), both inputs and the audit trail;
`/steps` shows every iteration-2 step with its figures, and `/steps/step-6` the freeze receipt.

## Which steps contributed, and where their evidence lives

| Step | Contribution | Methodology |
|---|---|---|
| iteration 1, step 6 | the reply that settled the pair; H009 supported; 1 of 6 spent | [083](../../../docs/iteration1/step-6/methodology/083-oracle-reply-submission-1.md) |
| 1 blind target set | 404 targets in 3 tiers + 396 matched decoys; recall@300 measured at 0.335, so enrichment not coverage; 73.6 % of genes uncurated | [084](../../../docs/iteration2/step-1/methodology/084-the-blind-target-set.md), [091](../../../docs/iteration2/step-1/methodology/091-recall-at-the-full-population.md) |
| 2 alleles from the reads | k-mer bait over 1.07 B reads; two callers at 0.9957 / 0.9927 concordance; 1,199 vendor-unreported alleles; no SV in `BUB1B`; phase unreachable; read route has no ranking power (H020 refuted) | [085](../../../docs/iteration2/step-2/methodology/085-the-bait-and-where-it-runs.md)–[090](../../../docs/iteration2/step-2/methodology/090-the-alleles-the-vendor-never-reported.md), [092](../../../docs/iteration2/step-2/methodology/092-depth-per-exon-and-the-phasing-drawn.md) |
| 3 alignment-free genotype + CN | both lead alleles one copy each (posterior 1.0); every `BUB1B` exon at two copies; X at 0.95 as the control | [093](../../../docs/iteration2/step-3/methodology/093-where-the-aligner-was-unsure.md), [095](../../../docs/iteration2/step-3/methodology/095-the-probes-and-the-counting-kernel.md)–[097](../../../docs/iteration2/step-3/methodology/097-copy-number-without-an-aligner.md) |
| 4 likelihood-ratio ranking | `BUB1B` first of 51,920 pairs in 11,465 genes with no filter; AUC 0.706; P(trans) undetermined | [098](../../../docs/iteration2/step-4/methodology/098-the-lanes-and-what-they-were-calibrated-against.md)–[101](../../../docs/iteration2/step-4/methodology/101-the-phase-that-cannot-be-measured.md) |
| 5 knowledge engine | AUC 0.634, not citation volume; the gene at rank 293 of 815; the missense outside every domain-typed entry | [102](../../../docs/iteration2/step-5/methodology/102-the-sources-and-what-they-could-be-asked.md)–[106](../../../docs/iteration2/step-5/methodology/106-where-the-missense-sits-in-the-protein.md) |
| 6 fusion + unblinding | same pair first under both weightings; one route carries it; second upload 0.000 bits; **this folder's file built and rehearsed** | [107](../../../docs/iteration2/step-6/methodology/107-the-routes-and-which-of-them-earned-a-rank.md)–[109](../../../docs/iteration2/step-6/methodology/109-what-the-mirror-found.md), [124](../../../docs/iteration2/step-6/methodology/124-the-reserve-file-built-and-rehearsed.md) |
| 8 mosaic aneuploidy bound | nothing above 2–3 % of cells on any autosome (allele balance) or 1.6 % (k-mer dosage); X and Y at one copy; both denominators agree | [115](../../../docs/iteration2/step-8/methodology/115-the-callset-reduced-to-what-a-mosaic-model-needs.md)–[118](../../../docs/iteration2/step-8/methodology/118-the-baseline-and-what-a-variegated-genome-does-to-it.md), [121](../../../docs/iteration2/step-8/methodology/121-the-second-instrument-and-the-shards-it-did-not-need.md), [123](../../../docs/iteration2/step-8/methodology/123-the-denominator-that-assumes-nothing-read-back.md) |
| 7 Track 2 | consumes the facts above (card v4); does not test the pair; its own draft is [`../../track2/iteration-2/`](../../track2/iteration-2/README.md) | [110](../../../docs/iteration2/step-7/methodology/110-the-card-revised-and-the-claims-filed-before-the-search.md)–[114](../../../docs/iteration2/step-7/methodology/114-the-dashboard-surface-for-step-7.md), [120](../../../docs/iteration2/step-7/methodology/120-the-card-at-version-4-and-the-second-submission-draft.md) |

## Integrity checks (run 2026-09-19)

| Check | Command | Result |
|---|---|---|
| Selectors resolve, one row each; nothing typed reaches the CSV | `uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-2/spec.selectors.json --out build/submission/spec.json --record-lineage` | 5 alleles, 4 rows; `derivation.json` written; 3 lineage edges appended |
| CSV rehearsed on the replica and re-graded with the organisers' scorer | `uv run python tools/design_submission.py --spec build/submission/spec.json --out submissions/track1/iteration-2/agharsallah_bub1b-comphet-replication.csv --decode-md submissions/track1/iteration-2/decode-table.md` | `agree` on the only key: 100 points, F-max 1.0, full match rank 1; gain 0.000 bits; sha256 `325205a8…` |
| Template conformance | same command | header byte-identical to the template, `PROBAND01`, `chr` prefix, epcr strictly descending, 4 rows |
| Folder complete and consistent | `uv run python tools/check_iteration.py submissions/track1/iteration-2` | see the folder gate's output in the commit that froze this README |
| No patient coordinate in the tree | `uv run python tools/check_coordinates.py` | clean |
| Blind gate | `uv run python tools/check_blind.py` | 38 iteration-2 entries declaring inputs — unblinded by 109 |
| Register publishable | `uv run mva-science check` | passes; evidence rows 144 (H054) and 145 (H044) added by entries 123 and 124 |

## After the upload (if the team decides to spend one)

1. `uv run mva-warehouse probe-log --by agharsallah --type F --payload-file submissions/track1/iteration-2/agharsallah_bub1b-comphet-replication.csv --response '<reply>' --rationale 'iteration 2, see submissions/track1/iteration-2'`
2. `uv run mva-science probe-link <probe_id> --hypothesis H009 --direction supports --claim '<what the reply said>'`
3. Find the reply's row in [`decode-table.md`](decode-table.md) — there is one; any other reply is a scorer change and is filed as such.
4. `uv run python tools/new_iteration.py --track track1 --reply '<reply>'` freezes this folder and opens iteration 3.

## Regenerate this folder

```bash
uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-2/spec.selectors.json --out build/submission/spec.json
uv run python tools/design_submission.py --spec build/submission/spec.json \
    --out submissions/track1/iteration-2/agharsallah_bub1b-comphet-replication.csv --decode-md submissions/track1/iteration-2/decode-table.md
for n in 1 2 3 4 5 6 8; do uv run python tools/render_it2_step${n}_figures.py; done
uv run python tools/md_to_html.py submissions/track1/iteration-2/report.md build/track1-report-it2.html \
    --repo-url https://github.com/agharsallah/mva-hackathon/blob/main
node tools/md_to_pdf.mjs build/track1-report-it2.html submissions/track1/iteration-2/agharsallah_track1_report.pdf
uv run python tools/fill_methods_form.py --sheet "Track 1 methods" \
    --answers submissions/track1/iteration-2/methods-form.json \
    --out submissions/track1/iteration-2/agharsallah_track1_methods_form.xlsx
uv run python tools/check_iteration.py submissions/track1/iteration-2
```
