# 078 — The Track 2 data layer: from the mechanism card to a first public-API snapshot

**Step:** step-8   **Hypotheses tested:** H011 (pre-registered 2026-09-06, before the run); H010 (one evidence row, stays `proposed`)
**Written:** 2026-09-06, from the runs quoted below. Nothing ranked, nothing argued: this entry
builds the instrument and records what it returned.

## Question

Track 2 asks which market-approved drugs act on the mechanism Track 1 found. Before any drug
is argued, three things had to exist: a **hand-off** from Track 1 that names the mechanism
without a coordinate; a **case-agnostic** way to turn that into a target set and a candidate
table from public sources; and a first **snapshot** with provenance, so every later claim
cites a row that can be regenerated.

## Hypothesis and prediction — written before the run

**H011:** no market-approved drug acts directly on BubR1; approved candidates will come only
from pathway neighbours and from the stress / proteostasis / tumour-context directions.
Predicted: Open Targets, ChEMBL and DGIdb return zero molecules with an approved status for
BUB1B; approved molecules appear only for other targets in the expanded set.

**H010** (mechanism class — hypomorphic loss of function, no gain-of-function component) is
filed alongside; this run tests only its pathway clause (Reactome places BUB1B in the spindle
assembly checkpoint). Its loss-of-function clause needs ClinVar/OMIM and the literature —
a later entry.

## What would refute it

H011: any molecule with ChEMBL `max_phase` 4 or an FDA label whose recorded mechanism of
action names BUB1B/BubR1. H010's pathway clause: Reactome mapping BUB1B to no
checkpoint/kinetochore/mitotic pathway.

## Method

| Piece | What it does | Where |
|---|---|---|
| **Mechanism card** | the Track 1 → Track 2 hand-off: gene, protein, allele classes (never positions), mechanism class, pathway, downstream consequences, tumour context, four repurposing directions with seed targets, source constraints. Version 1 written from H003–H009; version 2 corrects the MONDO id after the first run resolved the disease by name | [`ressources/track2/mechanism.json`](../../../../ressources/track2/mechanism.json), prose twin [`mechanism.md`](../mechanism.md) |
| **Pathway expansion** | Reactome pathways containing the card gene's UniProt accession; keep those whose name matches `checkpoint\|kinetochore\|mitotic` (a stated, case-agnostic rule); their human gene participants join the seed targets as `pathway` members | `mva.drugs.pathway`, `sources/reactome.py` |
| **Candidates** | for every target: Open Targets `drugAndClinicalCandidates`, ChEMBL target → mechanism → molecule (`max_phase`), DGIdb interactions; dedup on (drug, target); `approved` = ChEMBL phase 4 or Open Targets `APPROVAL` or DGIdb approved; openFDA label lookup for every approved name | `mva.drugs.candidates`, `sources/{opentargets,chembl,dgidb,openfda}.py` |
| **Trials, literature** | ClinicalTrials.gov v2 for the disease and for each approved drug × the tumour context; PubMed E-utilities for the gene, the pathway and each direction | `sources/{clinicaltrials,pubmed}.py` |
| **Snapshot + provenance** | five TSVs and `snapshot.json`, one manifest per table (inputs with retrieval time and body digest, outputs with row count and sha256, code version); every HTTP reply cached under gitignored `build/track2-cache/`, so a re-run is reproducible with zero live calls | `mva.drugs.snapshot`, `mva.drugs.provenance` |
| **Tests** | 122, no network: 14 trimmed real replies plus an invented second card (`GENEA`), so the code cannot pass by knowing the real case | `tests/test_drugs_*.py`, `tests/fixtures/track2/` |

Sources not used: **DrugBank** (licence required for programmatic access) — stated in the card.

## Commands

```bash
uv run mva-science hypothesis-add --step step-8 ...   # H010, H011 (before the run)
uv run mva-drugs snapshot                              # live: 2026-09-05T23:01–23:11 UTC
uv run mva-drugs snapshot                              # again: 0 live calls, identical rows
uv run mva-science evidence-add --hypothesis H011 ...  # row 30
uv run mva-science evidence-add --hypothesis H010 ...  # row 31
uv run mva-science verdict H011 --commit --status supported --reasoning '...'
tools/check-python.sh
```

## Observed

