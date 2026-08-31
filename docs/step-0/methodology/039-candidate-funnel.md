# 039 — The candidate funnel: every filter stage, and the point where the scope stops being the genome

**A step-0 platform entry, so it carries no hypothesis.** It records what was built, the
counts the executed derivation produced, one cross-check, and the two places the contract
carries a `NULL` on purpose.

## Question

The repository can already say *what* the candidate list is (`/api/panel/annotations`,
`results.panel_candidates`) but nothing says **how it got that short**. A reviewer's first
question about any N-of-1 shortlist is the funnel: how many records were there, what did
each filter remove, and is every removal defensible?

The honest complication is that **the funnel cannot be one funnel**. VEP annotation exists
for the eight-gene candidate panel only — 874 alleles in `warehouse.panel_annotations` —
and for nothing else in the genome. There is no genome-wide annotation in this repository
and therefore no genome-wide ranking. So: can the waterfall be derived and rendered in a
way that shows both segments and *labels the scope change* instead of letting a reader
slide from "5,012,204 records" to "1 pair" as though one screen produced the other?

## Inputs

| Input | Shape as read |
|---|---|
| `pg.warehouse.variants_raw` | 5,012,204 rows, all text, `FORMAT` + `sample_call` per record |
| `pg.warehouse.panel_variant_counts` | 8 rows, one per panel gene, `n_all` / `n_pass` |
| `pg.warehouse.panel_annotations` | 874 rows, one per VEP-annotated allele |
| Code | `src/mva/warehouse/analysis_funnel.py`, `src/mva/viz/queries.py`, `src/mva/viz/routes_warehouse.py`, `app/src/pages/compare/CandidateFunnel.tsx` |

Thresholds are not new here. `RARE_RECESSIVE_AF = 0.01` and
`PROTEIN_ALTERING = ('HIGH','MODERATE')` are imported from
`mva.warehouse.analysis_reference`, so the funnel and `panel_candidates` cannot drift apart.

## Commands run

```bash
uv run mva-warehouse pg-list                          # variants_raw = 5,012,204 rows
uv run mva-warehouse pg-derive --only candidate_funnel
uv run mva-viz-api --port 8943                        # own port; 8900 is the shared one
curl -s -w '%{time_total}' http://127.0.0.1:8943/api/callset/funnel   # ×3
uv run pytest -q
cd app && npm run typecheck && npm run build
```

The 215.8 s figure below comes from executing the same SQL read-only and timing it around
the fetch, so the write and the lineage append are excluded:

```python
from mva.warehouse.analysis_funnel import CANDIDATE_FUNNEL
from mva.warehouse.derivation import resolve
from mva.warehouse.postgres import attached
from mva.warehouse.settings import Postgres

s = Postgres.from_env()
with attached(s, read_only=True) as c:                 # 0.4 s
    rows = c.sql(resolve(CANDIDATE_FUNNEL.sql, f"pg.{s.schema}")).fetchall()
```

The cross-check of stage 4 recounts it straight from the callset, building the region
predicate through the one contig bridge:

```python
from mva.pipeline.variant import to_vcf_contig      # the single owner of the chr prefix

bed = c.execute(f'SELECT chrom, start, "end" FROM pg.{s.schema}.mva_panel_grch38').fetchall()
clauses = " OR ".join(
    f"(chrom = '{to_vcf_contig(chrom)}' AND CAST(pos AS BIGINT) BETWEEN {lo} AND {hi})"
    for chrom, lo, hi in bed)
c.execute(f"SELECT count(*), count(*) FILTER (WHERE filter = 'PASS') "
          f"FROM pg.{s.schema}.variants_raw WHERE {clauses}").fetchone()
```

## Observed output

### The executed stage table

Nine rows, straight from `results.candidate_funnel` as the endpoint serves them.

| # | Stage | Scope | n | % of previous | What the filter removes |
|---:|---|---|---:|---:|---|
| 1 | records called | genome | **5,012,204** | — | nothing; `COUNT(*)` over the delivered callset |
| 2 | FILTER = PASS | genome | **4,740,790** | 94.58 % | the caller's own vetoes (MQ40, QD2, LowQual) |
| 3 | heterozygous call | genome | **2,913,813** | 61.46 % | homozygous and no-call genotypes |
| 4 | inside a panel interval | panel | **841** | *n/a* | **scope change** — everything outside the 8 gene intervals |
| 5 | VEP-annotated allele | panel | **854** | 101.55 % | *widens*: unit changes from record to allele |
| 6 | rare in gnomAD | panel | **32** | 3.75 % | alleles at AF ≥ 0.01 in healthy people |
| 7 | protein-altering | panel | **2** | 6.25 % | LOW and MODIFIER consequences |
| 8 | in a gene carrying two or more | panel | **2** | 100.00 % | homozygotes, and lone alleles in their gene |
| 9 | candidate pairs | panel | **1** | *n/a* | unit changes from allele to pair |

Three of those rows need saying out loud.

**Stage 4 is not a subset of stage 3.** It counts PASS records of *every* genotype inside
the panel, so dividing it by the genome-wide het count would divide two different
populations. `of_previous_pct` is `NULL` there, and the note begins `SCOPE CHANGE`.

**Stage 5 is wider than stage 4, correctly.** `variants_raw` keeps a multi-allelic site
comma-packed in one record (`G -> A,C`) while `panel_annotations` is one row per ALT. 841
PASS records inside the panel carry 854 annotated alleles. Of the 874 annotated alleles,
**0 match no callset record** and **20 match only a filtered one**, which is where 874 − 854
goes.

