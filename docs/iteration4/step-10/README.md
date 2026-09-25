# Step 10 — Track 2: iteration 4's own answer

**Standing:** **opened 2026-09-25**; claims H093–H095 filed before any run; entries 154 and
155 reserved. Iteration 4, `step-10`, track 2. Marked **open** in
`src/mva/science/step_maps/iteration4.py`. Every number this page will quote is owned by an
entry under [`methodology/`](methodology/).

**Goal** (from `steps.py`):

> From iteration 4's evidence alone, which approved drugs do its independent generators (the
> PrimeKG walk, the phenotype twin, a screen-wide PRISM sweep, LINCS signature reversal)
> converge on beyond chance, and which of those survive every iteration-4 check (mechanism
> direction, the child's own safety, a decoy)?

**Feeds:** [`submissions/track2/iteration-4/`](../../../submissions/track2/iteration-4/README.md),
the Track 2 submission built from iteration 4 only (user decision, 2026-09-25).

## Why this step exists

Steps 7 and 9 made iteration 4's instruments. But E4 (entry 151) and E5+E6 (entry 152) tested
drugs taken from **iteration 2's shortlist** (`ressources/track2/shortlist.tsv`). A submission
built from iteration 4 alone cannot borrow that list. This step:

1. **generates** candidates from four iteration-4 sources that share no data;
2. **tests** whether they agree more often than chance (a permutation null);
3. **re-runs** iteration 4's checks on the new set: direction, the child's own safety, decoys.

E7 in step 9 ("grade D5 on the ladder") is answered here. The ladder was iteration 2's; the
grading is now convergence plus checks.

## Inputs — both sources

| source | what it gives this step | owner |
|---|---|---|
| the genome | the confirmed pair: one `stop_gained` (nonsense: the protein is cut short) and one missense allele in `BUB1B` (oracle reply, entry 083) | Track 1 |
| the genome | mechanism class: the missense scored as damaging by three zoo models (entry 129) and as destabilising (87th percentile ΔΔG, entry 149) | steps 5, 9 |
| the clinical terms | the 8 HPO terms: phenotype twin (entry 150), safety against the child's own phenotypes (entry 152) | `Challenge_Clinical_Phenotype_1.md` |
| public data | PrimeKG, MGI, PRISM/DepMap, LINCS L1000, OnSIDES, FAERS, CPIC | each entry's Inputs |

## The chain

```mermaid
flowchart LR
  V["confirmed BUB1B pair<br/>+ 8 HPO terms"]:::raw
  V --> G1["G1 PrimeKG walk<br/>(entry 142)"]:::machine
  V --> G2["G2 phenotype twin<br/>(entry 150)"]:::machine
  V --> G3["G3 PRISM sweep<br/>(entry 154)"]:::machine
  V --> G4["G4 LINCS reversal<br/>(entry 153)"]:::machine
  G1 --> C{"convergence<br/>≥ 2 generators<br/>vs permutation null"}:::decision
  G2 --> C
  G3 --> C
  G4 --> C
  C --> K1["direction check<br/>do-not classes"]:::machine
  C --> K2["child's safety<br/>genome + phenotypes"]:::machine
  C --> K3["PRISM contrary<br/>direction"]:::machine
  K1 --> S["survivors<br/>(entry 155)"]:::good
  K2 --> S
  K3 --> S
  classDef raw fill:#e9d5ff,stroke:#7e22ce
  classDef machine fill:#dbeafe,stroke:#1d4ed8
  classDef decision fill:#fef9c3,stroke:#a16207
  classDef good fill:#dcfce7,stroke:#15803d
```

> **Legend** purple = the raw inputs (genome and clinical terms) · blue = machinery, one
> independent source or one check each · yellow = the decision point (convergence against a
> null) · green = the answer: the drugs that survive every check.

## The generator rules — fixed 2026-09-25, before any join

A generator is a source that **proposes** drugs. A check only **filters** them. A check never
votes for a drug it could have generated.

| id | generator | the rule that makes its list | approved means | its universe (for the null) |
|---|---|---|---|---|
| G1 `walk` | PrimeKG walk from the MVA disease node (entry 142) | top **50** openFDA-labelled drugs by walk score | an openFDA label | every openFDA-labelled drug the walk reached |
| G2 `twin` | the phenotype twin's published interventions (entry 150) | every approved analogue in `model_interventions.tsv` whose row **supports** a direction | the row's `analogue_status` says approved | the approved drugs named by any row, plus every approved drug in the other three universes (the twin's space is literature, so it has no natural universe; the widest one is used, which makes the null harder to beat) |
| G3 `prism` | screen-wide PRISM sweep (entry 154) | union of the top **0.5 %** of eligible Launched compounds on each contrast (aneuploidy, rhabdomyosarcoma) | PRISM `Launched` | every eligible Launched compound |
| G4 `lincs` | signature reversal (entry 153) | approved drugs in the top **100** reversers of **both** SigCom LINCS and iLINCS | ChEMBL max phase 4 or an openFDA label | every approved compound present in both engines |

**Join key:** one normalised name, `mva.drugs.names.base_name` (salts and formulations folded).
**Null:** 10,000 draws; each list replaced by an equal-sized draw from its own universe; the
statistic is the number of drugs named by ≥ 2 generators; one-sided p (H094).
**Retrospective note:** dasatinib is already known in G2 (entry 150) and near the top of the
aneuploidy contrast (entry 151). Every convergence count is reported with and without it.

## The checks (H095)

| id | check | pass | source |
|---|---|---|---|
| K1 | direction | not a checkpoint-kinase inhibitor (Mps1/TTK, Aurora); spindle poisons carried as a **caution** | entry 151 (measured), E1/E2 mechanism |
| K2 | the child's safety | not flagged by **both** sources: the genome (PharmCAT/CPIC) and the phenotype (OnSIDES/FAERS) | entry 152 method, re-run on this set |
| K3 | contrary screen | PRISM does not measure it pointing against its proposed direction (δ < 0, one-sided p < 0.05 the other way) | entry 154 table |

## The table contract (every generator writes this)

`ressources/track2/it4/generators/<id>.tsv` + `<id>.universe.tsv` + `<id>.provenance.json`.

| column | meaning |
|---|---|
| `generator` | `walk` · `twin` · `prism` · `lincs` |
| `rank` | 1 = best, within the generator |
| `drug` | the join key, `base_name` of the drug |
| `drug_label` | how the source spells it |
| `approved` | `true` / `false`, by the generator's own rule above |
| `approval_evidence` | e.g. `openFDA NDA…`, `PRISM Launched`, `ChEMBL max_phase 4` |
| `score`, `score_name` | the generator's native score and what it is |
| `direction_hint` | the direction the source itself argues (`D3` dosage, `D5` senescence/mTOR, `D4` tumour context, `D2` aneuploidy stress, `none`) |
| `evidence` | one line, coordinate-free |
| `source_ids` | pipe-separated PMIDs, DrugBank, ChEMBL or BRD ids |

The universe file has two columns: `drug`, `approved`.

## Experiments

| id | what | claims | entry | status |
|---|---|---|---|---|
| S1 | screen-wide PRISM sweep (generator G3) | H093 `P4-28` | 154 | planned |
| S2 | convergence, checks, candidate table | H094 `P4-29`, H095 `P4-30` | 155 | planned |

G4 runs in step 9 as E3 (entry 153, H092 `P4-27`) and hands its list here.

## Data handling

No patient data leaves the laptop in this step except the PharmCAT result already produced by
entry 152. Nothing patient-derived is committed. No genomic position appears in any file.
