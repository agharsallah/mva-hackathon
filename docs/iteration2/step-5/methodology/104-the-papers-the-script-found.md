# 104 — Which published papers discuss a candidate gene alongside this child's own features?

**Written:** 2026-09-18. **Step:** `step-5` (iteration 2). **Hypotheses:** H037.
Instruments and their refusal semantics:
[102](102-the-sources-and-what-they-could-be-asked.md).

## Hypothesis and prediction

**H037** — *At least one published case report matches five or more of the child's seven
proband HPO terms and names a gene that step 4 ranks in its top 20.*

**Prediction.** In the script-derived anchor table, at least one PMID is returned by five
or more of the seven per-term PubTator queries for a single step-4 top-20 gene.

## What would refute it

No PMID reaches five matched terms for any top-20 gene. The literature then corroborates no
lead at case-report level, and step 6 records the knowledge route as silent rather than
negative.

## Inputs

| Source | What was read |
|---|---|
| `results.it2_targets`, `results.it2_decoys` (step 1) | 404 symptom-nominated genes and 396 length- and exon-matched controls |
| `results.it2_lr_top_pairs` (step 4) | the top 20 genes of the genome-wide ranking |
| clinical document, via `mva.phenotype.terms.PROBAND_ONLY` | the **seven proband term labels** — `Rhabdomyosarcoma`, `Nephrocalcinosis`, `Short stature`, `Failure to thrive`, `Skeletal muscle atrophy`, `Premature birth`, `Small for gestational age` |
| PubTator 3.0 | one search per (gene, term label); first page of each, plus the complete count across all pages |

No iteration-1 candidate table, and **no hand-written reading list**: the plan's own
bibliography enters only if these queries produce it.

## Commands

```bash
uv run python tools/build_it2_anchors.py --interval 0.7
uv run mva-warehouse pg-load-it2-step5
uv run mva-warehouse pg-derive --only it2_anchor_match
```

## Observed — the pass

| | |
|---|---|
| searches | **5,705** (815 genes × 7 terms), ~85/min at a 0.7 s courtesy interval |
| anchor rows written (≥ 2 matched terms) | **4,105** across **758** genes |
| papers per (gene, term) pair, mean / max | **101.2** / 56,141 |
| (gene, term) pairs with no paper at all | **798** of 5,705 |
| genes whose best paper reaches ≥ 5 terms | **54** — 38 targets, 16 decoys |
| of those, genes in the step-4 top 20 | **0** |

## Observed — H037 is refuted, and the refutation names the design flaw

**No paper reaching five terms names a step-4 top-20 gene.** The prediction fails on its own
pre-registered condition.

The useful half is *why*. Look at what a five-or-more-term paper actually is:

| PMID | terms | genes it covers | what it is |
|---|---|---|---|
| 37217505 | **6** | **68** of the 815 (49 targets, 18 decoys) | *Clinical diagnosis of genetic disorders at both single-nucleotide and chromosome level* — a broad clinical-genomics survey |
| 40301961 | 6 | 2 | a review of histone-related disorders |
| 37008163 | 5 | 5 | European diagnosis-and-management **guidelines** for neutropenia |
| 37000104 · 35905201 | 5 | 2 · 1 | **conference proceedings** of a national human-genetics society |

A single survey paper supplies the six-term anchor for **68 genes at once**, decoys
included. The matched-term count as pre-registered does not measure *"a paper describing a
patient like this one with a variant in this gene"*; it measures **breadth of coverage**,
and the papers that cover the most ground are surveys, guidelines and meeting abstracts.

## Observed — the paper the script *did* find, and where it scored

For the gene step 4 ranks first, the highest-scoring anchor is:

> **PMID 35804254** — *Pathogenic correlation between mosaic variegated aneuploidy 1 (MVA1)
> and a novel BUB1B variant: a reappraisal of a severe syndrome.* Neurol Sci, 2022.
> Matched terms: **Rhabdomyosarcoma; Premature birth; Small for gestational age** — **3 of 7**.

That is exactly the paper a clinician would want: the child's disease, the child's gene, a
novel variant, a severe presentation. The script found it **without being told the gene**,
from the target set alone. And the pre-registered threshold ranks it **below** a survey that
names 68 genes.

So the instrument works and the **threshold** is wrong. A paper's value as an anchor is not
monotone in how many of the patient's features it mentions, because mentioning many features
is what a broad paper does. Recorded here rather than fixed by moving the line after seeing
the data: the threshold was filed at five before the run, it failed, and a step 6 that wants
a case-report signal needs a specificity term — papers per gene, or matched terms divided by
genes covered — which this step did not pre-register and therefore does not claim.

## Observed — what the decoys did, which is why the threshold failure is visible at all

16 decoy genes reach five terms against 38 targets — a real difference (and the input to
H038), but **decoys reach the threshold at all**, and two of them (`DDX11`, `CRYBA4`) reach
six through the *same survey paper* as the targets. A run without a matched control set
would have reported "38 symptom-nominated genes have a five-feature paper" as a result.

## Evidence recorded

| Direction | Strength | Claim | Source |
|---|---|---|---|
| refutes | 0.75 | no paper reaching five of the seven proband terms names any step-4 top-20 gene; 54 genes reach the threshold and none is a leader | methodology/104 |
| neutral | 0.60 | the six-term anchor for 68 of the 815 genes, decoys included, is one broad clinical-genomics survey — the threshold measures coverage breadth, not case-report specificity | methodology/104 |
| supports | 0.35 | the script found an MVA1 case paper naming the leading gene and a novel variant in it (PMID 35804254), at 3 of 7 matched terms, without being told the gene | methodology/104 |

## Limitations, stated beside the result

* **The matched-term count is over the first page of each search, not every page.** A paper
  reaching five terms had to rank in the top ten of five separate relevance-sorted searches.
  The per-term *totals* are complete across all pages, so the two numbers are not symmetric
  and neither is the other's denominator. The cut applies identically to the decoys.
* **Co-occurrence is not a case report.** `GENE AND Short stature` returns papers mentioning
  both; nothing in the query says the paper reports that feature in a patient carrying a
  variant in that gene. This is the whole reason H037 failed the way it did.
* **A term label is a string.** PubTator matches the HPO label text, not the ontology term,
  so a paper writing "growth retardation" rather than "short stature" is invisible here.
* **Seven terms, one child.** The proband set is used; the parental term is excluded, per
  `mva.phenotype.terms`.
* **No threshold was moved after the run.** The five-term line stands as filed and the claim
  is recorded as refuted.

## Verdict

**H037 — refuted, confidence 0.15.** No five-term paper names a leading gene. The step keeps
the finding that matters more than the claim did: the pre-registered threshold selects
survey papers and conference proceedings, and the one genuine case report the script
surfaced for the causal gene scores three.

Next: [105](105-does-the-literature-beat-a-hit-count.md).
