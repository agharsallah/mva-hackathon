# The VCF reader is hand-rolled rather than pysam

**Standing:** provisional. Fine while we need four FORMAT fields. Revisit if the pipeline
starts needing real VCF surface area, at which point pysam earns its dependency.

The whole pipeline needs four fields from each record — `GT`, `AD`, `PGT`, `PID` — plus
FILTER and the alleles. A hundred lines of plain-text parsing covers that, and it keeps the
project installable anywhere with a stdlib Python, including a bare Modal container, with no
compiled htslib bindings to match against a host library.

`bcftools` still does the heavy lifting it is good at — indexing, region queries,
normalization, stats — invoked as a subprocess from the tooling scripts. The reader handles
what comes after.

## Consequences

The reader emits one `Call` per ALT allele, so a `1/2` multiallelic record becomes two calls.
The scorer has no notion of a comma-separated ALT, and biologically a `1/2` site already *is*
a compound heterozygote, so both alleles must reach the pair finder separately.

The reader never filters and never rewrites alleles. Non-PASS records are exactly where a
suppressed second allele would hide, and silently normalizing would destroy our ability to
test that normalization ran. Both are ranking decisions, made downstream.
