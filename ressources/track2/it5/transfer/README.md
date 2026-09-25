# `transfer/` — iteration 5's routes run on a second disease

**Standing:** written 2026-09-25 by the iteration-5 scalability run. Draft entry:
[`docs/iteration5/step-1/methodology/162-the-three-routes-on-bloom-syndrome.md`](../../../../docs/iteration5/step-1/methodology/162-the-three-routes-on-bloom-syndrome.md)
(unnumbered; the coordinator files it). Figure:
[`figures/it5/s1-transfer.svg`](../../../../figures/it5/s1-transfer.svg).

## What this is

Every table here is the **second case** — `BLM` / Bloom syndrome — produced by the *same* code
that produced iteration 5's `BUB1B` tables one directory up. The point is not the Bloom-syndrome
answer; it is the measurement of what moving to a second disease cost.

**No patient data.** The transfer case has no project patient. The `BLM` allele is a published
one (PMID 39174735, PMID 17407155) recorded in `r1/blm_allele_note.md`; no callset, no genomic
position, no HPO term of the child is read by any run here.

## Layout

| path | what it holds |
|---|---|
| `transfer_summary.tsv` | one row per route: config lines, code lines, control verdict, first-case byte-identity, wall clock |
| `transfer_diffstat.tsv` | the same, per file, with each file marked configuration or shared code |
| `r1/` | readthrough prediction, the **external check** against a held-out measurement of the same allele, the dosage ladder, and the allele note |
| `r2/` | proliferation-corrected `BLM` protein hits, the (reused) dataset control, candidate rows |
| `r3/` | corpus, the reader's raw rows, the quote-verified intervention and exposure tables, candidate rows |

Every `.tsv` has a `.provenance.json` beside it naming its inputs, parameters, assumptions,
limitations and validation.

## Read this before using r3/

**R3's declared positive control FAILED** (retrieval 3/3, extraction 0/3). Every row in
`r3/literature_candidates.tsv` carries `positive_control_passed = false` and **none of them is a
lead**. The failure and its diagnosis are in the entry. `r3/litmine_mva_exposures.tsv` keeps the
first case's word `mva` in its file name — the rows in it are Bloom-syndrome patients.

## Rebuild

```bash
BLM=(--gene BLM --card mva.drugs.readthrough_case_blm --accession P54132 \
     --build build/it5/transfer/r1 --tables ressources/track2/it5/transfer/r1 \
     --measurements build/it5/r1/toledano_ptc.tsv)
for stage in facts predict holdout dosage; do uv run python tools/it5_readthrough.py $stage $BLM; done

uv run python tools/it5_proteome.py run --target BLM --branch stop_allele \
  --out ressources/track2/it5/transfer/r2 --build build/it5/transfer/r2
uv run python tools/it5_proteome.py candidates \
  --out ressources/track2/it5/transfer/r2 --build build/it5/transfer/r2

R3=(--card it5_litmine_params_blm --build build/it5/transfer/r3 \
    --out ressources/track2/it5/transfer/r3)
uv run python tools/it5_litmine.py corpus $R3 && uv run python tools/it5_litmine.py screen $R3
uv run python build/it5/transfer/r3/extract_rows.py      # the reader's rows (build artefact)
uv run python tools/it5_litmine.py verify $R3 && uv run python tools/it5_litmine.py translate $R3

uv run python tools/it5_transfer_summary.py && uv run python tools/render_it5_s1.py
```

The first case is rebuilt with the same commands minus every flag.
