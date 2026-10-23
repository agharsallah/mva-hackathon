# ESM-2 falsification experiment: execution and submission decision plan

**Status:** proposed, not run. Written 2026-10-22 for final Track 2 iteration 6.
No new prediction, performance result, GPU duration or cost is claimed here.
The final submission must not describe this experiment as completed until its
artifacts and checks exist.

## Recommendation and correction to the original suggestion

Run one bounded ESM-2 experiment only if enough submission time remains to validate
and integrate it. Treat it as an incremental falsification check, not a promised
breakthrough or a way to improve the utility numbers.

Entry [149](../iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md)
already compared ThermoMPNN with the sequence-only ESM1b model:

| Existing result | Primary reference set |
| --- | --- |
| ThermoMPNN raw stability score | AUROC 0.60, bootstrap interval 0.13-1.00 |
| Negated ESM1b log-likelihood ratio | AUROC 0.53, bootstrap interval 0.00-1.00 |
| Experimental reference labels | Five abundance-lowering, three stable |
| Patient's existing ESM1b damage percentile | Approximately 73rd |

Consequently ESM-2 is a new model-generation check, not the first sequence-model
comparison and not an independent experimental validation. ESM1b and ESM-2 are
related sequence-model approaches; sequence and structural predictors can also
share biological biases. The labels have already been examined, so this is a
prospectively frozen analysis of previously used references, not a genuinely blind
external validation study.

## Scientific question

Does a fixed sequence-constraint score distinguish the existing experimentally
labelled abundance-lowering variants from stable variants, and does its placement
of the patient's substitution agree with the structural hypothesis?

These are separate questions. A damaging sequence score can indicate functional
impairment without reducing abundance. Agreement cannot distinguish an unstable
protein from a stable but impaired protein, establish drug responsiveness, or
replace the proposed patient-cell assay.

## 1. Freeze the protocol before new scores

Record a timestamped protocol and its digest before the ESM-2 run. Describe it as
prospectively specified, not as a prediction registered before all earlier work.

- Primary model: one frozen ESM-2 650M checkpoint, with exact revision and digest.
  Check its official interface and license before provisioning.
- Primary score: masked-marginal mutant-versus-reference log probability.
  Negate it for the damage ranking; do not reverse the direction after seeing labels.
- Primary references: the existing eight `primary=yes` rows in
  `ressources/track2/bub1b_published_alleles.tsv`, without relabelling or exclusion.
- Preserve the earlier experiment's minimum of four references per class.
  The current stable class has only three, so this run cannot overturn that
  underpowered verdict, even with a perfect score.
- Primary outcome: raw-score AUROC for abundance-lowering versus stable.
- Report existing ThermoMPNN and ESM1b results beside ESM-2, including the failed
  sequence comparator; do not select the best model and hide the others.
- Patient placement: pre-specify the full-protein substitution universe and the
  descriptive top-20% damage threshold. Report the continuous percentile too.
- Secondary checks: public domain-restricted percentiles, deterministic alternative
  sequence context, and the previously specified extended reference set. They must
  not rescue a failed primary endpoint.
- No fitting an ensemble, selecting a probability cutoff, tuning model size, or
  converting scores into a new 55/45 prior.

Do not multiply supposedly independent evidence probabilities or average ESM
scores with kcal/mol values. They measure different quantities.

## 2. Input and privacy checks

Use public UniProt O60566 and verify its sequence against the existing atlas.
Check all public reference substitutions against the reference amino acid and
one-based residue numbering. Fail explicitly on an isoform or coordinate mismatch.

Only public protein data and public reference variants may go to Modal. Produce
generic scores for every substitution of the public reference protein, without
marking or transmitting the patient's substitution. Join the private case locally,
using the existing `place` pattern; private outputs stay under `build/`.

Source the labels from the existing experimentally supported table, not a
pathogenicity database. Preserve its distinction between stable and functionally
impaired: not all stable variants have a demonstrated functional defect.

## 3. GPU execution on Modal

Use one ephemeral Modal function with one GPU, no public endpoint, bounded timeout
and container count, and pinned package/model versions. Start with an L4 or another
available single GPU that passes the memory smoke test; do not promise a particular
cost or fit before measuring it.

1. Test reference numbering, token indices and the score formula locally on synthetic
   examples; then smoke-test inference on public BUB1B reference positions.
2. Compare single-item versus batched scoring at fixed precision. Use `eval` and
   inference mode, fixed seeds, and tolerances recorded in the protocol.
3. Score the eight public reference substitutions before the larger public scan.
   This is an implementation gate, not a model-selection gate.
4. Mask one residue at a time. One forward pass produces the score distribution
   for all replacement amino acids at that site; do not run a separate forward pass
   for every mutant amino acid.
5. Score the 1,050 positions, yielding 19,950 non-reference substitutions. Include
   self-substitution zero checks internally.
6. Store raw scores, context bounds and sequence/model digests. Transfer only the
   generic results back, then evaluate and place the patient locally.
