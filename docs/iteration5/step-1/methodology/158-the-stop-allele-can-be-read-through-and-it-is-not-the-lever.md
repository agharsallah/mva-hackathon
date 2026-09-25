# 158 — Can the stop allele be read through, and is it worth reading through?

**Step:** iteration 5, [step 1](../README.md), route R1. **Date:** 2026-09-25. **Claims:** none — exploratory, a positive control instead ([note](../../notes/exploratory-no-hypotheses.md)).

## Question

The child has two damaged copies of `BUB1B`: one `stop_gained` (a **premature termination
codon**, PTC — the message says "stop" before the protein is finished) and one
`missense_variant` (one amino acid swapped). Oracle-confirmed as the causal pair (entry 083).

Three questions, in order:

1. **What kind of stop is it?** Which of the three stop codons, what sits next to it, and is
   the message destroyed before it is ever translated (**nonsense-mediated decay**, NMD)?
2. **Would a readthrough drug do anything?** Nonsense-readthrough compounds make the ribosome
   ignore a premature stop. Their effect depends far more on the *context* of the stop than on
   the drug. Can a model trained on other people's measured stops predict this one — and does it
   pass a control before it is allowed to say anything about this child?
3. **Would it matter?** How much working BubR1 does the child make now, how much could
   readthrough add, and where do both sit against the published levels that separate a viable
   hypomorph from neonatal death?

## Inputs

| input | version / identity | role |
|---|---|---|
| `build/it4/records.parquet` | run `it4-records-20260918T211517Z` (entry 114) | the child's normalized allele records: gene, consequence, coding-sequence spelling. Read for one row: `gene = BUB1B`, `consequence = stop_gained` |
| Ensembl REST | release 116, GRCh38, transcript `ENST00000287598` | the public gene model: 23 exons, coding sequence 3,153 nt, 1,050 residues |
| UniProt | `O60566` (BUB1B_HUMAN), 1,050 aa | the public domain annotation: BUB1 N-terminal 62–226, protein kinase 766–1050 |
| **Toledano, Supek & Lehner**, *Nat Genet* 56:1914–1924 (2024), **PMID 39174735**, supplementary table 3 | file sha256 `83b4661d…3a5b64`, downloaded 2026-09-25 | **5,837 measured pathogenic premature stop codons × 8 compounds + untreated**, pooled fluorescent reporter (sort-seq) in HEK293T with 144 nt of native context; values are *percent of the no-PTC control* |
| `ressources/track2/bub1b_published_alleles.tsv` | entry 149 | the published MVA missense alleles, which set the "unstable vs inactive" branches |
| `ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md` | the 8 HPO terms | which adverse-effect axes disqualify a candidate for *this* child |
| BubR1 dosage literature | PMIDs 15208629, 20516114, 23300461, 24825348, 31738183 | the levels a mouse or a cell needs, and the measured missense behaviour |

Code: `mva.drugs.readthrough_context` (sequence facts), `readthrough` (context model + control),
`readthrough_dataset` (wide-table loader), `readthrough_dosage` (the arithmetic),
`readthrough_case` / `readthrough_notes` / `readthrough_dossier` (this case's numbers, wording
and rows), `readthrough_tables` (writers). Drivers `tools/it5_readthrough.py` and
`tools/render_it5_r1.py`.

**Two facts about the dataset that were verified before it was used.** The paper exists under
that name and those authors (the brief's description was right; the first author's given name is
Ignasi). Its supplementary workbook is downloadable without a subscription, and supplementary
table 2 records that **ataluren was tested at 0.1–400 µg/mL and produced no reproducible
readthrough**, so it was excluded from that paper's own panel.

## Commands

```bash
# the workbook (10.2 MB), into the gitignored build tree
curl -L -o build/it5/r1/toledano_MOESM4.xlsx \
  'https://static-content.springer.com/esm/art%3A10.1038%2Fs41588-024-01878-5/MediaObjects/41588_2024_1878_MOESM4_ESM.xlsx'

uv run python tools/it5_readthrough.py all      # dataset → facts → control → predict → dosage
uv run python tools/render_it5_r1.py            # figures/it5/r1-*.svg
uv run python tools/check_coordinates.py        # clean
```

## Positive control

**Declared in writing before any number was computed for this child** (scratchpad
`status-r1.md`, 2026-09-25, and `mva.drugs.readthrough_case.BENCHMARK_PANEL`).

*Method under test.* Group means over `(drug, stop codon, +4 base, −1 base)`, backing off to
`(drug, stop, +4)`, then `(drug, stop)`, then `(drug)`, with at least 2 measured contexts per
cell. Nothing is fitted beyond the group means; the control is the test of whether even that
generalises.

