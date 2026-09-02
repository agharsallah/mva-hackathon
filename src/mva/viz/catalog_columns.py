"""What every column in the warehouse *means*, in one sentence each.

``information_schema`` gives a column's name and its SQL type. Neither says what the
number is. ``mean_vaf`` is a float; that it is the average fraction of reads carrying the
alternate allele at heterozygous sites — and that 0.5 is the healthy value — is knowledge
that exists only in the code that wrote it and in the head of whoever wrote it.

This module is that knowledge, written down. Two maps, resolved in order:

* :data:`BY_TABLE` — keyed ``(table, column)``, for a column whose meaning is specific to
  the table it sits in. ``length`` is the contig's size in ``contig_counts`` and the
  indel's size in ``stats_idd``; a single answer for both would be wrong in one of them.
  It is assembled from :mod:`mva.viz.catalog_columns_ingest` and
  :mod:`mva.viz.catalog_columns_results`, one per managed schema, for size alone.
* :data:`SHARED` — keyed by bare column name, for the columns that recur unchanged across
  tables. ``chrom``, ``pos``, ``ref``, ``alt`` and ``sha256`` appear in a dozen tables and
  mean the same thing in every one, so they are written once.

A column in neither map resolves to ``None``, never to a guess. The front end renders that
as a visible gap, which is the point: an undocumented column should look undocumented.

Every sentence here was read off the writer — :mod:`mva.warehouse.stage`,
:mod:`mva.warehouse.vcfstage`, :mod:`mva.warehouse.annotate`, :mod:`mva.warehouse.lineage`,
:mod:`mva.warehouse.source`, :mod:`mva.warehouse.probes`, :mod:`mva.science.hypothesis`,
:mod:`mva.science.evidence` and the derivation SQL — not inferred from the column name.
"""

from .catalog_columns_ingest import INGEST_COLUMNS
from .catalog_columns_results import RESULT_COLUMNS

