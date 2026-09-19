"""What step 8's tables look like, where each came from, and how to describe it.

Split out of ``it2_step8_tables`` when that module crossed the 400-line limit. The two
halves are genuinely different concerns: this one is a **declaration** -- column names and
types, the prose that goes into a lineage row, and which tables did not come from the
callset -- and its sibling is the **machinery** that reads a TSV and writes the rows.
Nothing here touches a database connection.

The schema is a promise about *types*, not about presence: a TSV written by an earlier run
legitimately carries fewer columns, and ``it2_step8_tables._columns_for`` narrows the
declaration to what a given file actually holds rather than refusing it.
"""

from __future__ import annotations

__all__ = [
    "CALLSET_REF",
    "CLINICAL_REF",
    "CLINICAL_TRANSFORM",
    "LIMITS_FIXED",
    "LIMITS_TABLE",
    "READS_REF",
    "SCHEMAS",
    "SOURCES",
    "TOOL",
    "TRANSFORMS",
]


SCHEMAS: dict[str, tuple[tuple[str, str], ...]] = {
    "it2_mosaic_bdev": (
        ("chrom", "VARCHAR"),
        ("arm", "VARCHAR"),
        ("n_sites", "BIGINT"),
        ("mean_depth", "DOUBLE"),
        ("bdev", "DOUBLE"),
        ("null_mean", "DOUBLE"),
        ("null_sd", "DOUBLE"),
        # The rejection threshold, per contig: the null is simulated from this contig's own
        # depths and site count, so a shallow contig is judged against a wider null rather
        # than flagged for being shallow.
        ("null_p95", "DOUBLE"),
        ("z", "DOUBLE"),
        ("p_value", "DOUBLE"),
        ("rho", "DOUBLE"),
        ("centre", "DOUBLE"),
        ("measurable", "BOOLEAN"),
        ("exceeds_null", "BOOLEAN"),
    ),
    "it2_mosaic_fractions": (
        ("chrom", "VARCHAR"),
        ("arm", "VARCHAR"),
        # The published DANFIP estimator as written, its value on null draws from the same
        # depths, and the difference. The gap between the first two is a measurement about
        # the instrument and is why all three columns travel together.
        ("f_raw", "DOUBLE"),
        ("f_null", "DOUBLE"),
        ("f_hat", "DOUBLE"),
        ("f_low", "DOUBLE"),
        ("f_high", "DOUBLE"),
        ("upper_sites", "BIGINT"),
        ("centre", "DOUBLE"),
    ),
    "it2_mosaic_models": (
        ("chrom", "VARCHAR"),
        ("model", "VARCHAR"),
        ("fraction", "DOUBLE"),
        ("tract", "DOUBLE"),
        # Fitted per chromosome here, unlike the genome-wide value the deviation null uses,
        # and the two together are how a reader tells a repeat-dispersed contig from a
        # mosaic one.
        ("rho", "DOUBLE"),
        ("noise_share", "DOUBLE"),
        ("depth_dispersion", "DOUBLE"),
        ("log_likelihood", "DOUBLE"),
        ("allele_log_likelihood", "DOUBLE"),
        ("depth_log_likelihood", "DOUBLE"),
        ("parameters", "BIGINT"),
        ("observations", "BIGINT"),
        ("bic", "DOUBLE"),
    ),
    "it2_mosaic_verdicts": (
        ("chrom", "VARCHAR"),
        # "not distinguishable" whenever the margin is under Kong 2018's ten, so a reader
        # cannot mistake a ranking for a call by reading the wrong column.
        ("call", "VARCHAR"),
        ("best", "VARCHAR"),
        ("runner_up", "VARCHAR"),
        ("delta_bic", "DOUBLE"),
        ("fraction", "DOUBLE"),
        ("trisomy_vs_cnloh", "DOUBLE"),
        ("confident", "BOOLEAN"),
        # The contig's tail burden under `normal`, and whether it is past the ceiling.
        ("noise_share", "DOUBLE"),
        ("measurable", "BOOLEAN"),
        # True when a parameter of the winning fit is pinned against its bound: the
        # optimiser reporting "as much as you let me" rather than an estimate. The leader's
        # own parameters travel with it so the verdict can be checked rather than trusted.
        ("degenerate", "BOOLEAN"),
        ("leader_rho", "DOUBLE"),
        ("leader_tract", "DOUBLE"),
        ("leader_noise", "DOUBLE"),
    ),
    "it2_mosaic_density": (
        ("chrom", "VARCHAR"),
        ("arm", "VARCHAR"),
        ("het_sites", "BIGINT"),
        ("pass_sites", "BIGINT"),
        ("arm_bp", "BIGINT"),
        ("acrocentric", "BOOLEAN"),
        ("het_per_mb", "DOUBLE"),
        ("het_share", "DOUBLE"),
    ),
    # The reads half. Written by tools/run_it2_dosage_pass.py rather than by the fitting
    # stages, because it is the only table here whose input is a pass over 1.07 billion
    # reads instead of a callset the warehouse already holds.
    "it2_chrom_dosage": (
        ("chrom", "VARCHAR"),
        ("probes", "BIGINT"),
        # Probes never seen at all. A large share is a broken probe set, not a zero dosage,
        # so it is a column rather than something averaged away.
        ("silent", "BIGINT"),
        ("silent_share", "DOUBLE"),
        ("mean_count", "DOUBLE"),
        # Against the autosomal median -- easy to read and easy to trust wrongly, because it
        # assumes most chromosomes are normal.
        ("relative", "DOUBLE"),
        ("low", "DOUBLE"),
        ("high", "DOUBLE"),
        # Against the genome-wide calibration set, which no single chromosome can move.
        ("absolute", "DOUBLE"),
        # Where the two denominators disagree, the median moved: defence (c) as a number.
        ("disagreement", "DOUBLE"),
        # How much of the read store the pass actually swept. Shards are flowcell
        # partitions, not genomic ones, so a subset is a uniform sample of the library and
        # a ratio between chromosomes stays unbiased -- only its variance rises. That makes
        # the thinning a precision statement rather than a bias one, and it travels with
        # the row so nobody has to go and find out which it was.
        ("shards_swept", "BIGINT"),
        ("thinning", "DOUBLE"),
    ),
    # Dosage after the GC trend is removed. This is the table a copy-number claim is made
    # from: `relative` carries a composition bias every probe on a contig shares, which its
    # bootstrap interval cannot see, and `z` is measured against the residual spread rather
    # than against that interval.
    "it2_dosage_composition": (
        ("chrom", "VARCHAR"),
        # The chromosome's own GC from the reference, not its probes' -- the probes are what
        # the uniqueness filter left and are not composed like the sequence around them.
        ("gc", "DOUBLE"),
        ("relative", "DOUBLE"),
        ("residual", "DOUBLE"),
        ("z", "DOUBLE"),
        # Signed: 2 x (residual - 1), so a loss reads negative instead of being folded.
        ("implied_fraction", "DOUBLE"),
    ),
    "it2_mosaic_multi": (
        ("fraction", "DOUBLE"),
        ("affected", "VARCHAR"),
        ("n_affected", "BIGINT"),
        ("recall", "DOUBLE"),
        # Untouched contigs flagged on the same replicate that recovered the injected ones.
        # Measured, not assumed from a nominal five per cent -- this is the column that says
        # whether a genome-wide bound survives on a variegated genome.
        ("false_positive_rate", "DOUBLE"),
        ("replicates", "BIGINT"),
        ("chromosomes_tested", "BIGINT"),
        # What the injected contigs did to the two constants a real run fits: the mechanism
        # behind any false positive, since nothing else here is shared between contigs.
        ("refit_centre", "DOUBLE"),
        ("refit_rho", "DOUBLE"),
        ("seconds", "DOUBLE"),
    ),
}

