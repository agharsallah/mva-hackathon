# 125 — The API anchors itself to the repository root, and a real 404 stops blaming the server

**Date:** 2026-09-19
**Question:** The dashboard's 3D-fold exhibit (`/panel`, "The fold in 3D — where BUB1B's
alleles sit in space") reported *"The running API does not have this endpoint / The API
process is older than this app"* against an API that had been started minutes earlier and
whose OpenAPI document listed the route. Which of the two statements in that message was
false, and what actually broke?

_(step-0 platform machinery: this entry records a defect, its cause and the fix, not a
hypothesis. Per [`docs/method.md`](../../method.md), step 0 takes no hypotheses. Filed in
step 0 rather than a research step because the fault was in the process every step's
exhibits are served through.)_

## What was observed

The route existed and answered. Asked directly:

```
$ curl -s http://127.0.0.1:8900/api/panel/structure-genes
{"data":[],"cached_at":null,"source":"ressources/reference/structure_genes.tsv + …;
 ensembl_release=unknown, structure_genes_sha256=unknown, built_at=unknown, …"}

$ curl -s -w '%{http_code}' 'http://127.0.0.1:8900/api/panel/protein-structure?gene=BUB1B'
404 {"detail":"no structure gene 'BUB1B': not in ressources/reference/structure_genes.tsv …"}
```

A **200 with an empty list** and a provenance line whose every manifest field says
`unknown`. The committed file is 3,518 bytes of 23 genes, and `ls` found it. So the server
was not reading the file that exists.

Sweeping every no-argument route the live OpenAPI document declares put a shape on it:

| Endpoint | Answer | What it reads |
|---|---|---|
| `/api/panel/structure-genes` | 200, `[]` | `ressources/reference/structure_genes.tsv` |
| `/api/panel/protein-structure?gene=…` | 404 for every gene | the same TSV |
| `/api/phenotype/{genes,terms,delta}` | 503 "is missing or empty" | `ressources/reference/hpo_gene_scores.tsv` |
| `/api/provenance/reference` | 200, `[]` | `ressources/reference/*.provenance.json` |
| everything backed by PostgreSQL or the object store | 200, populated | — |

Exactly the file-backed endpoints, and no others.

## The cause

The process's working directory:

```
$ pgrep -f mva-viz-api | while read p; do lsof -a -p $p -d cwd | tail -1; done
Python  38971 …  cwd  DIR  …  /Users/…/mva-hackathon/app     ← the one on :8900
Python  52317 …  cwd  DIR  …  /Users/…/mva-hackathon         ← an older one on :8011
```

The API had been started from `app/`. Every reference default in this package is spelled
relative — `Path("ressources/reference/structure_genes.tsv")`, `build/viz-cache`, `docs/` —
because they name positions in *this repository*, not on one machine. `mva.viz.geneset`
even says so in a comment: *"Relative to the repository root, which is where the API is
started from."* That sentence was an assumption, not a check.

The failure shape is what made it expensive. `geneset._load` catches `OSError` and returns
`()` on a missing TSV — deliberately, so a checkout without the built reference table still
serves the panel routes. Under the wrong working directory that deliberate empty answer
stops meaning "nothing curated here" and starts meaning "the file is one directory away",
and the endpoint answers **200 with an empty list**. Silent emptiness is the worst
available failure shape, because it reads as a finding.

Settings were unaffected: `mva.warehouse.settings.find_env` walks *upward* from the cwd, so
`app/` still found the repository's `.env`, which is why every database-backed endpoint was
healthy and only the file-backed ones were empty.

## What the app said about it, and why that was wrong too

`app/src/components/failure.ts` classified **any** 404 as `route-missing` — "the API process
is older than this app, restart it". The fetch layer next door
(`app/src/api/client.ts`, `isRouteMissing`) already had the correct, narrow rule and had
carried a docstring explaining it since it was written: FastAPI answers an unrouted path
with exactly `{"detail": "Not Found"}`, while an endpoint that ran and found nothing answers
with its own sentence. Two copies of one rule, one of them wrong, and the wrong one is the
copy the reader sees. It sent a reader to restart a server that was working.

