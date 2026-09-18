# 110 — The mechanism card revised from the confirmed pair, and six claims filed before any drug was looked up

**Written:** 2026-09-18. **Step:** `step-7` (iteration 2). **Hypotheses:** H045–H050 filed here,
none settled here. This is the instrument entry: it fixes what the drug search is about, and
what would count as a result, before [111](111-the-automated-stages-literature-trials-and-labels-per-drug.md)
asks a single drug-level question.

**Supersedes** nothing; it revises `ressources/track2/mechanism.json` from version 2 to
version 3 by a `history` entry, as the card's own rule demands ([078](../../../iteration1/step-8/methodology/078-track2-data-layer.md)
wrote versions 1 and 2). **Not blind by design** — step 7 works on the confirmed pair from the
start ([plan §3 step 7](../../plan.md)); every iteration-2 fact it consumes was unblinded by
[109](../../step-6/methodology/109-what-the-mirror-found.md) before this entry was written.

## Question

Track 2's goal has not moved since iteration 1: *which market-approved drugs act on the
mechanism the confirmed alleles imply, and how strong is the evidence for each?* What has
moved is the mechanism's standing. Iteration 1's card argued from an **inferred** trans pair;
the oracle confirmed it ([083](../../../iteration1/step-6/methodology/083-oracle-reply-submission-1.md)),
and iteration 2's steps 2–6 measured nine facts about the genotype that a drug argument should
carry. This entry asks: **what does the card look like once those facts are on it, and which
claims about the drug evidence follow from it — stated before the evidence is read?**

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| oracle | full match at rank 1 for the stop + missense pair | [083](../../../iteration1/step-6/methodology/083-oracle-reply-submission-1.md) |
| reads (step 2) | 164 consensus structural variants, none in the gene; 6,823 phase blocks, none reaching the gene's coding span | [088](../../step-2/methodology/088-the-alleles-the-reads-carry.md), [092](../../step-2/methodology/092-depth-per-exon-and-the-phasing-drawn.md) |
| k-mers (step 3) | both lead alleles at one-copy multiplicity, posterior 1.0; every target-gene exon at two copies, median 2.00 | [096](../../step-3/methodology/096-the-alleles-at-their-multiplicity.md), [097](../../step-3/methodology/097-copy-number-without-an-aligner.md) |
| VCF (step 4) | AlphaMissense lane 4.33 for the missense; the pair leads 51,920 hypotheses; P(trans) undetermined | [099](../../step-4/methodology/099-every-gene-ordered-with-nothing-filtered-out.md), [101](../../step-4/methodology/101-the-phase-that-cannot-be-measured.md) |
| knowledge (step 5) | missense outside every InterPro domain-typed entry, pLDDT 91.06; the gene at knowledge rank 293 of 815 | [106](../../step-5/methodology/106-where-the-missense-sits-in-the-protein.md), [105](../../step-5/methodology/105-does-the-literature-beat-a-hit-count.md) |
| fusion (step 6) | the blind fused ranking put the confirmed pair first | [109](../../step-6/methodology/109-what-the-mirror-found.md) |
| step 8 | **has not run** — the aneuploidy burden in the sample is unmeasured | [plan §3 step 8](../../plan.md) |
| clinical | the seven proband HPO terms on the card (the parental term left in [067](../../../iteration1/step-3/methodology/067-phenotype-ranking-run.md)), the tumour context rhabdomyosarcoma | `Challenge_Clinical_Phenotype_1.md` |
| literature | PMIDs for the new seeds and the anti-directions, each resolved live against PubMed E-utilities on 2026-09-18 (esummary; title and journal checked) | listed in the card |

Every fact above is read from the entry that owns it. Nothing is re-derived here, and no
genomic position appears in the card or in this entry — the card names the gene, the protein
and the allele classes.

## Method

### 1. The card, version 2 → 3

Written by a script over the JSON, appended as `history[2]`, never an edit:

