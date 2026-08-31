# 027 — The Aho-Corasick fix, confirmed on the server

**A step-0 platform entry, so it carries no hypothesis.** It supplies the one measurement
[026](026-multi-literal-matching-needs-aho-corasick.md) left open, and closes it.

## Question

026 replaced the regex survivor stage with Polars' columnar Aho-Corasick
(`str.contains_any`) and predicted 3–6 minutes for a 20-probe pass on the server, where
the regex shape had twice cost ~32 minutes. Does the prediction hold?

## Finding

**Yes: 335.2 s — 5.6 minutes — for all 20 probes, 5.8× faster than the regex path**, with
every count and verdict byte-identical to both slow runs (the third independent
reproduction of the same table, across three different query shapes).

```
$ time uv run mva-reads count --root /root/mva-staging/reads/ --kmers-file probes.tsv
                real      19      17      36      4  present
             … 18 mutants absent, mut_22_T error-level (1 read) …
20 probe(s) in one pass, 335.2s
real    5m37s      user    22m52s
```

| Survivor stage | 20 probes, full store | CPU per read |
|---|---|---|
| cross join of `contains` | killed at 32m40s | — |
| `regexp_matches` alternation | 1934 s | ~13.5 µs |
| **Polars `contains_any`** | **335 s** | **~1.3 µs** |

For scale: one probe via plain `contains` is 185.5 s ([024](024-the-kmer-strike-works.md)),
so twenty probes now cost 1.8× one — the batching promise, finally kept by the matcher
that was built for it.

## Conclusion

The k-mer strike is a ~5-minute operation for any probe set up to the API's 500-probe
cap, server-side, with verdicts calibrated by the measured noise floor (026). The read
store's query chapter is closed; the next escalation (a k-mer index or prescreen sketch)
is only warranted if a workload of *many such batches per day* appears.
