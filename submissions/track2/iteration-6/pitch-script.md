# Track 2 — 3-Minute Video Pitch Script & 7-Slide Companion Deck (Unified Iteration 6)

**Standing:** ready (written 2026-09-27 for `submissions/track2/iteration-6/`).
**Target duration:** 3 minutes 00 seconds (~420–430 spoken words at 140–145 wpm).
**Companion Slide Deck (in this folder):**
- **Interactive Widescreen HTML Deck:** [`pitch-slides.html`](pitch-slides.html) — open in any browser; use **`→` / `Space`** to advance slides at each **`[👉 SLIDE N]`** cue below, and press **`T`** to toggle the built-in bottom teleprompter between **Version A (Technical)**, **Version B (Plain-English)**, or **Hidden** (for clean video capture).
- **Print / Screen-Share 16:9 PDF Deck:** [`pitch-slides.pdf`](pitch-slides.pdf) — 7 widescreen slides with all research figures and our new two-panel synthesis diagram (`figures/it5/r6-pitch-overview.svg`) pre-embedded.

---

## 7-Slide Deck Map & Timing Cue Sheet

| Slide | Timestamp | Slide Title | Embedded Visuals on Slide | Key Message Before Advancing |
| :--- | :--- | :--- | :--- | :--- |
| **Slide 1** | `0:00 – 0:25` *(Tech)*<br/>`0:00 – 0:30` *(Plain)* | **The Child, the "Seatbelt Inspector" (`BUB1B`), and the 5-Instrument Mechanism** | `figures/it4/step9-e1-distribution.svg` ($\Delta\Delta G = +1.55\text{ kcal/mol}$) + `step9-e2-rank.svg` (`Bub1b^{H/H}` mouse twin top 0.99%) | Copy #1 (`stop_gained`) is destroyed; Copy #2 (`missense`) is the sole lever (`55% Unstable` vs. `45% Inactive`). |
| **Slide 2** | `0:25 – 0:52` *(Tech)*<br/>`0:30 – 0:52` *(Plain)* | **Why Stop-Skipping & Naive AI Fail — And What Survives Null Testing** | `figures/it5/r1-dosage.svg` + `figures/it4/step10-s2-upset.svg` + **5-Archetype Naive-AI Counterfactual Table** | Stop-codon readthrough adds `<1.5%` protein (`EVPPI = 0%`); **dasatinib** (`twin\|prism`) is the sole 2-generator survivor ($p=0.0096$). |
| **Slide 3** | `0:52 – 1:15` | **8,793-Compound Proteome Scan vs. 3D Pseudokinase Pocket Biophysics** | `figures/it5/r2-hits.svg` + **New Hero Diagram `figures/it5/r6-pitch-overview.svg`** (Buried core vs. distal `Lys668`) | `Gliclazide`/`migalastat` raise BubR1 `2.7x` in cells, but because the missense sits in a buried pseudokinase core (`RSA < 0.20`), distal `Lys668` `NAD+/SIRT2` shielding (`NMN`, `nicotinamide`, `niacin`) is biophysically superior. |
| **Slide 4** | `1:15 – 1:42` | **Cross-Iteration Synthesis & Route Calibration (`Entry 163`: 52 Drugs Unified)** | `figures/it5/r5-cross-iteration.svg` (Panel A candidate comparison + Panel B 20-step $w_{R2}$ sweep) | `EVPI = 0.1800` is 100% invariant (`100%` on `missense_class`); calibrating $w_{R2}=0.25$ raises the 48h `CHX`-chase blot value to **`69.1% of EVPI`**. |
| **Slide 5** | `1:42 – 2:05` | **Clinical Tumor Board Action Card & Paediatric PK/PD Dosing Protocol** | `figures/it5/r4-decision-tree.svg` + **Paediatric PK/PD Dosing & Liquid Formulation Table** | "Test Once Before You Treat": 48h blot $\rightarrow$ **Unstable:** `nicotinamide`/`niacin`/`NMN` (backups `migalastat`/`gliclazide`) · **Inactive:** `dasatinib` `PFOS` suspension · **Tumour D4:** `simvastatin`/`lovastatin` liquid. |
| **Slide 6** | `2:05 – 2:40` | **First, Do No Harm — 2-Source Per-Child Safety & PGx Callability Honesty** | `figures/it5/r3-mva-exposures.svg` + `figures/it4/step9-e56-coverage.svg` (`1.6%` VCF PGx coverage) | **Do-Not K1:** 33/34 Mps1/Aurora inhibitors fail in aneuploidy ($p=0.0096$) · **Double-Flag K2:** `vincristine` (`CYP3A5 *1/*3` + `HP:0003202`) · **Gate K3:** 5-gene PGx panel + `RYR1` anaesthesia alert. |
| **Slide 7** | `2:40 – 3:00` | **Zero-Edit Scalability — Re-Executed on Bloom Syndrome (`BLM`) in 53 Min for $0** | `figures/it4/step11-t1-stages.svg` + `figures/it5/s1-transfer.svg` | Full pipeline re-ran on Bloom syndrome in `53 min` for `$0` (`Blm` twin top `1.15%`, `Jaccard = 0.095`, 522 provenance edges). |

