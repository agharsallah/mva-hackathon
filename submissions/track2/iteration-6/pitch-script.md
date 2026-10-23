# Track 2 — 4-Minute Pitch Script & 10-Slide Companion Deck (Unified Iteration 6)

> **Embedded historical images:** R2–R5 images are retained as historical analysis illustrations, not current numerical authority. Any image label 1.47/1.44 as BUB1B log2FC is incorrect: canonical raw values are 0.22/0.20. Any historical .90-specificity or .912/.831 posterior label is superseded by assumed .85 specificity and the generated section 6 table.

> **Sensitivity headline:** Only 3,815/7,425 assumption-grid settings (51.38% unweighted coverage, not confidence) capture at least half of EVPI; EVSI/EVPI spans 0–0.98. The often-quoted 69.1% is the nominal assumed-point scenario, not a robust universal result. See section 6 for all six axes.

> **Current model and protocol:** All priors, utilities, route weights, safety multipliers and assay accuracies are assumed research-triage weights, not calibrated probabilities of benefit, a validated diagnostic assay, or clinical prescriptions. Current assumed Se = Sp = 0.85 gives P(low) = 0.535, P(normal) = 0.465, P(unstable | low) = 0.8738 and P(inactive | normal) = 0.8226. EVPI = prior(inactive) × 0.4 = 0.18 is structural over the reported route-weight sweep, not independent biological confirmation. Readthrough information value is zero because the strict dosage-feasibility prior is zero; context heuristic 0.10 is a separate score. Use primary patient and parental fibroblasts, CHX 0, 2, 4, 8 h ±MG132. These are assay sampling hours; culture and turnaround are weeks 1–2, with no guaranteed 48h clinical result. Candidate doses are literature context only, not a dosing plan. Embedded R4/R5 decision SVGs are historical illustrations: any .90-specificity or .912/.831 labels in those figures are superseded by the current .85 model.

**Standing:** ready (rewritten 2026-10-22 to match the 10-slide `pitch-slides.html`). The pitch is now **4:00**. It is the round-2 3:00 pitch plus a 60-second engineering and infrastructure segment (slides 7–8). Every science number traces to `report.md`, `README.md` or `methods-form.json` in this folder. Every infrastructure number traces to a file path in the repository, and the cited path is shown on each slide.
**Target duration:** 4 minutes 00 seconds, 10 slides, ~570 spoken words at ~145 wpm. Both versions are timed to the same slide grid: Version A runs 563 words and Version B runs 577.

> **3-minute cut.** The README describes the optional video pitch as 3 minutes. For a 3:00 delivery, **skip slides 7–8** (the engineering segment, 2:26–3:26). Their opening line ("Every number you just heard comes out of one machine…" / "How do you know any of this is real?") is that segment's only transition, so it goes with them. Nothing else in the script changes. To jump from the end of slide 6, press **`O`** and click slide 9. Exact 3:00 timings: slides 1–6 `0:00–2:26` (unchanged) · slide 9 `2:26–2:44` · slide 10 `2:44–3:00`. That is 428 words (A) or 440 words (B). **`A` (auto-advance) follows the 4:00 grid**, so for a 3:00 voice-over, advance by hand.

**Companion deck (in this folder):** [`pitch-slides.html`](pitch-slides.html) is a single self-contained file. It opens in any browser and needs no network. The notes for both versions live inside the deck.

