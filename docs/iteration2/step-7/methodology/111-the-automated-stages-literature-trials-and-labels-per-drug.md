# 111 — Three questions asked of every approved drug: the literature, the children, the label

**Written:** 2026-09-18. **Step:** `step-7` (iteration 2). **Hypotheses:** none settled here;
one refuting row for **H047** (the automated stage found no NAD⁺-axis drug). The claims were
filed in [110](110-the-card-revised-and-the-claims-filed-before-the-search.md) before this ran.

## Question

The snapshot ([078](../../../iteration1/step-8/methodology/078-track2-data-layer.md), refreshed
in 110) knows which approved drugs touch which target. It does not know three things a panel
asks first about any candidate: **has anyone written about this drug and this mechanism
together, has it ever been given to children, and does its label discuss children?** This entry
asks all three of every approved drug, automatically, with the questions derived from the card
and never typed.

## Hypothesis and prediction

None of its own. The three tables feed [113](113-the-ladder-the-shortlist-and-the-do-not-table.md),
where the rungs are assigned and H045–H050 are settled. H047's prediction had one clause this
stage tests directly — *the snapshot returns at least one approved NAD⁺ precursor or SIRT2-axis
molecule attached to a D3 target* — and it is answered below.

## What would refute it

Not applicable; see 113 for each claim's refutation condition.

## Inputs

| Source | What was read | Receipt |
|---|---|---|
| derived | `ressources/track2/drug_candidates.tsv` — 3,859 rows, folded to **329** distinct approved drugs by base name (salt and formulation words stripped: `mva.drugs.names`), plus the curated drugs of `evidence.tsv` not in the table | 110 |
| card v3 | gene, protein, pathway head, disease anchor, tumour context — the query vocabulary | `ressources/track2/mechanism.json` |
| PubMed E-utilities | two questions per drug: `"<drug>" AND (BUB1B OR BubR1 OR "spindle assembly checkpoint" OR aneuploidy)` and `"<drug>" AND rhabdomyosarcoma`; esearch count + a head of 10 ids | live 2026-09-18, cached under `build/track2-cache/pubmed/` |
| ClinicalTrials.gov v2 | `query.intr=<drug>` with `aggFilters=ages:child`, first page of 100, any indication; eligibility fields kept | live 2026-09-18, cached |
| openFDA | each drug's label re-read from the cache for `pediatric_use` (section 8.4) | cache from 078 / 110; 0 live |

The clinical dataset enters through the tumour context (rhabdomyosarcoma, HP:0002859 on the
card); the genomic dataset enters through the gene and pathway words. No genomic position
exists in any input or output of this stage.

## Method

`mva.drugs.mechlit` builds the two PubMed questions from the card (`mechanism_term`,
`context_term`) and asks them once per base name; `mva.drugs.pediatric` asks ClinicalTrials.gov
with the registry's own child-age aggregate and trims basket studies to 12 conditions and a
300-character title (one registry record carries a 240,000-character title); `mva.drugs.sources.openfda`
gained the `pediatric_use` field, read from replies already in the cache. `mva.drugs.enrich.run`
orchestrates and writes each table with a manifest naming the API roll-up digests and the tables
read. Rows for a drug the sources never listed (chloroquine, hydroxychloroquine, niacin,
nicotinamide) are asked the same questions, and their approval is what openFDA says, not
assumed.

## Commands

```bash
uv run python tools/track2_enrich.py          # live: PubMed 1,003 replies, ClinicalTrials.gov 329, openFDA 329
uv run python tools/track2_enrich.py --skip-live   # re-grade from the tables (113's re-runs)
```

## Observed

```
card v3 BUB1B: 329 drugs to grade
drug_mechanism_literature.tsv    658 rows   (2 per drug)
pediatric_trials.tsv          11,698 rows   (290 of 329 drugs have >= 1 study admitting children)
labels.json                      329 drugs  (258 with a US label; 208 with a section 8.4)
```

Per-drug literature, for the drugs 113 shortlists (PubMed records, drug AND mechanism / drug AND
rhabdomyosarcoma): bortezomib 59 / 15 · nicotinamide 28 / 10 · valproic acid 28 / 12 ·
metformin 9 / 5 · chloroquine 7 / 10 · vorinostat 4 / 9 · lovastatin 2 / 5 · hydroxychloroquine
2 / 0 · niacin 1 / 1 · simvastatin 1 / 18 · atorvastatin 1 / 8. For comparison, the drugs the
tumour-context trials surface without any mechanism link: paclitaxel 232 / 37, doxorubicin
142 / 461, cisplatin 127 / 216 — the counts follow how much a drug is used, not what it does
here, which is why the column is descriptive and never a rung.

**H047's snapshot clause.** SIRT2 returned 10 candidate molecules: eight unapproved tool
compounds (AGK2, paullone, ChEMBL ids) and two approved drugs listed against it with no
SIRT2-activating mechanism (gefitinib, panobinostat). CREBBP returned approved drugs only as
DGIdb noise (alprazolam, midazolam, colchicine). **No approved NAD⁺ precursor or SIRT2
activator came out of the automated stage** — the D3 route in 113 exists because the curated
table names it. Recorded as a refuting row against H047 (evidence 112).

## Conclusion

Three facts per drug, computed the same way for every drug and for a decoy card, with the
question vocabulary read off the card. They are the automated half of the ladder. They are
also where the automated stage shows its limit: the drugs with the most literature are the
chemotherapies the child would receive anyway, and the one direction with an in-vivo mechanism
result (D3) has no automated route to any approved molecule.

## Assumptions, limitations, quality checks

- **Assumption:** a base name is one molecule. True for salts; the fold is a fixed suffix list,
  so `PACLITAXEL PROTEIN-BOUND` and `PACLITAXEL` merge (intended) and prodrugs do not.
- **Limitation:** a PubMed count is co-mention, not support. Stated in the column description
  and in the ladder's rule; step 5 measured literature volume as a poor ranker (105).
- **Limitation:** a study *admitting* children is a pointer, not paediatric safety data; the
  first page of 100 studies per drug is a head, not a census. Both stated in the manifest.
- **Limitation:** openFDA's `pediatric_use` says a label *has* a section 8.4; the section may
  read "safety and effectiveness have not been established". A pointer to read.
- **Quality check:** the manifests' roll-up digests are reproducible from the cache; a
  re-run with `--skip-live` reads the tables and makes zero requests.
- **Quality check:** `tests/test_drugs_ladder.py` exercises name folding and the query
  construction on the invented card; `tests/test_drugs_sources.py` covers the adapters offline.
