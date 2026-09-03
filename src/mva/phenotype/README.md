# `mva.phenotype`

Phenotype-driven gene ranking, in Python, with no JVM.

**Standing:** 2026-09-03 — written from source, verified by an executed run recorded in
[`docs/step-3/methodology/056`](../../../docs/step-3/methodology/056-phenotype-ranking-without-java.md).

## What it is

- The child's eight HPO terms in, a ranking over **5,267 curated genes** out.
- Reads two public plain-text files. **Never reads the callset, the candidate panel, or a
  variant** — that independence is the entire value of the output.
- Nine modules, no new dependencies beyond `httpx`, which the repository already has.
- A reimplementation of Exomiser's hiPHIVE **human-only** path. **Not Exomiser**, and no
  result from it may be reported as Exomiser output.

## Why it is a reimplementation and not a wrapper

Exomiser ships its data as H2 MVStore databases and Java-serialised Jannovar objects — no
Python reader exists, and the hg38 bundle is 31.5 GB unpacked against 20 GB of free disk.
Its *phenotype* inputs, though, are plain text.

And the published optimisation study (Genome Medicine 17:127, 2025, PMID 41121346)
measures `prioritiser-params=human` at **82.8%** top-10 against **66.6%** for the
all-species default. The two components that are genuinely hard to reproduce — the STRING
protein-interaction random walk and the mouse and zebrafish models — are the ones the
evidence says to switch off. What remains is a DAG walk and a logarithm.

## The modules

| Module | Concern |
|---|---|
| `terms.py` | The eight delivered HPO terms, declared once. Ships two sets — with and without the **parental** term — so "run it both ways" is two constants, not two hand-edits |
| `ontology.py` | `hp.obo` as a DAG: ancestor closure, depth, information content, and the most informative common ancestor |
| `associations.py` | `genes_to_phenotype.txt` → gene symbol → curated feature set |
| `similarity.py` | Resnik similarity rolled up best-match-average, both directions, normalised |
| `prioritise.py` | Every gene scored and ranked against a term set, with the per-feature breakdown kept |
| `prior.py` | The ranking as a `gene_prior` dict for `mva.pipeline.ranking.rank_pairs` |
| `remote.py` | Phen2Gene and Monarch semsim as independent second opinions |
| `cli.py` | `mva-phenotype`: `rank`, `gene`, `delta`, `agreement` |

## How it joins the pipeline

`rank_pairs()` already accepts `gene_prior: dict[str, float]`. `prior.gene_prior()`
produces one. **That is the whole integration — no file in `mva.pipeline` changed.**

Before this, the only gene prior in the codebase was a hand-typed `{"BUB1B": 2.0}` in a
test, and `mva.science.dossier` correctly recorded any such prior as *neutral evidence of
strength zero* — "a stated assumption, not the data alone". A prior derived from 5,267
measured comparisons is a different object.

## Usage

```bash
uv run tools/build_phenotype_data.py          # fetch ~68 MB, write two reference tables
uv run mva-phenotype rank --limit 30 --panel  # the ranking, panel genes marked
uv run mva-phenotype gene BUB1B               # why one gene placed where it did
uv run mva-phenotype delta                    # what the parental term costs
uv run mva-phenotype agreement                # ours vs Phen2Gene vs Monarch
```

## Gotchas

- **The information content depends on the release.** HPO publishes monthly and a term's
  rarity moves with curation, so a stored score names the release that produced it.
- **Counts are over distinct genes, never summed up the graph.** Summing per-term counts
  double-counts a gene annotated to both a term and its parent, making internal nodes look
  rarer than they are. `Corpus.closure_counts` is the only correct path.
- **An unranked gene is not a gene ranked last.** A gene HPO has never curated has no
  phenotype evidence either way; `rank_of` answers `None`, and it means *no knowledge*.
- **Forward and reverse disagree on purpose.** Forward ignores everything else a gene does;
  reverse penalises heavily curated genes. Where they diverge, that is a fact about how
  well studied the gene is, not about the child.
- **375 rows of the upstream annotation file have `-` as the gene symbol**, spanning seven
  distinct genes. They are dropped at parse time; loading them creates a phantom gene that
  ranked 22nd before the fix.
- **The hosted cross-checks never raise.** A service that is down costs a second opinion
  and nothing else. Monarch's `/search` returns at most 50 genes, so a gene it omits has
  not been ranked last.