#: Columns that recur across tables with one meaning. Written once, used everywhere.
SHARED: dict[str, str] = {
    # ── the variant's address ─────────────────────────────────────────────────────────
    "chrom": "Contig (chromosome) the row is about, spelled as that table stores it — "
    "bare on the callset side, `chr`-prefixed on the panel side.",
    "pos": "Position of the variant on the contig, 1-based, the VCF's POS. Kept as text "
    "in the raw layer and typed everywhere else.",
    "ref": "Reference allele — the base or bases the GRCh38 assembly has at this position.",
    "alt": "Alternate allele — what was seen instead of the reference. Comma-packed in "
    "the raw layer, one allele per row everywhere else.",
    "rsid": "dbSNP identifier (`rs…`) for the allele, or null where it has none.",
    "gene": "HGNC gene symbol the row is about; null where no gene applies.",
    # ── the panel's intervals ─────────────────────────────────────────────────────────
    "start": "Interval start in BED convention: 0-based and half-open, so the first base "
    "is `start + 1` in VCF coordinates.",
    "end": "Interval end in BED convention: exclusive, and therefore equal to the last "
    "base's 1-based VCF coordinate.",
    "n_all": "Variant records called inside this gene's interval, before any filter.",
    "n_pass": "Of those records, how many carry `FILTER=PASS`.",
    "variants_per_mb": "Variant records per million bases of the interval — a density "
    "that is comparable between intervals of different sizes.",
    # ── the caller's own fields ───────────────────────────────────────────────────────
    "qual": "Phred-scaled confidence the caller has in the site (QUAL): 10 means a "
    "1-in-10 chance the site is wrong, 30 a 1-in-1,000 chance.",
    "filter": "The caller's verdict for the site — `PASS`, or the names of the filters it failed.",
    "count": "How many records fall in this row's bucket.",
    # ── the annotator's answer ────────────────────────────────────────────────────────
    "consequence": "Ensembl VEP's predicted effect of the allele on the transcript, e.g. "
    "`missense_variant`, `stop_gained`, `intron_variant`.",
    "impact": "VEP's severity bucket for that consequence: HIGH truncates the protein, "
    "MODERATE changes an amino acid, LOW and MODIFIER are silent or "
    "non-coding.",
    "gnomad_af": "Allele frequency in gnomAD — how common the allele is in the general "
    "population. Null means gnomAD has never seen it, which is rarer than "
    "any number here, not zero.",
    "gnomad_af_grpmax": "The highest gnomAD frequency across the population groups, so a "
    "variant common in one ancestry is not hidden by a low global "
    "average.",
    "clin_sig": "ClinVar's germline classification(s) for the allele, `;`-joined; null "
    "where ClinVar has no record.",
    # ── gnomAD constraint ─────────────────────────────────────────────────────────────
    "loeuf": "Upper bound of the observed/expected loss-of-function ratio. Low means "
    "healthy people almost never carry a broken copy, i.e. the gene is "
    "intolerant of being broken. Below ~0.35 is the constrained end.",
    "pli": "Probability the gene is intolerant of losing one copy (haploinsufficient). "
    "Near 1 means one broken copy is already a problem.",
    "mis_z": "How many standard deviations the observed missense count sits below what a "
    "mutation model expects. High means missense variants are being selected "
    "against.",
    "oe_lof": "Observed loss-of-function variants divided by expected. 1.0 is "
    "unconstrained; near 0 means healthy people do not carry them.",
    "lof_obs": "Loss-of-function variants actually observed in gnomAD for this gene.",
    "lof_exp": "Loss-of-function variants a mutation model expects for this gene, given "
    "its length and sequence.",
    # ── allele balance ────────────────────────────────────────────────────────────────
    "n_het": "Heterozygous calls on this contig — sites where one copy carries the "
    "alternate allele.",
    "mean_vaf": "Mean variant allele fraction at those heterozygous sites: the share of "
    "reads carrying the alternate allele. A diploid genome sits at 0.50.",
    "mean_dp": "Mean read depth at those sites — how many reads covered each one.",
    "pct_in_0_40_0_60": "Share of heterozygous sites whose allele fraction lands in the "
    "0.40–0.60 band, i.e. how tight the distribution is around 0.50.",
    # ── QC norms ──────────────────────────────────────────────────────────────────────
    "expected_low": "Low end of the published range a healthy callset is expected to "
    "fall in for this metric.",
    "expected_high": "High end of that published range.",
    "unit": "Unit the metric and its range are expressed in.",
    "applies_to": "The assay and population the published range was measured on — a "
    "whole-genome norm does not apply to an exome.",
    # ── files and objects ─────────────────────────────────────────────────────────────
    "file": "The delivered file this row is about, by name.",
    "bytes": "Size of the file in bytes.",
    "file_name": "The object's file name, without the bucket or the key prefix.",
    "object_key": "The object's address inside the bucket, e.g. `source/<name>` — a key, "
    "not a directory path.",
    "size_bytes": "Size of the object in bytes, as the store reports it.",
    "sha256": "SHA-256 digest of the bytes — a 64-hex fingerprint. Equal digests mean "
    "not one bit differs.",
    "etag": "The store's own entity tag for the object. Equal to the MD5 for a "
    "single-part upload and not a digest at all for a multipart one, which is "
    "why the SHA-256 beside it is the one that is checked.",
    "version_id": "The object-store version of these bytes. The bucket is versioned, so "
    "an overwrite adds a version rather than replacing one.",
    "est_reads": "Estimated reads in the file, from its byte size and read length — an "
    "estimate because counting means decompressing the whole file.",
    "est_gbases": "Estimated bases in the file, in billions, from the same arithmetic.",
    "lane": "Flowcell lane this row is about, read out of the file name.",
    # ── bookkeeping ───────────────────────────────────────────────────────────────────
    "line_no": "Position of this line in the source file, 1-based — what makes the "
    "original file reconstructible from the table.",
    "line": "The line itself, verbatim, exactly as the source file wrote it.",
    "n_rows": "How many rows the table held at the moment this row was written.",
    "recorded_at": "When this row was appended, in UTC. The table is append-only, so "
    "this is the row's age and never changes.",
    "author": "Who recorded the row — a person or the tool that wrote it.",
    "hypothesis_id": "The claim in the hypothesis register this row belongs to.",
}

#: Columns whose meaning belongs to one table, assembled from the two schema registries.
#: Beats :data:`SHARED` wherever both carry a key — ``length`` is the contig's size in
#: ``contig_counts`` and the indel's size in ``stats_idd``, and one answer for both would
#: be wrong in one of them.
BY_TABLE: dict[tuple[str, str], str] = {**INGEST_COLUMNS, **RESULT_COLUMNS}


def meaning(table: str, column: str) -> str | None:
    """What one column means, or ``None`` when nothing here describes it.

    Table-specific first, then the shared map. ``None`` is the honest answer and the front
    end renders it as a visible gap — a guessed sentence would be worse than no sentence.
    """
    found = BY_TABLE.get((table, column))
    return found if found is not None else SHARED.get(column)