| Block | Change | Why it matters for a drug |
|---|---|---|
| `mechanism.status` | *inferred* → **confirmed** (083) | the biggest rigor caveat of iteration 1's card is closed |
| `measured_facts` F1–F9 | new: one row per fact above, each with its entry and its implication | the report's mechanism section quotes the row, not the prose |
| `alleles[missense]` | structure (106) and pathogenicity lanes (099) added | *hypomorph* now rests on stated evidence, and the catalytic-dead-vs-unstable question is stated as **open** |
| `repurposing_directions` | D2 + `PSMB5`, `TFEB` (proteasome and lysosomal stress, PMID 39247952, 26404941); D3 + `SIRT2`, `CREBBP` (the acetylation axis, PMID 24825348, 23242215, 28985013); D4 + `HMGCR` (PMID 41249736) | the seeds a snapshot expands; every new seed carries its PMID in the rationale |
| `anti_directions` A1, A2 | new: further checkpoint weakening (*do not*); spindle poisons in a SAC-deficient background (*caution*); each with a `moa_pattern` the ladder applies | the do-not table is derived, not typed |
| `evidence_ladder` | new: rungs 5–1 with the test for each, and the rule that automated and curated tests print side by side | the rung is defined before any drug is placed on it |
| `case.context_standard_of_care` | new: the twelve drugs of the rhabdomyosarcoma backbone (PMID 41749943, 40421977) | a cytotoxic the child already receives can reach rung 5 automatically and must not be called a repurposing |

Card v3 is commit `37709ce`. The snapshot re-ran on it (same command as 078; warm cache,
new seeds live): **277** targets (32 seed, 245 pathway), **3,859** candidate rows, **359**
distinct approved drugs, **748** trial rows, 157 literature rows; 85 live calls in all.
`BUB1B` still returns zero candidates at any phase (H011 holds on the refreshed snapshot).

### 2. The claims, filed before the search

Six claims, one per direction plus two about the instrument, each with a prediction and a
refutation condition, filed through `mva-science hypothesis-add --step step-7` **before**
[111](111-the-automated-stages-literature-trials-and-labels-per-drug.md) ran:

| Id | Claim, in one line | Refuted by |
|---|---|---|
| H045 | D1 (checkpoint reinforcement) yields no submittable drug; it becomes the do-not table | an approved molecule with a cited cellular or animal result of strengthened checkpoint signalling in SAC-deficient or aneuploid cells |
| H046 | D2 holds an approved compound at rung ≥ 2 for the molecule itself (not only a tool compound) | every D2 rung-≥2 row is a proxy for AICAR / 17-AAG, or none reaches rung 2 |
| H047 | D3 has an approved-drug route on the SIRT2/NAD⁺ axis with in-vivo BubR1 evidence (rung 3, possibly by proxy) | no approved molecule attaches to a D3 target, or the in-vivo result cannot be tied to one even as a proxy |
| H048 | D4 holds an approved non-cytotoxic agent at rung ≥ 2 in rhabdomyosarcoma models with paediatric data | every D4 rung-≥2 drug is a standard-of-care cytotoxic, or the others lack paediatric data |
| H049 | the automated stages are not specific: some direction's approved set overlaps a decoy card's at Jaccard ≥ 0.10 | every direction is below 0.10 against both decoys |
| H050 | every shortlisted drug (rung ≥ 2) has paediatric data — a label section or a study admitting children | any shortlisted drug with neither |

