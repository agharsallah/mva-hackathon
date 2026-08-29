"""What lands in the warehouse, and what shape each source file is in.

A profile directory is a pile of tab-separated files written by shell pipelines. They are
not uniform: some carry a header row, some do not, some are cut into ``##`` sections, one
is a BED interval list. Before any of it can be queried in SQL it has to be described —
which file becomes which table, and which parser turns it into records.

This module is that description, and it is deliberately split in two:

* :func:`discover` **sniffs** a directory and infers the shape of every file it finds.
  Nothing here knows about this proband or this challenge, so pointing the toolkit at a
  different case yields a working warehouse with no code changes.
* :data:`OVERRIDES` names the handful of files whose shape cannot be inferred — a
  headerless table has no way to announce its own column names — and supplies them.

Adding a case means adding overrides, never editing the sniffer.
"""

from dataclasses import dataclass
from pathlib import Path

#: File suffixes worth staging. Everything else in a profile directory is documentation.
STAGEABLE = {".tsv", ".bed", ".txt"}

#: Shapes a source file can be in. Each maps to one normaliser in :mod:`mva.warehouse.stage`.
SHAPES = ("table", "sections", "bed", "lines")


@dataclass(frozen=True)
class Dataset:
    """One source file and the SQL table it becomes.

    ``columns`` is only consulted for headerless sources; when it is empty the first line
    of the file is taken as the header, which is the common case. ``description`` is
    carried through to the warehouse's own catalogue table so someone opening the database
    cold can see what each table is without going back to the repository.
    """

    table: str
    source: str
    shape: str = "table"
    columns: tuple[str, ...] = ()
    description: str = ""

    def path(self, root: Path) -> Path:
        """Where this dataset's source file lives under a profile directory."""
        return root / self.source


#: Files whose shape or column names cannot be read off the file itself.
#:
#: ``vcf_contig_counts.tsv`` is three bare columns with no header; ``vcf_fields.tsv`` is
#: three bare columns whose first cell is the VCF section it came from;
#: ``vcf_filter_gt_counts.tsv`` is two ``##`` blocks rather than one table.
OVERRIDES: dict[str, Dataset] = {
    "vcf_contig_counts.tsv": Dataset(
        table="contig_counts",
        source="vcf_contig_counts.tsv",
        shape="table",
        columns=("chrom", "length", "n_records"),
        description="Variant records per contig, with the contig's length in bases.",
    ),
    "vcf_fields.tsv": Dataset(
        table="vcf_fields",
        source="vcf_fields.tsv",
        shape="table",
        columns=("kind", "id", "description"),
        description="Every FILTER/INFO/FORMAT field the callset header declares.",
    ),
    "vcf_filter_gt_counts.tsv": Dataset(
        table="filter_gt_counts",
        source="vcf_filter_gt_counts.tsv",
        shape="sections",
        columns=("section", "label", "count"),
        description="How many records carry each FILTER value and each genotype.",
    ),
    "vcf_header.txt": Dataset(
        table="vcf_header_lines",
        source="vcf_header.txt",
        shape="lines",
        columns=("line_no", "line"),
        description="The raw VCF header, kept verbatim for provenance.",
    ),
    "vcf_stats_summary.txt": Dataset(
        table="stats_summary",
        source="vcf_stats_summary.txt",
        shape="lines",
        columns=("line_no", "line"),
        description="Raw bcftools stats output, kept verbatim for provenance.",
    ),
}

#: Human-readable notes for the tables the sniffer finds on its own. Absent keys are fine;
#: the catalogue simply carries an empty description.
NOTES: dict[str, str] = {
    "fastq_profile": "One row per FASTQ file: size, read length, estimated read and base counts.",
    "fastq_qc_l001": "fastp quality metrics sampled from one lane.",
    "fastq_read_headers": "First read name per FASTQ, with the index barcode redacted.",
    "manifest": "Delivered files with sizes and a checksum over the first megabyte.",
    "panel_variant_counts": "Variant records falling inside each panel gene's span.",
    "vcf_chrom_allele_balance": "Per-contig heterozygote count, mean VAF and mean depth.",
    "mva_panel_grch38": "The panel's gene intervals on GRCh38.",
}


def table_name(source: str) -> str:
    """Turn a filename into a SQL-safe table name.

    ``vcf_chrom_allele_balance.tsv`` becomes ``vcf_chrom_allele_balance``. A leading digit
    would be illegal unquoted, so it is prefixed.
    """
    stem = Path(source).stem
    name = "".join(char if char.isalnum() else "_" for char in stem).strip("_").lower()
    return f"t_{name}" if not name or name[0].isdigit() else name


def sniff(path: Path) -> str:
    """Guess a file's shape from its suffix and first meaningful line.

    Returns one of :data:`SHAPES`. A ``.bed`` is an interval list; a file whose first
    non-blank line opens a ``##`` block is sectioned; anything else tab-separated is a
    plain table, and a file with no tabs at all is kept as numbered lines.
    """
    if path.suffix == ".bed":
        return "bed"
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                if not line.strip():
                    continue
                if line.startswith("##"):
                    return "sections"
                if line.startswith("#"):
                    continue
                return "table" if "\t" in line else "lines"
    except OSError:
        return "lines"
    return "lines"


def discover(root: Path) -> list[Dataset]:
    """Describe every stageable file in a profile directory.

    Overrides win where they exist; everything else is sniffed. The result is sorted by
    table name so a staging run is deterministic and its log diffs cleanly between runs.
    """
    datasets: list[Dataset] = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix not in STAGEABLE:
            continue
        override = OVERRIDES.get(path.name)
        if override is not None:
            datasets.append(override)
            continue
        name = table_name(path.name)
        datasets.append(Dataset(
            table=name,
            source=path.name,
            shape=sniff(path),
            description=NOTES.get(name, ""),
        ))
    return sorted(datasets, key=lambda dataset: dataset.table)
