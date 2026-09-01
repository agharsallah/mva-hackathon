# 042 — Universal search: resolving a typed query against the live callset

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
two measured bake-offs that decided the design, and the contract facts that follow from
them.

## Question

Every panel in the viz app starts from a list the server chose: the eight candidate genes,
the 25 contigs, the 38 tables. Nothing let a reviewer ask about **a locus we did not
pre-select** — a gene from a paper, a coordinate from a colleague, an rsID from ClinVar.

Three sub-questions had to be answered by measurement, not by assumption:

1. **How wide a window can the raw callset layer serve?** It is 5,012,204 all-text rows
   and the existing `/api/panel/locus` route already needs ~8 s for one gene. Where does
   an arbitrary region stop being affordable, and *what* actually makes it stop?
2. **How should an rsID be resolved?** A live scan of `variants_raw.id` was expected to be
   ~20 s and therefore unusable; Ensembl REST was expected to win. Is that true?
3. **Can "unknown name" stay distinct from "real place, never called"?** A search box that
   collapses those two teaches the user that absence means "not sequenced".

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 rows, every column `character varying`, **no index** |
| `pg.warehouse.mva_panel_grch38` | the staged panel BED — gene symbol → interval, `chr`-prefixed |
| `https://rest.ensembl.org/lookup/symbol/homo_sapiens/<symbol>` | gene interval, bare contig |
| `https://rest.ensembl.org/variation/human/<rsID>` | dbSNP placement, `mappings[]` |
| Code | `src/mva/viz/search.py`, `search_resolve.py`, `routes_search.py`; two lines in `routes_warehouse.py` |
| Page | `app/src/pages/Search.tsx` + `app/src/pages/search/` (SearchBox, Results, DensityStrip) |
| Tests | `tests/test_viz_search.py`, 72 tests, hermetic |

## Commands run

```bash
# the index question, answered rather than assumed
uv run python -c "…postgres_query('pg', 'SELECT indexname FROM pg_indexes
                  WHERE schemaname=''warehouse'' AND tablename=''variants_raw''')…"

# span cost and payload weight, one attached session so the ATTACH is paid once
uv run python scratchpad/measure.py      # 1 kb … 10 Mb, timed with perf_counter
uv run python scratchpad/measure2.py     # 5 Mb … 102 Mb, plus json.dumps byte counts

# the rsID bake-off, both mechanisms, three trials each
#   (a) SELECT chrom, pos FROM pg.warehouse.variants_raw WHERE id = ?
#   (b) GET https://rest.ensembl.org/variation/human/<rsID>

# the endpoints, live, on a private port
uv run mva-viz-api --port 8951
curl -s -w '%{http_code} %{time_total}s %{size_download}B' \
     'http://127.0.0.1:8951/api/callset/region?chrom=15&start=…&end=…&refresh=true'

uv run pytest -q                                  # 1078 passed, 11 pre-existing failures
cd app && npm run typecheck && npm run build      # both green
```

## Observed output

### Finding 1 — the raw layer has no index, and the scan is not the cost

`pg_indexes` for `warehouse.variants_raw` returns **zero rows**. Every read of that table
is a sequential pass over five million rows. The expectation was that a wider window would
therefore cost more. It does not:

| Window on one contig | Latency (2 trials) | Rows | JSON payload |
|---|---|---|---|
| 1 kb | 9.30 s cold / 1.56 s | 6 | <1 kB |
| 10 kb | 1.67 / 1.51 s | 34 | ~4 kB |
| 100 kb | 1.95 / 1.65 s | 80 | ~9 kB |
| 1 Mb | 1.81 / 1.38 s | 1,143 | 0.13 MB |
| 5 Mb | 1.44 / 1.57 s | 5,766 | 0.64 MB |
| 10 Mb | 1.79 / 1.62 s | 12,459 | 1.39 MB |
| 25 Mb | 2.19 s | 40,555 | 4.55 MB |
| 50 Mb | 2.11 s | 77,844 | 8.72 MB |
| 102 Mb | 2.23 s | 101,130 | **11.34 MB** |

Latency is flat at ~1.4–2.7 s across five orders of magnitude of span. PostgreSQL holds
the 1,338 MB database in its buffer cache, so the scan is memory-speed and the wire is the
bottleneck; the first 1 kb trial's 9.30 s is the cold cache, and it never recurs.

