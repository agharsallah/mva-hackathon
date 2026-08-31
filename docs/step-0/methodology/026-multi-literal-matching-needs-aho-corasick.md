# 026 — Multi-literal matching needs the right automaton, and the noise floor is measured

**A step-0 platform entry, so it carries no hypothesis.** It records the server run that
falsified [025](025-many-probes-one-pass.md)'s fix, the second fix, and — the durable
scientific result — the delivery's k-mer noise floor.

## Question

025 replaced the probe cross join with one `regexp_matches` alternation, measured flat on
a laptop (20 probes = 1 probe = 0.8 s over 6M reads). Does it hold on the server against
all 1.07 billion reads?

## Finding first

**No — 32 minutes again, twice.** The regex alternation costs the server ~1.9 µs of
per-call overhead per read, and there are a billion calls. The fix that holds is a
**columnar multi-literal matcher** (Aho-Corasick with SIMD prefilters, via Polars
``str.contains_any``), which builds its automaton once per chunk instead of re-entering a
regex engine per row.

And on the way, the run delivered the number the variant work needs: **the noise floor.
Eighteen of nineteen single-base mutants of a real 31-mer are absent from all 1.07
billion reads; one appears in exactly one read.** A true allele at this depth is ~36
reads; sequencing error manufactures at most ~1. The separation is three orders of
magnitude wide.

## The server runs (observed)

```
$ time uv run mva-reads count --root /root/mva-staging/reads/ --kmers-file probes.tsv
               probe     fwd     rev   total  lanes  verdict
                real      19      17      36      4  present
             mut_5_A       0       0       0      0  absent
             … 16 more mutants, all absent …
            mut_22_T       0       1       1      1  error-level
            mut_30_G       0       0       0      0  absent
20 probe(s) in one pass, 1934.2s
real    32m15s     user    241m23s
```

Run twice (2012.2 s, then 1934.2 s) — reproducible, not a fluke. For scale: a
single-probe `contains` scan of the same store is **185.5 s**
([024](024-the-kmer-strike-works.md)).

## Why the laptop lied twice

| Shape | Laptop, 6M reads, 20 probes | Server, 1.07B reads, 20 probes |
|---|---|---|
| cross join of `contains` | 14.7 s (18× one probe) | killed at 32m40s |
| `regexp_matches` alternation | 0.8 s (flat) | **1934 s (~10× one probe)** |
| Polars `contains_any` | 0.57 s (flat) | *pending — the command below* |

`user 241m ÷ 1.07B reads ≈ 1.9 µs per read` of pure CPU on the server, versus ~0.13 µs
per read on the laptop for the same query — a ~15× per-call gap that does not show up in
laptop benchmarks at any sample size, because it is a property of the CPU (shared VPS
vCPUs, cold caches for a 40-literal DFA), not of the data volume. Two lessons compound:
021's ("what dominates a cost is a measurement") plus this one — **the measurement must
be taken on the machine that will pay it.**

## The fix

`scan.survivors()` now finds needle-carrying reads with Polars:
``scan_parquet → select → str.contains_any(all probes, both strands) → streaming collect``
— a Rust Aho-Corasick/Teddy matcher evaluated over whole column chunks, then DuckDB joins
the surviving handful of reads back to the probe table for attribution, as before. The
regex path remains as the fallback when Polars is absent, and
`tests/test_reads_store.py::test_fallback_survivors_agree_with_polars` pins the two to
identical answers. `polars` moves from a transitive bench dependency to a direct one.

Laptop parity: 0.57 s for 20 probes over 6M reads (regex: 0.68 s). **The server timing is
the open measurement**; per the table above nothing local can stand in for it.

## The noise floor, kept

| Class | Reads carrying the 31-mer |
|---|---|
| real allele (44× depth) | **36**, both strands, all 4 lanes |
| 18 of 19 single-base mutants | **0** |
| worst mutant (`mut_22_T`) | **1**, one strand, one lane |

This is the calibration for every future "is this candidate allele in the reads?" check:
**present** means dozens of reads spread over lanes and strands; **1–2 reads in one lane**
means sequencing error; the `count` verb's verdicts encode exactly this.

## Conclusion

Batching probes is the right design; the regex engine was the wrong matcher for a
billion short strings on weak cores. Aho-Corasick — built for exactly "many literals,
one pass" — replaces it. The server number decides whether this entry closes the chapter.
