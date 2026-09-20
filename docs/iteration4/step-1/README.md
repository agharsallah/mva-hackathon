# Step 1 — The allele record

**Standing:** **run 2026-09-18/19**, protein windows added **2026-09-20** (wave 4, opt-A);
`P4-1a` filed as H058 and **supported**, `P4-1`'s protein half filed as H071 and **supported**;
the step is marked **done** in `src/mva/science/step_maps/iteration4.py`. Iteration 4, `step-1`.

**Goal** (from `steps.py`):

> Can every allele in scope be expressed as one normalized record that every model class can read — genomic change, transcript, protein change, DNA window, protein window — with lineage?

**Plan:** [`../plan.md`](../plan.md) §5, *Step 1*. MVP and optional substeps are labelled there.

## What happened

| Claim | Prediction | Verdict |
|---|---|---|
| H058 (`P4-1a`) | ≥ 99 % of coding alleles get a non-null `hgvs_c` or `hgvs_p` | **supported** — 0.99953 (38,069 of 38,087), confidence 0.95 ([114](methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md)) |
| H071 (`P4-1`, protein half) | ≥ 98 % of missense records get a complete protein window pair | **supported** — **99.821 %** (15,592 of 15,620), confidence 0.90 ([141](methodology/141-a-window-for-every-substitution-the-spelling-actually-describes.md)) |

**39,286 records**: 38,087 distinct coding alleles (from 38,437 allele rows) plus exactly the
1,199 alleles only the raw reads saw. One VEP REST pass at **release 116 / GRCh38**, 196
batches of 200, checkpointed per batch, **1 h 45 m** end to end. The 18 coding alleles with no
spelling at all are 14 alleles outside any transcript plus 4 singletons — no consequence class
the zoo scores is materially unspelled.

Two things the run found that change what follows:

- **`uniprot=1` is not served by Ensembl's POST endpoint** (HTTP 500, reproduced on a public
  example variant; the same option answers on GET). So `AlleleRecord.uniprot` is null for all
  39,286 records and the ESM1b lane's `ENSP` → UniProt mapping is step 2's problem.
- **O7 / risk R9: the lane gap hits the confirmed pair.** `BUB1B` carries exactly two alleles
  in the record set — one `missense_variant` and one `stop_gained`. Three of the four MVP lanes
  are missense-only and the fourth is a splice lane, so no MVP lane can score the `stop_gained`
  half by consequence class. **GPN-MSA's promotion into the MVP is due** (plan §10 R9); it is
  recorded in [`../todo.md`](../todo.md) and not built here.

### What wave 4 added (2026-09-20, entry 141)

The record now carries the one input a model that **runs** needs: the protein's own letters,
64 residues either side of the change, as the reference protein and again with the one letter
swapped.

- **15,592 of 15,620 missense records get a complete window pair — 99.821 %.**
- **Zero residue mismatches** over all 15,592: the residue `hgvs_p` spells equals Ensembl's
  sequence at that position every time. A window built on a disagreeing isoform looks exactly
  like a good one, so this check is the point of the exercise, not a formality.
- **No identifier lookup was needed.** The `ENSP` accession is `hgvs_p`'s own prefix, so the
  `uniprot = null` finding below does not block this lane the way it blocked ESM1b.
- The 28 without a window are all `delins` spellings replacing two or more residues — VEP
  calls them `missense_variant`, but a one-residue substitution model has nothing to score.
- The confirmed **missense** allele has a 113-residue window (clamped at BubR1's C-terminus).
  The confirmed **nonsense** allele has none, and must not: there is no mutant protein to
  window, which is why that half of the pair is GPN-MSA's job (entry 140), never ESM2's.
- DNA windows are still null — plan §5 labels them opt-B (`P4-1`'s DNA half, wave 5).

## Outputs

| Artifact | Where |
|---|---|
| the coordinate-free record set, 39,286 rows | `results.it4_allele_records` |
| the same rows **plus** the coordinate | `build/it4/records.parquet` (gitignored), sha256 `85da1380…` |
| inputs, parameters, row counts, digest, tool | `build/it4/records.provenance.json` |
| the lineage edge naming the four source tables | `warehouse.data_lineage`, `transform LIKE 'it4-allele-records%'` |
| the VEP answers, resumable | `build/it4/vep-hgvs/batch-*.jsonl` (gitignored) |

`protein_window_ref` / `protein_window_alt` are filled on 15,592 rows of the parquet and are
written **nowhere else** — not to `results.it4_allele_records`, not into an entry. A window is
patient sequence. `dna_window_*` stay null (opt-B).

The per-protein sequence cache is `build/it4/protein-seq/<ENSP>.json`, 8,732 files, gitignored.

## Tools this step needed

| Tool | Why |
|---|---|
| `mva.zoo.record` / `record_hgvs` / `record_write` | read → HGVS pass → write, with the coordinate kept beside the record and never inside it |
| `mva.zoo.types.allele_id` | the one key that leaves; computed identically in Python and in SQL |
| `mva.pipeline.annotate_vep` + `vep_response` | the REST transport, its retry policy, and `best_transcript` |
| `mva.warehouse.annotate_coding.Checkpoint` | per-batch resume — a crash costs one batch, not a morning |
| `mva.warehouse.lineage` | one edge per run, append-only, while the table is replaced |
| `mva.zoo.record_window` (wave 4) | `hgvs_p` → `(accession, position, ref, alt)`; the Ensembl sequence client with its rate-limit policy and per-accession cache; the window pair with its residue check; the in-place Parquet extension |

## Limitations

Stated by entry 114, beside the result rather than under it.

- **`uniprot` is null on all 39,286 records.** Ensembl's POST endpoint answers HTTP 500 for
  `uniprot=1` (reproduced on a public example variant), so the protein-accession column the
  ESM1b lane wants is empty and the lane joins through a gene-symbol bridge instead.
- **DNA windows are still null.** `protein_window_*` is filled (entry 141); `dna_window_*` is
  opt-B and waits for wave 5, so `P4-1`'s DNA half is not measurable yet.
- **A window is not a score.** Entry 141 measures that an input exists, not that any model can
  turn it into a useful number — that is step 3's measurement.
- **The pass adds, it never corrects.** An annotation already in the warehouse is kept as it is;
  the HGVS pass only fills what was missing.
- **One representative spelling per allele.** A change on several transcripts gets the canonical
  one, not all of them.
- **Release-bound.** Ensembl release 116 / GRCh38. Another release is another record set.
- **The catalogue fields are present** (`mask_catalogue=false`): masking is a scoring-time
  decision, and the record set carries `clin_sig` so both modes can be served from it.

## Reproduce

```bash
uv run python -c "
from pathlib import Path
from mva.warehouse.settings import Postgres
from mva.zoo import record
print(record.run(Postgres.from_env(), mask_catalogue=False,
                 out_dir=Path('build/it4'), timeout=300.0, batch_size=200, progress=print))"
shasum -a 256 build/it4/records.parquet   # against build/it4/records.provenance.json
```

## Methodology

[`methodology/114`](methodology/114-one-record-per-allele-and-what-it-can-be-spelled-as.md) —
the run, the two REST fixes it needed, the verdict, and the O7 answer.