| Key | What it does |
| :--- | :--- |
| **`→` / `Space` / `PageDown`**, **`←` / `PageUp`** | Next or previous step. Each **`[click]`** below reveals one fragment, and the slide advances after its last fragment. Clickers work the same way. |
| **Mouse on slides 7–8** | Architecture boxes, the **Trace** buttons, lineage chains and API endpoints are buttons. Clicking them opens facts or animates a path, and **never advances the slide**. They also work with `Tab` and `Enter`. Below, these are marked **`[tap: …]`**, which is different from `[click]`. |
| **`F`** | Fullscreen |
| **`P`** | Opens the presenter window (current and next slide, notes, timer). Put it on your second screen. |
| **`N`** *(presenter window)* | Switches the presenter notes between Tech and Plain |
| **`T`** *(audience window)* | Cycles the inline teleprompter: Tech → Plain → Hidden |
| **`V`** | Visibility panel for timing, criterion, sources, caveat, captions, teleprompter, toolbar and more. It has three presets: **Rehearsal** (everything visible), **Live pitch** (hides timing, teleprompter and toolbar on the audience screen) and **Recording** (also hides the progress bar and timer). |
| **`S`** | Start or pause the timer. `Shift`+`R` resets it. |
| **`A`** | **Auto-advance on the slide timings (4:00 grid).** It follows the timer and spreads each slide's fragments evenly over that slide's budget. Use it for voice-over recording of the full 4:00. |
| **`O`** · **`Z`** · **`L`** · **`B`** | Overview grid (click a slide to jump) · zoom the figure · laser pointer · blackout |
| **`?`** | Shows every shortcut |
| URL **`pitch-slides.html?preset=recording`** | Opens with the Recording preset already applied. **`?view=presenter`** opens the presenter view directly. |
| Toolbar **print** button | Exports a PDF with all fragments revealed, one slide per page. The interactive slides print in their default state: the full diagram and every chain listed. |

---

## 10-Slide Deck Map & Timing Cue Sheet

| Slide | Timestamp | Slide Title | Visuals on Slide | Key Message Before Advancing |
| :--- | :--- | :--- | :--- | :--- |
| **Slide 1** | `0:00 – 0:22` | **One child, one lever left** | Copy #1 vs Copy #2 compare panel · `s1-mgi-twin` (child's 8 HPO terms vs 76,699 MGI genotypes) · KPIs: Rank 1 oracle, 8 HPO terms, top 0.99% mouse twin · "seatbelt inspector" callout | Copy #1 (`stop_gained`) is lost to NMD, so every therapeutic decision runs through Copy #2 (pseudokinase missense). |
| **Slide 2** | `0:22 – 0:46` | **One unknown decides the treatment** | `s1-thermompnn` (all 19,950 substitutions, child at +1.55 kcal/mol, 87.3rd pct) · KPIs: ΔΔG, 55%, 45%, AUROC 0.76 across 11 DMS proteins (0.60 on 8 MVA alleles; new-protein range `0.31–0.88`) · two-branch bullets · "We did not hide the weak link" callout | Is BubR1 **unstable (55%)** or **inactive (45%)**? The stability score works on 18,825 measured buried variants in 11 proteins (AUROC 0.76), but it cannot say which branch this protein is on (new-protein range 0.31–0.88), so 55/45 stays and the blot decides. |
| **Slide 3** | `0:46 – 1:10` | **How we refused to fool ourselves** | `s2-upset` (4-generator convergence) · KPIs: 21 pre-registered, 8 refuted, p = 0.263, R1 = 0.33 · naive-pipeline vs executed-test table (DO-NOT / FUTILE / CONFOUNDED / CALIBRATED) | The refutations are the product. Convergence on dasatinib is at chance, readthrough is futile, and the naive shortcuts fail. |
| **Slide 4** | `1:10 – 1:34` | **What survived, and how we weighed it** | Full-width `s4-r5-calibration` (Panel A: R4 vs R5 utilities; Panel B: 20-step w<sub>R2</sub> sweep, flip points 0.2743 / 0.6857) · evidence-hierarchy flow: in vivo rescue → senolytic clearance → cell-line proteomics | With the one-replicate screen weighted at w<sub>R2</sub> = 0.25, the in-vivo `Bub1b` rescues lead again: NMN overall, dasatinib among approved drugs. |
| **Slide 5** | `1:34 – 2:04` | **Test once before you treat** | `s5-decision-tree` (R4 tree) · KPIs: EVPI 0.1800, 100% on `missense_class` / 0% readthrough, 69.1% of EVPI · **next-experiment flow:** CHX-chase blot protocol → Branch A (P = 0.874) / Branch B (P = 0.823) / tumour adjunct · "first measurement in the child's own cells" callout | One cycloheximide-chase blot in weeks 1–2 captures 69.1% of the decision value, and its result selects a branch that was specified in advance. |
| **Slide 6** | `2:04 – 2:26` | **First, do no harm** | `s6-pharmcat-coverage` (20 / 1,223 PharmCAT positions callable) · KPIs: 33/34, vincristine, 1.6%, 5 genes · DO-NOT / MONITOR / GATE list | The checkpoint-inhibitor class is hard-excluded. Vincristine gets a monitoring alert. We order the panel rather than assume reference. |
| **Slide 7** *(new)* | `2:26 – 2:58` | **One machine behind every number** | **Interactive architecture**, five lanes (Sources → Compute → Storage → API → Experience) with 9 clickable boxes: patient WGS delivery, 13 public databases, laptop CPU, Modal GPU, MinIO, PostgreSQL 18.4, provenance manifests, `mva-viz-api`, React dashboard · three **Trace** buttons (a request, a figure, the patient data) · KPIs: 84.99 GB in MinIO (12/12 hash-verified), 87 API operations with one `{data, cached_at, source}` envelope, < 15 s to re-run the whole synthesis on a laptop CPU | One storage layer, one API envelope and one dashboard, so any number can be followed back to where it came from. |
| **Slide 8** *(new)* | `2:58 – 3:26` | **Every claim walks back to its bytes** | **Interactive lineage**: three clickable chains, each lighting source → script@commit → artifact (SHA-256) → ledger → claim. The chains are EVSI 69.1%, ΔΔG +1.55 and 33/34 Do-Not · fragment: **"Or ask the API yourself"**, three real endpoints with sample envelopes · KPIs: 150 manifests, 3,656 Python tests (+483 app), 11 CI gates including the patient-coordinate gate | Nothing has to be taken on trust: each number names its table, its script and commit, and the hashes of its inputs. |
| **Slide 9** | `3:26 – 3:44` | **A second disease, with the cost measured** | `s7-case-card-transfer` (Iteration-5 routes R1–R3 moved to Bloom: lines written vs the 378-line Iteration-4 driver; positive-control and byte-identity grid) · KPIs: 53 min · $0, `Blm` top 1.15%, Jaccard 0.095 · H096 and Bloom re-test callouts | Bloom syndrome ran end to end on the same machine. The zero-edit claim was refuted and the fix measured: R1 and R2 pass their control on Bloom, R3 fails, and MVA stays byte-identical. |
| **Slide 10** | `3:44 – 4:00` | **What we are asking for** | Ask flow: Day 1 (5-gene PGx panel + vincristine / `RYR1` alerts) → Week 1–2 (CHX-chase blot) → branch · openness callout · "Stated plainly" disclaimer | Order the panel, chart the alerts, run the blot. Then choose the medicine with the evidence in hand. |