The `chrom` pushdown still earns its place: the same 100 kb window **without** the contig
constraint costs **5.46 s** and returns 3,481 rows from all 25 contigs, against **1.7 s**
and 80 rows with it.

**So the span cap is a payload and render guard, not a latency guard.** The cap is
**5,000,000 bp** — the widest window that keeps the answer under a megabyte of JSON and
under ~6,000 table rows, and wide enough to contain any human gene (the longest, RBFOX1,
is ~2.5 Mb). Anything wider is a `422` naming the cap. A latency-based cap would have been
*no cap at all*, and the page would hand a browser eleven megabytes for a whole chromosome.

### Finding 2 — the rsID bake-off, and why the answer is "both"

| Mechanism | Cold | Warm | Trials |
|---|---|---|---|
| (a) scan `variants_raw.id`, id **present** | 1.40 s | 0.76 / 0.98 s | 3 |
| (a) scan `variants_raw.id`, id **absent** | 0.90 s | 0.90 / 0.69 s | 3 |
| (b) Ensembl `variation/human/<rs>`, known | 0.49–0.94 s | 0.02–0.09 s | 6 |
| (b) Ensembl `variation/human/<rs>`, unknown | 0.41–1.29 s | — | 4 |

**The expectation was wrong.** The live scan was expected to be ~20 s and therefore
unusable; it is **under 1.4 s**, for the same buffer-cache reason as Finding 1. Both
mechanisms are viable on speed alone, so speed did not decide it — *what each can say* did:

- The scan is authoritative for **"it is here"** and **silent** for everything else. It
  cannot tell a misspelt rsID from a real variant this callset never called.
- Ensembl can tell them apart, but makes the common case depend on a third party.

So the resolver runs **both, in order**: the callset first (4,408,823 of the 5,012,204
records carry an rsID, so it usually hits, costs no network, and keeps working during an
Ensembl outage), then Ensembl only on a miss, purely to split *unknown id* from
*resolved-but-never-called*. Neither alone satisfies sub-question 3; the composition does.

Two supporting counts, both measured, both zero, and both load-bearing: **0** ids contain
a `;` and **0** non-`.` ids are anything but a bare `rs…`. Exact match is therefore correct
and a `LIKE` would only cost a scan it could not use.

### Finding 3 — Ensembl answers "no such name" with 400, not 404

Verified live:

```
GET /variation/human/rs99999999   -> 400 {"error":"rs99999999 not found for human"}
GET /lookup/symbol/homo_sapiens/NOTAGENE1234
                                  -> 400 {"error":"No valid lookup found for symbol NOTAGENE1234"}
GET /lookup/symbol/homo_sapiens/BUB1B  -> 200, 4.98 s cold, 0.06 s warm
```

`mva.viz.genestructure._get` maps **every** non-200 to `EnsemblError`, which is right
there — every id it sends comes from the committed panel, so a rejection really is a fault.
Here the name is typed by a user, so a 400 is the normal answer to a normal question. That
is the one reason `search_resolve._get` exists rather than reusing the other: it maps
400/404 to `NotFound` (**404** to the browser) and everything else to `EnsemblError`
(**502**). Reusing the existing helper would have reported every typo as an outage.

### Finding 4 — endpoint timings, live on port 8951

| Request | Status | Cold | Warm (cached) |
|---|---|---|---|
| `/api/search?q=BUB1B` (panel) | 200 | 1.13 s | 0.003 s |
| `/api/search?q=chr15:…-…` (region) | 200 | 0.003 s | not cached — nothing was looked up |
| `/api/search?q=TTN` (Ensembl symbol) | 200 | 1.72 s | 0.003 s |
| `/api/search?q=rs1042522` (callset scan) | 200 | 1.76 s | 0.003 s |
| `/api/search?q=rs137852899` (scan miss → Ensembl) | 200 | 5.42 s | 0.003 s |
| `/api/search?q=NOTAGENE1234` | 404 | 0.59 s | — |
| `/api/search?q=rs99999999` | 404 | 1.30 s | — |
| `/api/search?q=!!!` | 422 | 0.001 s | — |
| `/api/search?q=1:1-99000000` | 422 | 0.001 s | — |
| `/api/callset/region` 1 kb | 200 | 2.52 s | 0.006 s |
| `/api/callset/region` 100 kb | 200 | 1.85 s, 11,959 B | 0.006 s |
| `/api/callset/region` 1 Mb | 200 | 2.61 s, 168,295 B | — |
| `/api/callset/region` 5 Mb | 200 | 2.17 s, 847,700 B | — |
| `/api/callset/region` 5 Mb + 1 bp | 422 | 0.002 s | — |
| `/api/callset/region` bad contig | 422 | 0.001 s | — |