```
targets    {'seed': 27, 'pathway': 246, 'total': 273}
pathways   {'walked': 10, 'matched': 4, 'pattern': 'checkpoint|kinetochore|mitotic'}
candidates {'total': 3766, 'approved': 1067, 'with_fda_label': 808,
            'by_source': {'chembl': 1659, 'dgidb': 3702, 'opentargets': 1732},
            'distinct_drugs': 1513, 'distinct_approved_drugs': 336}
rows       {'targets': 273, 'drug_candidates': 3766, 'trials': 747, 'literature': 157, 'pathways': 10}
requests   chembl 736 | clinicaltrials 337 | dgidb 1 | openfda 336 | opentargets 545 | pubmed 17 | reactome 5
openfda    251/336 approved drug names have a current US label
trials     cond="Mosaic variegated aneuploidy syndrome 1" → 0 studies; 94 of 336 approved drugs have ≥ 1 rhabdomyosarcoma trial
```

Reactome pathways matched for BUB1B (O60566): R-HSA-141444 *Amplification of signal from
unattached kinetochores via a MAD2 inhibitory signal* (92 participants), R-HSA-176409
*APC/C:Cdc20 mediated degradation of mitotic proteins* (63), R-HSA-68877 *Mitotic
Prometaphase* (200), R-HSA-9648025 *EML4 and NUDC in mitotic spindle formation* (115).

**H011's prediction held:** BUB1B has **zero** candidate rows in all three sources, at any
phase. The 336 distinct approved drugs attach elsewhere. Approved drugs per seed target
(distinct names): TP53 155, MTOR 41, HSP90AA1 29, PLK1, PRKAA1/2 (metformin, phenformin,
acadesine), HDAC1–3 (belinostat, panobinostat, romidepsin, valproic acid, 4-phenylbutyrate),
AURKB 9 (kinase inhibitors, off-target listings), CDK4/6 (palbociclib, ribociclib,
abemaciclib), MAD1L1 (carboplatin, paclitaxel protein-bound). Among pathway members the
tubulin genes dominate (TUBB/TUBA*: ~30 approved drugs each — the taxanes and vinca
alkaloids). Rhabdomyosarcoma trials: vincristine 47, doxorubicin 45, ifosfamide 39,
irinotecan 35 — the standard-of-care backbone, as expected.

**What the run corrected in the tooling** (all live-verified): Open Targets renamed
`knownDrugs` → `drugAndClinicalCandidates` and phases to `maxClinicalStage` strings; ChEMBL
serves `max_phase` as `"4.0"`; Reactome's UniProt lookup is `/data/mapping/UniProt/{acc}/pathways`;
DGIdb concept ids arrive as `chembl:CHEMBLnnn` and an upper-case-before-strip bug left
261 of 759 ChEMBL ids unresolved on the first pass (fixed, regression test, 747/747 after);
the card's MONDO id was wrong (`MONDO:0009551` → `MONDO_0009759` in Open Targets; card
version 2). PubMed returned 0 hits for directions D2 and D4 because a long descriptive name
becomes a long AND-chain — recorded as 0, not swapped for a looser query.

## Evidence recorded

```
evidence 30  H011 supports 0.7  measurement  methodology/078 — zero BUB1B molecules at any phase in three sources; 336 approved drugs attach to other targets (273 targets: 27 seed, 246 pathway)
evidence 31  H010 supports 0.3  annotation   methodology/078 — Reactome maps BUB1B to four checkpoint/kinetochore/mitotic pathways; the loss-of-function clause is not tested here
```

## Verdict

**H011 — supported, committed at 0.80** (revision 2): one measurement across three sources;
the heuristic's number is triage, not a posterior; re-weighed on refresh or if DrugBank
becomes available. **H010 stays `proposed`**: only its pathway clause has evidence.

## Limitations, stated

- **Noise.** DGIdb lists weak or historical interactions (TP53 with 155 "approved drugs",
  ascorbic acid and nicotine under CDK4). The table is a *candidate space*, not a ranking;
  every drug still needs a hypothesis with a refutation condition before it is argued.
- **Source concordance is lost by the dedup.** A row keeps one `source`; a drug named by all
  three sources for the same target shows once. Next: keep the source list and use
  concordance as a quality cue (today 0 rows can show ≥ 2 sources, by construction).
- **Pathway members carry no direction id** (716 approved rows with `direction_ids` empty):
  the rule assigns directions to seeds only. A drug reaching the checkpoint through a tubulin
  gene is a D1 candidate in biology but not in the column — to fix in the next entry.
- **Approval is US-centric** (openFDA labels; ChEMBL phase 4 is global). 85 approved names
  have no current US label.
- The **mechanism itself rests on an inferred trans pair** (H009 `testing`); the ranking waits
  for the oracle by design.

## Next test

Rank: a scoring entry that combines source concordance, interaction type, direction fit,
trial evidence in the tumour context and literature support into a transparent score with its
arithmetic printed; each top candidate then filed as H0xx with a refutation condition. Then
the `/api/track2` route and a dashboard page, and the drug × mechanism evidence table for
the report.
