"""One directory of profiling artifacts, loaded into one object.

``tools/profile-genomic-data.sh`` reduces an 80 GB dataset to roughly 600 KB of headers,
tallies and distributions. That directory is the exploration substrate: it is committable,
it loads in milliseconds, and it answers most questions a first pass at a callset asks.
This module turns it into a typed object so the views never touch a filename.

The filename mapping lives in :class:`ProfileLayout` rather than being hard-coded, which
is the seam that makes the toolkit case-agnostic — a different lab's profile directory is
a different layout, not a different reader and not a different set of views.

**Every section is optional.** A profile with no FASTQ files, or a run that died before
``bcftools stats`` finished, loads fine and simply reports fewer exhibits. A missing artifact
is a gap in the report, never a traceback, because the most common time to want a profile
is while the pipeline that builds it is still being debugged.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from . import readers
from .readers import Region, Sections, Table, VcfHeader


@dataclass(frozen=True)
class ProfileLayout:
    """Which filename holds which artifact.

    Override any field to read a differently-named profile directory::

        layout = ProfileLayout(callset_stats="bcftools_stats.txt")
        profile = CallsetProfile.load("other-case/", layout)
    """

    manifest: str = "manifest.tsv"
    vcf_header: str = "vcf_header.txt"
    vcf_fields: str = "vcf_fields.tsv"
    contig_counts: str = "vcf_contig_counts.tsv"
    callset_stats: str = "vcf_stats_summary.txt"
    filter_genotype_counts: str = "vcf_filter_gt_counts.tsv"
    allele_balance: str = "vcf_chrom_allele_balance.tsv"
    read_profile: str = "fastq_profile.tsv"
    read_qc: str = "fastq_qc_L001.tsv"
    read_headers: str = "fastq_read_headers.tsv"
    panel_bed: str = "mva_panel_grch38.bed"
    panel_counts: str = "panel_variant_counts.tsv"


@dataclass(frozen=True)
class Contig:
    """One reference sequence, with how many variants were called on it."""

    name: str
    length: int
    records: int

    @property
    def is_primary(self) -> bool:
        """True for the 24 chromosomes plus the mitochondrion, false for scaffolds.

        A GRCh38 analysis set carries ~2,600 contigs, almost all of them unplaced
        scaffolds, alternate haplotypes and decoys. Charting all of them buries the
        biology, so views default to the primary assembly and count the rest as a total.
        """
        return self.name.removeprefix("chr") in _PRIMARY

    @property
    def density_per_mb(self) -> float:
        """Variants called per megabase — the length-normalised comparison between contigs."""
        return self.records / (self.length / 1e6) if self.length else 0.0


@dataclass(frozen=True)
class ChromBalance:
    """Per-chromosome heterozygous allele balance — the aneuploidy fingerprint.

    A normal diploid chromosome puts a heterozygous site at half alternate reads. A whole
    extra or missing copy in some fraction of cells drags that mean away from 0.5 and
    widens the spread, so a chromosome that stands out here is the signal the whole
    Mosaic Variegated Aneuploidy question turns on.
    """

    chrom: str
    n_het: int
    mean_vaf: float
    mean_depth: float
    pct_in_band: float

    @property
    def deviation(self) -> float:
        """Distance of the mean allele balance from the diploid expectation of 0.5."""
        return self.mean_vaf - 0.5


@dataclass(frozen=True)
class ReadFile:
    """One FASTQ file's yield, as estimated from its compressed size and read length."""

    name: str
    size_bytes: int
    read_length: int
    reads: int
    gigabases: float

    @property
    def lane(self) -> str:
        """The flow-cell lane token (``L001``), or the filename when there is none."""
        for part in self.name.split("_"):
            if len(part) == 4 and part.startswith("L") and part[1:].isdigit():
                return part
        return self.name

    @property
    def mate(self) -> str:
        """``R1`` or ``R2`` — which end of the pair this file holds."""
        for part in self.name.split("_"):
            if part in ("R1", "R2"):
                return part
        return "R1"


