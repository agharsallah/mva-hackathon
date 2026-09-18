# Track 2 report — which approved medicines could act on this child's broken checkpoint?

**Standing:** draft, written 2026-09-18 from executed runs (iteration 2, step 7 — methodology
entries [110](../../../docs/iteration2/step-7/methodology/110-the-card-revised-and-the-claims-filed-before-the-search.md)–[113](../../../docs/iteration2/step-7/methodology/113-the-ladder-the-shortlist-and-the-do-not-table.md)).
Every number is read from a table with a provenance manifest, every claim was registered before
its test, and every cited paper was resolved against PubMed the same day. **Not uploaded.**
Track 2 accepts one submission; this folder will be re-read and re-rendered before it goes.

Written for the panel, in plain words. Each technical term appears once with its meaning in
brackets; the full dictionary is served at `/learn` on the dashboard.

> The challenge's own framing, kept in view throughout: *submissions are hypotheses for
> follow-up, not evidence that a medicine works.* Nothing below is a recommendation to treat.

---

## 1. The answer in one page

**The child.** A boy with mosaic variegated aneuploidy (MVA: in some of his cells, a chromosome
is missing or duplicated, and different cells are wrong in different ways), short stature,
failure to thrive, calcium deposits in the kidneys, and a rhabdomyosarcoma (a muscle-tissue
cancer of childhood). Eight clinical terms were delivered with the case.

**The cause.** Track 1 found, and the challenge's answer key confirmed, two different broken
copies of one gene, `BUB1B` — one from each parent (a *compound heterozygote*). The gene makes
BubR1, the protein that acts as the **brake** on cell division: it holds a dividing cell until
every chromosome is properly attached before the cell is allowed to split. One copy makes no
protein at all (a *stop* change); the other makes a weakened protein (a *missense* change in the
protein's last stretch). The child therefore has **some brake, but less than normal** — which is
exactly the pattern every published MVA case with this gene shows, because having no brake at
all is not survivable.

**The mechanism, in the form the methods form asks for.** *Loss of function*, not gain: less
BubR1, a leakier checkpoint, chromosomes that separate too early, cells with the wrong count,
and — in surviving cells — a chronic stress from carrying the wrong number of copies of many
proteins. Downstream: the aneuploidy that names the disease, the growth problems, and a
predisposition to exactly the cancers this child has.

**Four ways a drug could act, graded on a ladder written before the search.**

| Direction | The idea | What we found | Best rung |
|---|---|---|---|
| **D1** reinforce the brake | make the remaining checkpoint stronger | **no approved drug does this.** Every checkpoint drug on the market or in trials *weakens* it. D1 became the do-not table | — |
| **D2** exploit the stress of aneuploid cells | aneuploid cells are already stressed; some approved drugs tip them over | **chloroquine** (a malaria drug) killed aneuploid cells preferentially in the reference screen; metformin, hydroxychloroquine and bortezomib inherit the result through their drug class | 2 (cell model) |
| **D3** raise the amount of working BubR1 | the weakened copy still works; stabilise it | **niacin / nicotinamide** (vitamin B3 forms): boosting the NAD⁺ pathway raised BubR1 in mice bred to have too little of it; valproic acid and vorinostat act on BubR1's acetylation switch | 3 (animal model) |
| **D4** the child's actual tumour | approved, non-chemotherapy drugs with a mechanism in rhabdomyosarcoma | **statins** (lovastatin, simvastatin, atorvastatin): rhabdomyosarcoma cells depend on making their own cholesterol; lovastatin itself slowed them; simvastatin has already been in a completed paediatric sarcoma trial | 5 (approved, trialled in this tumour, used in children) — carried by rung-2 mechanism evidence |

**The half a clinician may care about most: what not to do.** Thirteen approved drugs are
*spindle poisons* — they work by jamming cell division and relying on the checkpoint to hold
the cell. In a child whose checkpoint is the broken part, that reliance is a hypothesis worth
weighing before treatment. Several of them (vincristine, vinorelbine) are standard
rhabdomyosarcoma chemotherapy. **This report flags the question for the treating team; it does
not advise withholding standard care.**

**What we do not know.** How aneuploid this child's cells actually are (the sequencing data
delivered cannot measure it with any power; the analysis that could is planned and not run).
Whether the weakened BubR1 copy is unstable or simply inactive. And whether any drug on this
page helps — rung 3 is one mouse paper.