*Control A (primary).* Fourteen PTC contexts that the readthrough literature already benchmarks
on — CFTR G542X, W1282X, R1162X, R553X, G550X, Y1092X (both its stop spellings), TP53 R213X,
DMD R1051X and R3381X, USH2A R626X, PTEN R130X, **BUB1B R114X**, CEP57 R339X — removed entirely
from the fit, then predicted.

*Control B (secondary).* A random 20 % of contexts (1,156 of 5,781), seed 20260925.

*Bar, fixed before the run.* Per compound: Spearman **ρ ≥ 0.5** and pairwise ordering accuracy
**≥ 0.7** on the held-out contexts. A compound is used only if it clears the bar on **both**
controls; anything else is reported as uninterpretable.

*Built-in negative control.* The dataset's own **untreated** column goes through the identical
pipeline. If sequence context "predicted" readthrough with no drug present, the method would be
fitting assay structure rather than biology, and every drug column would be void.

### Result of the control

| compound | A: ρ (14 held out) | A: pair acc. | B: ρ (1,130–1,147 held out) | B: pair acc. | verdict |
|---|---|---|---|---|---|
| **DAP** (2,6-diaminopurine) | **0.83** | 0.820 | **0.81** | 0.808 | **passes both** |
| **G418** | **0.78** | 0.798 | **0.78** | 0.799 | **passes both** |
| **SRI-41315** | **0.65** | 0.742 | **0.64** | 0.735 | **passes both** |
| Gentamicin | 0.75 | 0.809 | 0.52 | **0.688** | fails B (ordering) |
| Clitocine | 0.37 | 0.685 | 0.77 | 0.787 | fails A |
| SJ6986 | 0.47 | 0.674 | 0.67 | 0.747 | fails A |
| CC90009 | 0.25 | 0.573 | 0.60 | 0.721 | fails A |
| 5-fluorouridine | 0.75 | 0.795 | 0.33 | 0.617 | fails B |
| **Untreated** (negative control) | **0.02** | 0.494 | **0.12** | 0.543 | **fails, as it must** |

The negative control behaves exactly as required: with no drug, stop context carries no
information (ρ 0.02 and 0.12, pairwise ordering at chance). The route is therefore interpretable
for DAP, G418 and SRI-41315, and for nothing else.

> **Figure** `figures/it5/r1-control.svg` — blue = the named benchmark panel (primary); green =
> the random held-out fifth; yellow dashed = the pass bar fixed before the run; the red note
> marks the no-drug column, which must fail and does.

## Output

### 1. The stop allele's readthrough-relevant facts

Derived by `mva.drugs.readthrough_context` from the public gene model; the coding offset stayed
inside `build/`. No genomic position appears here or in any table.

| fact | value | why it matters |
|---|---|---|
| stop codon | **UGA** (`TGA` on DNA) | the most readthrough-permissive of the three stops, and the only one DAP acts on |
| **+4 base** (immediately after the stop) | **A** | the single strongest context feature. `C` is the best base; `A` is second for DAP and near-worst for aminoglycosides |
| −1 base | **G** | a weaker modifier, used as the model's finest key |
| exon | **17 of 23** | well inside the body of the transcript |
| distance to the last exon–exon junction | **746 nt**, with **6** junctions downstream | the 50–55 nt rule: more than 55 nt upstream ⇒ **NMD-competent**, the message is destroyed |
| protein truncated | **736 of 1,050 residues** kept — **29.9 % lost** | |
| domains lost | the **entire protein-kinase domain** (UniProt 766–1050) | the domain the child's *other* allele also sits in |
| domains kept | BUB1 N-terminal (62–226) and the KNL1-interaction region | a truncated chain, if any were made, would still reach kinetochores |
| ClinVar | pathogenic / likely pathogenic; gnomAD AF 3.29 × 10⁻⁵ | |

The child's own stop is **not** in the 5,837-variant library (its only `BUB1B` entry is R114X),
so every number below is a prediction, never a lookup.

> **Figure** `figures/it5/r1-stop-anatomy.svg` — purple = coding exons before the stop; yellow =
> the exon carrying the stop (the decision point for the 50–55 nt rule); red = the exons the
> truncated protein never reaches; blue = the junction the rule is measured against.

### 2. Predicted readthrough for this stop (`ressources/track2/it5/readthrough.tsv`)

Every prediction came from the finest cell (`stop+4-1`), backed by 143–144 measured PTC contexts
that share this child's UGA / +4 A / −1 G.

