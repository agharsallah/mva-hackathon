# Sources for an ESM-2 vs ThermoMPNN BUB1B variant benchmark

**Standing:** research note, not a verdict. Written to check a proposed benchmark against
primary sources before any run; it does not plan the run, size it, or place it in the pitch —
that is the parent's job.

## Framing correction: this is not a new orthogonal modality

`docs/iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md` already
ran a sequence-only comparator — **ESM1b**, not ESM-2 — against the exact same 5-abundance-
lowering/3-stable BUB1B label set used here, and reported raw −ESM1b LLR AUROC **0.53**
[0.00, 1.00] against ThermoMPNN's **0.60** [0.13, 1.00] (`149-...md`, "Separation" table). Both
are at or inside the inconclusive band the experiment itself pre-registered. Three consequences
follow directly from that entry and must not be lost in an ESM-2 writeup:

1. **ESM-2 vs ThermoMPNN on this label set is not "orthogonal modality A vs modality B" — it is
   a second sequence-only model run against labels where a first sequence-only model (ESM1b)
   already returned a null/chance result.** The interesting prior question is not "does ESM-2
   beat ThermoMPNN" but "does ESM-2 beat ESM1b's 0.53 on the same n=8", since both are the same
   modality (sequence conservation). Reporting it only as "sequence vs structure" without citing
   the ESM1b precedent misrepresents what has already been tried.
2. **These n=8 labels are known, published, and already used as the evaluation set once.**
   Scoring ESM-2 against them is a retrospective replication on a fixed, previously-consumed
   label set, not a prospective blind validation. Any claim of "independent confirmation" is not
   supported — the labels were not held out from this project's own prior analysis, and
   `149-...md` explicitly used them as ground truth to refute H083.
3. **Running ESM-2 after ESM1b was null, on the same n=8, carries a model-shopping risk.** If
   ESM-2 is tried specifically because ESM1b (and ThermoMPNN) did not clear the bar, any positive
   result must be reported as one more draw from a small label set under multiple-model testing,
   not as a confirmed finding. With n=8 and CIs already spanning ~0.9 (`149-...md`, Limitations),
   trying additional models until one clears an arbitrary AUROC threshold is exactly the failure
   mode a pre-registered line was meant to prevent — and no such line has been pre-registered for
   ESM-2 in this project as of this note.

**Protocol consequence:** freeze the ESM-2 run as a single prospective, pre-registered
computational scoring pass (one scoring strategy, one model size, one pre-stated AUROC
threshold/floor, decided and written down *before* the run, mirroring `149-...md`'s own
discipline) rather than as a blind validation study — it cannot be a blind study, since the
labels and their class split are already known from the prior ThermoMPNN/ESM1b entry. State this
plainly in any downstream report: "retrospective, label-known, third model on a previously
null-tested n=8 set", not "new independent validation."

## What ESM-2 actually scores

