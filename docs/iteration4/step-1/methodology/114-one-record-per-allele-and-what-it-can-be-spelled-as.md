# 114 — One record per allele, and what it can be spelled as

**Written:** 2026-09-18. **Step:** `step-1` (iteration 4). **Run:** R1 of the wave-2 chain
([`plan.md` §7b](../../plan.md)). **Hypotheses tested:** H058 (plan label `P4-1a`).

First entry of iteration 4. It opens step 1, answers the plan's open item **O7** (risk R9 —
does the confirmed pair fall in a consequence class an MVP lane can see), and produces the
record set every later run in the chain reads.

## Question

Can the child's ~39,300 in-scope alleles — 38,437 coding rows from `results.coding_alleles`
plus the 1,199 alleles only the raw reads saw — be expressed as **one normalized record**
(`results.it4_allele_records`) that every model class can key on, with a protein- or
cDNA-level spelling (**HGVS notation** — the standard text form of a change, e.g.
`ENSP…:p.Arg550Ter`) for essentially all of them, and with full lineage?

## Hypothesis and prediction

*Written before the first command ran.* Filed as H058 by
`uv run mva-science hypothesis-add --iteration iteration4 --step step-1 … --by wave2`.

| | |
|---|---|
| **Statement** | `P4-1a`: at least 99 % of the callset's coding alleles get a non-null `hgvs_p` or `hgvs_c` from the VEP HGVS pass, so one normalized allele record can key every tier-1 model lookup. |
| **Prediction** | The step-1 run's `RunSummary` reports `p4_1a_fraction ≥ 0.99` over the coding (non read-only) alleles of `results.it4_allele_records`. |

## What would refute it

*Written before the first command ran.*

> `p4_1a_fraction` below **0.95** — then the failing consequence class is named from
> `RunSummary.by_consequence` and tier-1 coverage is reported per class.

Between 0.95 and 0.99 the claim is neither supported nor refuted by its own terms; the entry
says so and the gap is named rather than rounded away.

Two gates that are **not** hypotheses, only correctness conditions on the pass:

* `RunSummary.read_only` must be **1,199** and `RunSummary.total` ≈ **39,300**; a much
  smaller total means the read-only union or the id dedupe mis-fired.
* `records.provenance.json`'s `sha256` must equal `sha256sum build/it4/records.parquet`, and
  exactly one `warehouse.data_lineage` edge must carry `transform = 'it4-allele-records'`.

## Inputs

| input | rows | role |
|---|---|---|
| `results.coding_alleles` | 38,437 | the callset's coding alleles (allele rows, so one variant with two ALTs is two rows) |
| `warehouse.coding_annotations` | 38,087 | iteration-2 VEP layer: gene, consequence, impact, gnomAD AF, ClinVar |
| `warehouse.it2_insilico_annotations` | 38,087 | the same plus AlphaMissense and SpliceAI columns |
| `warehouse.it2_read_annotations` | 1,199 | the alleles only the raw reads saw ([data-findings §6.3](../../../../ideation/data-findings.md)) |
| Ensembl VEP REST | — | **release 116, assembly GRCh38**, read from the server, not assumed |

Row counts are the manifest's own `inputs` block and match
[`ideation/data-findings.md` §6](../../../../ideation/data-findings.md).

**Code.** `mva.zoo.record` / `record_hgvs` / `record_write` (agent *record*, wave 1),
`mva.zoo.types.allele_id` (wave 0). Parameters: `mask_catalogue=false`, `batch_size=200`,
`timeout=300.0`, `base_url=https://rest.ensembl.org`.

### Two fixes this run needed, both measured before being applied

The pass as delivered could not run. Neither failure was in the callset.

**1. `uniprot=1` is not served by the POST endpoint.** The first smoke run died with
`VepError: POST /vep/homo_sapiens/region gave up after 5 attempts (500 server error)`.
A four-cell probe against a **public example variant** (Ensembl's own documentation line, not
this callset) separated the option from the data:

