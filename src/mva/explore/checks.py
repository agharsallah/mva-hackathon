"""Turning measured numbers into verdicts.

Reading a profile by hand means knowing that a transition/transversion ratio near 2.0 is
what a healthy whole genome looks like, that a duplication rate above 25% means the
library was over-amplified, and that a chromosome whose heterozygous sites sit away from
half alternate reads is the thing this entire project is looking for. That knowledge
normally lives in the analyst's head and gets re-applied, inconsistently, every time.

This module writes it down. Each check is a named threshold with a stated basis, so the
report says *why* a number is acceptable rather than only what it is, and so a threshold
can be argued with — which is the point of putting it in one file.

**These are conventions, not measurements.** The numbers being judged come from executed
runs; the bands they are judged against are community expectations for a germline
short-read whole genome, cited in each check's ``basis``. A ``WARN`` is a prompt to look,
never a finding on its own.
"""

from dataclasses import dataclass
from enum import Enum

from .profile import CallsetProfile
from .theme import BAD, DECISION, GOOD, MACHINE, Hue


class Verdict(Enum):
    """How a measured value compares to its expected band."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"

    @property
    def hue(self) -> Hue:
        """The repository colour for this verdict, so every badge agrees with every chart."""
        return {
            Verdict.PASS: GOOD,
            Verdict.WARN: DECISION,
            Verdict.FAIL: BAD,
            Verdict.INFO: MACHINE,
        }[self]


@dataclass(frozen=True)
class Check:
    """One judged metric: what was measured, how it reads, and on what authority."""

    name: str
    value: float | None
    display: str
    verdict: Verdict
    expected: str
    basis: str
    consequence: str = ""

    @property
    def is_actionable(self) -> bool:
        """True when this check asks someone to do something."""
        return self.verdict in (Verdict.WARN, Verdict.FAIL)


def _band(
    value: float | None, good: tuple[float, float], tolerated: tuple[float, float]
) -> Verdict:
    """Grade a value against an inner good band and an outer tolerated band."""
    if value is None:
        return Verdict.INFO
    if good[0] <= value <= good[1]:
        return Verdict.PASS
    if tolerated[0] <= value <= tolerated[1]:
        return Verdict.WARN
    return Verdict.FAIL


def run_checks(profile: CallsetProfile) -> list[Check]:
    """Grade every metric the profile supports, skipping the ones it cannot support."""
    checks: list[Check] = []
    for build in (_callset_checks, _filter_checks, _read_checks, _balance_checks):
        checks.extend(build(profile))
    return checks


def _callset_checks(profile: CallsetProfile) -> list[Check]:
    out: list[Check] = []
    tstv = ts_tv(profile)
    if tstv is not None:
        out.append(
            Check(
                name="Transition/transversion ratio",
                value=tstv,
                display=f"{tstv:.2f}",
                verdict=_band(tstv, (1.9, 2.2), (1.7, 2.4)),
                expected="1.9 – 2.2 genome-wide",
                basis="Transitions are chemically easier than transversions, so real human "
                "variation runs about 2:1. Random sequencing error has no such bias and "
                "pulls the ratio toward 0.5, which makes this the standard single number "
                "for 'is this callset mostly real'.",
                consequence="A low ratio means false positives are diluting the callset.",
            )
        )

    snps = profile.summary.get("SNPs")
    indels = profile.summary.get("indels")
    if snps and indels:
        ratio = indels / snps
        out.append(
            Check(
                name="Indel / SNP ratio",
                value=ratio,
                display=f"{ratio:.3f}",
                verdict=_band(ratio, (0.10, 0.25), (0.08, 0.35)),
                expected="0.10 – 0.25 for short-read whole genomes",
                basis="Insertions and deletions are rarer and harder to call than substitutions. "
                "An inflated ratio usually means alignment artefacts in repetitive sequence.",
                consequence="Indels dominate the representation problem, so an excess raises the "
                "cost of skipping normalization.",
            )
        )

    multiallelic = profile.summary.get("multiallelic sites")
    if multiallelic is not None:
        out.append(
            Check(
                name="Multiallelic sites",
                value=float(multiallelic),
                display=f"{multiallelic:,}",
                verdict=Verdict.FAIL if multiallelic else Verdict.PASS,
                expected="0 after normalization",
                basis="A site with two alternate alleles on one row cannot be string-matched "
                "against a submission that names one allele. `bcftools norm -m -both` "
                "splits them.",
                consequence="Every one of these is a variant the scorer cannot be shown until "
                "the callset is normalized.",
            )
        )

    genotypes = profile.genotype_counts
    het = genotypes.get("0/1", 0) + genotypes.get("0|1", 0)
    hom = genotypes.get("1/1", 0) + genotypes.get("1|1", 0)
    if het and hom:
        ratio = het / hom
        out.append(
            Check(
                name="Heterozygous / homozygous-alt ratio",
                value=ratio,
                display=f"{ratio:.2f}",
                verdict=_band(ratio, (1.3, 2.1), (1.1, 2.6)),
                expected="1.3 – 2.1 for an outbred individual",
                basis="Consanguinity and long runs of homozygosity push this down; contamination "
                "and false-positive heterozygous calls push it up.",
                consequence="A low ratio would argue for a homozygous rather than compound-"
                "heterozygous answer.",
            )
        )
    return out


def _filter_checks(profile: CallsetProfile) -> list[Check]:
    counts = profile.filter_counts
    total = sum(counts.values())
    if not total:
        return []
    passing = counts.get("PASS", 0)
    fraction = passing / total
    out = [
        Check(
            name="PASS fraction",
            value=fraction,
            display=f"{fraction:.1%}",
            verdict=_band(fraction, (0.90, 1.0), (0.80, 1.0)),
            expected="above 90% of records",
            basis="Hard filters are tuned to remove a small tail. Removing much more than a "
            "tenth of the callset means the filters, not the biology, are deciding what "
            "is visible.",
            consequence=f"{total - passing:,} suppressed calls are a search space, not garbage — "
            "a real variant in repetitive sequence is exactly what gets flagged.",
        )
    ]

    phased, records = profile.phased_records, profile.total_records
    if phased is not None and records:
        share = phased / records
        out.append(
            Check(
                name="Records carrying physical phasing",
                value=share,
                display=f"{share:.1%}",
                verdict=Verdict.INFO,
                expected="reported, not graded",
                basis="Read-backed phasing only reaches variants close enough to share a read "
                "pair — a few hundred bases. Most pairs are therefore of unknown phase.",
                consequence="Phasing confirms a compound heterozygote when it is available; it "
                "cannot be the filter that finds one.",
            )
        )
    return out


def _read_checks(profile: CallsetProfile) -> list[Check]:
    qc, out = profile.read_qc, []
    q30 = qc.get("after_filtering.q30_rate") or qc.get("before_filtering.q30_rate")
    if q30 is not None:
        out.append(
            Check(
                name="Q30 rate",
                value=q30,
                display=f"{q30:.1%}",
                verdict=_band(q30, (0.90, 1.0), (0.80, 1.0)),
                expected="above 90% of bases",
                basis="Q30 means a 1-in-1000 chance the base is wrong. Illumina specifies at "
                "least 75–80% of bases at Q30 for a patterned flow cell; a healthy run "
                "clears 90%.",
            )
        )
    gc = qc.get("after_filtering.gc_content") or qc.get("before_filtering.gc_content")
    if gc is not None:
        out.append(
            Check(
                name="GC content",
                value=gc,
                display=f"{gc:.1%}",
                verdict=_band(gc, (0.38, 0.44), (0.35, 0.48)),
                expected="around 41% for human",
                basis="The human genome is about 41% G+C. A shifted value points at bacterial "
                "contamination or a biased amplification step, not at the patient.",
            )
        )
    dup = qc.get("duplication_rate")
    if dup is not None:
        out.append(
            Check(
                name="Duplication rate",
                value=dup,
                display=f"{dup:.1%}",
                verdict=_band(dup, (0.0, 0.15), (0.0, 0.25)),
                expected="below 15%",
                basis="PCR duplicates are copies of one original fragment. They inflate apparent "
                "depth without adding evidence, so a high rate means effective coverage is "
                "lower than the raw number suggests.",
            )
        )
    insert = qc.get("insert_size_peak")
    if insert is not None:
        out.append(
            Check(
                name="Insert size peak",
                value=insert,
                display=f"{insert:.0f} bp",
                verdict=_band(insert, (200, 600), (150, 800)),
                expected="200 – 600 bp for 2×150 sequencing",
                basis="The fragment must be longer than the two reads or the mates overlap and "
                "the pair stops spanning anything. Longer fragments also carry phasing "
                "information further.",
                consequence="The insert length is the hard ceiling on how far read-backed phasing "
                "can reach between two candidate variants.",
            )
        )
    coverage = _coverage(profile)
    if coverage is not None:
        out.append(
            Check(
                name="Estimated raw coverage",
                value=coverage,
                display=f"{coverage:.0f}×",
                verdict=_band(coverage, (30, 200), (20, 200)),
                expected="at least 30× for germline whole-genome calling",
                basis="Thirty independent reads over a position is the community floor for "
                "confidently calling a heterozygous site; below it, one of the two copies "
                "can be missed by chance.",
            )
        )
    return out


def _balance_checks(profile: CallsetProfile) -> list[Check]:
    autosomes = [b for b in profile.balance if b.chrom.removeprefix("chr").isdigit()]
    if not autosomes:
        return []
    worst = max(autosomes, key=lambda b: abs(b.deviation))
    out = [
        Check(
            name=f"Largest autosomal allele-balance deviation (chr{worst.chrom.removeprefix('chr')})",
            value=worst.deviation,
            display=f"{worst.mean_vaf:.4f} (Δ {worst.deviation:+.4f})",
            verdict=_band(worst.mean_vaf, (0.48, 0.52), (0.46, 0.54)),
            expected="0.48 – 0.52; a diploid chromosome sits at 0.50",
            basis="Every heterozygous site on a two-copy chromosome should show half alternate "
            "reads. A population of cells carrying a third copy, or missing one, drags the "
            "mean off 0.5 in proportion to how many cells are affected.",
            consequence="This is the direct blood-derived test for mosaic aneuploidy. A flat "
            "profile is a real negative result and belongs in the write-up as one.",
        )
    ]

    by_name = {b.chrom.removeprefix("chr"): b for b in profile.balance}
    x, y = by_name.get("X"), by_name.get("Y")
    if x and y:
        called = "male (XY)" if y.n_het and y.mean_depth > 5 else "female (XX)"
        out.append(
            Check(
                name="Genetic sex from sex-chromosome evidence",
                value=None,
                display=f"{called} — chrX {x.n_het:,} het @ {x.mean_depth:.0f}×, "
                f"chrY {y.n_het:,} het @ {y.mean_depth:.0f}×",
                verdict=Verdict.INFO,
                expected="one of XX or XY, consistent with the clinical record",
                basis="A single X gives few heterozygous sites and half the autosomal depth; a "
                "present Y gives real depth on a chromosome that is absent in a female "
                "sample. Residual chrY heterozygosity comes from the pseudoautosomal "
                "regions the X and Y share.",
                consequence="A mismatch against the clinical record means a sample swap, which "
                "invalidates everything downstream.",
            )
        )
    return out


def ts_tv(profile: CallsetProfile) -> float | None:
    rows = profile.stats.get("TSTV")
    if not rows or len(rows[0]) < 3:
        return None
    try:
        return float(rows[0][2])
    except ValueError:
        return None


def _coverage(profile: CallsetProfile) -> float | None:
    """Raw coverage from sequenced bases over the GRCh38 genome length."""
    total = profile.total_gigabases
    if not total:
        return None
    return total * 1e9 / GENOME_BASES


#: GRCh38 primary assembly length in bases — the denominator for coverage.
GENOME_BASES = 3_099_734_149