| compound | predicted % of the no-PTC control | × over the no-drug floor | control |
|---|---|---|---|
| **DAP** | **2.85** | 15.8× | passed |
| SJ6986 | 2.63 | 14.6× | failed |
| **SRI-41315** | **2.34** | 13.0× | passed |
| Clitocine | 1.74 | 9.7× | failed |
| CC90009 | 0.63 | 3.5× | failed |
| **G418** | **0.58** | 3.2× | passed |
| 5-fluorouridine | 0.37 | 2.1× | failed |
| Gentamicin | 0.21 | **1.18×** | failed B |
| *untreated floor* | *0.18* | — | negative control |

**The allele-specific finding.** The +4 base costs the two classes very differently. Moving this
stop's +4 from `A` to the best base `C` would raise **G418 3.6-fold** (0.58 → 2.10) but **DAP
only 1.3-fold** (2.85 → 3.71). For *this* child's stop, the aminoglycoside class is worth almost
nothing — gentamicin's prediction sits 18 % above the assay floor, i.e. inside the noise — while
the UGA-selective agents keep most of their effect. Context, not potency, decides the ranking.

> **Figure** `figures/it5/r1-plus4.svg` — red = the +4 base this child's stop actually has;
> blue = the three it does not; grey dotted = the no-drug floor below which a prediction is noise.

### 3. The dosage arithmetic (`ressources/track2/it5/allele_dosage.tsv`)

Per allele, `0.5 × mRNA surviving × protein per mRNA × full-length share × specific activity`, so
a healthy person scores 100 %. Inputs, each sourced: the stop allele's message survives at most
10 % (in MVA patient cells the 386X transcript was undetectable and the 731X allele's absent,
PMID 20516114; the mouse X753 allele matched a null, PMID 31738183); the missense allele's
message is normal and its protein is 2–6-fold low (PMID 20516114), with normal activity once
present (forced overexpression of I909T and L1012P fully restored the checkpoint, same paper).

| scenario | working BubR1 (% of wild type) | drug adds | nearest published genotype |
|---|---|---|---|
| wild type | 100.00 | — | — |
| one healthy copy (a parent) | 50.00 | — | mouse +/− |
| child now, missense 2-fold down | 25.00 | — | above the fidelity cliff |
| **child now, missense 4-fold down (base case)** | **12.50** | — | between mouse H/H (~10 %) and the ~13 % fidelity cliff |
| child now, missense 6-fold down | 8.50 | — | mouse H/H (~10 %) |
| child now, missense **inactive** branch | 5.00 | — | mouse −/H (~4.5 %, neonatal death) |
| child + DAP (readthrough only) | 12.57 | **+0.07 pt** | unchanged |
| child + SRI-41315 | 12.56 | +0.06 pt | unchanged |
| child + G418 | 12.51 | +0.01 pt | unchanged |
| child + DAP **and** a complete NMD blockade (a ceiling, not a dose) | 13.21 | +0.71 pt | unchanged |
| **a perfect readthrough agent** (full transcript, best measured readthrough, wild-type product) | 13.92 | **+1.42 pt** | unchanged |
| **a 2-fold stabilisation of the missense protein** | **25.00** | **+12.5 pt** | clears the fidelity cliff |

The base case lands where a viable MVA child should land — between the mouse hypomorph H/H
(~10 %) and the ~13 % level at which human cells segregate chromosomes near-normally
(PMID 20516114) — which is the closest thing this arithmetic has to an external check.

**The arithmetic's verdict is unambiguous.** Even with every assumption at its most generous —
the whole transcript rescued from NMD, the best readthrough value measured for any UGA context,
and a readthrough product as good as wild type — the stop allele is worth **at most 1.4
percentage points**. Closing the gap the cell measurements identify (~6 % → ~13 %) needs about
**6.5 points**, which would require **~25 % readthrough**; no compound in the dataset exceeds
about 5 % on any context. The missense allele, by contrast, already carries a normal message and
a protein that works once it is present, so doubling its abundance is worth **12.5 points** on
the same arithmetic.

> **Figure** `figures/it5/r1-dosage.svg` — green = scenarios with a treatment; blue = untreated
> states; dashed = published genotypes as yardsticks (green safe, yellow the viable hypomorph,
> red the failing side).

### 4. Candidate rows (`ressources/track2/it5/readthrough_candidates.tsv`, 19 rows)

