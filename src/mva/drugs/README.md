# `mva.drugs`

Track 2's data layer: a **mechanism card** in, a repurposing evidence set out, entirely
from public APIs.

**Standing:** 2026-09-06 — written from source; every endpoint schema note in this page and
in the adapters was verified against the live API on that date, and the row counts quoted
anywhere else come from the executed `mva-drugs snapshot` run, never from this page.

## What it is

The card (`ressources/track2/mechanism.json`) is the Track 1 → Track 2 hand-off: it names
the gene, the protein, the disease, the affected pathway and a list of **repurposing
directions**, each with seed gene symbols. This package turns that into five tables:

| Table | One row is |
|---|---|
| `targets.tsv` | a gene worth looking for drugs against, and *why* it is in the set (`seed` from a direction, or `pathway` from the Reactome walk) |
| `drug_candidates.tsv` | a drug–target pair, with mechanism, clinical phase, approval status and FDA-label evidence |
| `trials.tsv` | a registered study matching one of the snapshot's queries, tagged with the query that found it |
| `literature.tsv` | a publication matching one of the four literature query families |
| `pathways.tsv` | a Reactome pathway the expansion walked, kept or dropped, and how many participants it had |

Plus `snapshot.json` (counts per table, per source and per query, including the zeros) and
one `<name>.provenance.json` per table.

**No genomic position is written anywhere, and none can be.** The card is coordinate-free
by rule and this package deals in gene symbols, ChEMBL ids, NCT ids, PMIDs and counts.
`tests/test_drugs_snapshot.py` asserts it over every file a run produces.

## The case-agnostic rule

Nothing here hard-codes a gene, a disease, a drug or a pathway. Two indirections carry it:

1. **Every value comes off the card.** `--card <path>` runs a different case unchanged.
   `mva-drugs card` prints exactly what the pipeline will therefore ask, before it asks.
2. **The pathway filter is a parameter.** Seeds are the card's union in card order. Pathway
   members are every human `ReferenceGeneProduct` participating in a Reactome pathway that
   (a) contains the card's UniProt accession and (b) whose `displayName` matches the
   pattern — default `/checkpoint|kinetochore|mitotic/i`, overridable with
   `--pathway-pattern`. A gene that is already a seed keeps role `seed`, because a seed
   carries a direction id and a pathway member does not.

The rule is written into every `targets` and `pathways` manifest by `pathway.rule_text()`,
so a reader of the table alone can criticise it without opening this file.

## The modules

| Module | Answers |
|---|---|
| `mechanism.py` | what does the card say, and what search strings does it imply? |
| `cache.py` | one polite, disk-cached JSON client — the cache key, the retry ladder, the provenance digest |
| `sources/opentargets.py` | which drugs does Open Targets tie to this target or disease, at what clinical stage? |
| `sources/chembl.py` | what is the mechanism of action, the max phase, the first approval, the ATC class? |
| `sources/dgidb.py` | what does the union of ~40 curated resources say about this gene? |
| `sources/reactome.py` | which pathways contain this protein, and who else is in them? |
| `sources/clinicaltrials.py` | has anyone registered a trial for this disease, or this drug in this tumour? |
| `sources/pubmed.py` | what has been published about this gene, this pathway, this direction? |
| `sources/openfda.py` | is there a current US label for this drug name? |
| `pathway.py` | seeds + the pathway walk → the target set |
| `candidates.py` | three sources merged, deduped, enriched, and the `approved` flag |
| `queries.py` | the trial and literature question families, derived from the card |
| `tables.py` | the five TSVs: columns, and how a cell is spelled |
| `methods.py` | one sentence per table for the manifests — prose, kept out of the pipeline module |
| `decoy.py` | the same child, a different gene: the **specificity** control |
| `transfer.py` | a different **case** entirely: the card, the `phenotype.hpoa` reader, the **portability** control |
| `compare.py` | both controls' side-by-side counts: the decoy per direction, the transfer per case |
| `provenance.py` | one manifest per table, in the repository's reference shape |
| `snapshot.py` | run everything once, write everything, count everything |
| `cli.py` | `mva-drugs`: `card`, `targets`, `drugs`, `trials`, `literature`, `snapshot` |

## How to run it

```bash
uv run mva-drugs card                       # what the card says, and the queries it implies
uv run mva-drugs targets                    # the seed + pathway target set
uv run mva-drugs drugs --approved-only      # the market-approved candidates
uv run mva-drugs literature                 # the publications, per query family
uv run mva-drugs snapshot                   # everything, written to ressources/track2/
uv run mva-drugs --card other/card.json snapshot --out-dir ressources/other-case
uv run mva-drugs snapshot --refresh         # bypass the cache for this run
uv run python tools/track2_decoys.py --symbol XDH ...   # a decoy: same child, wrong gene
uv run python tools/track2_transfer.py --warm           # a transfer case: a different case
```

A cold `snapshot` is a few thousand requests over roughly half an hour, almost all of it
polite waiting. A warm one is seconds.

## What is cached where

- **`build/track2-cache/<source>/<method>-<sha256>.json`** — one file per request, keyed by
  `sha256(method + url + canonical params/body)`, holding `{url, method, params,
  retrieved_at, status, body}`. Gitignored via `build/`, because it is rebuildable.
