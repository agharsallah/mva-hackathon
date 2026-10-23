# 141 — A window for every substitution the spelling actually describes

**Written:** 2026-09-20. **Step:** `step-1` (iteration 4). **Run:** G1/A1 of wave 4 (opt-A).
**Hypotheses tested:** H071 (the protein half of plan label `P4-1`).

Step 1's MVP record carries every *string* a lookup lane joins on. It does not carry the one
input a model that **runs** needs: the protein's own letters around the change. This run adds
them.

## Question

Can a wild-type and mutant amino-acid window be built for essentially every missense allele
in the record set from `hgvs_p` plus the Ensembl protein sequence — with **no extra identifier
lookup**, given that entry 114 measured `uniprot` as null for every record?

## Hypothesis and prediction

*Written before the run. Filed as H071 before it
(`mva-science hypothesis-add --iteration iteration4 --step step-1`).*

| | |
|---|---|
| **Statement** | The protein half of `P4-1`: a wild-type and mutant amino-acid window can be built for essentially every missense allele in the record set from `hgvs_p` plus the Ensembl protein sequence, with no extra identifier lookup. |
| **Prediction** | At least **98 %** of the 15,620 `missense_variant` records get a complete window pair, where *complete* means the Ensembl sequence for the `ENSP` accession `hgvs_p` names was fetched **and** its residue at the named position equals the reference residue `hgvs_p` spells. |

## What would refute it

*Written before the run.*

> Fewer than **90 %** of missense records get a complete window pair.

The residue check is part of the definition of *complete*, not a separate test, and that is
deliberate: a window built on a different isoform looks exactly like a good one, would be
scored with full confidence, and would be a window of the wrong protein.

## Inputs

| input | what it is |
|---|---|
| `build/it4/records.parquet` | 39,286 records; **15,620** are `missense_variant` (entry 114) |
| `hgvs_p` | e.g. `ENSP00000287598.7:p.Asn1002Lys`. The `ENSP` accession is the string's own prefix — which is why no identifier lookup is needed, and the reason entry 114's `uniprot = null` finding does not block this |
| Ensembl REST | `POST https://rest.ensembl.org/sequence/id?type=protein`, 50 accessions per request, **8,732 distinct accessions** |
| cache | `build/it4/protein-seq/<ENSP>.json`, one file per protein — gitignored; protein sequence never leaves `build/` |
| parameters | `radius = 64` → a 129-residue window; `mva.zoo.record_window` |

## Commands

```python
# uv run python - (the whole driver; the entry is the record of it)
from mva.zoo import adapters, record_window

records = adapters.records_from_parquet("build/it4/records.parquet")
missense = [r for r in records if r.consequence == "missense_variant"]
windows, report = record_window.protein_windows(
    missense, cache=record_window.SequenceCache("build/it4/protein-seq"), radius=64
)
record_window.write_windows("build/it4/records.parquet", windows)
```

Log: `build/it4/r8-windows.log`; report JSON: `build/it4/window-report.json`.

## Results

Two passes. The first was run while the GPN-MSA fan-out was saturating the link; the second
re-asked only for what the cache was missing.

| | pass 1 (7,699 s) | pass 2 (144 s) |
|---|---|---|
| missense records considered | 15,620 | 15,620 |
| `hgvs_p` parsed as a one-residue substitution | 15,592 | 15,592 |
| sequence missing | **360** | **0** |
| **residue mismatch** | **0** | **0** |
| complete window pairs | 15,232 | **15,592** |
| fraction complete | 0.97516 | **0.99821** |
| clamped at a terminus | 5,677 | 5,825 |

Pass 1's 360 misses were 11 accessions the REST endpoint answered with HTTP 500 during the
contention; hand-run a minute later the same accessions answered 200. Pass 2 asked for 221
accessions and got every one, which is what the per-accession cache exists for.

Window lengths: min 24, max 129, mean 114.6 — the shortfall from 129 is clamping at a
protein's start or end, not truncation. 15,592 rows of `build/it4/records.parquet` now carry
`protein_window_ref` and `protein_window_alt`.

**The confirmed missense allele** (`p.Asn1002Lys`) has a window pair, 113 residues long: BubR1
is 1,050 residues and the change is at 1002, so the window is clamped 48 residues short at
the C-terminus. The confirmed **nonsense** allele has none, and must not — there is no mutant
protein to window, which is why the `stop_gained` half of the pair is GPN-MSA's job (entry
140) and never ESM2's.

### The 28 that could not be parsed

Every one is a `delins`: `p.Asp12_Leu13delinsHisGln` and 27 like it. VEP labels them
`missense_variant` because the consequence class is coarse, but they replace **two or more**
residues. A protein-substitution model scores one changed letter against one reference
letter, so these have no window by definition rather than by failure. They are 0.18 % of the
missense set and they are named here rather than rounded away.

## Verdict

**H071 supported** (confidence 0.9, committed with a stated reason).

99.821 % against a 98 % prediction and a 90 % refutation line. Recorded on pass 2's number,
with pass 1's in the table beside it: the difference is a busy server, not a property of the
method, and hiding either would misrepresent the run.

## Assumptions, limitations and quality checks

- **Zero residue mismatches over 15,592 alleles** is the strongest thing this run says. It
  means the `ENSP` accession in `hgvs_p` and the sequence Ensembl serves for it agree on
  every single position VEP named — the isoform hazard the check exists for did not fire
  once. It also means the check cannot be shown to *work* by this data alone; the unit tests
  cover the failing case instead.
- **The version suffix is dropped** (`ENSP00000287598.7` → `ENSP00000287598`). Ensembl serves
  the current version under the bare accession, so a record spelled against an older protein
  version would be caught by the residue check rather than silently mis-windowed. None was.
- **Clamping is not padding.** A window at a terminus is shorter, never filled with a
  placeholder residue, because a placeholder would be sequence the protein does not have and
  a language model would read it as such. 5,825 of 15,592 windows are clamped.
- **A window is patient sequence.** It is written to `build/it4/records.parquet` and to
  nothing else — not to `results.it4_allele_records`, not into this entry. No window appears
  in any tracked file; `tools/check_coordinates.py --quiet` is green.
- **This run says nothing about scores.** It says an input exists. Whether ESM2 can turn it
  into a useful number is step 3's measurement.
- **Rate limiting was the whole cost.** 8,732 accessions took 7,699 s on pass 1 and the
  server's 500s were being *bisected* by the client, which turned one rate-limited batch into
  99 requests. The fix — retry 429/500/502/503/504 with `Retry-After`, bisect only what
  survives four attempts, 0.2 s between requests — is why pass 2 took 144 s.