7. Record actual wall time, GPU-active time if available, observed billing and Modal
   app identifier. Confirm the ephemeral job has stopped.

### Long-sequence handling is a required gate

BUB1B is 1,050 residues. Do not silently truncate the protein or assume that a model
accepting an input length establishes reliable context at that length.

Verify the chosen checkpoint's documented and implemented context behavior.
If using a conservative 1,022-residue context, define the same deterministic
site-centered, terminal-clamped window rule for every site before inference.
Record the original-to-window residue mapping and special-token offset.

For reference alleles and the public pseudokinase domain, compare a second
predefined legal window wherever both include the scored site. Report changes
in score/rank. A context-dependent patient interpretation must be disclosed and
is not a headline result. There is no full-length-equivalence claim.

### Planning envelope

Reserve roughly 60-90 minutes for implementation, checks, inference and reporting,
plus a separate 20-30 minute integration buffer. These are planning estimates,
not measured runtimes or a cloud-service guarantee. Model download, cold start,
GPU availability and batching can dominate.

Measure a small public-position pilot and extrapolate before committing to the
full scan. Stop if the remaining time cannot accommodate validation and document
regeneration. Establish an explicit spend ceiling before execution; do not launch
an open-ended job. A reference-only run can be reported as partial, but cannot
support a patient-wide percentile.

## 4. Evaluation without small-n overclaiming

Reuse `src/mva/drugs/variant_atlas_model.py` for the existing AUROC and stratified
bootstrap conventions. Preserve raw scores and show every labelled allele.

Report:

- AUROC and a seeded stratified bootstrap interval for all three predictors.
- The exact one-sided label-permutation tail for ESM-2's pre-specified direction.
  There are only C(8,5)=56 class assignments. Enumerate them with the actual scores,
  including ties; do not simulate an unnecessarily large permutation null.
- The paired AUROC difference versus each existing predictor as descriptive
  evidence, not proof of improvement from a higher point estimate alone.
- Each stable variant's error, especially a stable but functionally impaired
  allele that a generic sequence-damage model may reasonably flag.
- Public domain/context sensitivity and the patient's local, private placement.

With distinct scores, the reference AUROC changes in steps of 1/15:

| Correct positive-negative orderings | AUROC | Exact upper-tail fraction |
| --- | --- | --- |
| 12/15 | 0.8000 | 7/56 = 0.1250 |
| 13/15 | 0.8667 | 4/56 = 0.0714 |
| 14/15 | 0.9333 | 2/56 = 0.0357 |
| 15/15 | 1.0000 | 1/56 = 0.0179 |

These are a transparent mathematical reference, not observed results or a
multiple-model-selection correction. Label exchangeability is also questionable:
the reference variants differ in domain and experimental setting, and some come
from the same study or allele background. Domain-confounded separation and a
bootstrap interval from eight alleles do not establish external validity.

Do not call ESM-2 significantly better than ThermoMPNN merely because its own
permutation test is below 0.05. Testing against chance and testing two predictors'
difference are different questions.

## 5. Go/no-go for the final submission

In every case, the blot remains the proposed discriminator and the decision
model's utility assumptions remain unchanged.

| Observed outcome | Report treatment | Main pitch treatment |
| --- | --- | --- |
| Strong reference discrimination on the existing eight: at least 14/15 pair orderings, exact one-sided p <= 0.05; context-stable scores; patient in the pre-specified high-damage range | Add a clearly qualified exploratory result, all three models, interval and limitations; the original class-size floor is still unmet | Appendix/backup by default; not sufficient alone for a new positive headline |
| Strong result also reproduces in genuinely new, independently labelled references collected under a frozen protocol, with the class-size floor met and useful uncertainty bounds | Add the external result separately; explain sample size, independence and experimental comparability | Eligible for one qualified slide-2 fragment if it materially improves the story; no abundance-diagnosis claim |
| Good reference discrimination but patient not in high-damage range | Explain the contradiction; do not claim agreement or silently change the prior | At most a short statement that computation did not resolve mechanism; detailed result in backup |
| Patient scores damaging but references do not discriminate abundance classes | Record as unvalidated sequence-damage evidence | No positive mechanistic headline; patient agreement alone is insufficient |
| Weak/null discrimination or wide, unstable results | Keep a transparent negative result in appendix/evidence audit | Omit the new numerical result unless it makes the uncertainty story simpler |
| Strong results driven by domain separation, context choice or one control | Label fragile/exploratory; show sensitivity | Backup only |
| Numbering error, nonfinite scores, failed smoke test, unresolved provenance or incomplete job | Exclude the invalid output from scientific claims; record the failure | Do not add |
| Insufficient time to regenerate and check report/deck/PDFs | Preserve the current submission; optional clearly labelled proposed-work note | Do not add last-minute claims |

These thresholds are editorial inclusion gates, not biological validation
criteria. A valid negative result belongs in the written record even when it
does not earn scarce pitch time.

## 6. What to expect

