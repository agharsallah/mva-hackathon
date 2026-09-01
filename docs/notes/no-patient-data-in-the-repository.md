# No patient data in the repository, at any size

**Standing:** firm. This one is not a design preference — it follows from the Data
Transfer Agreement and does not change as the pipeline evolves.

The dataset is gated under a Data Transfer Agreement that forbids resharing through any
channel and requires deletion within 30 days of the hackathon close. Git makes deletion
effectively impossible: a slice committed once survives in history, in every clone, and in
any fork of the public repository we are also required to publish. So the rule is absolute
rather than proportionate — no VCF slice, no read, no variant table with real coordinates,
no IGV screenshot, regardless of how small.

Real derived artifacts live in the warehouse database on the remote VPS, queried through
the reads API / viz API — never on a contributor's disk, outside the git tree either way.
What may be committed is aggregate: counts, distributions, redacted headers, per-gene
tallies. A count is not a record.

## Consequences

Pipeline development needs data that is *shaped* like the real thing but is not it, so
`tests/fixtures/` holds synthetic VCFs — see [synthetic fixtures](synthetic-fixtures.md).

`.gitignore` blocks the genomic file types, but it is a safety net and not the control.
The control is that the data was never in the tree to begin with.

The committed VCF header is redacted: the delivered one carries the lab accession in the
sample column *and* inside the Sentieon and GATK command lines, plus the sequencing
provider's internal DNAnexus job paths. `tools/profile-genomic-data.sh` strips all three.
