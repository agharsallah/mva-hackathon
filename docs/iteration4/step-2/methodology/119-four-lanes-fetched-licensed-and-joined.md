# 119 — Four lanes, fetched, licensed, and joined to the record set

**Written:** 2026-09-19. **Step:** `step-2` (iteration 4). **Run:** R2 of the wave-2 chain.
**Hypotheses tested:** H059 (plan label `P4-2a`), H060 (plan label `P4-3`).

Follows [114](../../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md),
which produced the 39,286-record set this entry measures coverage against, and which left one
problem on step 2's doorstep: `AlleleRecord.uniprot` is null for every record, so the ESM1b
lane has no join key unless this step makes one.

## Question

Of the four MVP lanes the registry enables — AlphaMissense, SpliceAI, ESM1b (Brandes 2023) and
REVEL — which can actually be **fetched, licensed and joined** to `results.it4_allele_records`,
and what fraction of the callset does each one cover?

## Hypothesis and prediction

*Both written before the first command ran.* Filed as H059 and H060 by
`uv run mva-science hypothesis-add --iteration iteration4 --step step-2 … --by wave2`.

| Id | Statement | Prediction |
|---|---|---|
| **H059** (`P4-2a`) | All four MVP lanes run end-to-end on the iteration-4 record set on the laptop in one day. | Each of the four enabled cards in `src/mva/zoo/models.toml` can be fetched (or is already a warehouse column), is licensed for this use, and joins to `results.it4_allele_records` so that `mva-zoo coverage` reports a non-zero scored count for it. |
| **H060** (`P4-3`) | Every precomputed missense table that runs covers ≥ 90 % of the callset's missense alleles, EVE excepted (predicted < 30 %). | For each missense lane that runs, `mva-zoo coverage`'s by-consequence row for `missense_variant` shows `scored/total ≥ 0.90` of the **15,620** missense alleles in `results.it4_allele_records`. |

## What would refute it

*Both written before the first command ran, quoted from [`plan.md` §5](../../plan.md).*

> **H059** — any one of the four cannot be fetched, licensed or joined; then that lane is
> replaced from the opt-A list and the substitution is recorded.

> **H060** — any missense table other than EVE covers below 70 % of the callset's missense
> alleles.

Two correctness gates that are **not** hypotheses, taken from the *cache+adapters* agent's
hand-over (`build/it4/agents/cache-adapters.md`): AlphaMissense must report **10,601** scored
and SpliceAI **32,534** — the non-null counts of `warehouse.it2_insilico_annotations`. A
different number means the `allele_id` join is wrong, and nothing downstream is trustworthy
until it is fixed.

## Inputs

| input | size / rows | role |
|---|---|---|
| `results.it4_allele_records` | 39,286 records (15,620 `missense_variant`) | what coverage is measured against — [entry 114](../../step-1/methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md) |
| `warehouse.it2_insilico_annotations` | 38,087 rows; `am_pathogenicity` 10,601 non-null, `spliceai_ds_max` 32,534 non-null | the AlphaMissense and SpliceAI lanes — no download |
| `ALL_hum_isoforms_ESM1b_LLR.zip` | 1,335,361,543 bytes, sha256 `42b90ce7…`, 42,287 members | the ESM1b lane, MIT, from the authors' Hugging Face Space |
| Ensembl VEP REST, `REVEL=1` | per request | the catalogue-adjacent lane |

**Code.** `src/mva/zoo/registry.py`, `tools/fetch_zoo_tables.py`, `src/mva/zoo/adapters/*`,
`src/mva/zoo/tables.py` (new, this entry), `src/mva/zoo/adapters/protein_table.py` (new, this
entry). The digest was reproduced on **two independent downloads**, byte count and all.

## Commands

```bash
uv run python tools/fetch_zoo_tables.py --list
uv run python tools/fetch_zoo_tables.py --fetch esm1b                       # dry run
uv run python tools/fetch_zoo_tables.py --fetch esm1b --execute \
    --accessions build/it4/tables/esm1b.accessions.txt                      # 12,183 of 42,287
uv run python -c "from mva.zoo import registry as r; r.write_cards(r.load(), 'docs/iteration4/cards')"

uv run mva-zoo coverage --model alphamissense
uv run mva-zoo coverage --model spliceai
uv run mva-zoo coverage --model esm1b
uv run mva-zoo score --model revel --limit 200 --dry-run
uv run mva-zoo score --model revel --limit 200
```

## Observed

### The two warehouse lanes join correctly

| lane | scored / 39,286 | of the 15,620 missense | gate |
|---|---|---|---|
| **AlphaMissense** | **10,601** (27.0 %) | **10,601 — 67.9 %** | 10,601 expected ✓ |
| **SpliceAI** | **32,534** (82.8 %) | 13,163 — 84.3 % | 32,534 expected ✓ |

