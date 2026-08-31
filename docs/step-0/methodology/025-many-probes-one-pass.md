# 025 — Many probes, one pass: the cross join that wasn't free

**A step-0 platform entry, so it carries no hypothesis.** It corrects the batching claim
made when the multi-probe verbs were added after [024](024-the-kmer-strike-works.md), and
records the measured fix.

## Question

`scan`/`count` were given multi-probe support on the claim that a full pass is dominated
by decompressing the `sequence` column, so extra probes ride along almost free. The first
real batch said otherwise:

```
$ time uv run mva-reads count --root /root/mva-staging/reads --kmers-file probes.tsv   # 20 probes
^C  … interrupted …
real    32m40s        user    242m13s
```

One probe takes 3.5 minutes. Twenty took more than 32 before being killed. Why, and what
makes the claim actually true?

## Finding first

**The cross join multiplied the search, and search is not free at 40× decode.** The query
joined every read against every (probe, strand) row — 40 rows × 1.07B reads ≈ 43 billion
separate `contains` calls. Decode stopped being the dominant term the moment the search
term was multiplied by 40.

**The fix is one combined pattern.** All probes (both strands) become a single regex
alternation of literals; the engine compiles it into one automaton, so each read is
examined **once** regardless of probe count. Survivors — dozens of reads, not billions —
are then joined back to the probe table for attribution. Measured on a 6,000,000-read
store (laptop, oxbow-built shards):

| Query shape | 1 probe | 20 probes |
|---|---|---|
| plain `contains` baseline | 0.6 s | — |
| cross join of `contains` (the mistake) | — | **14.7 s** |
| regex prefilter + survivor join (the fix) | 0.8 s | **0.8 s** |

Flat. The 18× cross-join penalty at 6M reads extrapolates to the ~10× observed on the
full store before the kill. Full-store prediction for the fixed path: **~3.5 minutes for
any probe count** (up to the 500-probe API cap; an alternation of 1,000 31-mer literals
is well inside the regex engine's comfort).

## Where the fix lives

- `scan.expand()` — one place produces every (name, sequence, strand) row, so the SQL
  probe table and the prefilter pattern cannot disagree about what is searched.
- `scan.pattern()` — the alternation; interpolation-safe because `clean()` admits only
  `ACGTN`, none of which is a regex metacharacter.
- `scan.kmers()` / `scan.counts()` — prefilter CTE, then attribution join on survivors.
- Correctness pinned by `tests/test_reads_store.py`: multi-probe results equal
  single-probe results, absent probes report absent, metacharacters cannot reach the
  pattern.

The single-probe path pays the machinery too: 210.0 s versus 185.5 s on the full store
(~13%), the price of per-probe ranking and attribution. Accepted — the multi-probe case
is the real workload.

## Also in this change: the API mirrors the verbs

`mva-reads-api` (FastAPI, `docs/step-0/reads-api.md`) serves the same verbs over HTTP
with the same code underneath — scans run as cancellable jobs, results survive restarts.
Aligned with this entry: probe batching goes through the same prefilter; the SQL verb's
row cap is pushed into the engine (`LIMIT n+1` wrapped around the validated query) rather
than truncating a materialised result; and a second `convert` is refused with 409 while
one runs, because two would race for the same staging directory and object keys.

## Conclusion

A batched scan now really is one pass. The general lesson is the same one 021 taught
about row groups: a claim about what dominates a cost is a measurement, not an intuition
— the first 20-probe run was the measurement, and it said no.