The two decoys H049 names were chosen here, before their snapshots ran: **NTRK3**, the first
row of `results.it2_decoys` ordered by `md5(symbol || '20260918')` (a stated, seeded rule
over step 1's matched decoy set), and **XDH**, an unrelated, well-drugged metabolic enzyme
chosen for being nothing like a checkpoint. Their cards are built by
`mva.drugs.decoy.decoy_card` — the clinical side copied, the gene swapped — and their
snapshots (`tools/track2_decoys.py`) are the material [112](112-two-decoy-cards-through-the-same-pipeline.md) compares.

### 3. The curated evidence table, written before the ladder ran

`ressources/track2/evidence.tsv`: thirteen rows, one cited result each, placed on rung 2
(cell) or 3 (in vivo) with `proxy=true` wherever the paper tested a same-axis compound and
not the approved molecule. Every PMID was resolved live (esummary) and the sentence for the
claim was written from the abstract, fetched the same way. Rows are for chloroquine and
hydroxychloroquine, metformin, bortezomib (D2); niacin, nicotinamide, valproic acid,
vorinostat (D3); lovastatin, simvastatin, atorvastatin (D4). No D1 row exists — which is
H045's prediction, and the ladder is what tests it.

## Commands

```bash
uv run python - <<'EOF'   # the card v2 → v3 script, in the commit
...
EOF
uv run mva-drugs snapshot                                   # 85 live calls, 277 targets
uv run mva-science hypothesis-add --step step-7 ... × 6     # H045–H050, before any run
uv run python tools/track2_decoys.py --symbol NTRK3 --uniprot Q16288 ...
uv run python tools/track2_decoys.py --symbol XDH --uniprot P47989 --pattern purine ...
```

## Observed

```
card v3 written; directions: {'D1': 12, 'D2': 8, 'D3': 9, 'D4': 6}
snapshot: rows {'targets': 277, 'drug_candidates': 3859, 'trials': 748, 'literature': 157, 'pathways': 10}
          targets {'seed': 32, 'pathway': 245, 'total': 277}   distinct_approved_drugs 359
          live: chembl 32 · clinicaltrials 23 · dgidb 1 · openfda 21 · opentargets 8 · pubmed 0 · reactome 0
recorded H045 … H050 under iteration2/step-7
decoy NTRK3: targets 14 (1 seed, 13 pathway) · 771 candidate rows · 174 approved · 6 of 10 pathways matched /NTRK|neurotrophin|Trk/
decoy XDH:   targets 14 (1 seed, 13 pathway) ·  91 candidate rows ·  47 approved · 1 of 3 pathways matched /purine/
```

Three drugs the curated table names — chloroquine, hydroxychloroquine, niacin — attach to
**no** target the sources drug (`ATG5` and `SIRT2` return no approved molecule), so they would
not exist in a ranking built from the candidate table alone. The ladder admits them as
`curated_only` rows, and their approval is checked against openFDA in
[111](111-the-automated-stages-literature-trials-and-labels-per-drug.md) rather than assumed.

## Conclusion

The card is now a statement about a confirmed genotype with nine measured facts on it, one of
which (the aneuploidy burden) is honestly *unmeasured*. Six claims are on the register with
timestamps earlier than any drug-level query. What follows is a test of them, not a search
for support.

## Assumptions, limitations, quality checks

- **Assumption:** the null + hypomorph reading. It rests on the allele classes, the MVA1
  literature and the pathogenicity predictors — the missense is *outside* every curated
  domain (106), so the card states the catalytic-dead-vs-unstable question as open and argues
  D3 as a dosage direction only.
- **Limitation:** F8 — no measured aneuploid fraction in this child. D2 is argued from the
  literature on MVA and aneuploid cells, and the report says so wherever D2 is quoted.
- **Limitation:** the curated table is one person's reading of thirteen abstracts on one day.
  Its rungs are the strongest claims in step 7 and the least automated; every row carries the
  PMID so the reading can be checked.
- **Quality check:** every PMID in the card and in `evidence.tsv` resolved live; four PMIDs
  first recalled from memory were wrong and were replaced by title search before writing
  (North 2014, Choi 2009, Park 2013, Santaguida 2015 — the wrong numbers never entered a file).
- **Quality check:** `mva-science check` passes (no coordinates); `tests/test_drugs_snapshot.py`
  asserts the same over every file the snapshot and the decoy runs produced.