Both hit the pre-registered gate **exactly**, so the `allele_id` join between the record set
and `warehouse.it2_insilico_annotations` is right and everything downstream can be trusted.
AlphaMissense is missense-only by construction (0 in every other class); SpliceAI is the only
MVP lane with an opinion outside missense — it covers 216 of 289 `stop_gained` (74.7 %) and
4,471 of 5,490 `intron_variant` (81.4 %).

### O5 — which field REVEL answers under

Probed against a **public example variant**, not the callset:

```
POST /vep/homo_sapiens/region  {"variants": [...], "REVEL": 1, "hgvs": 1, "canonical": 1}
→ 200; transcript_consequences[0] = {"transcript_id": "ENST00000366667", "revel": 0.157, "canonical": 1}
→ the only REVEL-ish key anywhere in the reply: ['revel']
```

**The field is spelled `revel`**, lowercase — which is exactly the adapter's default
(`plugin.lower()`), so no card change was needed. O5 is settled by measurement, and CADD stays
declared-but-disabled with iteration 2's HTTP 500 as its reason.

A live 200-allele batch then wrote **52 scored rows** into `warehouse.allele_scores` with
`venue = vep-rest`, `licence = REVEL non-commercial`, and `aux = {"field": "revel", "mode":
"catalogue-free", "plugin": "REVEL"}`.

### Five fixes this run needed, each measured before it was applied

**1. The REVEL lane timed out, for step 1's reason.** `PluginAsker` sent
`QUERY_PARAMS + {REVEL: 1}`, so every allele carried the AlphaMissense and SpliceAI plugin
lookups and two gnomAD frequency joins *on top of* REVEL; a 200-allele batch read-timed out on
all five attempts. It now sends **only** `{REVEL: 1}` — the lane reads one field off the reply —
and `VepRestAdapter` carries its own `timeout` (300 s) rather than the transport's 60 s.

**2. `models.d/esm1b.toml`'s index column is not `column0`.** The converter excluded a column
named `column0`; the reader actually names the matrix's unheaded first column `column000` or
`column00000`, the width following the member's length. The name is now read from the file.

**3. DuckDB refuses a bound parameter as a `COPY` target** — `INTERNAL Error: Unsupported
parameter type for filename: expected e.g. TARGET 'file.parquet'`. Paths are interpolated as
quoted literals now.

**4. The accession regex matched the directory.** `regexp_extract(filename, '([^/]+?)_LLR', 1)`
returned `ALL_hum_isoforms_ESM1b` for every member, because the *folder* also ends `_LLR`. Every
row would have carried one fictitious accession and the lane would have covered nothing, with no
error. The accession now comes from the member's own file name.

**5. One `UNPIVOT` over a glob does not finish.** A matrix member's column names *are its
protein's residue positions*, so no two members share a schema and `union_by_name` over 42,287
of them asks DuckDB to reconcile hundreds of thousands of distinct column names. One statement
per member does work and was measured at **~1,000 members per 10 minutes** — two hours for this
lane. The reshaping moved to `mva.zoo.tables.unpivot_matrix_members` (Python `csv` + `pyarrow`),
which did the 12,183 members this case needs in **95 s, 169,457,840 rows**.

And one bug the fixes introduced, caught by a spot check rather than by a test: **`score_sign`
was applied twice**, once in the converter and once in the lane, so ESM1b returned **−11.537**
for a damaging change. The converted table now stores the publisher's numbers verbatim and
orientation belongs to the lane alone; the same allele now returns **+11.537**.

### ESM1b: fetched and licensed, but joinable only through a bridge

The record set carries **no UniProt accession at all** (entry 114: Ensembl's POST endpoint
answers `uniprot=1` with HTTP 500), and its `hgvs_p` is Ensembl-flavoured and three-letter
(`ENSP…:p.Arg550Gln`, 13,664 distinct `ENSP` ids). ESM1b's table is keyed by a UniProt accession
*with isoform suffix* and a one-letter change (`R550Q`). Neither half of that key exists.

The archive ships its own bridge — `contents_u_df.csv`, 42,286 rows of accession → gene — so a
new lane (`mva.zoo.adapters.protein_table`) joins `gene` + a translated `hgvs_p`. It is safe
because **the wild-type residue is part of the key**: an isoform whose residue 550 is not an
arginine has no `R550Q` row and cannot match. The cost is coverage, not correctness:

| | |
|---|---|
| genes in the publisher's map, of the 7,383 carrying a missense allele | **3,169 (42.9 %)** |
| missense alleles in a mapped gene | 6,322 / 15,620 (40.5 %) — the ceiling |
| **missense alleles ESM1b actually scores** | **4,562 / 15,620 — 29.2 %** |

The gap between 40.5 % and 29.2 % is the guard doing its job: residue numbering that does not
agree between the Ensembl protein and any UniProt isoform of that gene yields no row.