#: The step-8 limits table is written with one power column per simulated fraction, so its
#: schema is built from the grid the run actually used rather than fixed here.
LIMITS_TABLE = "it2_mosaic_limits"
LIMITS_FIXED: tuple[tuple[str, str], ...] = (
    ("chrom", "VARCHAR"),
    ("statistic", "VARCHAR"),
    ("n_sites", "BIGINT"),
    ("mean_depth", "DOUBLE"),
    # Empty when the contig never reaches 80 % power at any simulated fraction. Empty is the
    # honest value: a blind spot is not a large limit.
    ("f80", "DOUBLE"),
)

TRANSFORMS: dict[str, str] = {
    "it2_mosaic_bdev": (
        "mean |BAF - centre| over each contig's heterozygous PASS calls, against a null "
        "simulated from that contig's own depth margin and the genome-wide beta-binomial "
        "over-dispersion; mva.mosaic.bdev via tools/fit_it2_mosaic.py"
    ),
    "it2_mosaic_fractions": (
        "Markello 2012's DANFIP relation on the upper band, with the same estimator run on "
        "null draws and subtracted; mva.mosaic.bdev.danfip"
    ),
    "it2_mosaic_models": (
        "five per-chromosome models (normal, monosomy, mitotic trisomy, meiotic trisomy, "
        "copy-neutral LOH) re-implemented from Kong 2018 and fitted by bounded maximum "
        "likelihood: a beta-binomial mixture on allele fraction times one Gaussian on the "
        "contig's mean depth ratio; mva.mosaic.madseq"
    ),
    "it2_mosaic_verdicts": (
        "BIC ranking of the five fits with Kong 2018's Delta-BIC < 10 low-confidence rule "
        "adopted as written; mva.mosaic.madseq.best"
    ),
    "it2_mosaic_density": (
        "heterozygous calls per megabase of arm and per PASS call, straight from "
        "results.it2_mosaic_density"
    ),
    "it2_mosaic_multi": (
        "forward mixing simulation with two and three contigs abnormal at once, rescoring "
        "every contig on the same replicate; mva.mosaic.variegated.multi_chromosome"
    ),
    "it2_chrom_dosage": (
        "per-chromosome k-mer dosage from one counting pass over the whole read store: "
        "reference-unique 31-mers per contig plus a genome-wide calibration set, counted "
        "with mva.kmer.count and divided by two denominators; mva.kmer.dosage"
    ),
    "it2_dosage_composition": (
        "per-chromosome k-mer dosage regressed on the chromosome's GC content measured from "
        "GRCh38, reported as the residual and its z against the residual spread; "
        "mva.kmer.dosage.composition via tools/analyse_it2_dosage.py"
    ),
    LIMITS_TABLE: (
        "power against injected cell fraction from the contig's own depths, for the "
        "fold-over statistic and for entry 037's mean-BAF statistic on identical draws; "
        "mva.mosaic.simulate.power_curve"
    ),
}