The realistic upside is a stronger falsification story and a reproducible
cross-model comparison, not a new therapy or a measured stability probability.
Given the existing ESM1b AUROC of 0.53, there is no sound basis to promise that
ESM-2 will separate the abundance classes.

Even a clean AUROC of 1.0 on eight reused references would remain a small,
retrospective-reference result requiring new experimental labels. The experiment
cannot validate NMN, dasatinib or a proteomics lead, change EVPI by measurement,
or establish that increasing BubR1 abundance restores its function.

## 7. Exact integration locations, only after evaluation

The final destination stays `submissions/track2/iteration-6/`; no iteration 7.

**Report:** add an adjacent subsection to the stability/mechanism discussion
(currently section 3.2), titled "Pre-specified ESM-2 model-generation check".
Show the three-model table and one compact figure; put per-allele scores, window
checks and complete methods in a clearly titled appendix subsection. Cross-link
the experiment from the uncertainty/VOI limitations without changing model weights.

**Figure:** one two-panel exhibit: all eight experimentally labelled references
on the three models' native scales, followed by AUROC point estimates and
intervals. Annotate the patient's descriptive percentiles separately, without
exposing its identity. Do not overlay unlike units or present predictor agreement
as an experimental label.

**Pitch:** slide 2, "One unknown decides the treatment", at approximately
0:22-0:46. Replace existing material rather than adding an eleventh slide. Budget
about 8-12 seconds and rehearse within the original 24-second slot. Use one fragment,
one small visual and at most two performance numbers. Keep full labels and caveats
in presenter notes or backup material.

Conditional technical wording, only with genuinely qualifying observed results
and new reference evidence sufficient to clear the main-pitch gate:

> We challenged the structural prediction with a fixed sequence model and checked
> it on [observed N] new experimentally labelled variants. Both computational views
> flagged this substitution. That is support, not an abundance measurement.

Conditional plain-language wording:

> A second kind of computer model also flagged the change, after we checked it
> against known examples. Neither model tells us whether this child's protein
> disappears too quickly. That is why the cell test still comes first.

Do not say "two independent validations", "we confirmed destabilization",
"ESM-2 proved NMN works", or "the new model measured the 55% prior".
Do not add a new slide of GPU branding or use cost as the scientific result.

If the new model fails:

> A newer sequence model did not reliably distinguish protein loss from stable
> variants. We kept that negative result and retained the patient-cell assay.

That sentence is optional in the main pitch; it earns space only if it improves
clarity rather than adding another model name.

**Files:** keep public results and manifests in a dedicated
`ressources/track2/it6/esm2_check/` directory, private placement under `build/`,
and public figures in `figures/it6/`. Link them from the iteration-6 README.
Update `report.md`, `pitch-script.md`, `pitch-slides.html`, both PDFs and any
affected methods JSON/XLSX together. Preserve deck interactions.

Before adding this experiment, recheck the existing spoken script as well as
headline tables: disclaimers do not repair an incorrect statement in a spoken
paragraph. In particular, no historical "nearly threefold" proteomics wording
should survive when the current raw changes are +0.22/+0.20 log2FC.

## 8. Acceptance and stopping checklist

1. Frozen protocol, one model, explicit context rule and spend/time ceiling.
2. Reproducible public-input inference, numbering and self-substitution checks.
3. Actual eight-reference results, exact null and all prior model comparisons.
4. Patient placement performed locally only; no case identifiers in cloud inputs.
5. Valid negative outcomes retained; no post hoc model/threshold shopping.
6. Inclusion gate applied before editing the pitch.
7. Numeric assertions, citations and manifests verified; old score/clinical claims
   absent from spoken script, HTML, report and generated files.
8. Updated PDFs/XLSX and submission readiness gate pass; pitch rehearsed at duration.

**Decision:** worth a bounded exploratory run if the integration buffer exists.
Not worth risking a consistent final submission for. It can improve the rigor
and narrative if the controls work; it cannot by itself take the biological
evidence to the next level that new abundance or functional measurements would.

## Sources and follow-up verification

- Existing experiment and measured comparator results:
  [methodology entry 149](../iteration4/step-9/methodology/149-the-stability-atlas-and-the-childs-missense.md).
- Existing public labels:
  [`bub1b_published_alleles.tsv`](../../ressources/track2/bub1b_published_alleles.tsv).
- Existing score/evaluation implementation:
  [`variant_atlas_model.py`](../../src/mva/drugs/variant_atlas_model.py).
- Official ESM project and variant-prediction examples:
  <https://github.com/facebookresearch/esm> and
  <https://github.com/facebookresearch/esm/tree/main/examples/variant-prediction>.
- Official Modal GPU documentation:
  <https://modal.com/docs/guide/gpu>.
- Companion primary-source review:
  [ESM-2 benchmark sources](esm2-orthogonal-benchmark-sources.md). It confirms the
  scoring formula, distinguishes ESM-2 from ESM1b length handling, and records
  remaining uncertainties. Verify checkpoint/context details before execution.
  This plan does not authorize a GPU run.