@dataclass(frozen=True)
class PanelGene:
    """One candidate gene, its span, and how many variants fell inside it."""

    symbol: str
    chrom: str
    start: int
    end: int
    variants: int
    passing: int
    note: str = ""

    @property
    def suppressed(self) -> int:
        """Calls the caller emitted but flagged — the non-PASS rescue space for this gene."""
        return max(self.variants - self.passing, 0)

    @property
    def suppressed_fraction(self) -> float:
        """Share of this gene's calls that are non-PASS, comparable across genes."""
        return self.suppressed / self.variants if self.variants else 0.0

    @property
    def kilobases(self) -> float:
        """Span in kb, for length-normalising the variant count."""
        return (self.end - self.start) / 1000 if self.end > self.start else 0.0

    @property
    def variants_per_kb(self) -> float:
        """Variant density — what makes a long gene and a short one comparable."""
        return self.variants / self.kilobases if self.kilobases else 0.0


@dataclass(frozen=True)
class CallsetProfile:
    """Everything a profile directory knows, in one object.

    Built by :meth:`load`. Each attribute is independently optional, so check the one you
    need (or use :attr:`available`) rather than assuming a complete run.
    """

    source: Path
    layout: ProfileLayout = ProfileLayout()
    header: VcfHeader | None = None
    contigs: list[Contig] = field(default_factory=list)
    stats: dict[str, list[list[str]]] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)
    filters_and_genotypes: Sections | None = None
    balance: list[ChromBalance] = field(default_factory=list)
    reads: list[ReadFile] = field(default_factory=list)
    read_qc: dict[str, float] = field(default_factory=dict)
    read_qc_note: str = ""
    panel: list[PanelGene] = field(default_factory=list)
    manifest: Table | None = None

    @classmethod
    def load(cls, directory: str | Path,
             layout: ProfileLayout = ProfileLayout()) -> "CallsetProfile":
        """Load every artifact present in ``directory``, skipping every one that is not."""
        root = Path(directory)
        profile = cls(source=root, layout=layout)
        for attribute, filename, build in _LOADERS(layout):
            path = root / filename
            if not path.exists():
                continue
            profile = replace(profile, **build(path))
        # The BED carries why each gene is a candidate; the counts table carries the
        # numbers. Joining them here means no view ever has to know they arrived apart.
        bed = root / layout.panel_bed
        if profile.panel and bed.exists():
            profile = replace(profile, panel=annotate_panel(profile.panel,
                                                            readers.read_bed(bed)))
        return profile

    @property
    def available(self) -> list[str]:
        """Names of the sections that actually loaded — what the report can show."""
        present = []
        for name in ("header", "contigs", "stats", "filters_and_genotypes",
                     "balance", "reads", "read_qc", "panel"):
            if getattr(self, name):
                present.append(name)
        return present

    @property
    def primary_contigs(self) -> list[Contig]:
        """The 24 chromosomes plus the mitochondrion, in assembly order."""
        ordered = [c for c in self.contigs if c.is_primary]
        return sorted(ordered, key=lambda c: _PRIMARY.index(c.name.removeprefix("chr")))

    @property
    def scaffold_records(self) -> int:
        """Variants called outside the primary assembly, as one number."""
        return sum(c.records for c in self.contigs if not c.is_primary)

    @property
    def filter_counts(self) -> dict[str, int]:
        """Records per FILTER combination, exactly as the caller wrote them."""
        return self.filters_and_genotypes.counts("FILTER counts") if self.filters_and_genotypes else {}

    @property
    def genotype_counts(self) -> dict[str, int]:
        """Records per genotype string (``0/1``, ``1/1``, ``1/2``)."""
        return self.filters_and_genotypes.counts("genotype counts") if self.filters_and_genotypes else {}

    @property
    def phased_records(self) -> int | None:
        """Records carrying a physical phasing group, or ``None`` if not measured."""
        scalars = self.filters_and_genotypes.scalars if self.filters_and_genotypes else {}
        return readers.as_int(scalars.get("records_in_phase_group"))

    @property
    def total_records(self) -> int | None:
        """Total records, preferring the tally over the ``bcftools stats`` figure."""
        scalars = self.filters_and_genotypes.scalars if self.filters_and_genotypes else {}
        return readers.as_int(scalars.get("total_records")) or self.summary.get("records")

    @property
    def total_gigabases(self) -> float | None:
        """Estimated sequenced bases across every FASTQ file."""
        return sum(f.gigabases for f in self.reads) if self.reads else None