CALLSET_REF = (
    "results.it2_mosaic_sites + results.it2_mosaic_depth + results.it2_mosaic_density "
    "(all derived from warehouse.variants_raw) + warehouse.cytoband_arms"
)
CLINICAL_REF = "ressources/hackathon-rules/Challenge_Clinical_Phenotype_1.md"
CLINICAL_TRANSFORM = (
    "not an input: the clinical document lists no karyotype and no term a blood-DNA "
    "aneuploid fraction would predict, and the delivery never states which tissue was "
    "sequenced. Recorded so a reader cannot take a cell fraction here for a severity "
    "statement about the child"
)
TOOL = "mva-warehouse pg-load-it2-step8"

#: The dosage table did not come from the callset. It was counted over the raw read store
#: with reference-unique k-mers, so it shares no input with its neighbours past the FASTQ --
#: which is the entire reason the step runs it, and exactly the sort of thing a lineage row
#: that quietly inherited ``CALLSET_REF`` would hide.
READS_REF = (
    "the 272-shard read store (raw FASTQ) counted with reference-unique 31-mers from GRCh38; "
    "no callset, no aligner and no patient coordinate enters this route"
)

#: Tables whose source is not the callset: table -> (source kind, source reference).
SOURCES: dict[str, tuple[str, str]] = {
    "it2_chrom_dosage": ("raw", READS_REF),
    "it2_dosage_composition": ("raw", READS_REF),
}