---

## 2. Where this comes from — two datasets, one line of evidence

```mermaid
flowchart LR
  G[/"85 GB genomic data<br/>reads + variant calls"/]:::raw --> T1["Track 1, iterations 1–2<br/>the pair found blind and confirmed"]:::machine
  C[/"8 clinical terms<br/>(HPO)"/]:::raw --> T1
  T1 --> CARD["mechanism card v3<br/>gene · alleles · 9 measured facts<br/>4 directions · 2 anti-directions · the ladder"]:::machine
  C --> CARD
  CARD --> SNAP["7 public drug sources<br/>359 approved drugs on 277 targets"]:::machine
  SNAP --> LAD{{"the evidence ladder<br/>329 drugs × directions"}}:::decide
  CUR[/"13 curated results<br/>one PubMed paper each"/]:::raw --> LAD
  DEC["2 decoy genes<br/>same child, wrong gene"]:::machine --> LAD
  LAD --> S["shortlist: 11 argued<br/>+ 50 already in tumour trials"]:::good
  LAD --> N["do-not table: 23"]:::bad
  classDef raw fill:#f3e8ff,stroke:#7e22ce,color:#581c87
  classDef machine fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
  classDef decide fill:#fef9c3,stroke:#ca8a04,color:#713f12
  classDef good fill:#dcfce7,stroke:#15803d,color:#14532d
  classDef bad fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d
```

> **Legend** — **purple = raw inputs** (the child's DNA, the child's clinical terms, and the
> papers a person read); **blue = machinery** (every box is a tool with a manifest); **yellow =
> the decision point** (the ladder); **green = the goal** (the shortlist); **red = what to
> avoid** (the do-not table).

Both datasets are used at every stage: the genomic data fixed the gene and the two alleles;
the clinical terms fixed the disease, the tumour and — through the tumour — the fourth
direction and the paediatric questions. Where a result uses only one, the table says so.

---

## 3. The mechanism (methods form Q14: loss- versus gain-of-function, pathway, consequence)

### 3.1 Loss of function, of a specific shape

| copy | what changed | what it does to the protein | evidence |
|---|---|---|---|
| one | a *stop* change in exon 17 of 23 | the protein ends early, before its last working part — **no functional protein** | catalogued as disease-causing for MVA (ClinVar VCV000533901) |
| the other | a *missense* change in exon 23 of 23 — one amino acid swapped | a **weakened** protein: never seen in 140,000 healthy genomes, predicted damaging by two independent predictors | Track 1 (iteration 1, entries 070–074; iteration 2, entry 099) |

Nine facts measured in iteration 2 sit on the mechanism card so the argument does not rest on
the allele labels alone:

| fact | measured | what it changes for a drug |
|---|---|---|
| the two copies are on **different** chromosomes (*trans*) | **confirmed** by the challenge's answer key (a full match at rank 1) | the whole argument stands on a confirmed genotype, not an inference |
| each copy present **once** in the raw sequencing reads | yes — both alleles at one-copy dosage, read without an aligner | a *null + weakened* genotype: some BubR1 exists to stabilise (D3 is live) |
| no deleted or duplicated stretch in the gene | every exon at two copies; no structural variant in the gene | the two alleles are the whole story |
| where the missense sits in the protein | outside every catalogued domain, in a region the structure model is confident about | we **cannot** say whether the weakened copy is unstable or inactive; D3 is argued as *more BubR1*, not *refold it* |
| how aneuploid this child's cells are | **unmeasured** — the karyotype test iteration 1 ran has no power for mosaic gains; the powered analysis (step 8) has not run | D2 is argued from published aneuploid-cell biology, not from this child's burden |

