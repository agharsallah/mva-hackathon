# 106 — Where does the leading missense allele sit in its protein, and does the structure agree?

**Written:** 2026-09-18. **Step:** `step-5` (iteration 2). **Hypotheses:** H040.
Instruments, and the cut this claim replaces:
[102](102-the-sources-and-what-they-could-be-asked.md).

## Hypothesis and prediction

**H040** — *The missense allele of the leading pair falls inside an annotated InterPro
domain, in a region the structure model is confident about, and the AlphaMissense class
agrees that it is damaging.*

**Prediction.** The residue maps inside at least one InterPro domain range of the gene's
canonical UniProt entry, the AlphaFold per-residue pLDDT at that position is ≥ 70, and the
AlphaMissense class recorded for the allele is `likely_pathogenic`.

## What would refute it

The residue falls outside every annotated domain, **or** the pLDDT is below 70 so the model
has no confident opinion there, **or** AlphaMissense does not call it `likely_pathogenic`.
Any one of the three refutes the claim and is reported separately.

This is plan claim **H025** restated. The plan asked whether **ESM1b** and AlphaMissense
agreed; ESM1b is cut ([102](102-the-sources-and-what-they-could-be-asked.md)) and the second
opinion is structural context instead.

## Inputs

| Source | What was read |
|---|---|
| `results.it2_lr_top_pairs` | the top 20 genes of the genome-wide ranking |
| `warehouse.it2_insilico_annotations` | the three missense alleles per gene with the highest AlphaMissense pathogenicity, and their coordinates — used only to ask VEP for a residue, never written to a table |
| Ensembl VEP REST | `protein_start` on the canonical transcript |
| UniProt | the reviewed human accession and protein length per gene |
| InterPro | every entry mapped onto that accession, with its residue ranges and its `type` |
| AlphaFold DB | the per-residue pLDDT profile of the same accession |

## Commands

```bash
uv run python tools/score_it2_protein.py          # --genes 20 --per-gene 3
uv run mva-warehouse pg-load-it2-step5
uv run mva-warehouse pg-derive --only it2_protein_agreement
```

## Observed — coverage first, because it bounds everything else

| | count |
|---|---|
| leading genes with a reviewed human UniProt entry | **17 of 17** asked |
| missense alleles scored (3 per gene, strongest AlphaMissense first) | **45** |
| of those, a residue resolved on a canonical transcript | **36** (9 had no canonical protein consequence) |
| residues inside an InterPro entry typed `domain` | **18** |
| residues at pLDDT ≥ 70 | **22** |
| InterPro rows mapped across the 17 proteins | **146** |

## Observed — the leading allele, condition by condition

| Condition | Result |
|---|---|
| inside an InterPro entry typed `domain` | **no** |
| inside *any* InterPro entry (family / superfamily included) | yes — a family entry spanning almost the whole protein |
| AlphaFold pLDDT at the residue | **91.06** — confident |
| AlphaMissense class | `likely_pathogenic` — **agrees** |
| position along the protein | **95.4 %** of its length |

**H040 is refuted on its first condition and supported on the other two.** The refutation is
not a near miss and it is not an instrument failure: the protein's only InterPro entry typed
`domain` covers residues near the N-terminus, its protein-kinase-like **superfamily** entry
stops well before the residue, and the allele sits past both, in the last five per cent of
the chain.

The qualification is carried rather than used to rescue the claim. The residue is inside a
*family*-level entry that spans essentially the entire protein, and UniProt's own feature
table places a kinase region extending to the C-terminus — so *"outside every annotated
domain"* is a statement about **InterPro's domain-typed mapping**, not about the protein
being featureless there. The three columns `in_domain`, `in_superfamily` and `plddt` are in
the table precisely so a reader can see this without taking either reading on trust.

## Why `domain` and not every InterPro entry

Pre-registered, and load-bearing. InterPro's `family` and `homologous_superfamily` entries
routinely span 90–100 % of a protein: on the leading gene, the family entry covers 2 %–98.7 %
of the chain. Counting them would make *"inside an annotated domain"* true for almost any
residue of almost any protein, and the claim would have been unfalsifiable by construction.
The entries are fetched, stored and reported anyway, in their own column.

## Evidence recorded

| Direction | Strength | Claim | Source |
|---|---|---|---|
| refutes | 0.70 | the leading missense residue is outside every InterPro entry typed `domain`, at 95.4 % along the protein | methodology/106 |
| supports | 0.45 | AlphaFold pLDDT at that residue is 91.06, so the structure model is confident about the region | methodology/106 |
| supports | 0.45 | AlphaMissense calls the allele `likely_pathogenic`, agreeing with the step-4 lane that scored it | methodology/106 |
| neutral | 0.40 | the residue is inside an InterPro `family` entry spanning 2 %–98.7 % of the protein, which is why that entry type is excluded from the test | methodology/106 |

## Limitations, stated beside the result

* **A domain map is a curation, not a measurement.** InterPro says where domains have been
  *annotated*, and an unannotated region is not a region without function. The claim is
  therefore about annotation coverage, and the entry says so rather than reading "outside a
  domain" as "harmless".
* **pLDDT is not a pathogenicity score.** 91.06 says AlphaFold is confident about the
  *shape* there. It says nothing about whether changing the residue matters.
* **9 of 45 alleles have no canonical protein consequence** and carry a stated reason on the
  row rather than being dropped.
* **ESM1b was cut**, so H040 no longer tests what the plan's H025 tested: there is no second
  *model* opinion, only a second *kind* of evidence. Recorded as a limitation of the step,
  not as a substitution of equal weight.
* **Only the top three missense alleles per gene were scored.** Scoring all 306 in the top 20
  genes is dominated by the HLA loci and is throttled by Ensembl long before it finishes; no
  claim is about those alleles.

## Verdict

**H040 — refuted, confidence 0.20.** The residue is outside every annotated InterPro domain.
The other two conditions hold and are reported, and the failure is specific enough to name:
the claim assumed a leading missense allele would land in curated domain territory, and this
one lands in the last five per cent of its protein, in a region InterPro types only at
family level.

Next: [104](104-the-papers-the-script-found.md).
