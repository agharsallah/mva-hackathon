# Test fixtures are synthetic, and only plaintext fixtures may enter git

**Standing:** firm, as a consequence of
[no patient data in the repository](no-patient-data-in-the-repository.md).

Given [no patient data in the repository](no-patient-data-in-the-repository.md), tests
cannot use real data, but they still need input with the real file's
awkward properties. `tests/fixtures/mini.vcf` is fabricated base by base while mirroring
the shape that actually causes bugs: bare contig names, a lab-accession sample column,
Sentieon/GATK header provenance, the `GT:AD:DP:GQ:PGT:PID:PL` format, a multiallelic
`1/2` site, a right-aligned indel, a non-PASS record, and cis, trans and unphased pairs.

The `.gitignore` exception is deliberately narrow: `tests/fixtures/*.vcf` is allowed and
`tests/fixtures/*.vcf.gz` is not. A plaintext VCF appears in a diff, so a reviewer can read
it and confirm by eye that it is invented; a bgzipped one is opaque and would have to be
trusted. Tests bgzip and index into a temp directory when they need the compressed form.

## Consequences

The fixture is a fake, so it can prove the machinery works and can never prove we found the
real variant. Every test that scores a submission scores it against a *pretend* answer key,
and the test names say so.
