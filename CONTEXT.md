# MVA Proband Diagnosis

**Standing:** the naming discipline for code and write-ups — one chosen word per idea, plus
what to avoid. Distinct from [`docs/dictionary.md`](docs/dictionary.md), which *teaches*
the concepts; this file *fixes the vocabulary*. Last checked 2026-08-29.

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

### Exploration and reporting

**Profile**:
A directory of committable summary statistics describing a dataset — headers, tallies,
distributions — with no variant record and no read sequence in it. The substrate the
exploration toolkit reads.
_Avoid_: summary, stats dump, QC output

**Exhibit**:
One figure together with the caption saying how to read it and the legend decoding its
colours. The unit the report is assembled from. Deliberately not *panel*, which in this
project means the candidate gene set.
_Avoid_: panel, chart, plot, card, tile

**Check**:
One measured number graded against a stated expected band, carrying the reasoning behind
that band. Its result is a **verdict**: pass, warn, fail, or info.
_Avoid_: metric, test, QC flag, rule

**Band**:
The range a measured value is expected to fall in. A community convention, not a
measurement, and always cited as such.
_Avoid_: threshold, cutoff, limit

**Layout**:
Which filename in a profile directory holds which artifact. The seam that makes the
toolkit case-agnostic — reading another lab's profile is a layout swap.
_Avoid_: schema, mapping, config

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

**Term set**:
The child's HPO terms as one named object. Two exist — every delivered term, and only the
ones describing the child rather than the parents. A ranking always names which it used.
_Avoid_: phenotype list, symptoms, HPO codes, the terms

**Phenotype score**:
How well a gene's known clinical features match the child's, measured on the ontology
graph and normalised to 0–1. A property of a **gene**, never of a variant.
_Avoid_: phenotype match, HPO score, similarity, Exomiser score

**Gene prior**:
The multiplier a phenotype score contributes to a candidate pair's rank. Derived, never
asserted — a hand-typed prior is an assumption and is recorded as one.
_Avoid_: gene weight, boost, prior probability

### The research record

**Step**:
A unit of work carrying exactly one research goal. Every claim names one, so the record
reads by question rather than by date. Step 0 is the exception — it is machinery and takes
no claims.
_Avoid_: phase, stage, milestone, sprint

**Goal**:
The single question a step exists to answer, phrased as a question. Not a task: a task is
done when it runs, a goal is done when it is answered.
_Avoid_: objective, aim, deliverable, task

**Hypothesis**:
A falsifiable claim about the patient, stated with its prediction and the observation that
would refute it, before the test runs. Never used for an engineering decision — those are
notes.
_Avoid_: theory, idea, assumption, guess, lead

**Refutation condition**:
The observation that would kill a claim. Written before the run, and required — the register
rejects a claim without one.
_Avoid_: falsification criterion, kill switch, negative control

**Evidence**:
One observation bearing on one claim, carrying its direction, its strength and the source it
came from. Singular and countable here: *an evidence row*, never *evidence* as a mass noun
for a general impression.
_Avoid_: finding, signal, support, data point, proof

**Direction**:
Which way an observation cuts — supports, refutes, or neutral. Neutral is recorded, not
dropped.
_Avoid_: sign, polarity, sentiment, vote

**Strength**:
How hard one observation cuts, 0 to 1. A stated human judgment. Deliberately not *weight*,
which in this project belongs to the ranking score, nor *confidence*, which is the claim's.
_Avoid_: weight, score, importance, significance

**Verdict**:
The evidence weighed into a status and a confidence, with a written reason. A verdict is a
new revision, never an edit.
_Avoid_: conclusion, decision, call, judgement

**Confidence**:
How strongly a claim is currently believed, 0 to 1. Always qualified as a triage heuristic,
never quoted as a calibrated probability. Distinct from **epcr**, which is the number
submitted to the scorer.
_Avoid_: probability, posterior, certainty, likelihood, epcr

**Dossier**:
One claim plus every revision, every evidence row, and the weighing over them. The unit the
export writes and the report renders.
_Avoid_: case file, record, bundle, summary

**Register**:
The append-only collection of hypotheses and their revisions. The evidence table beside it is
the **ledger**, matching the probe ledger and the upload ledger.
_Avoid_: database, store, log, tracker

### Ordering without filtering

**Likelihood ratio**:
How many times more likely an observation is if a hypothesis is true than if it is not. The
unit that replaces a filter: nothing is removed, only multiplied. Written *ratio* in prose
when the context is already about scoring.
_Avoid_: weight, score, boost, penalty, odds ratio

**Evidence lane**:
One named strand of evidence carrying a ratio, a source and a correlation group. Always
*lane*, never *feature* or *signal* — a feature is an input to a model, and this is a term in
a printed product.
_Avoid_: feature, signal, factor, component, criterion

**Correlation group**:
A set of lanes trained or curated on overlapping data, of which only the strongest counts.
The others are **damped**, not dropped: they keep their row and their name.
_Avoid_: deduplication, collinearity handling, redundancy filter

**Shape (of a biallelic hypothesis)**:
Which of `compound`, `homozygous` or `single` a scored row is. Not *type*, which this project
uses for variant classes, and not *class*, which belongs to the genotype model.
_Avoid_: type, class, category, kind

**P(trans)**:
The probability two alleles sit on opposite copies of a chromosome, estimated from a
reference population. Always written with its state — `observed`, `undetermined`,
`same-site` — and never called *phase*, which is a fact about this child that is not known.
_Avoid_: phase probability, trans probability, phasing score

**Unphaseable**:
Both alleles real, both single-copy, no fragment spanning them and no parental DNA. A
statement that phase **cannot be established**, never that it is unfavourable.
_Avoid_: unphased, phase unknown, unresolved

**Decoy null**:
A matched control set scored through the identical code path, reported as an AUC with a
bootstrap interval. Distinct from the **permutation null**, which resamples the *input*
rather than the gene set.
_Avoid_: negative control set, background, baseline
