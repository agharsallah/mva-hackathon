# MVA Hackathon 2026

An N-of-1 causal-variant pipeline for the [Rare Disease, Real Kid: MVA Hackathon 2026](https://sagebio-rare-disease-real-kid-mva-hackathon-2026.hf.space/).

One child with Mosaic Variegated Aneuploidy, whole-genome sequencing, and a
compound-heterozygous answer key: two variants in one gene, one on each allele.

## Data handling — read this first

The 80 GB dataset is gated under a Data Transfer Agreement. **No patient sequence enters
this repository**, ever: no VCF slice, no read, no variant table with real coordinates,
no IGV screenshot. `.gitignore` blocks the file types as a safety net, but the real
control is keeping the data outside the git tree entirely.

| | Location | In git |
|---|---|---|
| Raw dataset | `~/ubuntu/data/` | no |
| Derived patient slices, panel extracts, smoke samples | `~/ubuntu/work/` | no |
| Aggregate profiles, counts, redacted headers | `ressources/data-profile/` | yes |
| Synthetic fixtures | `tests/fixtures/` | yes |

Everything must be deleted within 30 days of the hackathon close, with confirmation
emailed to the organisers.

The fixture guard is deliberately narrow: `tests/fixtures/*.vcf` is allowed but
`*.vcf.gz` is not, so any fixture entering git is plain text a reviewer can read in a
diff and confirm by eye is fabricated. Tests bgzip them into a tmp dir at run time.

## Getting started

```bash
tools/setup-env.sh            # uv + micromamba (bcftools, samtools, seqkit, fastp)
source tools/activate.sh      # puts the bio binaries on PATH
uv run pytest                 # runs entirely on synthetic fixtures, no data needed
```

To reproduce the data profile (needs the gated dataset, ~10 min):

```bash
tools/profile-genomic-data.sh ~/ubuntu/data
```

## Documentation

| | |
|---|---|
| [`CONTEXT.md`](CONTEXT.md) | the domain vocabulary this codebase speaks |
| [`docs/architecture.md`](docs/architecture.md) | the map: data flow, seams, sharp edges |
| [`docs/roadmap.md`](docs/roadmap.md) | status, next steps, and the plan for the full 80 GB |
| [`docs/notes/`](docs/notes/) | why the code looks like this, and what is still provisional |
| [`ideation/data-findings.md`](ideation/data-findings.md) | what is measurably in the data |
| [`methodology/`](methodology/) | how each result was reached, reproducibly |

## Layout

```
src/mva/
  variant.py        variant identity in the scorer's exact representation
  vcf.py            reading the callset into per-ALT-allele calls
  compound_het.py   pairing het calls, classifying cis / trans / unknown
  annotation.py     the functional-annotation port (VEP, gnomAD) + a lookup fake
  ranking.py        scoring pairs so the best lands at rank 1
  submission.py     the Track 1 CSV contract
  scorer.py         a local replica of the challenge scorer, for rehearsing probes
tests/              one test module per seam, plus an end-to-end tracer
tools/              environment setup, data profiling, panel BED construction
ideation/           strategy brief, data findings, method notes
ressources/         challenge documents and committable data profiles
```

## Where the work stands

Measured facts about the dataset are in [`ideation/data-findings.md`](ideation/data-findings.md);
strategy is in [`ideation/hackathon-intel.md`](ideation/hackathon-intel.md). The three
findings that most shape the pipeline:

1. **The VCF's contigs have no `chr` prefix and the scorer does not normalize them.**
   Submitting `15` instead of `chr15` is a well-formed, silent, total miss.
2. **The callset is SNV + indel only — no SV or CNV caller in its provenance.** If one
   causal allele is structural it is absent at every FILTER level, and the FASTQ is the
   only path to it.
3. **Physical phasing resolves 0.3% of candidate pairs.** It reaches ~300 bp, so it is a
   confirmatory tool, not the discriminator. Rarity and consequence must carry the ranking.

The blocking dependency is functional annotation — gnomAD frequency and VEP consequence.
It is designed as a port (`annotation.py`) with a fake in tests, so ranking logic is
already testable and the real backend is a swap.