---

This document provides **two complete 3-minute scripts** synchronized to the exact same 7 slides:
1. **[Version A — Technical Bioinformatics & Pharmacology Cut](#version-a--technical-bioinformatics--pharmacology-cut):** Written for computational biology and clinical pharmacology judges.
2. **[Version B — Plain-English / Non-Technical Cut (With Everyday Analogies)](#version-b--plain-english--non-technical-cut-with-everyday-analogies):** Written for non-technical audiences, patient families, and general reviewers.

---

## Version A — Technical Bioinformatics & Pharmacology Cut

### `[🎬 START ON SLIDE 1 — 0:00]` The Child, the "Seatbelt Inspector" (`BUB1B`), and the 5-Instrument Mechanism
- **On screen (`Slide 1 / 7`):** KPI cards (`Rank 1 Confirmed`, `ΔΔG = +1.55 kcal/mol`, `Top 0.99% MGI Twin`, `RMSD = 0.45 Å`) + `step9-e1-distribution.svg` (ThermoMPNN stability atlas) + `step9-e2-rank.svg` (76,699 MGI mouse twin ranking).
- **Spoken narration (`0:00 – 0:25`):**
  > "In Track 1, the oracle confirmed at Rank 1 that this child's Mosaic Variegated Aneuploidy and rhabdomyosarcoma are caused by two broken copies of `BUB1B`: one premature stop codon and one missense swap in the BubR1 pseudokinase domain.
  > Before naming a single medicine, we read the disease mechanism from five independent instruments that share no data: nine variant-effect models, a Boltz-2 structure fold, an all-19,950-substitution ThermoMPNN stability atlas *(point left)*, and a cross-species match of the child's 8 HPO terms against all 76,699 mouse genotypes in MGI *(point right)*.
  > The result is hypomorphic loss of function: the child's phenotype twin in the top 1% of all mouse models (`p = 0.026`) is the `Bub1b^{H/H}` hypomorph — a mouse with too little stable BubR1, premature cellular senescence, and muscle wasting. Meanwhile, the child's missense allele sits at the 87.3rd percentile of destabilizing folding energy (`+1.55 kcal/mol`), giving a 55% prior that the mutant protein is unstable and degraded, versus 45% that it folds stably but is catalytically inactive."

### `[👉 ADVANCE TO SLIDE 2 — 0:25]` Why Stop-Skipping & Naive AI Pipelines Fail — And What Survives Null Testing
- **On screen (`Slide 2 / 7`):** Left: `r1-dosage.svg` (stop-allele readthrough dosage gap) + `step10-s2-upset.svg` (4-generator convergence). Right: **5-Archetype Naive-AI Counterfactual Benchmark Table**.
- **Spoken narration (`0:25 – 0:52`):**
  > "**[CLICK → SLIDE 2]** Rather than trusting a single pipeline or a naive AI target lookup — which, as our counterfactual table on the right shows, would fatally recommend mitotic inhibitors or neurotoxic vincristine — we forced every generator through pre-registered negative controls and permutation nulls.
  > Across four independent drug generators *(point bottom-left)*, only one FDA-approved drug converged across two sources: **dasatinib**, which clears senescent cells in the `Bub1b^{H/H}` twin and ranks at the 99.4th percentile for selectively killing high-aneuploidy cancer cells (`p = 0.0096`).
  > And because our 10,000-draw permutation null showed one overlap can occur by chance (`p = 0.263`), we audited stop-codon readthrough (`Route R1`, *top-left*) and proved its sequence context is suboptimal (`score = 0.33`), adding under 1.5% functional protein against an 8.5% to 28.5% rescue gap."

### `[👉 ADVANCE TO SLIDE 3 — 0:52]` 8,793-Compound Proteome Scan vs. 3D Pseudokinase Pocket Biophysics
- **On screen (`Slide 3 / 7`):** Left: `r2-hits.svg` (proliferation-corrected & Gygi-10k proteome raisers). Right: **`r6-pitch-overview.svg`** (3D Buried Pseudokinase Core `RSA < 0.20` vs. Distal `Lys668` `SIRT2`/`NAD+` Shielding).
- **Spoken narration (`0:52 – 1:15`):**
  > "**[CLICK → SLIDE 3]** Next, we scanned 8,793 chemical perturbations in the Gygi-10k proteome atlas (`Route R2`, *left*) using empirical-Bayes shrinkage, uncovering two oral FDA-approved drugs — **gliclazide** and **migalastat** — that raise endogenous BubR1 protein 2.7-fold (`+1.47` and `+1.44 log2FC`).
  > Crucially, we then audited 3D biophysical plausibility across all 1,178 substitutions in the 62-residue buried pseudokinase core (`RSA < 0.20`, *right*): because the missense site is buried inside a non-catalytic pseudokinase with no open cleft for polar chaperones like `migalastat` (`logP = -2.6`), distal deacetylation of solvent-exposed `Lys668` via `SIRT2` and `NAD+` precursors (**NMN, nicotinamide, and niacin** — which double `Bub1b^{H/H}` mouse survival *in vivo*) is biophysically superior to direct orthosteric docking."

### `[👉 ADVANCE TO SLIDE 4 — 1:15]` Cross-Iteration Synthesis & Route Calibration (`Entry 163`)
- **On screen (`Slide 4 / 7`):** KPI banner (`w_R2 = 0.25`, `EVPI = 0.1800`, `EVSI = 69.1% of EVPI`, `2 Exact Flip Points`) + full-width `r5-cross-iteration.svg` (Panel A & Panel B).
- **Spoken narration (`1:15 – 1:42`):**
  > "**[CLICK → SLIDE 4]** In Iteration 6 (`Entry 163`), we unified all 52 drug candidates across Iterations 2, 4, and 5 and swept the Route-R2 proteomics weight across 20 calibration steps *(Panel B)*.
  > Two mathematical results stand out:
  > First, Expected Value of Perfect Information (`EVPI = 0.1800`) is 100% invariant across every weight — and **100% of that uncertainty (`EVPPI = 0.1800`) sits on a single biological question**: is the child's missense protein unstable or inactive? Zero percent sits on stop-codon readthrough.
  > Second, calibrating `w_R2 = 0.25` *(Panel A)* restores evidence-hierarchy coherence and increases the Value of Sample Information of a single **48-hour cycloheximide-chase BubR1 Western blot** from **59% to 69.1% of EVPI (`EVSI = 0.1245`)**."

### `[👉 ADVANCE TO SLIDE 5 — 1:42]` Clinical Tumor Board Action Card & Paediatric PK/PD Dosing Protocol
- **On screen (`Slide 5 / 7`):** Left: `r4-decision-tree.svg` (two-state VOI tree). Right: **Paediatric PK/PD Dosing, Liquid Formulations & Mandatory Pre-Gates Table**.
- **Spoken narration (`1:42 – 2:05`):**
  > "**[CLICK → SLIDE 5]** This gives the Clinical Tumor Board a bedside-ready protocol with paediatric `mg/kg` and `mg/m²` formulations:
  > - **Step 1:** Run the 48-hour cycloheximide-chase Western blot in patient versus parental cells.
  > - **Before the blot — and if the blot shows stable-but-inactive BubR1:** **dasatinib** (`60–85 mg/m²/day` paediatric `PFOS` oral suspension, `EU = 0.2537`) is the #1 FDA-approved lead.
  > - **If the blot confirms unstable BubR1:** **NMN** (`u = 0.4800`) is the #1 overall compound, oral **nicotinamide** (`10–20 mg/kg/day`) and **niacin** (`u = 0.1920`, supported across all three iterations) are the #1 FDA-approved drugs, and **migalastat** and **gliclazide** serve as oral backups.
  > - **For the presenting embryonal rhabdomyosarcoma:** `SLCO1B1`-gated **simvastatin or lovastatin** oral suspension (`NCT02390843`) is our Rung-5 tumour adjunct."

### `[👉 ADVANCE TO SLIDE 6 — 2:05]` First, Do No Harm — 2-Source Per-Child Safety & PGx Callability Honesty
- **On screen (`Slide 6 / 7`):** Red/Amber safety KPIs + `r3-mva-exposures.svg` (published MVA exposures) + `step9-e56-coverage.svg` (`1.6%` PharmCAT VCF coverage).
- **Spoken narration (`2:05 – 2:40`):**
  > "**[CLICK → SLIDE 6]** Every candidate was audited against the child's own genome and clinical terms (`Entries 152, 161`).
  > First, **Do-Not K1**: across 919 cancer lines, **33 of 34 Mps1/TTK and Aurora kinase inhibitors** are *less* effective in aneuploid cells (`p = 0.0096`) and worsen chromosomal chaos — they are strictly contraindicated.
  > Second, **vincristine** — a standard rhabdomyosarcoma backbone drug — is the only medicine flagged by **both** safety sources: a `CYP3A5 *1/*3` genotype plus an exact drug-label match to the child's skeletal muscle atrophy (`HP:0003202`).
  > Third, because the delivered variant-only VCF covers just **1.6% (`20 of 1,223`)** of PharmCAT loci *(right)*, we require a **5-gene clinical PGx panel (`SLCO1B1`, `ABCG2`, `CYP2C9`, `G6PD`, `UGT1A1`)** before statin or adjunct therapy, plus malignant-hyperthermia anaesthesia precautions for an incidental `RYR1` variant."

### `[👉 ADVANCE TO SLIDE 7 — 2:40]` Zero-Edit Scalability — Re-Executed on Bloom Syndrome (`BLM`) in 53 Min for $0
- **On screen (`Slide 7 / 7`):** Scalability KPIs (`53 Min • $0`, `Top 1.15% MGI Twin`, `522 Provenance Edges`, `Zero Coordinates Leaked`) + `step11-t1-stages.svg` + `s1-transfer.svg`.
- **Spoken narration (`2:40 – 3:00`):**
  > "**[CLICK → SLIDE 7]** Finally, this entire platform is built for any N-of-1 rare disease. We executed the full chain on a second chromosomal-instability disorder — **Bloom syndrome (`BLM`)** — in 53 minutes on a laptop for **$0**, matching `Blm` mice in the top 1.15% of MGI and generating a disease-specific candidate list (`Jaccard = 0.095`) with byte-identical regression checks on Case 1. Every script, provenance manifest, and negative result is open and reproducible in our repository. Thank you."

---

## Version B — Plain-English / Non-Technical Cut (With Everyday Analogies)

### Plain-English Analogy Cheat-Sheet (How We Explain the Science)

| Scientific Concept | Plain-English Meaning & Analogy Used in Script |
| :--- | :--- |
| **`BUB1B` gene / BubR1 protein** (spindle assembly checkpoint kinase) | **The cell's "seatbelt inspector"**: Before a cell divides in two, BubR1 checks that every chromosome is buckled in properly so neither daughter cell gets the wrong number of chromosomes. |
| **Mosaic Variegated Aneuploidy (MVA)** | **Unbuckled cell division**: Because the seatbelt inspector is faulty, cells divide with missing or extra chromosomes, causing slow growth, premature cell aging, and childhood muscle cancer (**rhabdomyosarcoma**). |
| **Compound heterozygote (`stop_gained` + `missense_variant`)** | **Two different broken instruction manuals** (one from each parent): Copy #1 has a **full stop sign halfway through** (`stop_gained`), so the cell shreds it. Copy #2 has a **single letter typo** (`missense_variant`) — it still builds the inspector protein, which is the only reason this child is alive. |
| **`unstable` vs. `inactive` missense state** | **The one big question about Copy #2**: Does the typo make the inspector protein **crumple and melt away too fast** (`unstable`, 55% chance), or does it **hold its shape but fail to do its job** (`inactive`, 45% chance)? |
| **Value of Information (`EVPI` / `EVSI`) & Cycloheximide-chase Western blot** | **"Test once before you treat"**: A math framework that proves **one simple 48-hour lab test on the child's cells** (measuring how fast the BubR1 protein disappears) removes **nearly 70% of the guesswork** before a doctor picks a medicine. |

---

### `[🎬 START ON SLIDE 1 — 0:00]` The Child's Condition — A Faulty "Seatbelt Inspector" Inside Dividing Cells
- **On screen (`Slide 1 / 7`):** KPI cards + 3D stability distribution (`step9-e1-distribution.svg`) + 76,699 mouse twin match (`step9-e2-rank.svg`).
- **Spoken narration (`0:00 – 0:30`):**
  > "Every time one of our cells divides, a guardian protein called **BubR1** acts like a **seatbelt inspector** — making sure every chromosome is properly lined up before the cell splits.
  > In Track 1, we proved that this child inherited two broken copies of the `BUB1B` gene that makes this inspector.
  > The first copy has a premature stop sign halfway through, so the cell's cleanup crew destroys it almost completely.
  > That means the child's survival depends entirely on the **second copy**, which has just a **single-letter typo**.
  > By testing that typo across 3D protein-folding models *(point left)* and comparing the child's symptoms against over 76,000 laboratory mouse models *(point right)*, we found the child's exact biological twin: a well-studied mouse with **too little working BubR1**, whose cells age prematurely and whose muscles waste away.
  > And our 3D folding map revealed the **one crucial question** that decides how to treat this child: does that single typo make the BubR1 protein **crumple and break down too fast** — a 55% chance — or does the protein **hold its shape, but sit on the job without working** — a 45% chance?"

### `[👉 ADVANCE TO SLIDE 2 — 0:30]` Why "Stop-Skipping" Drugs & Standard AI Shortcuts Fail
- **On screen (`Slide 2 / 7`):** Left: `r1-dosage.svg` + `step10-s2-upset.svg`. Right: **5-Archetype Naive-AI Counterfactual Table**.
- **Spoken narration (`0:30 – 0:52`):**
  > "**[CLICK → SLIDE 2]** Because developing a brand-new drug takes a decade, we searched thousands of **already-approved medicines** from three completely different angles — and we checked every idea against strict statistical controls so we wouldn't fall into the traps that trip up standard AI tools *(point right)*.
  > **First**, we asked: can a drug force the cell to ignore the stop sign on Copy #1? Our sequence check *(top-left)* showed that 'stop-skipping' drugs would restore less than 1.5% of normal protein, which isn't enough.
  > And when we asked what protects tissues if Copy #2 cannot be rescued at all *(bottom-left)*, one FDA-approved medicine stood out across both our mouse twin and 919 cancer cell lines: **dasatinib**, which clears out damaged aging cells."

### `[👉 ADVANCE TO SLIDE 3 — 0:52]` 8,793-Drug Protein Scan & Why Surface Shielding (`Lys668`) Beats Deep Docking
- **On screen (`Slide 3 / 7`):** Left: `r2-hits.svg`. Right: **`r6-pitch-overview.svg`** (3D Buried Core vs. Distal `Lys668` `NAD+/SIRT2` Shield).
- **Spoken narration (`0:52 – 1:15`):**
  > "**[CLICK → SLIDE 3]** **Second**, we asked: what if Copy #2 is **crumpling too fast**?
  > A scan of **8,793 compounds** in human cells *(left)* uncovered two oral pills — **migalastat** and **gliclazide** — that raised BubR1 protein levels more than **two-and-a-half-fold**.
  > And when we inspected the 3D protein structure *(right)*, we saw why our mouse-twin **vitamin B3 / NAD+ boosters — NMN, nicotinamide, and niacin** — are even stronger: the child's typo is buried deep inside the protein core where a drug cannot easily dock, whereas **NAD+ boosters flip a surface switch (`Lys668`)** that shields the whole BubR1 protein from being thrown in the cellular trash — doubling healthy lifespan in the matching mouse model."

### `[👉 ADVANCE TO SLIDE 4 — 1:15]` One Simple Lab Test Removes 70% of the Guesswork (`Entry 163`)
- **On screen (`Slide 4 / 7`):** KPI banner + `r5-cross-iteration.svg` (52 candidates unified + 20-step calibration curve).
- **Spoken narration (`1:15 – 1:42`):**
  > "**[CLICK → SLIDE 4]** In our final unified submission, we combined all 52 drug candidates from every stage of our work into a single **clinical decision engine** that weighs real whole-animal survival higher than single petri-dish experiments.
  > Instead of handing doctors a static list and guessing, our math proves something remarkable: **100% of the uncertainty** about which drug is best comes down to that one question about Copy #2.
  > Better yet, doctors don't have to guess. A **single, standard 48-hour lab test** on a small sample of the child's cells — called a **protein stability blot** — measures whether the child's BubR1 protein melts away too fast or holds steady, capturing **nearly 70% of the entire decision value** before giving a single dose."

### `[👉 ADVANCE TO SLIDE 5 — 1:42]` The Bedside Action Card — Child-Friendly Doses for Every Branch
- **On screen (`Slide 5 / 7`):** Left: `r4-decision-tree.svg`. Right: **Paediatric PK/PD Dosing & Liquid Formulation Table**.
- **Spoken narration (`1:42 – 2:05`):**
  > "**[CLICK → SLIDE 5]** Here is how the care team uses our Action Card at the bedside:
  > - **If the 48-hour lab test shows the protein melts away too fast:** start with the **NAD+ boosters (NMN, niacin, or nicotinamide in child-friendly liquid form)** to stabilize BubR1 via its natural repair pathway, with **migalastat** or **gliclazide** as oral backups.
  > - **If the lab test shows the protein is stable but inactive:** switch to **dasatinib oral suspension** to clear damaged aging cells.
  > - **And to help fight the child's muscle tumour directly:** pair standard care with **simvastatin or lovastatin strawberry oral suspension**, two cholesterol medicines already tested in children's cancer trials that starve this specific muscle tumour."

### `[👉 ADVANCE TO SLIDE 6 — 2:05]` First, Do No Harm — Checking the Child's Own DNA for Drug Safety
- **On screen (`Slide 6 / 7`):** Safety KPIs + `r3-mva-exposures.svg` + `step9-e56-coverage.svg`.
- **Spoken narration (`2:05 – 2:40`):**
  > "**[CLICK → SLIDE 6]** For a fragile child, knowing **what not to give** is just as important as finding a treatment.
  > First, a common hunch in biology is to use cell-division-blocking cancer drugs. Our data across 919 cell lines proves the exact opposite: **33 out of 34 drugs in that class actually work worse** in cells like this child's and make chromosome scrambling worse. We flag the entire class as **strictly do-not-give**.
  > Second, by cross-checking the child's DNA and existing muscle weakness against drug safety labels, we flagged **vincristine** — a routine childhood chemotherapy — as a **double-warning risk** for severe nerve and muscle toxicity in this specific child.
  > And because standard genetic files only cover **1.6%** of known drug-metabolism spots *(right)*, we give the care team an exact **5-gene safety checklist** to run before prescribing a statin, plus an anaesthesia surgical alert we caught in the child's DNA."

### `[👉 ADVANCE TO SLIDE 7 — 2:40]` Built to Help the Next Rare-Disease Child in Under an Hour
- **On screen (`Slide 7 / 7`):** `step11-t1-stages.svg` + `s1-transfer.svg` (Bloom syndrome transfer in 53 minutes for $0).
- **Spoken narration (`2:40 – 3:00`):**
  > "**[CLICK → SLIDE 7]** Best of all, we didn't build a one-off script just for this hackathon. We built a reusable, open-source rare-disease engine. When we pointed it at a completely different genetic disorder — **Bloom syndrome** — without changing a single line of code, it ran in **53 minutes on a standard laptop for $0** and produced a tailored, safety-checked treatment roadmap. Thank you."