| payload | reply |
|---|---|
| `QUERY_PARAMS` (the annotation pass's set) | **200**, `transcript_consequences[]` carries `hgvsc`, `hgvsp`, `alphamissense`, `spliceai` |
| `uniprot=1` alone | **500** |
| `QUERY_PARAMS` + `uniprot=1` | **500** |
| `hgvs=1` + `uniprot=1` | **500** |
| GET region endpoint, `uniprot=1` | **200**, and `swissprot` + `uniparc` are present |
| `QUERY_PARAMS` + `protein=1` (POST) | **200**, adds `protein_id` (the Ensembl `ENSP`) |

So the option works on **GET** — one variant per request, not a route for 39,286 alleles —
and is unserved on **POST**. Same class of fact as
`annotate_vep.UNAVAILABLE_PARAMS = ("CADD", "LoF")`, which iteration 2 recorded for the same
server. `protein=1` does answer on POST, but returns the `ENSP` accession that `hgvs_p`
already carries as its own prefix, so it buys nothing.
**Fix:** `record_hgvs.EXTRA_PARAMS` is now `{}`, with the measurement in its docstring.
**Consequence, not worked around:** `uniprot` is null for all 39,286 records, and the ESM1b
lane's `ENSP` → UniProt mapping becomes step 2's problem.

**2. The annotation pass's payload times out at 200 alleles.** With `EXTRA_PARAMS` empty the
second smoke run died with `ReadTimeout` on every one of five attempts. `QUERY_PARAMS` asks
for the `AlphaMissense` and `SpliceAI` plugins and two gnomAD frequency joins *per allele* —
none of which this pass reads (`_fill` takes five fields: `transcript`, `hgvsc`, `hgvsp`,
`uniprot`, `consequence`) and all of which are already columns of
`warehouse.it2_insilico_annotations`. Iteration 2's own pass hit the same wall and dropped to
50 alleles and 300 s (`tools/annotate_it2_insilico.py`, whose `--batch-size` help text says
so). **Fix:** `record_hgvs.LEAN_PARAMS = {hgvs, canonical, variant_class}` — `canonical`
because `vep_response.best_transcript` breaks ties on it. The full 200-allele batch then
answered in seconds.

Both fixes are in `src/mva/zoo/record_hgvs.py` and change *what is asked for*, never what is
recorded.

## Commands

```bash
# smoke — 200 alleles, one batch, a throwaway out_dir
uv run python -c "
from pathlib import Path
from mva.warehouse.settings import Postgres
from mva.zoo import record
print(record.run(Postgres.from_env(), mask_catalogue=False,
                 out_dir=Path('build/it4/smoke'), limit=200, timeout=300.0, progress=print))"

# the full pass — 196 batches of 200, checkpointed per batch, resumable
uv run python -c "
from pathlib import Path
from mva.warehouse.settings import Postgres
from mva.zoo import record
print(record.run(Postgres.from_env(), mask_catalogue=False,
                 out_dir=Path('build/it4'), timeout=300.0, batch_size=200, progress=print))"
#   equivalently: uv run mva-zoo records   (the CLI verb, at the 60 s default timeout)

# verification
shasum -a 256 build/it4/records.parquet          # against records.provenance.json
```

## Observed

Copied from the run's own `RunSummary`, not retyped from memory.

| field | value |
|---|---|
| `run_id` | `it4-records-20260918T211517Z` |
| `total` | **39,286** |
| `coding` | **38,087** |
| `read_only` | **1,199** |
| `with_hgvs_c` | 39,267 |
| `with_hgvs_p` | 29,492 |
| `uniprot` non-null | **0** (see fix 1) |
| `transcript` non-null | 39,285 |
| **`p4_1a_fraction`** | **0.9995273977997742** |
| `asked` / `resumed` | 39,086 / 200 |
| `source` | `ensembl-vep-rest release=116 assembly=GRCh38` |
| `sha256` | `85da1380470441a58ce34bdbfbece0ee223ea7fae882b14d3f376a5399c962fb` |
| wall-clock | **6,317.5 s = 1 h 45 m 18 s** |

`total` 39,286 = 38,087 distinct coding alleles (from 38,437 allele rows, so 350 rows collapse
on the id — two contig spellings or a repeated row) + 1,199 read-only. `read_only` is exactly
the 1,199 expected; both correctness gates hold.

**The 18 coding alleles with neither spelling**, by consequence class — the whole of the
0.047 % the claim misses:

| consequence | in class | unspelled |
|---|---|---|
| `upstream_gene_variant` | 9 | **9** |
| `downstream_gene_variant` | 5 | **5** |
| `stop_gained` | 278 | 1 |
| `intergenic_variant` | 1 | 1 |
| `3_prime_UTR_variant` | 489 | 1 |
| `incomplete_terminal_codon_variant` | 2 | 1 |

Fourteen of the eighteen are alleles **outside any transcript** (`upstream`, `downstream`,
`intergenic`): VEP has no cDNA to spell them against, so the absence is correct rather than a
gap. One read-only allele is also unspelled; read-only alleles are excluded from the claim's
denominator by construction (they have no VCF row).

**Digest and lineage.** `shasum -a 256 build/it4/records.parquet` =
`85da1380470441a58ce34bdbfbece0ee223ea7fae882b14d3f376a5399c962fb`, equal to the manifest's
`sha256`. `warehouse.data_lineage` holds **two** `it4-allele-records` edges — the smoke's
(200 rows, digest `41ff341c…`) and the full pass's (39,286 rows, digest `85da1380…`). The
table is *replaced* per run while the edge list is append-only, which is the design: the
39,286-row edge is the current state, the 200-row edge is the audit trail of the smoke.

**Cost note, for step 3's budget.** Of the 6,317 s, the 196 VEP batches took ≈ 3,100 s and the
**per-row `INSERT` of 39,286 rows into a remote Postgres took ≈ 2,900 s** (measured by polling
the row count from a second connection: 20,673 rows at ~22 min, 33,955 at ~37 min). That is a
`executemany` of single-row inserts over a network link, not a VEP cost, and it is the obvious
thing to batch before any lane re-runs this step.

## O7 — the confirmed pair's consequence classes, and which lanes can see them

Plan open item **O7** / risk **R9**. `gene = 'BUB1B'` selects exactly **two** alleles in the
record set — the confirmed pair, and nothing else to disambiguate:

| allele_id | consequence | `hgvs_c` | `hgvs_p` | `clin_sig` | `af_gnomad` |
|---|---|---|---|---|---|
| `93e077ae83ac2642` | **`missense_variant`** | yes | yes | *(null)* | *(null)* |
| `addc19de8fa29228` | **`stop_gained`** | yes | yes | `pathogenic;likely_pathogenic` | 3.286e-05 |

Exactly the stop_gained + missense the brief predicted. What that means per MVP lane, from the
lanes' own input classes (`src/mva/zoo/models.toml`):

| lane | class it scores | missense allele | stop_gained allele |
|---|---|---|---|
| AlphaMissense | missense only | **yes** | **no** |
| ESM1b (Brandes) | missense only | yes *if* the UniProt join can be made (fix 1) | **no** |
| REVEL (catalogue-adjacent) | missense only | **yes** | **no** |
| SpliceAI | splice windows, any SNV in range | probably not | **only if it falls in a splice window** |

**The lane gap hits the pair.** Three of the four MVP lanes are missense-only and cannot score
a `stop_gained` allele at all; the fourth is a splice lane. The zoo's pair score is
`(min, max)` of the two allele scores, and `mva.zoo.rank` **excludes** a pair one of whose
alleles is unscored rather than scoring it zero — so unless SpliceAI happens to cover the
stop_gained allele, every MVP lane will report *no opinion* on the confirmed pair and claims
`P4-6` and `P4-8` will have nothing to measure.

Plan §10 risk R9 pre-registered the response: **promote GPN-MSA** (opt-A, tier 1, precomputed,
scores any SNV including nonsense and non-coding) into the MVP. This entry records the
promotion as **due**; it is written into [`todo.md`](../../todo.md) and **not built here** —
building it is opt-A work, and the chain's next run is step 2. Which lanes in fact cover which
allele is a *measurement*, and it belongs to step 2's coverage run, not to this entry's
class-level reasoning.

## Evidence recorded

| evidence | direction | claim | source |
|---|---|---|---|
| `p4_1a_fraction` = 0.99953 over 38,087 coding alleles | supports | H058 | this entry |
| 18 unspelled alleles, 14 of them outside any transcript | supports | H058 | this entry |
| `total` 39,286 = 38,087 + 1,199; `read_only` exactly 1,199 | supports | H058 | this entry |

## Verdict

**H058 (`P4-1a`) — supported, confidence 0.95** (`mva-science verdict H058 --commit`,
revision 3). `p4_1a_fraction = 0.9995` clears the 0.99 threshold the claim
named and is nowhere near the 0.95 that would refute it. The prediction was written before the
run and the number was computed by `record_write.summarise`, which judges nothing.

The weighing suggested **0.97**; **0.95** was committed, because the three evidence rows are
counts off one run of one pass and are not independent the way the log-odds sum treats them.
The weighing is a transparent triage heuristic, not a calibrated posterior.
*Revision 2 of H058 recorded the suggested 0.97 by omitting `--confidence`; revision 3
supersedes it and says so, because the register is append-only.*

The refutation clause ("name the failing consequence class") is answered anyway, because a
claim that passes still owes its residue: the 18 misses are 14 alleles outside any transcript
plus 4 singletons, and no consequence class the zoo scores is materially unspelled.

**What the claim does *not* say.** It is about *spelling*, not *coverage*. 29,492 of 39,286
records carry `hgvs_p`; the other 9,794 are alleles with no protein change to spell (intronic,
synonymous, UTR), and how many of them any lane can score is step 2's question.

## Limitations

- **`uniprot` is null everywhere**, so the ESM1b lane has no join key from this pass. Recorded,
  not worked around; step 2 must map `ENSP` → UniProt or the lane's coverage is 0 by
  construction.
- **No sequence windows.** `protein_window_*` and `dna_window_*` are columns of the parquet and
  stay null (plan §5, opt-A/opt-B). Claim `P4-1` (window completeness) is not measurable yet.
- **The pass adds, it never corrects.** A field the warehouse already carried wins over VEP's,
  so a wrong `consequence` upstream stays wrong here.
- **One representative spelling per allele.** Where one allele appears under two contig
  spellings, `min()` picks the representative, so the parquet's `chrom` is deterministic but
  not necessarily the one a reader would guess.
- **Release-bound.** Every HGVS string here is Ensembl release 116 / GRCh38. The same query
  against a later release may legitimately pick a different transcript; that is why the release
  is read from the server and stored in `source` rather than hard-coded.
- **The catalogue fields are present** (`mask_catalogue=false`). Catalogue-free runs mask in
  memory at score time (`AlleleRecord.masked()`), never by rewriting this table.

## Next test

Step 2 (R2): fetch and convert the ESM1b table, then `mva-zoo coverage` for the four MVP lanes
over these 39,286 records — which is where `P4-2a` and `P4-3` are settled, where the
`ENSP` → UniProt problem is either solved or the lane substituted, and where the O7 lane gap
stops being an expectation and becomes a measurement.