**Stage 9 can be wider than stage 8.** k alleles in one gene give k(k−1)/2 pairs, so a gene
with four surviving alleles yields six pairs. Here k = 2 and the answer is one pair.

### The cross-check on the one borrowed number

Stage 4 reads `panel_variant_counts` rather than re-joining the panel BED to the callset,
because the BED is `chr`-prefixed and the callset is bare, and
`mva.pipeline.variant.to_vcf_contig` is the repository's single owner of that bridge
(`../notes/chr-prefix-bridge.md`). A second normaliser written in SQL is exactly the
failure mode that note exists to prevent.

So the shortcut was verified once, from Python, with the bridge used properly:

```
interval scan 59.9 s   n_all=861  n_pass=841
panel_variant_counts:  n_all=861  n_pass=841
```

Exact agreement. The shortcut costs nothing in accuracy and saves a second whole-contig
scan inside an already-expensive derivation.

### Cost

| Step | Cost |
|---|---|
| `ATTACH` to hosted PostgreSQL | 0.4 s |
| the derivation SQL, executed read-only | **215.8 s** |
| `pg-derive --only candidate_funnel` (SQL + write + lineage), wall clock | **3 min 55.9 s** |
| `GET /api/callset/funnel`, 9 rows | **0.48 – 0.54 s** (three runs; the attach dominates) |

The 215.8 s is two passes over the five-million-row callset pulled out of PostgreSQL: one
whole-genome aggregate for stages 1–3, and one restricted to the eight panel contigs for
the annotation join. That is the same order as `variant_density_bins`, and it is the reason
this is a precomputed table and not a query the HTTP request runs. The endpoint reads nine
rows.

### The chart: why log-x bars rather than Plotly's `funnel`

5,012,204 → 1 spans 6.7 decades. Plotly's `funnel` trace, and any linear bar, scale stages
6–9 to *zero pixels* — the interesting half of the argument becomes a blank strip. A
horizontal bar chart on a logarithmic x axis is the only encoding where all nine stages are
legible at once.

The cost is real and is stated in the exhibit's legend: on a log axis **bar length is no
longer proportional to count**, so the count is printed on every bar and tabulated in full
underneath. The scope change is drawn three ways at once — the bars change colour
(blue = genome machinery → purple = the panel-scoped input, green for the goal row), a
dashed yellow rule crosses the plot at the boundary, and an annotation on that rule reads
*"scope narrows — annotation exists only inside the 8-gene panel; stages below count panel
records only"*.

## Conclusions

1. **A funnel is the pipeline's argument, so every row has to carry its justification.**
   `note` is a column of the derived table, not a caption written next to the chart, which
   is why the JSON is as honest as the picture and why the note can quote numbers the SQL
   computed (`20 matched only a filtered one`, `1 gene(s) carrying at least two`).
2. **The scope change is a fact of the data and belongs in the schema.** `scope` is a
   column; `of_previous_pct` is `NULL` wherever the row is not a subset of the row above.
   A `0` or an invented ratio there would draw a cliff that did not happen.
3. **Unit changes are shown, not smoothed.** The waterfall widens twice — record → allele,
   allele → pair — and both are correct. A funnel that only ever narrows would have had to
   hide a multi-allelic site.
4. **Heterozygosity is tested generically.** `analysis_funnel.het()` builds the predicate
   as "two different non-missing allele indices" rather than `GT IN ('0/1','1/2')`, so a
   callset emitting `0/2`, `2/3` or a phased `0|1` is still read correctly. The phase
   separator is normalised before the predicate sees it.
5. **The bottom row is a shape, not a diagnosis.** One candidate pair, with phase unproven —
   nothing here shows the two alleles sit on different parental copies, and with one sample
   and no parents this callset cannot settle it. The exhibit says so in a callout, and so
   does the stage note.

## What this does *not* establish

- **No genome-wide ranking exists.** Stages 4–9 are measurable only inside the panel. A
  causal pair in a ninth gene would never enter this funnel, because there is no annotation
  to filter it with. The chart labels that; it does not fix it.
- **Stage 3 is not a candidate stage.** A genome-wide het count is a denominator, not a
  shortlist. It is in the funnel to show the scale the panel restriction is escaping, not to
  imply 2.9 million candidates were evaluated.

## Tests

`tests/test_warehouse_funnel.py`, 35 tests, hermetic: the real derivation SQL runs against
a DuckDB schema of eleven synthetic records and eight synthetic annotations, chosen so that
**every stage drops exactly one thing for exactly one reason** — a homozygote, a common
allele, a filtered record, a MODIFIER consequence, an annotation with no callset record, a
contig outside the panel, a no-call, and a `FORMAT` that does not start with `GT`. Also
covered: the het predicate over fourteen genotype spellings including phased and no-call,
the multi-allelic membership join refusing an invented `TG` allele, the two `NULL` shares,
the pair count widening from 3 alleles to 6 pairs when a fourth allele lands, and a callset
with no surviving pair reporting `0` rather than `NULL`.

`tests/test_viz_funnel.py`, 11 tests, hermetic: `queries.fetch` is replaced, so a failure
means the route, the ordering or the envelope is wrong. Covered: the envelope, the source
string naming `pg.results.candidate_funnel`, the `callset` OpenAPI tag, the six-column
contract, stage order, both scopes surviving the round trip with the genome rows first,
`NULL` reaching the client as `null` at stages 1/4/9, and `SCOPE CHANGE` present in the
payload rather than only in the chart.

`uv run pytest -q` → **925 passed**, 11 failures, all pre-existing in
`tests/test_reads_api.py` and unrelated to this change.
`cd app && npm run typecheck && npm run build` → both clean.