ESM-2 is a general-purpose masked protein language model (`esm2_t6_8M` … `esm2_t36_3B`,
`esm2_t48_15B`), trained on UniRef50/90, released with Lin et al. 2022 (*Science* 379:1123,
https://www.science.org/doi/abs/10.1126/science.ade2574). The official repo README states
plainly: ESM-2 "could be used for variant prediction as well, and is expected to have similar
performance to ESM-1v" — it is not purpose-trained for variant effects the way ESM-1v is.
Source: `facebookresearch/esm` README, "Zero-shot variant prediction" section
(https://raw.githubusercontent.com/facebookresearch/esm/main/README.md).

### Masked-marginal scoring formula (verified against the official script)

`examples/variant-prediction/predict.py` in `facebookresearch/esm`
(https://raw.githubusercontent.com/facebookresearch/esm/main/examples/variant-prediction/predict.py)
implements three strategies; the one matching "mutant vs wildtype log probability at the masked
site" is `masked-marginals`:

```python
# for each position i in the sequence, mask it and run the model once:
batch_tokens_masked[0, i] = alphabet.mask_idx
token_probs = torch.log_softmax(model(batch_tokens_masked)["logits"], dim=-1)
all_token_probs.append(token_probs[:, i])
...
# label_row(): the actual mutant-vs-wildtype score
score = token_probs[0, 1 + idx, mt_encoded] - token_probs[0, 1 + idx, wt_encoded]
```
(`predict.py:95-103, 180-191`, line numbers approximate to the fetched file). The `+1` offset is
for the BOS token the batch converter prepends. This requires **one forward pass per position**
(L passes for a protein of length L) for masked-marginals, versus one single forward pass for
the `wt-marginals` strategy (no masking, score read directly off the wild-type-conditioned
logits). The repo's own doc does not state which strategy is "official" for ESM-2; both exist
for ESM-1v in the same script, and the note cited above says ESM-2 "is expected to have similar
performance", not that masked-marginals is validated specifically for ESM-2 on BUB1B-like
targets.

### Length handling for a ~1050 aa protein (BubR1 / BUB1B, UniProt O60566)

- ESM-2 uses rotary positional embeddings (Lin et al. 2022), not the learned absolute position
  embeddings of ESM-1 models, so it does not have ESM-1b's hard 1024-token training-time position
  limit. The public repo does not publish an explicit hard-coded max sequence length for ESM-2 in
  the README; the practical constraint is compute/memory, not position-embedding support.
  **This is inferred from the architecture description in the Lin et al. 2022 paper, not quoted
  from an explicit "max length = N" line in the repo** — flag as unverified against the paper
  text itself (paper was not directly fetched in this pass; only the repo README and script).
- The repo documents memory-saving flags built for long sequences: `--cpu-offload` ("can be
  useful for making predictions on longer sequences... offload some parameters to CPU RAM"),
  `--chunk-size` (axial attention chunking, O(L²)→O(L), relevant to ESMFold not ESM-2's MLM head),
  and `--truncation_seq_length` on `esm-extract` for bulk embedding jobs. Source: same README,
  "ESMFold Structure Prediction" and "Compute embeddings in bulk from FASTA" sections.
- A 1,050-residue protein scored by masked-marginals means **1,050 separate forward passes**
  (one per masked position) just to build the per-position log-prob matrix once; each pass is
  itself quadratic-ish in L in the attention layers. This is a real, measurable cost driver that
  scales with protein length, independent of model size choice (8M vs 650M vs 3B parameters).

### GPU feasibility on Modal — official doc facts, no measured numbers

Source: https://modal.com/docs/guide/gpu (fetched 2026-10-22). Modal's documented GPU argument
values: `T4, L4, A10, L40S, A100, A100-40GB, A100-80GB, RTX-PRO-6000, H100/H100!, H200, B200/B200+,
B300`. No GPU-second cost, latency, or throughput numbers for ESM-2 specifically are published on
this page — the only concrete cost data available to this project is the project's own measured
ThermoMPNN run (see below), not a Modal or Meta number for ESM-2.
**Any ESM-2-on-Modal runtime/cost estimate is necessarily an estimate, not a citation, until it is
actually run — this note does not run it.**

## What ThermoMPNN predicts, and how that differs from ESM-2's target

This project already ran ThermoMPNN on BUB1B and recorded it in
`docs/iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md`. Key
facts from that record, which bound what a fair ESM-2 comparison means:

- ThermoMPNN predicts **ΔΔG of folding** (destabilisation) from a single AlphaFold structure
  (`149-...md`, "stability model" row: Dieckhaus 2024, PNAS, PMID 38285937). It is a structural,
  not sequence-evolutionary, predictor.
- The project's label set is **n = 8** published BUB1B missense alleles with a protein-level
  (abundance) readout: **5 abundance-lowering** (I909T, R727C, R814H, L844F, L1012P) and
  **3 stable** (Y155C, R550Q, Q921H), all from Suijkerbuijk 2010 (PMID 20516114), primary set;
  a 9th ("extended", C945Y, non-MVA) is a sensitivity-analysis addition, not part of primary n=8.
  (`149-...md`, "Labels recovered" table.)
- ThermoMPNN's raw ΔΔG AUROC on this primary 5-vs-3 split was **0.60** (bootstrap 95% CI
  [0.13, 1.00]) — at the pre-registered refutation line (≤0.6), and the hypothesis (H083) was
  explicitly refuted, also **flagged as underpowered** because the stable class had only 3
  members against a pre-registered floor of 4 per class.
- Critically, **ESM1b** (not ESM-2) was already run as a comparator in that same experiment:
  "raw −ESM1b LLR (comparator)" gave AUROC **0.53** [0.00, 1.00] on the same primary 5-vs-3 set,
  i.e. indistinguishable from chance, and *worse* than ThermoMPNN's already-inconclusive 0.60.
  Source: `149-...md`, "Separation" table. **This means a near-identical sequence-only LLR
  benchmark against this same label set has already been run once (ESM1b, not ESM-2) and failed
  to separate the classes.** An ESM-2 masked-marginal run is a different model and possibly a
  different (masked-marginal vs ESM1b's own marginal convention) scoring recipe, but it predicts
  the same kind of quantity — an evolutionary/sequence-conservation log-odds, not ΔΔG, not
  abundance — and should be expected, on priors, to face the same ceiling this label set imposes.

### What ESM-2's score does *not* predict

ESM-2 masked-marginal log-odds is a **variant-conservation / fitness proxy**: it tells you how
unusual a substitution is relative to the family of sequences the model internalised during
pretraining on UniRef. It is not trained on, and is not a stand-in for:
- protein abundance / steady-state levels (ThermoMPNN's ΔΔG is a mechanistic proxy for this,
  not a ground-truth measurement either — "stability model" row in `149-...md`);
- the abundance-lowering vs function-impairing distinction the n=8 labels encode, which was
  measured by Suijkerbuijk 2010 via overexpression assays in HeLa/U2OS cells, not by anything a
  sequence model can see.
Using ESM-2's score as, or converting it into, an abundance call or a prior for abundance would
not be supported by anything in the official ESM docs — the repo's own framing of ESM-2 is
general-purpose "structure, function and other protein properties," and the zero-shot-variant
section cites ESM-1v's fitness-effect framing (Meier et al. 2021,
https://doi.org/10.1101/2021.07.09.450648), which itself targets DMS fitness scores, not
cellular abundance.

## Overlap, dependence, and leakage risks specific to this benchmark

1. **Same n=8, same labels, same two classes already tested once.** Comparing ESM-2 to
   ThermoMPNN on the identical 5-vs-3 BUB1B label set as `149-...md` is not an independent
   benchmark — it is a second model scored against a label set already shown (via ESM1b) to be
   at or below the power floor for this question. Any AUROC reported must carry the same
   "no power below 4 per class" caveat the project already registered for H083.
2. **Pre-registration already happened once for this exact label set.** `149-...md` pre-set
   its refutation line (AUROC ≤ 0.6, or <4 labels/class) *before* running ThermoMPNN. Running
   ESM-2 against the same 8 labels without a symmetric pre-registered line invites post-hoc
   threshold shopping — the CI widths reported (spanning ~0.9 at n=8, per `149-...md`
   Limitations) mean almost any point estimate in [0.1, 0.9] is statistically indistinguishable
   from both 0.5 and 1.0.
3. **Label provenance is not independent of sequence conservation.** The 5 "abundance-lowering"
   alleles cluster in/near the kinase domain (Suijkerbuijk's own positional rule, noted in
   `149-...md` Conclusion as "drawn from the same alleles, so it is a prior, not a test"). Kinase
   domains are also the most evolutionarily conserved regions of most proteins, which is exactly
   what a sequence model's masked-marginal score is sensitive to. A naive AUROC improvement for
   ESM-2 over ThermoMPNN here could reflect "ESM-2 is better at recognising kinase-domain
   conservation" rather than "ESM-2 predicts abundance better" — the domain/position confound is
   not separable with n=8.
4. **Bootstrap/permutation validity at n=8.** `149-...md`'s own bootstrap CIs (2,000-draw
   stratified bootstrap, seed 0) already span the full plausible range at this n; a permutation
   test for ESM-2 vs ThermoMPNN comparison (e.g., DeLong or a paired permutation of per-allele
   scores) will have very limited resolving power with only 3 stable-class alleles — standard
   guidance for AUROC CIs (and this project's own stated floor) is ≥4 per class, and even that is
   described as underpowered in `149-...md`. **Report any comparison explicitly as
   underpowered/directional, not as a significant difference, unless both classes clear a
   considerably larger n.**
5. **ESM-2 is not a drop-in replacement for ESM1b in this record.** The existing comparator run
   used ESM1b (Brandes 2023, PMID 37563329), a different model from ESM-2, with its own published
   precomputed LLR matrices (`ALL_hum_isoforms_ESM1b_LLR.zip`, already in this repo's
   `build/it4/tables/esm1b/`, per `149-...md` "sequence model (comparator)" row). Swapping in
   ESM-2 does not reuse that asset; it requires a fresh masked-marginal run per the official
   `predict.py` recipe above. Don't conflate "we already have an ESM-family comparator" with
   "we already have ESM-2."

## Recommended protocol (sourced constraints only — sizing/runtime decisions are the parent's)

- Use the **masked-marginals** strategy (`predict.py --scoring-strategy masked-marginals`) to
  match "mutant vs wildtype log probability at the masked site" as specified; `wt-marginals` is a
  cheaper but different (non-masked, single-pass) approximation and should not be silently
  substituted without noting the difference in the writeup.
- Score the same primary n=8 label set used in `149-...md` for comparability, but **report the
  same pre-registered power floor** (≥4 labels/class) that experiment used, and state up front
  that the stable class (n=3) does not clear it — exactly as `149-...md` did for ThermoMPNN.
- Do **not** convert the ESM-2 log-odds into an abundance label, an abundance "prior", or feed it
  into a classifier trained to predict the abundance-lowering/stable split without flagging that
  the official docs characterise this score as conservation/fitness, not abundance.
- Any Modal GPU runtime/cost figures must be labelled "estimated" until measured; this research
  pass did not run GPU jobs and found no official published ESM-2-on-Modal benchmark numbers to
  cite — only Modal's generic GPU-type documentation above.
- Flag the ESM1b-vs-ThermoMPNN precedent (AUROC 0.53 vs 0.60, both inconclusive) prominently in
  any ESM-2 writeup so a reader does not treat a new number on the same n=8 as a novel,
  independent validation.

## Gaps and uncertainties

- Did not fetch the Lin et al. 2022 *Science* paper full text directly (paywalled via
  `science.org`); the "no hard 1024 limit, rotary embeddings" claim rests on the repo's framing
  and general ESM-2 architecture knowledge, not a quoted passage — treat as likely-correct but
  **not independently re-verified against primary paper text in this pass**.
- Did not find an official Meta/ESM benchmark or Modal blog post with measured ESM-2 masked-
  marginal runtime/cost for a ~1,050 aa protein; none exists in the two sources checked.
  Suggested follow-up: a bounded smoke test (e.g. 10-position subset) on Modal, logged the same
  way `149-...md` logged its ThermoMPNN smoke run (GPU-seconds, billing report), before any full
  1,050-position run — this note does not perform that run.
- Did not check facebookresearch/esm GitHub issues for community-reported ESM-2 length/OOM
  reports on ~1,000+ aa proteins; the only length-handling facts cited are from the README's own
  flag documentation (`--cpu-offload`, `--chunk-size`, `--truncation_seq_length`).
- This note does not evaluate plan/expected-outcomes/go-no-go/pitch placement, per the scope
  given — that synthesis is left to the parent.
