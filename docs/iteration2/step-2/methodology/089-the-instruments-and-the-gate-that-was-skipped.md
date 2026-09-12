# 089 — Which instruments were actually available, and does the kernel scale as the plan assumed?

**Written:** 2026-09-12, after [088](088-the-alleles-the-reads-carry.md) closed the step's
five claims. **Step:** `step-2` (iteration 2). **Hypotheses:** none tested here; this entry
records the evidence behind two **supersessions** (H017, H018) and runs a pre-registered
gate that was skipped.

**Supersedes nothing.** 085–088 stand as written. This entry supplies what they left
unrecorded.

## Inputs

| Source | What was read | Version / receipt |
|---|---|---|
| public | Homebrew formulae API, PyPI JSON API | queried 2026-09-11 |
| local | the machine: `uname -m`, `which docker podman apptainer conda` | Apple M1 Pro, arm64, 16 GiB |
| derived | the bait array | `build/it2/step-2/bait.npy`, 36,038,037 k-mers, entry 086 |
| store | one shard of the read store, taken whole | `reads/lane=1/read=1/part-0.parquet`, first 1,000,000 reads |

No annotation, no callset, no candidate table. Both questions are about machinery.

## Part 1 — two claims named instruments that do not exist here

`plan.md` wrote H017 around **DeepVariant** and H018 around **Manta / LUMPY / GRIDSS**.
Neither claim is about a tool; H017 is about agreement with the vendor's callset and H018
is about two *method classes*. But a claim names its instrument, and the register recorded
both as `superseded` with reasoning and **no evidence row**, which
`mva-science check` refuses — correctly: a settled claim with nothing behind it is an
assertion.

| Tool the plan named | arm64 macOS build? | Checked by |
|---|---|---|
| DeepVariant | **no** — amd64 container images only, and this machine has no Docker, Podman, Apptainer or conda | image tags; `which` |
| Manta | **no** — Linux x86-64 release tarball only | release assets |
| GRIDSS | **no** — needs a JVM *and* bwa; no arm64 path | release assets |
| LUMPY / smoove | **no** — Linux binary | release assets |
| freebayes 1.3.10 | yes, Homebrew bottle | formulae API |
| bcftools 1.24 | yes, already installed | `bcftools --version` |
| delly 2.6.0 | yes, Homebrew bottle | formulae API |
| dysgu 1.9.0 | yes, cp313 arm64 wheel | PyPI |
| whatshap 2.8 | sdist, Cython, builds | PyPI |
| minimap2 2.31 | yes, Homebrew bottle | formulae API |

**Conclusion.** The substitutions are forced by the platform, not chosen for convenience,
and they preserve what each claim was written about: freebayes (Bayesian over observed
haplotypes) and `bcftools call -m` (pileup) are disjoint model classes from each other and
from Sentieon Haplotyper (GATK-style local reassembly); delly (read-pair + split-read) and
dysgu (local assembly + learned classifier) are the two method classes Kosugi 2019 Fig. 6–7
is actually about. This is the evidence row H017 and H018 were missing.

**What it costs, stated plainly.** freebayes is weaker than DeepVariant on indels, so
[088](088-the-alleles-the-reads-carry.md) reports SNV and indel concordance separately and
no conclusion rests on an indel-only call. Two SV callers instead of four is a thinner
consensus than the plan intended.

## Part 2 — the scaling gate, run late, and reported as late

`plan.md` §5 stage 4 pre-registered a numeric gate — *measure the kernel at 10³…10⁷
patterns; the projected server-side pass must be under an hour* — to be run **before**
stage 5. It was not run. The pass went ahead on a one-shard smoke test instead.

That is a skipped gate, and a skipped gate is a failed one until it is run. It is recorded
here rather than quietly ticked, and **it can no longer do the job it was written for**:
the pass has already happened, so this cannot license it. What the measurement is still
worth is the engine's scaling curve, which step 3 and any later reuse of `mva.kmer` need.

### Command

```
uv run python tools/scale_it2_bait.py
```

One unselected shard of the store, 1,000,000 reads of 149 bp, stride 16, k = 31, each bait
size drawn at random from the 36 M-k-mer bait (never its sorted prefix, which would flatter
both the binary search and the bitmap).

### Observed

| bait k-mers | seconds | reads/s | hit rate | bait MB | projected full pass |
|---|---|---|---|---|---|
| 1,000 | 2.44 | 410,302 | 0.00001 | 0.0 | 43.5 min |
| 10,000 | 2.31 | 432,550 | 0.00002 | 0.1 | 41.3 min |
| 100,000 | 2.28 | 439,498 | 0.00025 | 0.8 | 40.6 min |
| 1,000,000 | 2.33 | 429,309 | 0.00237 | 8.0 | 41.6 min |
| 10,000,000 | 2.38 | 420,004 | 0.01176 | 80.0 | 42.5 min |
| **36,038,037** (the real bait) | 2.57 | 388,935 | **0.01411** | 288.3 | **45.9 min** |

Receipt: `build/it2/step-2/scaling.json`.

### Verdict on the gate

**Pass — 45.9 min against a 60 min gate**, and the top of the curve is the bait as it
actually is rather than an extrapolation.

**The shape is the result.** A 36,000-fold increase in bait size costs **1.05x per read**.
Three effects were in play and the flat curve says which won: the binary search does grow
(~10 comparisons at 10³, ~25 at 3.6x10⁷) and the bitmap does get denser (~0.1 % full to
~3.4 %, so more windows survive the cheap test), but both are swamped by the work that does
not depend on the bait at all — decoding bases to 2-bit codes, rolling the windows, taking
the canonical form. **The engine's cost is set by bytes of sequence, not by bait size**,
which is the property that makes a 42 Mb bait affordable and the reason this design was
worth building rather than buying.

### An independent check nobody asked for

The hit rate at the full bait on an unselected shard is **1.411 %**. The real pass over all
272 shards matched **1.36752 %**, and the bait covers **1.361 %** of the genome. Three
numbers from three different routes, agreeing to within 4 %.

## Assumptions and limitations

- **Kernel time only.** `project()` multiplies a measured per-read rate; a real pass also
  moves bytes. On the laptop that term dominated by an order of magnitude (55.8 s per shard
  of I/O, entry 085) and it is why the pass ran beside the data.
- **One shard, one machine.** The curve's *shape* should transfer; its absolute rate is
  this laptop's.
- **Peak RSS is a process high-water mark**, so it only climbs across the series and is not
  a per-point footprint. `bait_bytes` is the exact per-point figure.
- The tool availability table is a snapshot of 2026-09-11 and will age.