## What was changed

1. **`src/mva/paths.py`** (new) — `repo_root()` walks up from the module's own file for all
   of `pyproject.toml` + `src/mva` + `ressources` (all three, so a stray `pyproject.toml`
   above an installed package cannot claim the root), plus `resolve()` for one path and
   `anchor_cwd()` for the process. `None` when there is no checkout above the package: a
   wheel in site-packages keeps the working directory it was given.
2. **`mva-viz-api` and `mva-reads-api` anchor themselves** at startup, before the first
   module reads a default, and print the move when there is one. Done in the two entry
   points rather than by rewriting a hundred defaults to absolute paths: the relative
   spellings are the contract the module docstrings state, and one `chdir` is smaller and
   more reviewable than a hundred call sites.
3. **`isRouteMissing` is exported from `app/src/api/client.ts`** and is now the single rule
   `classifyError` uses. A 404 carrying the endpoint's own sentence gets a new failure kind,
   `not-found` — *"The API has no data for this selection"*, quoting the API's `detail` and
   pointing at Status and Provenance — and offers no restart command.

## Verification

Restarted from the repository root and re-swept every no-argument route:

| Endpoint | Before | After |
|---|---|---|
| `/api/panel/structure-genes` | 200, 0 genes | 200, 23 genes |
| `/api/panel/protein-structure?gene=BUB1B` | 404 | 200, 63,133 bytes |
| `/api/phenotype/genes` | 503 | 200 |
| `/api/provenance/reference` | 200, `[]` | 200, 9 manifests |

Every other route kept its previous answer. All 25 dashboard routes were then loaded in a
real browser and scanned for `role="alert"`: **zero failure cards** outside `/style-guide`,
whose eight are the deliberate gallery of every failure kind (now including `not-found`).
The 3D fold renders for BUB1B, and the API log shows the live 200 behind it.

One thing the sweep surfaced that is **not** a defect: `/api/catalog/tables` answered with
42 tables and `cached_at: 2026-09-01`. The response cache has no TTL by design — a hit
returns the stored payload *and* the instant it was built, so staleness is visible rather
than silent. `?refresh=true` rebuilt it to 121 tables. The two working directories had two
separate cache directories, which is how one of them came to hold an older answer.

## Assumptions, limitations, quality checks

- **Assumption:** the repository markers identify the checkout. If all three are ever
  removed from the root, `repo_root()` answers `None` and the servers behave as they did
  before this entry — cwd-dependent — rather than guessing.
- **Limitation:** only the two server entry points anchor. The CLIs (`mva-warehouse`,
  `mva-science`, …) still resolve relative defaults against the cwd. That is defensible for
  a foreground command whose output the operator reads immediately, and `resolve()` is there
  for any of them that later wants anchoring.
- **Limitation:** this removes the *silent* form of the fault. A server whose checkout
  genuinely lacks a built reference table still answers 200 with an empty list, which is the
  intended behaviour of `geneset._load`.
- **Checks run:** `tests/test_paths.py` (3 cases: root independent of cwd, `resolve` on a
  relative and an absolute path, `anchor_cwd` idempotent); `app/src/test/failure.test.ts`
  (19 cases, two of them new — a 404 with the endpoint's own sentence classifies as
  `not-found`; a 400 is never `route-missing`); `tools/check-python.sh` gates on the changed
  files — ruff format, ruff lint, module size, `lint-imports` (3 contracts kept), mypy, the
  coordinate gate, the iteration-folder gate; `tsc --noEmit` and eslint on the changed app
  files.

## Conclusion

The message was false in both halves: the API was not older than the app, and the endpoint
was not missing. It was a working server pointed one directory away from its own reference
data, reporting that as an empty result. Two defects, one visible: a relative-path contract
nothing enforced, and a duplicated error rule whose wrong copy was the one shown to a human.
Both are now single-sourced — `mva.paths` for the first, `isRouteMissing` for the second.