The 5.42 s worst case is the two-stage rsID path paying both stages — an 0.9 s scan miss
plus a cold Ensembl call — and it is cached afterwards.

### Finding 5 — the state the page exists to make legible, observed

`rs137852899` (a public ClinVar-cited site) resolves through Ensembl to chromosome 12 and
its ±1 kb window returns **2 records, neither at the resolved site**. The page states, in
the summary line above the table, that the position came from dbSNP and that an empty
table therefore means the site was never called. Without that line the same screen is
indistinguishable from a typo.

`chr99:1-2` is rejected at classification. `\d{1,2}` would have accepted it: the contig
pattern spells out `[1-9]|1\d|2[0-2]|X|Y|MT|M` instead, because this genome has 22
autosomes and `chr99` is a typo, not a contig to scan for.

## Conclusions

1. **Measure the cap's cause, not just its threshold.** The expected reason for a span cap
   — latency — is measurably absent. The real reason is payload and browser render, and it
   sets a different number (5 Mb, not "whatever answers in 2 s", which is everything).
2. **A bake-off can end in "both".** The scan and Ensembl cost the same order of
   magnitude, so cost did not decide it; *expressiveness* did. Chaining them makes the
   common case network-free and the rare case honest, which neither achieves alone.
3. **Buffer cache, not indexes, is why the raw layer is usable at all.** Nothing here
   should be read as "the raw layer is fast": it is one sequential scan every time, and it
   stays affordable only because the database fits in RAM and the filter is pushed down.
4. **Four failure modes, four statuses.** 422 unparseable-or-too-wide, 404 unknown name,
   502 Ensembl down, 200-with-zero-rows resolved-but-absent. Collapsing any pair of them
   would make the page lie about a different thing each time.
5. **Two requests, not one.** Resolution is cheap, cacheable and shareable; the region read
   is the expensive one that carries real patient positions. Splitting them lets the page
   show *what the query meant and who said so* before paying for the scan.

## Contract facts a client must respect

- `chrom` is **bare** everywhere in these payloads, as the callset spells it.
- `id` is **null** where the VCF wrote `.` — the site has no dbSNP name in this callset.
- `ad_alt` and `vaf` are **null** at a `1/2` multiallelic site, the same convention
  `/api/panel/locus` uses, and `alt` stays comma-packed.
- `note` on a resolution is a caveat the UI must render, and is **null** when there is none.
- **`/api/callset/region` serves real patient positions.** Cached under gitignored
  `build/`, never written where git can see them. The committed fixture is a synthetic
  1,000,000-based ladder.

## Tests

`tests/test_viz_search.py`, **72 tests**, hermetic: Ensembl is an `httpx.MockTransport` in
the style of `tests/test_annotate_vep.py`, and the warehouse is a fragment-matched fake
`fetch` in the style of `tests/test_viz_api.py`. The outage test points the service at
`http://127.0.0.1:1`, so it exercises the real client on the real code path without a
packet leaving the machine. Covered: all three classifications and every accepted region
spelling, the refusal message naming all three forms, the contig pattern rejecting
`chr99`, the span cap at the boundary and one base past it, panel-before-Ensembl,
callset-before-Ensembl, the exact-match scan, the scaffold placement being skipped for the
chromosome one, a GRCh37-only reply being `NotFound`, the `.`-to-null id, the `1/2` nulls,
the pushdown ordering, the four HTTP statuses, the cache keys of two different windows, and
the resolved-but-empty window.

`uv run pytest -q` → **1078 passed**, 11 failures, all pre-existing in
`tests/test_reads_api.py` and unrelated. `npm run typecheck` and `npm run build` green.