(Complete list F1–F9, with the entry each comes from: mechanism card v3, and step 7's README.)

### 3.2 The pathway: the spindle assembly checkpoint

BubR1 is a core part of the **spindle assembly checkpoint** (SAC — the wait-until-attached
brake) and of the complex that switches off the machinery that pulls chromosomes apart. Less
BubR1 means a **leaky brake**: division can proceed with chromosomes still unattached.
Published MVA patient cells show strongly reduced BubR1 and a weakened checkpoint
(Suijkerbuijk 2010, PMID 20516114); the founding paper tied biallelic `BUB1B` changes to MVA
with cancer predisposition (Hanks 2004, PMID 15475955). Complete loss is lethal before birth
in mouse and human — which is why "switch BubR1 off" is never a therapeutic direction here.

### 3.3 Downstream consequences, and where a drug could stand

```mermaid
flowchart LR
  A[/"BUB1B: null + weakened copy"/]:::raw --> B["less BubR1 · leaky checkpoint"]:::machine
  B --> C{{"D3 · more working BubR1<br/>NAD⁺ / SIRT2 · acetylation"}}:::decide
  B --> D["chromosomes separate too early"]:::bad
  D --> E["cells with the wrong chromosome count<br/>(burden in this child: unmeasured)"]:::bad
  E --> F{{"D2 · exploit their stress<br/>autophagy · proteasome · AMPK"}}:::decide
  E --> G["rhabdomyosarcoma · growth restriction · kidney calcium"]:::bad
  G --> H{{"D4 · the tumour itself<br/>cholesterol synthesis"}}:::decide
  B -.-> X["D1 · strengthen the brake<br/>no approved drug"]:::bad
  D -.-> Y["spindle poisons need the brake<br/>caution"]:::bad
  classDef raw fill:#f3e8ff,stroke:#7e22ce,color:#581c87
  classDef machine fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
  classDef decide fill:#fef9c3,stroke:#ca8a04,color:#713f12
  classDef bad fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d
```

> **Legend** — **purple** the genotype; **blue** the molecular consequence; **yellow** the three
> places an approved drug could stand, each a direction below; **red** what goes wrong, and the
> two dotted boxes are the direction with no drug and the class to be cautious with.

---

## 4. How the candidates were found and graded

### 4.1 The search: one card, seven public sources, no hand-typed query

The mechanism card (a structured file naming the gene, the two allele classes, the pathway,
the disease, the tumour and four *directions* with seed genes) drives every query. The Reactome
pathway map widens the seed genes into 277 targets; Open Targets, ChEMBL and DGIdb list every
drug known to act on them (3,859 drug–target rows, **359 market-approved drugs**); openFDA
confirms a current US label; ClinicalTrials.gov and PubMed answer the trial and literature
questions. Every table carries a manifest with the retrieval time and a digest of every reply,
and the same command re-runs it for any other case by swapping the card.

### 4.2 The ladder: written before the search

Every approved drug, on every direction it touches, is placed on **the highest rung it passes**:

| rung | meaning | how it is tested |
|---|---|---|
| **5** | approved for a related indication, with paediatric use | approved **and** a registered trial in the child's tumour **and** a paediatric pointer (a label section 8.4, or a registered study admitting children) |
| **4** | clinical trial in a related indication | a registered trial in the child's tumour |
| **3** | animal model of the mechanism | a paper, read by a person, with its PubMed id |
| **2** | cell model of the mechanism | a paper, read by a person, with its PubMed id |
| **1** | mechanism only | the drug acts on a target in the direction's set — *named, never submitted* |

Two rules the ladder prints rather than hides. **Automated and curated tests sit side by side:**
rungs 4–5 are looked up by a program and say "already being tried in this tumour"; rungs 2–3
come from a paper a person read, and the row carries the PubMed id. **Inherited evidence is
marked:** when the paper tested a same-axis compound and not the approved drug (the screen used
AICAR; the approved drug is metformin), the row says `proxy` and names what was tested.

### 4.3 A control the search had to pass: the same child, a different gene

Track 1 tested every ranker against decoy genes; Track 2 does the same. The mechanism card was
copied with the child's clinical side kept and the gene swapped — once for **NTRK3**, drawn by a
seeded rule from Track 1's matched decoy set, once for **XDH**, a metabolic enzyme with nothing
to do with cell division — and the unchanged pipeline ran on both. Whatever came out for the
decoy as readily as for `BUB1B` was nominated by the clinical queries or by database density,
not by the mechanism.

![Overlap of each direction's approved drugs with a decoy gene's](../../../figures/track2/decoy-overlap.png)

> **Legend** — one bar per decoy gene; the dashed yellow line is the pre-registered 0.10
> threshold. **D4 (the tumour direction) is above it** against NTRK3 (Jaccard 0.25): the
> cancer pharmacopoeia comes out for any cancer-adjacent gene. **D1–D3 are below it** against
> both decoys: the mechanism directions are specific to the gene. The consequence, applied:
> D4 is argued only from curated mechanism results, never from "this drug has a
> rhabdomyosarcoma trial".

The control also caught a flaw in the first grading run: a rhabdomyosarcoma trial was lifting
drugs onto rung 5 on *mechanism* directions (85 drugs, tetracycline among them). A trial in the
tumour says nothing about a checkpoint; the rule was narrowed to the tumour direction and the
run repeated before any verdict — the change is recorded with before/after counts in entry 113.

---

## 5. The candidates

![Every drug at rung 2 or higher, on every direction it touches](../../../figures/track2/evidence-ladder.png)

> **Legend** — the number is the rung; **green** a curated result and rung 4–5; **yellow** a
> curated result at rung 2–3; **blue** the automated tests alone (already being tried in the
> tumour — not a finding of this work); **red** set aside (a spindle poison or the standard
> chemotherapy); `*` inherited (proxy) evidence. Drugs with a curated result are listed first.

### 5.1 The eleven drugs with a cited mechanism result

| # | drug (approved for) | direction | rung | the cited result | inherited? | given to children? |
|---|---|---|---|---|---|---|
| 1 | **lovastatin** (cholesterol) | D4 tumour | 5 | lovastatin itself slowed rhabdomyosarcoma cells; the tumour depends on making its own cholesterol and cannot take it up instead (Gizaw 2025, PMID 41249736). A completed phase-1 study gave a statin with chemotherapy to children with relapsed solid tumours including rhabdomyosarcoma (NCT02390843) | no | label section 8.4; studies admitting children |
| 2 | **simvastatin** (cholesterol) | D4 | 5 | same class result; it is the statin in NCT02390843 | yes (lovastatin) | studies admitting children |
| 3 | **nicotinamide** (vitamin B3) | D3 more BubR1 | 3 | the NAD⁺ precursor NMN raised BubR1 in mice, and more SIRT2 (the enzyme that stabilises BubR1) extended the life of BubR1-deficient mice (North 2014, PMID 24825348) | yes (NMN) | studies admitting children |
| 4 | **niacin** (cholesterol; vitamin B3) | D3 | 3 | same result; niacin is the prescription-strength NAD⁺ precursor | yes (NMN) | studies admitting children |
| 5 | **chloroquine** (malaria) | D2 stress | 2 | chloroquine itself preferentially killed cells with an extra chromosome in the reference screen (Tang & Amon 2011, PMID 21315436) | **no** | studies admitting children |
| 6 | **bortezomib** (myeloma) | D2 | 2 | aneuploid human cells depend on degrading proteins faster and are more sensitive to proteasome inhibitors; myeloma patients' aneuploidy tracked their response (Ippolito 2024, PMID 39247952; Chui 2019, PMID 31530568) | yes (the drug class) | label 8.4; studies admitting children |
| 7 | **valproic acid** (epilepsy) | D3 | 2 | HDAC2/3 strip the acetyl mark that protects BubR1 from being degraded (Park 2017, PMID 28985013; Choi 2009, PMID 19407811); an HDAC inhibitor would be expected to slow that loss — inferred, not shown | yes (class mechanism) | label 8.4; studies admitting children |
| 8 | **metformin** (diabetes) | D2 | 2 | the AMPK activator AICAR was aneuploidy-selective in the same screen; metformin is the approved AMPK activator | yes (AICAR) | label 8.4; studies admitting children |
| 9 | **vorinostat** (lymphoma) | D3 | 2 | same class mechanism as valproic acid | yes | label 8.4; studies admitting children |
| 10 | **hydroxychloroquine** (lupus, arthritis) | D2 | 2 | chloroquine's result, inherited by its clinical analogue | yes (chloroquine) | label 8.4; studies admitting children |
| 11 | **atorvastatin** (cholesterol) | D4 | 2 | same class result as lovastatin; carries a paediatric indication on its label | yes (lovastatin) | label 8.4; studies admitting children |

Reading the table honestly: **one** drug has a molecule-level animal result on the checkpoint
itself — none. The deepest mechanistic lead (D3, more BubR1) rests on one mouse paper and is
inherited by two vitamin-B3 forms. The best-supported *tumour* lead (statins) has a completed
paediatric trial behind it and a molecule-level cell result. The only molecule-level
*aneuploidy* result is chloroquine's.

![How 329 approved drugs shrink to the shortlist](../../../figures/track2/rung-funnel.png)

> **Legend** — drugs counted once at their best rung; **green** rung 4–5 and the shortlist,
> **yellow** rungs 2–3, **grey** rung 1 (named, never submitted). Most of the 62 at rung 5 are
> there by the automated test alone: approved, trialled in rhabdomyosarcoma, used in children.

### 5.2 Fifty drugs already being tried in rhabdomyosarcoma — listed, not claimed

Fifty more approved drugs reach rung 5 automatically: they have a registered rhabdomyosarcoma
trial and a paediatric pointer (dexamethasone, azacitidine, methotrexate, bevacizumab, the
CDK4/6 and mTOR inhibitors, the checkpoint antibodies…). They are in `shortlist.tsv` with the
verdict *context trial only – not a mechanism finding*, because the decoy control showed the
same list comes out for a gene that has nothing to do with the checkpoint. They are the tumour's
trial landscape, and a reader deserves to see them; they are not this work's finding.

### 5.3 The do-not table

| verdict | drugs | why |
|---|---|---|
| **caution** — spindle poisons (13) | vincristine, vinorelbine, vinblastine, vinflunine, paclitaxel, docetaxel, cabazitaxel, eribulin, ixabepilone, epothilone D, colchicine, brentuximab vedotin, polatuzumab vedotin | these drugs work by jamming the division machinery and *relying on the checkpoint to hold the cell*; MVA cells have a weakened checkpoint and slip through (Suijkerbuijk 2010, PMID 20516114; Sinha 2019, PMID 30601084). Vincristine and vinorelbine are standard rhabdomyosarcoma chemotherapy: **a hypothesis for the treating team to weigh, never advice to withhold treatment** |
| **do not** — further checkpoint weakening (0 approved) | Mps1/TTK and Aurora inhibitors | aneuploid cancer cells are selectively killed by weakening the checkpoint further (Cohen-Sharir 2021, PMID 33505028) — the same logic makes a child whose checkpoint is constitutionally weak the worst possible candidate. None is approved; every one in the candidate table is phase 3 or earlier |
| **standard of care** (10) | vincristine, dactinomycin, cyclophosphamide, ifosfamide, doxorubicin, etoposide, irinotecan, temozolomide, carboplatin, cisplatin, topotecan | already the treatment for the tumour; giving them is not a repurposing. Named so a reader sees they were considered, not missed |

### 5.4 Has each candidate been given to children?

![Paediatric pointers per shortlisted drug](../../../figures/track2/pediatric-evidence.png)

> **Legend** — **green** a US label with a *Pediatric Use* section (8.4); **blue** at least one
> registered study admitting children, in any indication; empty = neither found. Every argued
> drug has at least one pointer. **A pointer is something to read, never a licence**: a label
> section can say "safety not established", and a study that admits children may have enrolled
> none.

---

## 6. What this report cannot tell you

1. **Whether any of these drugs helps this child.** Rung 3 is one mouse paper; rung 2 is a dish.
   The challenge's words hold: hypotheses for follow-up.
2. **How aneuploid this child is.** The delivered data was tested with a statistic that has no
   power for mosaic gains; the powered analysis is planned (iteration 2, step 8) and has not
   run. Direction D2 inherits this gap entirely.
3. **Whether the weakened BubR1 copy is unstable or inactive.** It sits outside every
   catalogued domain; the structural model is confident about the region but says nothing about
   function. D3 is therefore argued as *more BubR1*, not *repair this BubR1*.
4. **Anything about a drug the public sources never listed** beyond what a person put in the
   curated table. Four of the eleven argued drugs (chloroquine, hydroxychloroquine, niacin,
   nicotinamide) are there only because a person read the paper; their rows say `curated_only`.
5. **The curated rungs are one person's reading of thirteen abstracts on one day.** Every row
   carries its PubMed id so the reading can be checked.
6. **DrugBank was not queried** (it needs a licence for programmatic access); Open Targets,
   ChEMBL, DGIdb, openFDA, Reactome, ClinicalTrials.gov and PubMed were.

---

## 7. Reproducibility

Every step is one command, case-agnostic (swap the card, get another case), with a manifest:

```bash
uv run mva-drugs snapshot                       # card → 5 tables, 7 public APIs, cached replies
uv run python tools/track2_decoys.py ...        # a decoy card and its snapshot (×2)
uv run python tools/track2_enrich.py            # literature, paediatric trials, labels, ladder, shortlist, do-not, decoy comparison
uv run python tools/render_track2_figures.py    # the figures in this report
uv run python tools/record_track2_lineage.py    # 63 lineage edges into the warehouse ledger
```

Runtime on a laptop: the snapshot ~10 minutes cold (mostly polite waiting between requests),
the enrichment ~10 minutes cold, both seconds when cached. Code: the public repository named in
the submission form; every table is under `ressources/track2/`, every entry under
`docs/iteration2/step-7/`. **No patient data appears anywhere in Track 2** — gene symbols, drug
names, trial ids and PubMed ids only; the mechanism card names allele *classes*, never positions.

## 8. Where every claim lives

| claim | register id | verdict · confidence | entry |
|---|---|---|---|
| D1 yields no submittable drug and becomes the do-not table | H045 | supported · 0.80 | 113 |
| D2 holds an approved compound with a molecule-level cell result | H046 | supported · 0.70 | 113 |
| D3 has an approved route on the NAD⁺/SIRT2 axis with animal evidence, by proxy | H047 | supported · 0.60 | 113 |
| D4 holds a non-chemotherapy approved drug at rung ≥ 2 with paediatric data | H048 | supported · 0.80 | 113 |
| the automated stages are non-specific (a direction overlaps a decoy ≥ 0.10) | H049 | supported · 0.85 | 112 |
| every argued drug has a paediatric pointer | H050 | supported · 0.70 | 113 |
| no approved drug acts directly on BubR1 | H011 (iteration 1) | supported · 0.80 | 078 |

Confidence is a transparent triage heuristic printed with its arithmetic, not a calibrated
probability; the register is append-only and shows every revision, including one committed too
early and corrected in the open (entry 113).
