# 050 — The pair comparator and the probe hand-off

> **Redacted 2026-09-05** ([075](075-coordinate-gate-and-redaction.md)): this entry originally quoted the two
> candidate positions verbatim in the CSV row and the staged-pair line below. They are replaced by
> `<pos-1>` / `<pos-2>`. Nothing else in the entry was changed.

**A step-0 platform entry, so it carries no hypothesis.** It records what was added to `app/`
on top of [038](038-pair-matrix.md) (the pair matrix) and [046](046-probe-builder.md) (the
submission builder), and how it was verified against both fixtures and the live API.

## Question

The pair matrix draws the whole het × het grid and answers *where is phase resolved?*. It
cannot answer the question a submission row is actually built from: **is this specific pair
worth spending a rank on?** That needs the two alleles' evidence side by side — rarity,
consequence, ClinVar, and the read evidence under all of it — plus the phase verdict for the
cell they form. And once the answer is yes, the pair still had to be re-entered by hand into
the builder, which is the one place a coordinate gets retyped.

So: can any two heterozygous alleles of one panel gene be compared field by field, given a
pair verdict, and handed to the probe builder without a single value being retyped or a
single number being derived in the browser?

## Inputs

| Input | Version / shape |
|---|---|
| `GET /api/panel/het-pairs?gene=` | live on `127.0.0.1:8900` — `{variants, pairs, summary}`, `mva.viz.phase` |
| `POST /api/probe/build` | live — `{csv, valid, problems, self_test}`, `mva.viz.probebuild` |
| `GET /api/panel/genes` | live — the gene picker's option list |
| Existing app | `app/` at commit `40eb901` plus the concurrent session's working tree |
| Fixture | `app/src/fixtures/panel-pairs.ts` — **unchanged**, it already plants all five pair states |
| Node toolchain | vite 8.2.2, typescript 7.0.2 — **no new npm dependency** |

## What was built

**`pages/compare/PairComparator.tsx`** — a fourth exhibit on the Compare page, after the
candidate funnel. Gene `Select` plus two variant pickers; a three-column table (field, A, B)
over QUAL, VAF, DP, gnomAD AF, grpmax, consequence + IMPACT, ClinVar, GT, FILTER, rsID,
position and the raw phase fields; then the pair verdict; then the hand-off.

**`pages/compare/PairFields.tsx`** — the field declarations, split out for the 400-line rule.
It is a table of *what each column means*, not logic: null AF renders `novel`, an unannotated
allele's booleans render `unknown` rather than `false`, `vaf` null says why (`1/2` record),
and `FILTER` renders `PASS (by construction)` because **the endpoint has no filter column** —
it serves PASS het alleles only, and inventing a field would have been the alternative.

**`pages/compare/comparator.ts`** — the pure rules: index selection with its fallbacks, the
labels, the verdict lookup, the "worth probing" check, the hand-off encoding.

**No phase logic was reimplemented.** The verdict is `pairs.find(...)` over the payload's own
resolved-cell list, normalising `i`/`j` order. A cell not in the list is `unknown`, which is
the honest default and ~99.7 % of the grid ([006](006-phasing-power-on-bub1b.md)). The rule
itself stays owned by `mva.pipeline.compound_het.classify_phase`.

**Four verdict states, coloured by the repo's palette:** green resolved trans (proven compound
het), red resolved cis (excluded — the only verdict that kills a pair), yellow auto-trans (the
two ALTs of one `1/2` record, proven by genotype with no phasing), grey unknown, carrying the
~300 bp phasing-reach sentence so grey never reads as a rendering failure.

### The hand-off design

| Direction | Owner | Mechanism |
|---|---|---|
| write | `comparator.encodePairParam` | `/probes?pair=chrom:pos:ref:alt+chrom:pos:ref:alt`, percent-encoded (a bare `+` in a query string decodes to a space) |
| read | `probePayload.ingestPairParam` | `parseLines`, the builder's **existing** free-entry grammar |

One grammar, one parser. The parameter format was chosen to be exactly what the builder's
copy-paste box already accepts, so the reader is the module that owns that grammar and there
is no second parser to drift from it. `ProbeBuilder` stages the pair **once** on mount behind
a ref (React StrictMode double-mounts effects) and deletes the parameter, so a reload does not
re-add the row and the address bar stops advertising state that is now editable.

The second button, *copy CSV row*, POSTs the single pair at `epcr 0.99` to `/api/probe/build`
and copies the emitted **data row** — line 2 of the server's CSV. The browser never assembles
a CSV string; problems come back as the server's own `error` / `warning` list.

