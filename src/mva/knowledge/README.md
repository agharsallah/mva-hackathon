# `mva.knowledge` — what has been published about a candidate set, and whether that is worth anything

**Standing:** built 2026-09-18 for iteration 2, step 5
([`docs/iteration2/step-5/README.md`](../../../docs/iteration2/step-5/README.md)).
Case-agnostic: nothing here names a gene, a disease or a coordinate.

A literature route is the easiest route in a rare-disease pipeline to fool yourself with.
The gene at the top of any literature search is the gene most has been written about, and
in a symptom-derived candidate set that is very often the gene somebody already solved. So
this package answers three knowledge questions **and** a fourth one that decides whether
the first three measured anything.

| Module | Question | Source |
|---|---|---|
| `sources.py` | — | LitVar 2.0, PubTator 3.0 (both NCBI), and E-utilities through `mva.drugs.sources.pubmed` |
| `catalogue.py` | Has anyone published about the alleles **this sample carries**? | LitVar 2.0, keyed on dbSNP identifiers |
| `anchors.py` | Does any single paper discuss a candidate gene alongside several of the patient's clinical features? | PubTator 3.0, one search per (gene, term) |
| `protein.py` | Does a missense allele land in an annotated domain, where the structure model is confident? | UniProt → InterPro → AlphaFold DB |
| `baselines.py` | Does any of that order anything a raw publication count does not? | the other four, plus `mva.pipeline.nulls` |

## Three rules the package is built on

1. **The catalogue runs allele-first, not gene-first.** "Every published allele of gene X"
   is somebody else's alleles. "Which of *this* sample's alleles has been written about"
   has a complete denominator and a meaningful zero.
2. **An allele with no dbSNP identifier is `NOT_ASKED`, never zero.** Unqueryable and
   unpublished are different findings, and a single coverage percentage would merge them.
3. **Citation volume never enters a score, only a baseline.** `anchors.rank` breaks ties on
   the gene symbol precisely so that `baselines.agreement` can ask an independent question.

## Where the fetching lives

Nowhere in this package. Every function takes a `mva.drugs.cache.Fetcher` as its first
argument, which owns the disk cache, the 3-requests-per-second courtesy interval, the retry
ladder and the provenance digest. That is also why this package sits one import layer above
`mva.drugs` — it reuses those adapters rather than owning a second HTTP client.

## Re-run

```bash
uv run python tools/fetch_it2_catalogue.py          # LitVar over the sample's own alleles
uv run python tools/build_it2_anchors.py            # PubTator, gene x clinical term
uv run python tools/score_it2_protein.py            # UniProt, InterPro, AlphaFold
uv run python tools/run_it2_knowledge_baselines.py  # the decoy null and the citation baseline
```