Rubric (stated here, applied in `readthrough_notes.STRENGTH_RUBRIC`): **0.8** measured in a
living BubR1-deficient animal or in human MVA patient cells for this exact lever; **0.6** a
prediction for this child's exact stop context whose declared control passed on both held-out
sets; **0.5** measured for this gene but not this allele; **0.4** a clinical-grade fact that
bears on use; **0.3** a prediction whose control failed; **0.2** mechanism only; **0.0** ruled
out.

| branch | row | strength | the one-line reason |
|---|---|---|---|
| missense_unstable | NMN / NAD⁺ precursors | 0.80 | the only intervention reported to raise BubR1 *in a living mouse* (SIRT2/K668 axis, PMID 24825348); SIRT2 overexpression extended median lifespan in BubR1 H/H |
| stop_allele | **DAP** | 0.60 | 2.85 % predicted, control passed, UGA-selective — and it inhibits NMD at active concentrations (PMID 32198346), the one agent that attacks both constraints |
| stop_allele | **G418** | 0.60 | control passed but 0.58 % predicted, and it is a laboratory selection reagent, never a medicine |
| stop_allele | **SRI-41315** | 0.60 | 2.34 % predicted, control passed; degrades eRF1, so it reads through normal stops too |
| missense_unstable | proteasome inhibition | 0.50 | MG132 prevents the accelerated turnover of mutant BubR1 in patient-derived cells (PMID 20516114); not a chronic paediatric agent |
| missense_inactive | senolytics (dasatinib + quercetin) | 0.40 | clearing p16-positive cells delayed ageing phenotypes in BubR1 H/H (PMID 22048312); genetic clearance, not a drug, was tested |
| stop_allele | ELX-02 | 0.40 | the only readthrough agent with a live paediatric programme (from age 6, NCT05448755); no prediction here, as the source assay dropped it on cost |
| stop_allele | Clitocine, SJ6986, CC90009, FUr, Gentamicin | 0.30 | predictions exist; their controls failed, so the numbers are not interpretable |
| stop_allele | NMD inhibition (SMG1i, NMDI-14) | 0.20 | the binding constraint this route identified — but NMD is essential (Smg1-null mice die as embryos) and every agent is preclinical |
| stop_allele | amlexanox | 0.20 | dual readthrough + NMD inhibition and already approved, but not reproducible in this route's source assay |
| missense_unstable | CBP/p300 inhibition | 0.20 | the implied inverse of the SIRT2 axis; never shown to raise BubR1 in vivo |
| missense_inactive | rapalogs | 0.20 | mTORC1 hyperactivation tracked sarcopenia in BubR1 +/X753 carriers (PMID 31738183); untested in any BubR1 model |
| missense_unstable | **HSP90 inhibitors** | **0.00** | **ruled out as harmful**: mutant, not wild-type, BubR1 depends on HSP90 (PMID 20516114) |
| stop_allele | **ataluren** | **0.00** | **ruled out three times**: EU authorisation not renewed (EC decision 28 March 2025); discovered in a firefly-luciferase assay it directly stabilises (PMID 19208811); no reproducible readthrough in this route's orthogonal dataset |
| any | Untreated | 0.00 | the negative control row, kept so the check is on the record |

### 5. Safety, cross-referenced against the child's own clinical terms

| candidate | collides with | HPO term |
|---|---|---|
| gentamicin, amikacin, G418 | class proximal **renal tubular** injury in a child who already has calcium deposits in the kidney | Nephrocalcinosis **HP:0000121** |
| the same class | irreversible, cumulative cochleovestibular toxicity under the chronic dosing readthrough needs; MT-RNR1 m.1555A>G causes profound loss at normal doses (CPIC, PMID 34032273) | — (a pharmacogenomic question the variant-only callset cannot answer) |
| clitocine | incorporates into RNA; a genotoxicity question in a child who has already had a sarcoma | Rhabdomyosarcoma **HP:0002859** |
| SJ6986, CC90009, 5-fluorouridine | cytotoxic/anticancer chemotypes, not chronic paediatric agents in a child with failure to thrive | **HP:0001508**, **HP:0004322** |
| ELX-02 | subcutaneous injection, renally eliminated; unresolved audiometric signal at 5.0 mg/kg | HP:0000121 (renal handling) |

The aminoglycoside class is therefore ruled out twice over for this child, and by two
independent arguments: its predicted readthrough for **this** stop context is at the assay
floor, and its toxicity lands on the child's own kidney term.

## Conclusion

1. The stop allele is a **UGA with a +4 A in exon 17 of 23, 746 nt upstream of the last exon
   junction**: firmly NMD-competent. It removes the entire kinase domain.
2. A context model over 5,837 measured PTCs predicts this stop's readthrough at the finest key
   available, and **passes a pre-declared held-out control for DAP, G418 and SRI-41315 while
   failing it for the other five compounds and, correctly, for the no-drug column.**