- A second run of any verb reads the cache and makes **no** live call. `--refresh` bypasses
  it for that run and rewrites what it fetches.
- The cache is what makes the manifests honest: each input's `sha256` is a **roll-up** —
  the sha256 over the sorted per-reply body digests for that API. Same replies in, same
  value out, whatever order the adapters asked in. A public API has no single byte stream
  to hash, so listing one file, or a thousand, would be worse than one reproducible digest.
- **`ressources/track2/`** holds only the committed outputs and the card. No patient data
  ever reaches either place.

## The two controls, and what each can say

| Control | What is swapped | What it measures | What it cannot say |
|---|---|---|---|
| **decoy card** (`decoy.py`) | the gene; the child, the disease and the clinical queries are kept | **specificity** — how much of the drug list any gene would also have produced | whether the curated rungs are right; a decoy gets no hand-read literature |
| **transfer card** (`transfer.py`) | the whole case — another disease with its own OMIM/MONDO ids, its own HPO terms read from `phenotype.hpoa`, its own tumour and standard of care | **portability** — that the code is case-agnostic in fact, not only in claim | whether the second case's drug list is any good; it has no alleles and no `evidence.tsv`, so rungs 2 and 3 cannot exist for it |

A transfer card copies exactly three blocks from the template — `anti_directions`,
`evidence_ladder`, `constraints` — because those are the *method*, not the child, and it
records in its own `transfer` block that it did and why. Everything else is built from the
committed spec. Exactly one direction may carry `context: true` (the tumour direction);
anything else raises, because that flag is the only route to the automated rungs 4 and 5.

**What the first transfer run measured** (TRIP13 / MVA3, entry
[138](../../../docs/iteration2/step-7/methodology/138-a-second-case-through-the-same-pipeline.md)):
the pipeline ran unchanged and the directions came out the same shape — every D1 row at rung 1,
no D1 row in the shortlist, only the context direction above rung 1 — but the **anti-directions
did not fire**. That is a reusability gotcha, not a one-off: an anti-direction is matched by
`moa_pattern` against each drug's `action_type` + `interaction_or_moa`, and that text arrives with
the ChEMBL rows that *pathway expansion* pulls in. Reactome matched no pathway for TRIP13, so the
candidate set was seed-only and the spindle poisons in it were never flagged. **Before trusting a
new case's do-not table, check that `pathways.tsv` is not header-only.**

## Gotchas

- **Open Targets moved.** `Target.knownDrugs` no longer exists; the field is
  `drugAndClinicalCandidates`, and the phase is a *string* stage (`APPROVAL`, `PHASE_2_3`),
  not an integer. `opentargets.STAGES` maps it back, so the row shape downstream is
  unchanged. `APPROVAL` is phase 4.
- **ChEMBL's `max_phase` is a string** (`"4.0"`). `chembl.phase()` parses it and answers
  `None` — never `0` — when it is absent.
- **Reactome's `/data/pathways/low/entity/{id}` does not take a UniProt accession.** It
  404s. The mapping endpoint `/data/mapping/UniProt/{acc}/pathways` is what works, and is
  what `pathways_for_uniprot` calls.
- **A 404 is sometimes data.** openFDA answers 404 for "no label under that name" and
  Reactome for "not curated here". Those adapters pass `allow_status=(404,)` and return an
  empty answer; every other 404 raises `SourceError` naming the url.
- **An anti-direction flag is only as wide as the target set.** `A1`/`A2` are matched
  against the mechanism-of-action text of drugs already in `drug_candidates.tsv`, so a drug
  class reaches the do-not table only if some target in the set is drugged by it. On the
  BUB1B card every spindle-poison flag comes from tubulin genes the *Reactome expansion*
  added; a case Reactome does not curate (TRIP13 has no pathway at all) gets no pathway
  targets, so its do-not table is silent about the same class. Measured in
  [`docs/iteration2/step-7/methodology/138`](../../../docs/iteration2/step-7/methodology/138-a-second-case-through-the-same-pipeline.md).
- **`fda_label` empty is not `false`.** Empty means *not checked* — only approved rows are
  label-checked, because it is one request per drug.
- **`approved` is a disjunction, not a consensus.** ChEMBL phase 4 *or* an Open Targets
  `APPROVAL` stage *or* DGIdb's flag. The three disagree in both directions (ChEMBL carries
  phase 4 for drugs approved only outside the US; openFDA labels generics ChEMBL never
  phased), so the row keeps all the evidence and lets a reader see which one it rests on.
- **A literature query that returns nothing is recorded as zero,** never replaced by a
  looser one. The direction family is the weak one: a long descriptive direction name
  becomes a long PubMed AND-chain. That is visible in `snapshot.json`, deliberately.
- **The provenance primitives are duplicated here on purpose.** `mva.viz.refprovenance`
  owns the same `digest`/`code_version`/`now`, but the package layering forbids anything
  outside `mva.viz` importing it, and `mva.drugs` sits far below the web layer. The
  algorithm is identical, so the values are comparable.

## Where it sits

`mva.drugs` imports **no** sibling package — it is a self-contained leaf on the row above
`io`/`pipeline`/`render`, beside `mva.phenotype`, and is enforced there by
`uv run lint-imports`. See [`../README.md`](../README.md).