### The confirmed pair, per lane

| lane | missense allele `93e077ae83ac2642` | `stop_gained` allele `addc19de8fa29228` |
|---|---|---|
| AlphaMissense | **scored**, `am_class = likely_pathogenic` | **not scored** (missense-only) |
| ESM1b | **scored**, 11.537 | **not scored** (missense-only) |
| REVEL | missense-only — a full pass decides | **not scored** (missense-only) |
| SpliceAI | scored, `ds_max` **0.00** | scored, `ds_max` **0.03** |

This sharpens entry 114's O7 answer into a measurement: **SpliceAI is the only MVP lane that
can see both halves of the confirmed pair, and what it sees is "no splice effect" in both.**
Because `mva.zoo.rank` scores a pair as `(min, max)` of its two allele scores and *excludes* a
pair one of whose alleles is unscored, the three missense lanes will have **no opinion** on the
confirmed pair, and SpliceAI will rank it by two near-zero numbers. That is the state in which
`P4-6` and `P4-8` will be tested; it is recorded here, before those runs, so the result cannot
be read as a surprise.

## Evidence recorded

| evidence | direction | claim |
|---|---|---|
| all four lanes fetched, licensed and joined; each reports a non-zero scored count | supports | H059 |
| AlphaMissense 10,601 and SpliceAI 32,534 — the pre-registered join gates, exactly | supports | H059 |
| ESM1b joins only through a gene-symbol bridge, and covers 29.2 % of missense | refutes | H060 |
| AlphaMissense covers 67.9 % of missense — below the 70 % refutation line | refutes | H060 |

## Verdict

**H059 (`P4-2a`) — supported, confidence 0.80.** All four MVP lanes ran end-to-end on the real
record set inside one day: two are warehouse columns that joined on the first attempt and hit
their gates exactly, one is a live REST plugin that answered 52 of 200 alleles, and one is a
1.24 GiB download that is MIT-licensed, digest-reproduced on two downloads, converted, and
joined. Held below the suggested number because "runs end-to-end" is doing real work for ESM1b
only via a bridge this entry had to build, and because the four lanes needed five fixes — the
claim is about feasibility, and feasibility here was not free.

**H060 (`P4-3`) — refuted.** The claim was that every precomputed missense table covers ≥ 90 %
of the callset's missense alleles, refuted below 70 %. Both missense tables are below the
refutation line: **AlphaMissense 67.9 %**, **ESM1b 29.2 %**. The prediction was wrong in the
same direction twice, for two different reasons:

- **AlphaMissense** is not served here from the published genome-wide table but from
  `it2_insilico_annotations`, which iteration 2 filled through VEP's REST plugin. That plugin
  answers for the transcripts it has, not for every missense allele in a callset. The 90 % in
  the plan is a property of the *published table*; 67.9 % is a property of *this delivery of
  it*. Naming that difference is the finding.
- **ESM1b** is keyed on a protein namespace the record set does not carry, and the gene-symbol
  bridge reaches 42.9 % of the relevant genes because UniProt's gene names are not always the
  HGNC symbol.

**What follows, pre-registered here:** the plan's response to a refuted `P4-3` is not to widen a
threshold but to report coverage per class, which this entry does. A new revision of `P4-3` is
due when a lane is added (plan §5 step 2), and the honest way to raise AlphaMissense's number is
to fetch the published table rather than to re-ask REST — opt-A work, not done here.

## Limitations

- **The remote lane's `coverage()` is an estimate, and it reads 100 %.** `mva-zoo coverage
  --model revel` reports every record as covered because the lane cannot know what the server
  will answer until it asks. The real number is the scored count after a pass; the 200-allele
  sample gave 52. Do not quote REVEL coverage from `coverage`.
- **ESM1b's parquet is a subset**, 12,183 of 42,287 members — every accession whose gene this
  case carries. It is the plan's tier-1 rule (§10 R7) and it makes the conversion minutes, but
  the file cannot be reused for another case without re-running the fetch with that case's
  accession list.
- **The gene-symbol bridge is weaker than an accession join.** A UniProt → Ensembl protein
  mapping (UniProt's `HUMAN_9606_idmapping`) would raise ESM1b's coverage and remove the symbol
  dependency; it is a download and a join, and it is not done here.
- **`P4-2a` says nothing about usefulness.** Three of the four lanes are missense-only, which is
  a fact about the MVP roster, not about this run — see the confirmed-pair table above.
- **Nothing here is scored at scale yet.** Only 52 REVEL rows are in the cache; the full passes
  are step 3's run.

## Next test

Step 3 (R3): `mva-zoo score` over all four lanes, the no-op re-run that proves the cache key,
and the `--mode aware` pass for the catalogue ablation — where `P4-4a` (≤ 1 h laptop, $0) is
settled.