# --- artifact loaders -------------------------------------------------------------
# One per file. Each returns the keyword arguments to fold into the profile, so adding an
# artifact is one function and one line in _LOADERS, with no change to CallsetProfile.load.

def _load_header(path: Path) -> dict:
    return {"header": readers.read_vcf_header(path)}


def _load_contig_counts(path: Path) -> dict:
    contigs = []
    for line in Path(path).read_text().splitlines():
        cells = line.split("\t")
        if len(cells) < 3:
            continue
        length, records = readers.as_int(cells[1]), readers.as_int(cells[2])
        if length is None or records is None:
            continue
        contigs.append(Contig(cells[0], length, records))
    return {"contigs": contigs}


def _load_stats(path: Path) -> dict:
    sections = readers.read_bcftools_stats(path)
    return {"stats": sections, "summary": readers.summary_numbers(sections)}


def _load_filters(path: Path) -> dict:
    return {"filters_and_genotypes": readers.read_sections(path)}


def _load_balance(path: Path) -> dict:
    table = readers.read_table(path)
    rows = []
    for row in table.rows:
        vaf = readers.as_float(row.get("mean_vaf"))
        if vaf is None:
            continue
        rows.append(ChromBalance(
            chrom=row.get("chrom", ""),
            n_het=readers.as_int(row.get("n_het")) or 0,
            mean_vaf=vaf,
            mean_depth=readers.as_float(row.get("mean_dp")) or 0.0,
            pct_in_band=readers.as_float(row.get("pct_in_0.40_0.60")) or 0.0,
        ))
    return {"balance": rows}


def _load_reads(path: Path) -> dict:
    table = readers.read_table(path)
    files = []
    for row in table.rows:
        reads = readers.as_int(row.get("est_reads"))
        if reads is None:
            continue
        files.append(ReadFile(
            name=row.get("file", ""),
            size_bytes=readers.as_int(row.get("bytes")) or 0,
            read_length=readers.as_int(row.get("read_len")) or 0,
            reads=reads,
            gigabases=readers.as_float(row.get("est_gbases")) or 0.0,
        ))
    return {"reads": files}


def _load_read_qc(path: Path) -> dict:
    table = readers.read_table(path)
    metrics = {}
    for row in table.rows:
        value = readers.as_float(row.get("value"))
        if value is not None:
            metrics[row.get("metric", "")] = value
    return {"read_qc": metrics, "read_qc_note": "; ".join(table.comments)}


def _load_panel(path: Path) -> dict:
    table = readers.read_table(path)
    genes = []
    for row in table.rows:
        start, end = readers.as_int(row.get("start")), readers.as_int(row.get("end"))
        if start is None or end is None:
            continue
        genes.append(PanelGene(
            symbol=row.get("gene", ""), chrom=row.get("chrom", ""),
            start=start, end=end,
            variants=readers.as_int(row.get("n_all")) or 0,
            passing=readers.as_int(row.get("n_pass")) or 0,
        ))
    return {"panel": genes}


def _load_manifest(path: Path) -> dict:
    return {"manifest": readers.read_table(path)}


def _LOADERS(layout: ProfileLayout) -> list[tuple[str, str, Callable[[Path], dict]]]:
    return [
        ("header", layout.vcf_header, _load_header),
        ("contigs", layout.contig_counts, _load_contig_counts),
        ("stats", layout.callset_stats, _load_stats),
        ("filters_and_genotypes", layout.filter_genotype_counts, _load_filters),
        ("balance", layout.allele_balance, _load_balance),
        ("reads", layout.read_profile, _load_reads),
        ("read_qc", layout.read_qc, _load_read_qc),
        ("panel", layout.panel_counts, _load_panel),
        ("manifest", layout.manifest, _load_manifest),
    ]


def annotate_panel(genes: list[PanelGene], regions: list[Region]) -> list[PanelGene]:
    """Attach each BED interval's note column to the matching gene.

    The counts table carries numbers and the BED carries why the gene is on the panel at
    all. Joining them by symbol keeps the annotation next to the count in every view.
    """
    notes = {r.name: (r.extras[-1] if r.extras else "") for r in regions}
    return [replace(g, note=notes.get(g.symbol, g.note)) for g in genes]


_PRIMARY = [str(n) for n in range(1, 23)] + ["X", "Y", "M", "MT"]
