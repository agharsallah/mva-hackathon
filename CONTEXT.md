# MVA Proband Diagnosis

Identifying the two causal variants in one child with Mosaic Variegated Aneuploidy, from
whole-genome sequencing, and submitting them in the form the challenge scorer accepts.

The vocabulary below is what the code, the tests and the write-ups all use. Where clinical
genetics offers several words for one idea, one is picked and the rest are listed to avoid.

## Language

### The patient and the answer

**Proband**:
The child whose genome we are analysing. Exactly one exists in this project.
_Avoid_: patient, subject, case, sample

**PROBAND01**:
The identifier the scorer requires in every submission row. Unrelated to the VCF's sample
column, which carries the sequencing lab's accession instead.
_Avoid_: sample ID, proband name

**Answer key**:
The two variants the challenge organisers hold as the validated diagnosis. Never visible
to us directly; only ever probed through the scorer's reply.
_Avoid_: ground truth, gold standard, label, solution

**Compound heterozygote**:
Two different damaging variants in one gene, one on each inherited copy, so neither copy
produces working protein. This is the shape of the answer key.
_Avoid_: biallelic pair, double het, recessive pair

### Variants and genotypes

**Variant**:
One alternate allele at one position, written as the scorer compares it: chr-prefixed
chromosome, 1-based position, uppercase ref and alt. The submission representation.
_Avoid_: mutation, SNP, allele, locus

**Call**:
What the caller observed for one variant in this proband — genotype, depths, filters,
phasing. A Variant is an identity; a Call is evidence about it in this genome.
_Avoid_: record, row, site, observation

**Contig**:
A chromosome as this VCF names it — bare, without the `chr` prefix (`15`, not `chr15`),
because the callset was built against a no-chr reference.
_Avoid_: chromosome name, seqname, reference name

**Phase set**:
A group of variants close enough to share read support, so the caller could determine
which copy of the chromosome each sits on. Carried in `PID`, with `PGT` giving the
haplotype. Reaches roughly 300 bp.
_Avoid_: phasing block, haplotype block, PS

**Cis**:
Two variants on the same copy of the chromosome. The other copy is intact, so a cis pair
is not a compound heterozygote and is rejected.
_Avoid_: same haplotype, in phase, coupled

**Trans**:
Two variants on opposite copies. Both copies are damaged, which is what a compound
heterozygote means.
_Avoid_: opposite haplotype, out of phase, repulsion

**Unknown phase**:
No evidence either way. The common verdict — it applies to 99.7% of pairs — and it is
never a rejection.
_Avoid_: unphased, undetermined, missing phase

**Allele balance**:
The fraction of reads at a heterozygous site carrying the alternate allele. Sits near 0.5
in a normal diploid sample; a shift betrays mosaic aneuploidy, contamination, or a bad call.
_Avoid_: VAF, allele fraction, alt ratio

### Scoring and submission

**Submission row**:
One line of the Track 1 CSV: either a single variant, or a compound-heterozygous pair
carried in ONE row via the second variant columns. At most ten rows per submission.
_Avoid_: prediction, entry, candidate line

**epcr**:
The confidence value in (0, 1] attached to a submission row. Rows are ranked by descending
epcr, so distinct values are what make a rank — and therefore a probe reply — unambiguous.
_Avoid_: score, confidence, probability, weight

**Full match**:
A row whose variant set equals the answer key exactly. Takes precedence over any partial
match, at whatever rank it sits.
_Avoid_: exact hit, correct answer

**Partial match**:
A row containing exactly one of the two true variants, alone or paired with a wrong
partner. Worth half the rank points of its position.
_Avoid_: half hit, single match

**Probe**:
A submission spent to learn about the answer key rather than to score. A *singles probe*
puts ten candidates in ten rows to identify an allele; a *pair probe* fixes one confirmed
allele and varies the partner; a *final strike* submits the confirmed pair at rank 1.
_Avoid_: query, guess, attempt, trial

**Secondary finding**:
A medically significant variant unrelated to the presenting phenotype, submitted with
`finding_type` `secondary`. Reviewed qualitatively and cannot lower the automated score.
_Avoid_: incidental finding, off-target finding

### Analysis inputs

**Panel**:
The candidate gene set — the known MVA genes plus rhabdomyosarcoma differentials — with
GRCh38 coordinates. The first place to look, not the only place.
_Avoid_: gene list, target regions, candidate genes

**Annotation**:
What an external source says about a variant's consequence and population frequency.
Absent from this VCF entirely and supplied through a port.
_Avoid_: functional prediction, VEP output, effect

**Loss of function**:
A consequence that abolishes the protein — stop gained, frameshift, splice site loss,
start lost, transcript ablation. Ranks above missense.
_Avoid_: LoF, null variant, truncating, deleterious

**Non-PASS**:
A call the caller emitted but flagged as untrustworthy. A search space, not garbage: 271k
of them exist and a real variant in repetitive sequence is exactly what gets flagged.
_Avoid_: filtered out, failed, low quality, rejected

**Normalization**:
Rewriting variants to one canonical form — indels left-aligned and trimmed, multiallelic
sites split one allele per record. Mandatory before any comparison, because the scorer
matches strings exactly.
_Avoid_: canonicalisation, standardisation, cleaning
