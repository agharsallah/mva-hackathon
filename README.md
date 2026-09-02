# MVA Hackathon 2026

**Standing:** the front door. What this is, where the data may live, how to start. Every
other topic is one link away in [`docs/README.md`](docs/README.md), which is the only
documentation index. Last checked 2026-08-29.

An N-of-1 causal-variant pipeline for the
[Rare Disease, Real Kid: MVA Hackathon 2026](https://sagebio-rare-disease-real-kid-mva-hackathon-2026.hf.space/).

One child with Mosaic Variegated Aneuploidy, whole-genome sequencing, and a
compound-heterozygous answer key: two variants in one gene, one on each allele.

## Data handling — read this first

The dataset is gated under a Data Transfer Agreement. **No patient sequence enters this
repository**, ever: no VCF slice, no read, no variant table with real coordinates, no IGV
screenshot. The rule, why it is absolute rather than proportionate, and what it forbids:
[no patient data in the repository](docs/notes/no-patient-data-in-the-repository.md).

Where everything lives:

| | Location | In git |
|---|---|---|
| The delivery as source of truth | MinIO bucket `mva`, `source/` — remote VPS | no |
| Ingested and derived tables | PostgreSQL `mva` — remote VPS | no |
| Derived patient slices, panel extracts, smoke samples | warehouse tables, queried via the reads API / viz API — remote VPS | no |
| Aggregate profiles, counts, redacted headers | `ressources/data-profile/` | yes |
| Synthetic fixtures | `tests/fixtures/` | yes |

`.gitignore` blocks the genomic file types as a safety net; the real control is keeping the
data outside the git tree entirely. The fixture guard is deliberately narrow —
`tests/fixtures/*.vcf` is allowed but `*.vcf.gz` is not — so any fixture entering git is
plain text a reviewer can read in a diff and confirm by eye is fabricated.

Everything must be deleted within 30 days of the hackathon close, with confirmation emailed
to the organisers.

## Getting started

```bash
tools/setup-env.sh            # uv + micromamba (bcftools, samtools, seqkit, fastp)
sh tools/setup-git.sh         # hooks, commit template, rebase-pull — idempotent, repo-local
source tools/activate.sh      # puts the bio binaries on PATH
uv run pytest                 # hermetic: synthetic fixtures, no dataset, no services
```

How to get a change in — the two toolchains, the quality gates, the commit convention and the
history rules: [`CONTRIBUTING.md`](CONTRIBUTING.md).

Look at the data profile (needs no dataset — the profile is committed):

```bash
uv run mva-explore checks ressources/data-profile     # graded metrics, in the terminal
uv run mva-explore report ressources/data-profile     # figures/explore-report.html
```

Reproduce the profile itself (needs the gated dataset, ~10 min):

```bash
tools/profile-genomic-data.sh ~/ubuntu/data
```

Query the same data in SQL, against the shared Postgres and object store:

```bash
cp .env.example .env                       # fill in PGPASSWORD and the S3 keys
uv run mva-warehouse pg-check              # resolved settings + a live probe
uv run mva-warehouse s3-check
```

Setup, ports, credentials and the sharp edges: [`docs/step-0/infrastructure.md`](docs/step-0/infrastructure.md).

## How a question becomes an answer

Work is grouped by **step**, and every research step declares one goal. A claim under it
states its prediction and what would refute it *before* it is tested; every observation is
recorded with the run it came from; every verdict is weighed and appended, never edited.
The loop, and what the register refuses to store: [`docs/method.md`](docs/method.md).

```bash
uv run mva-science steps                                   # the goals, no database needed
uv run mva-science report --from docs/science-register.json  # the record, as a page
```

The register is currently **empty** — step 1 has not run, so nothing has been claimed.

## Where the work stands

Test count, what is provisioned, what runs, and the known gaps:
[`docs/current-state.md`](docs/current-state.md).
What is measurably in the data: [`ideation/data-findings.md`](ideation/data-findings.md).

## Documentation

Everything is indexed in **[`docs/README.md`](docs/README.md)**. Start there.