3. For this stop, the class ranking flips: **UGA-selective agents keep their effect, and
   aminoglycosides do not** — gentamicin's prediction is within noise of the untreated floor.
4. **The route's own arithmetic argues against itself.** Because the stop allele's message is
   destroyed, readthrough of it is worth at most ~1.4 percentage points of wild-type BubR1 under
   the most generous assumptions, against the ~6.5 points that the published cell titration says
   separates majority mis-segregation from near-normal fidelity. **The allele worth treating is
   the missense one**, where the message is intact and the protein is degraded — and where a
   2-fold stabilisation is worth 12.5 points on the same arithmetic.
5. The branch therefore decides everything, and it is not decided: if the missense protein is
   *unstable*, the levers are protein-abundance ones (NAD⁺/SIRT2 first, PMID 24825348); if it is
   *inactive*, no protein-level lever exists and the target moves downstream (senolysis,
   mTORC1). The cycloheximide-chase measurement that separates them is route R4's question.

## Limits

- **Nothing has been measured in this child.** Every allele factor comes from other people's
  BUB1B alleles or from mouse genotypes. There is no protein, no RNA and no cell line here.
- **The dosage model's own premise is contradicted by its best source.** PMID 31738183 showed
  BubR1 H/H and H/L1002P mice carry indistinguishable *total* BubR1 yet differ by 147 days of
  median lifespan. Total level is a necessary, not a sufficient, predictor.
- **NMD of this allele is inferred, not measured.** No allele-specific expression assay has ever
  been published for *BUB1B* in an MVA patient, and no NMD-inhibition rescue in patient cells.
  The 10 % escape used here is a generous upper reading of "undetectable" in PMID 20516114. This
  gap is also the route's clearest experimental proposal.
- **One assay, one cell line, one concentration.** HEK293T sort-seq, 144 nt of context; 431 of
  52,062 values are censored at the assay ceiling and are read as lower bounds, so group means
  are lower bounds. Reporter readthrough is not functional protein rescue.
- **The readthrough product's activity is a stated guess (0.5).** A near-cognate amino acid is
  inserted where the stop was; nothing is measured for this position. The ceiling scenario runs
  it at 1.0, and the conclusion does not change.
- **The model is group means, not the published GLM.** Toledano's own logit-link model reaches
  r² 0.76–0.88 per drug; this route's coarser model is used because it is auditable and because
  its control is what licenses it — not because it is better.
- **`evidence_strength` is a triage rubric, not a probability**, and no row here is clinical
  advice.
- Verified only at abstract level: the NMN dose, route and fold-increase in PMID 24825348.

## Both datasets

| source | what it contributed |
|---|---|
| **Genomic** (the child's WGS callset, via entry 114's records) | the one input that made this route possible: the stop allele's consequence class and its coding-sequence offset, from which the stop codon identity, the +4 and −1 bases, the exon index, the NMD verdict and the truncation were derived. The offset never left `build/`; no genomic position appears in any table or figure. |
| **Clinical** (the proband's 8 HPO terms) | decided which candidates are usable. Nephrocalcinosis (HP:0000121) rules out the aminoglycoside class independently of its predicted efficacy; rhabdomyosarcoma (HP:0002859) argues against RNA-incorporating and cytotoxic chemotypes; failure to thrive and short stature (HP:0001508, HP:0004322) argue against chronic parenteral regimens; the muscle terms (HP:0003202) are what makes the mTORC1 row relevant at all. |
| **Both together** | the conclusion needs both: the genome says the aminoglycoside class is near-useless *for this stop context*, and the clinic says it would be harmful *for this child*. Either alone would be a weaker argument. |

## Files

| file | sha256 (first 12) |
|---|---|
| `ressources/track2/it5/readthrough.tsv` (9 rows) | `9483f717f028` |
| `ressources/track2/it5/allele_dosage.tsv` (12 rows) | `c340fc8bf281` |
| `ressources/track2/it5/readthrough_candidates.tsv` (19 rows) | `3eb2433c9bac` |
| `build/it5/r1/toledano_ptc.tsv` (5,837 rows, gitignored) | `8654a0e155b6` |
| `build/it5/r1/stop_facts.json` (gitignored: transcript offsets) | `e63a27621849` |

Each table carries a `.provenance.json` with its inputs, digests, parameters, assumptions,
limitations and validation. Figures: `figures/it5/r1-{stop-anatomy,control,plus4,dosage}.svg`,
each with its own manifest and legend.