**Why the engineering segment sits at 2:26.** By then the audience has heard every science number. The segment then shows the machine that makes those numbers checkable: storage, compute, the API envelope, the dashboard, and three of those numbers traced back to their hashed sources. The Bloom slide that follows becomes the proof that the same machine takes a second disease. Slides 7–8 can be cut without touching any other line (see the 3-minute cut above).

Figures used: 7 of the 12 research figures, one per science slide. Slides 7, 8 and 10 have none; slides 7–8 are interactive diagrams instead. Four figures were dropped to keep the rest legible: `r1-dosage`, `r2-hits`, `r3-mva-exposures` and `step11-t1-stages`. The numbers they carried are still on the slides or in the notes. A fifth, the `r6-pitch-overview` infographic, is too dense to read at slide scale.

**What slides 7–8 deliberately do not claim.** Track 2's drug tables are committed files with SHA-256 manifests, not Postgres tables. PostgreSQL holds their lineage edges and the Track 1 warehouse, and MinIO holds the Track 1 patient delivery and read store. The password-gated Vercel hosting path is built and tested but **not deployed**, so no live URL is shown. The setup is research infrastructure on one VPS, not production. Its table and ledger counts date from September 2026 and were not re-counted live for this deck.

---

This document provides **two complete 4-minute scripts**, synchronized to the same 10 slides and the same `[click]` cues:
1. **[Version A — Technical Cut](#version-a--technical-cut)**, for computational-biology, clinical-pharmacology and engineering judges. This text is the deck's **Tech** teleprompter.
2. **[Version B — Plain-English Cut](#version-b--plain-english-cut)**, for patient advocates, families and general reviewers. This text is the deck's **Plain** teleprompter.

`[click]` marks where to press `→` mid-sentence. With **`A`** (auto-advance), the fragments fall at about ⅓ and ⅔ of each slide's window (on slides 4 and 8, at the halfway point), so pace the words to land near those marks. `[tap: …]` marks a mouse click on an interactive element of slides 7–8. It never advances the slide, and auto-advance does not perform it.

---

## Version A — Technical Cut

### `[🎬 START ON SLIDE 1 — 0:00]` One child, one lever left
- **On screen (`Slide 1 / 10`):** Copy #1 vs Copy #2 compare panel and the Rank 1 / 8 HPO KPIs. Click 1 reveals the mouse-twin figure. Click 2 reveals the seatbelt-inspector callout.
- **Stage direction:** open calmly, on the child, not on the data.
- **Spoken narration (`0:00 – 0:22`, 53 words):**
  > "This child is a **BUB1B** compound heterozygote, confirmed at Rank 1: one `stop_gained` allele lost to nonsense-mediated decay, one pseudokinase missense in trans. Biallelic nulls are lethal, so the missense copy carries all remaining function. **[click]** Independently, the child's 8 clinical terms select the `Bub1b` hypomorph mouse in the top 1% of 76,699 genotypes. **[click]**"

### `[👉 SLIDE 2 — 0:22]` One unknown decides the treatment
- **On screen (`Slide 2 / 10`):** ThermoMPNN atlas and the ΔΔG KPI. Click 1 reveals the 55% / 45% KPIs and the two branches. Click 2 reveals AUROC 0.76 across 11 DMS proteins (0.60 on 8 alleles, new-protein range 0.31–0.88) and the "We did not hide the weak link" callout.
- **Stage direction:** point left at the atlas and the child's line.
- **Spoken narration (`0:22 – 0:46`, 57 words):**
  > "The missense costs plus 1.55 kilocalories per mole: the 87.3rd percentile of all 19,950 substitutions. **[click]** So is mutant BubR1 unstable, 55%, or folded but inactive, 45%? One answer says keep the protein; the other, clear the damage. **[click]** Across 11 measured proteins the score works, AUROC 0.76, but a new protein ranges 31 to 88%, so 55/45 stands."

### `[👉 SLIDE 3 — 0:46]` How we refused to fool ourselves
- **On screen (`Slide 3 / 10`):** 21 / 8 KPIs. Click 1 reveals the UpSet figure plus p = 0.263 and 0.33. Click 2 reveals the naive-pipeline table.
- **Stage direction:** say the 21 / 8 numbers slowly, and linger on the DO-NOT row.
- **Spoken narration (`0:46 – 1:10`, 55 words):**
  > "We pre-registered 21 hypotheses; 8 came back refuted, and we show them. **[click]** Four generators overlapped on one drug, dasatinib: exactly what a 10,000-draw null predicts, p = 0.263. Readthrough context scored 0.33. **[click]** And the obvious shortcuts fail our executed tests: checkpoint inhibitors are worse in aneuploid cells, and LINCS reversal is confounded by generic arrest."

### `[👉 SLIDE 4 — 1:10]` What survived, and how we weighed it
- **On screen (`Slide 4 / 10`):** full-width calibration figure. Click 1 reveals the evidence-hierarchy flow.
- **Stage direction:** point at Panel A, where the violet proteomic bars shrink under calibration, then at Panel B's two flip lines. Say "discounted" as the violet step appears.
- **Spoken narration (`1:10 – 1:34`, 56 words):**
  > "A scan of 875 compounds found two oral approved drugs raising BubR1 by about 15%, but from one replicate whose own positive control failed. So we swept that route's weight over 20 steps and solved its two exact flip points; we calibrate at 0.25. **[click]** The in-vivo `Bub1b` rescues lead again: NMN overall, dasatinib among approved drugs."

### `[👉 SLIDE 5 — 1:34]` Test once before you treat
- **On screen (`Slide 5 / 10`):** decision tree, EVPI 0.1800, and 100% `missense_class` / 0% readthrough. Click 1 reveals the blot protocol, the branches and 69.1% of EVPI. Click 2 reveals the "first measurement in the child's own cells" callout.
- **Stage direction:** point at the tree's single node, then hold one beat on the callout.
- **Spoken narration (`1:34 – 2:04`, 74 words):**
  > "Value of information picks the next step. EVPI is 0.18 at every weight: all on the missense class, none on readthrough. **[click]** So step one is a cycloheximide-chase BubR1 blot: zero to eight hours, with and without MG132, patient versus parental cells, weeks one to two. It captures 69.1% of EVPI. Rapid decay means unstable at 0.87: NAD-plus precursors. Normal abundance means inactive at 0.82: dasatinib. **[click]** It is our first measurement in the child's cells."

### `[👉 SLIDE 6 — 2:04]` First, do no harm
- **On screen (`Slide 6 / 10`):** callability figure and the 33 / 34 KPI. Click 1 reveals vincristine and the DO-NOT / MONITOR / GATE list. Click 2 reveals 1.6% and the 5-gene panel.
- **Stage direction:** stress "monitoring alert, not a discontinuation order", and point left at the figure on "1.6%".
- **Spoken narration (`2:04 – 2:26`, 50 words):**
  > "Safety is audited per child. Across 919 cancer lines, 33 of 34 Mps1 and Aurora inhibitors work worse in aneuploid cells: hard-excluded. **[click]** Vincristine alone is flagged by both the child's genome and symptom-matched drug labels. **[click]** And the file calls only 1.6% of pharmacogenomic positions, so we order a five-gene panel."

### `[👉 SLIDE 7 — 2:26]` One machine behind every number *(engineering; skip in the 3-minute cut)*
- **On screen (`Slide 7 / 10`):** the full five-lane architecture and three KPIs (84.99 GB, 87, < 15 s). There are no fragments. Everything else on this slide is a tap.
- **Stage direction:** sweep left to right across the lanes on the first sentence. Tap boxes as they are named. The fact panel opens without moving the slide.
- **Spoken narration (`2:26 – 2:58`, 68 words):**
  > "Every number you just heard comes out of one machine. The child's 85-gigabyte genome sits in a versioned MinIO bucket, **[tap: MinIO]** hash-checked against the publisher, and DuckDB queries it in place. Postgres holds the warehouse and an append-only lineage ledger. **[tap: PostgreSQL]** Track 2 runs on a laptop, with GPU models on demand on Modal; the whole synthesis re-runs in under fifteen seconds. One FastAPI service, 87 routes, one envelope: data, cached-at, source. **[tap: Trace a request]** The dashboard renders it."
- **If time allows:** **`[tap: Trace a figure]`** previews slide 8's ΔΔG chain. Skip it when running long.

### `[👉 SLIDE 8 — 2:58]` Every claim walks back to its bytes *(engineering; skip in the 3-minute cut)*
- **On screen (`Slide 8 / 10`):** three lineage chains and three KPIs (150 manifests, 3,656 tests, 11 gates). Click 1 reveals "Or ask the API yourself" with three real endpoints.
- **Stage direction:** tap each chain as you name it, and let it light from source to claim before speaking the next one.
- **Spoken narration (`2:58 – 3:26`, 67 words):**
  > "Every claim walks back to bytes. **[tap: EVSI = 69.1% of EVPI]** EVSI 69.1% is one row of the route-weight sweep, built by the synthesis script at commit fb9c708 from eighteen hashed inputs. **[tap: ΔΔG +1.55]** The ΔΔG goes back to an AlphaFold model, a T4 scan, the atlas parquet and five lineage edges. 150 manifests like these, 3,656 tests, and a gate that fails the build if a patient coordinate leaks. **[click]** Anyone can query it."

### `[👉 SLIDE 9 — 3:26]` A second disease, with the cost measured
- **On screen (`Slide 9 / 10`):** Bloom KPIs and the case-card transfer figure. Click 1 reveals the H096 callout. Click 2 reveals the "Re-tested on Bloom" callout.
- **Stage direction:** keep the pace brisk. Point at the red 378-line bar, then at the pass / fail grid.
- **Spoken narration (`3:26 – 3:44`, 44 words):**
  > "Does it scale? The whole chain ran on Bloom syndrome: 53 minutes, zero dollars, Blm twin top 1.15%, Jaccard 0.095, cisplatin flagged. **[click]** Our zero-edit claim failed, so we parameterised the later modules. **[click]** On Bloom, two of three routes passed their control; MVA stayed byte-identical."

### `[👉 SLIDE 10 — 3:44]` What we are asking for
- **On screen (`Slide 10 / 10`):** the Day 1 → Week 1–2 → branch flow. Click 1 reveals the openness callout. Click 2 reveals the disclaimer.
- **Stage direction:** walk the three steps left to right. Do not rush the thank you.
- **Spoken narration (`3:44 – 4:00`, 39 words):**
  > "So the ask. Day one: order the five-gene panel; chart both alerts. Weeks one to two: run the chase blot in the child's cells; its result picks the branch. **[click]** Everything is open. **[click]** These are hypotheses, not prescriptions. Thank you."

---

## Version B — Plain-English Cut

### Plain-English Analogy Cheat-Sheet (How We Explain the Science)

| Scientific Concept | Plain-English Meaning & Analogy Used in Script |
| :--- | :--- |
| **`BUB1B` gene / BubR1 protein** (spindle assembly checkpoint) | **The cell's "seatbelt inspector".** Before a cell divides, BubR1 checks that every chromosome is buckled in, so neither daughter cell ends up with the wrong number. |
| **Compound heterozygote (`stop_gained` + `missense_variant`)** | **Two broken copies of the instructions, one from each parent.** Copy one has a stop sign halfway through, so the cell shreds it. Copy two has a one-letter typo but still builds the inspector. |
| **`unstable` vs `inactive` missense** | **The one big question.** Does the typo make the inspector crumple and get thrown away (55%), or hold its shape but not do its job (45%)? |
| **Route weight `w_R2` (calibration)** | **A trust dial.** One petri-dish experiment is turned down so that it cannot outvote a whole-animal rescue. |
| **Cycloheximide-chase Western blot (EVSI = 69.1% of EVPI)** | **"Test once before you treat."** Stop the child's cells making new protein and watch how fast the inspector disappears. This one result removes most of the guesswork before anyone picks a medicine. |
| **MinIO object store / PostgreSQL warehouse** | **A locked filing room and a card index.** The raw genome sits in the filing room, checked byte by byte. The index holds the tables and a ledger of where each one came from. |
| **SHA-256 provenance manifest / lineage chain** | **A receipt with a fingerprint.** Every table carries a receipt naming the script that made it and a fingerprint of every file it used. Change one byte and the fingerprint no longer matches. |

### `[🎬 START ON SLIDE 1 — 0:00]` One child, one lever left
- **Spoken narration (`0:00 – 0:22`, 55 words):**
  > "BubR1 is the cell's seatbelt inspector: before a cell divides, it checks every chromosome is buckled in. This child inherited two broken copies of its gene. Copy one is shredded by the cell, so everything rests on copy two, which has a one-letter typo. **[click]** The child's symptoms match a mouse with far too little inspector. **[click]**"

### `[👉 SLIDE 2 — 0:22]` One unknown decides the treatment
- **Spoken narration (`0:22 – 0:46`, 59 words):**
  > "Which medicine depends on copy two. Our folding atlas of every possible typo puts the child's among the more damaging. **[click]** Does it make the inspector crumple and get thrown away, or hold its shape but not work? Different answers, different medicines. **[click]** Eight published cases could not settle it, and eleven external protein scans still leave protein-to-protein spread, so we keep fifty-five, forty-five."

### `[👉 SLIDE 3 — 0:46]` How we refused to fool ourselves
- **Spoken narration (`0:46 – 1:10`, 56 words):**
  > "Then we tried hard to prove ourselves wrong. We wrote down twenty-one predictions before testing them; eight came back wrong. **[click]** Even our hoped-for agreement between four search methods proved no better than chance. **[click]** And the obvious shortcuts? Blocking cell division makes things worse in cells like the child's; skipping the stop sign adds too little protein."

### `[👉 SLIDE 4 — 1:10]` What survived, and how we weighed it
- **Spoken narration (`1:10 – 1:34`, 58 words):**
  > "What survived? Two ordinary pills raised the inspector protein by about 15% in human cells, but from a single experiment. So we turned how much to trust it into a dial, tested every setting, and set it low. **[click]** Back on top: vitamin B3-type boosters that doubled lifespan in the matching mouse, and a drug that clears worn-out cells."

### `[👉 SLIDE 5 — 1:34]` Test once before you treat
- **Spoken narration (`1:34 – 2:04`, 75 words):**
  > "So instead of a ranked list, we hand doctors a rule. All the uncertainty comes down to that one question. **[click]** One standard lab test answers most of it: stop the child's cells making new protein, and watch how fast the inspector disappears, within the first two weeks. If it melts away, the stabilising route. If it holds steady, the cleanup route. **[click]** And it is the first test in the child's own cells, not a mouse's."

### `[👉 SLIDE 6 — 2:04]` First, do no harm
- **Spoken narration (`2:04 – 2:26`, 56 words):**
  > "For a fragile child, what not to give matters as much. Blocking cell division is wrong here: thirty-three of thirty-four such drugs do worse in cells like the child's. **[click]** One routine chemotherapy is flagged by both the child's DNA and muscle weakness. **[click]** And the child's DNA file barely covers drug-handling genes, so we order a test."

### `[👉 SLIDE 7 — 2:26]` One machine behind every number *(skip in the 3-minute cut)*
- **Spoken narration (`2:26 – 2:58`, 70 words):**
  > "How do you know any of this is real? Behind every number sits one machine. **[tap: MinIO]** The child's genome lives in a locked storage bucket, checked byte by byte. **[tap: PostgreSQL]** A database keeps the tables, plus a ledger of where each one came from. Almost everything runs on a laptop, with rented graphics cards only when a protein model needs them. **[tap: Trace a request]** Every answer the website receives says where it came from, and the dashboard shows that."

### `[👉 SLIDE 8 — 2:58]` Every claim walks back to its bytes *(skip in the 3-minute cut)*
- **Spoken narration (`2:58 – 3:26`, 66 words):**
  > "And you can check us. Pick any claim on these slides and follow it back. **[tap: EVSI = 69.1% of EVPI]** The sixty-nine percent is one row of one table, made by one saved script from eighteen fingerprinted files. **[tap: ΔΔG +1.55]** The folding score traces to a public protein model and a short graphics-card run. **[click]** That makes a hundred and fifty receipts and thousands of automatic tests, with a guard against patient data leaking."

### `[👉 SLIDE 9 — 3:26]` A second disease, with the cost measured
- **Spoken narration (`3:26 – 3:44`, 44 words):**
  > "It is not a one-off. On another disorder, Bloom syndrome, it ran in under an hour on a laptop, for nothing. **[click]** Our no-code-change claim was wrong, so we rebuilt for it. **[click]** Now two of three newer parts pass their check on the new disease."

### `[👉 SLIDE 10 — 3:44]` What we are asking for
- **Spoken narration (`3:44 – 4:00`, 38 words):**
  > "Here is the ask. Order the five-gene safety test; put both warnings in the chart. Run the one lab test and let it choose the branch. **[click]** Everything is open. **[click]** These are ideas to test, not prescriptions. Thank you."

---

## Recording Checklist

1. **Choose the cut.** For the full **4:00**, record all 10 slides with **`A`** or by hand. For the **3:00** video, skip slides 7–8: at the end of slide 6, press **`O`** and click slide 9, then advance by hand. Auto-advance runs on the 4:00 grid. Targets for the 3:00 cut: slide 9 at `2:26`, slide 10 at `2:44`, end at `3:00`.
2. **Open the Recording preset.** Load `pitch-slides.html?preset=recording`, or press **`V`** and choose **Recording**. This hides timing, teleprompter, toolbar, progress bar and timer on the audience screen.
3. **Put the presenter on the second screen.** Press **`P`**, drag the presenter window to the other display, and press **`N`** to pick Tech or Plain notes. Record only the audience window, in fullscreen (**`F`**). Do the slide 7–8 taps in the **audience** window. The presenter preview is a static copy.
4. **Do one timed dry run.** Press **`S`** at 0:00 and read the chosen version against the presenter timer. Each slide should land within ±2 s of its cue above. On slides 7–8, rehearse the taps. Each tap must land on its word without stalling the sentence.
5. **Check before recording.** Every figure is legible (press **`Z`** on any figure to inspect it). Nothing is clipped at the recording resolution. The slide 7 fact panel and the slide 8 chains are readable at that resolution.
6. **Export the PDF.** Press the toolbar **print** button and save as PDF to make the static companion deck. It has one slide per page with all fragments revealed, and slides 7–8 print in their default state.