**Both buttons disable when the payload came from a fixture** (`origin === 'fixture'`, which
happens only when the API is unreachable), with the reason stated: fixture positions are
synthetic, and staging them would put invented coordinates in a submission file.

### URL keys added

| Key | Default | Meaning |
|---|---|---|
| `cmp.gene` | `BUB1B` | the comparator's gene — deliberately **not** the Panel page's `gene`, so one link never silently re-aims the other page |
| `cmp.a` / `cmp.b` | first two rare + protein-altering alleles | selection indices into the payload's `variants` |
| `pair` (on `/probes`) | absent | the hand-off; consumed and deleted on mount |

## Commands run

```
$ cd app && npm run typecheck        # tsc -b
$ npm run build                      # tsc -b && vite build
$ find src -name '*.ts*' | xargs wc -l | sort -rn | head

# fixture mode: the app pointed at a dead port so no request can reach a server
$ VITE_API_URL=http://127.0.0.1:9999 npx vite --port 5195 --host 127.0.0.1
# live mode: the default API URL, read-only against the running 8900
$ npx vite --port 5195 --host 127.0.0.1

$ uv run pytest -q
```

Browser checks were driven through Chrome DevTools on both servers: every verdict state
forced by URL, the hand-off followed end to end, and the console read after each.

## Observed output

**Typecheck and build:** clean. `Compare` chunk 40.95 kB → gzip 13.01 kB. Largest touched
file 346 lines (`PairComparator.tsx`), all under the 400-line rule — the first draft was 514
and was split into `PairFields.tsx`.

**Fixture mode** (`panel-pairs.ts`, synthetic positions):

| forced selection | rendered verdict |
|---|---|
| `cmp.a=0&cmp.b=1` (default) | `RESOLVED TRANS — A PROVEN COMPOUND HETEROZYGOTE` |
| `cmp.a=2&cmp.b=3` | `RESOLVED CIS — EXCLUDED` |
| `cmp.a=4&cmp.b=5` | `AUTO-TRANS — PROVEN BY THE 1/2 GENOTYPE ALONE` |
| `cmp.a=0&cmp.b=7` | `UNKNOWN PHASE — NEITHER PROVEN NOR EXCLUDED` |
| `cmp.a=99&cmp.b=x` | falls back to the default pair, silently |

Both hand-off buttons `disabled: true`, with the fixture reason rendered. Console clean apart
from the deliberate `ERR_CONNECTION_REFUSED` to the dead port that forces fixture mode.

**Live mode** against `127.0.0.1:8900`, gene BUB1B — 58 het alleles served. The default
selection landed on the two the recessive filter leaves:

```
field          A                                B
consequence    stop gained · rs759242053 · HIGH missense · MODERATE
ClinVar        pathogenic;likely_pathogenic     no assertion
gnomAD AF      3.3e-5                           novel
gnomAD grpmax  7.3e-5                           novel
QUAL           709                              345
DP             46×                              28×
VAF            0.543                            0.464
phase          unphased                         unphased
verdict        UNKNOWN PHASE — NEITHER PROVEN NOR EXCLUDED
```

*copy CSV row* returned, from the server:

```
PROBAND01,chr15,<pos-1>,T,G,chr15,<pos-2>,T,G,0.99,primary,"BUB1B compound-het candidate, phase unknown"
```

— chr-prefixed on the way out, bare on the way in, exactly as `mva.viz.probebuild` documents.

*add pair to probe builder* navigated to `/probes`, staged **one** row
(`15:<pos-1> T>G` + `15:<pos-2> T>G`, labelled `from the pair comparator`), and the `pair`
parameter was gone from the address bar. Console clean, zero errors.

**`uv run pytest -q`:** 12 failed, 1191 passed. Eleven are the pre-existing
`tests/test_reads_api.py` failures; the twelfth is `tests/test_warehouse_background.py`, an
untracked file belonging to another agent's concurrent work. **No Python was touched by this
entry.**

## Conclusion

Yes. Two alleles of one gene compare field by field with no number derived in the browser, the
verdict is a lookup in the server's own resolved-pair list, and the pair reaches a validated
submission row in one click without a coordinate being retyped. The default selection on the
live BUB1B locus lands on the case's actual candidate pair — a ClinVar-pathogenic stop-gained
against a novel missense — and correctly reports that phasing says nothing about it.

What the exhibit **cannot** do is resolve phase. Unknown stays unknown; the comparator makes
that visible next to the evidence rather than hiding it behind a colour, which is the only
honest thing a client can do with a 300 bp measurement.
