"""Build manifests for the three population-reference tables in ``ressources/reference/``.

``tools/build_reference_data.py`` derives ``gnomad_constraint.tsv`` and ``clinvar_panel.tsv``
from two large public downloads that are deliberately never committed (95 MB and 193 MB),
and ``qc_norms.tsv`` is hand-curated from primary literature with no generator at all. All
three therefore had the same defect: the bytes in the repository could not say what
produced them. Their provenance lived as prose in ``ressources/reference/README.md``, which
is a *claim* — the thing a manifest exists to replace.

This module owns the three JSON manifests written beside them. It mirrors
:mod:`mva.viz.genesetmanifest`: the tool calls it on every run, a human never edits the
output, and :mod:`mva.viz.refprovenance` normalises the file onto the row shape
``GET /api/provenance/reference`` returns.

Three shape decisions, each because the alternative would have been a fabrication:

* **A digest is measured or it is ``null``.** The upstream files live in gitignored
  scratch. When the scratch copy is on disk it is hashed; when it is not, ``sha256`` is
  ``null`` and a ``known_gap`` string says which fact is missing and why. A digest copied
  out of a README would name bytes this run never saw.
* **A release is read from the payload, never from the filename.** ClinVar publishes
  monthly at a *stable* URL, so the release can only come from the VCF's own
  ``##fileDate`` header. gnomAD's URL is versioned and immutable, so there the release is
  the path segment and stays true.
* **``qc_norms``' inputs are its own citations, extracted from the table.** The ``source``
  and ``url`` columns are the one place a citation is written; a hand-kept second list
  beside them would drift, and a drifted citation is worse than none because it looks
  checked.

No genomic position is written here or can be: a manifest records upstream URLs, releases,
digests, byte and row counts, and citations. ``tests/test_viz_refprovenance.py`` asserts
that over every committed manifest.
"""

import csv
import gzip
import subprocess
from collections.abc import Iterable
from pathlib import Path

from .manifestbase import committed, envelope, fileinput, output

#: The versioned gnomAD constraint object. The release lives in the path, so the URL and
#: the release cannot disagree; ``tools/build_reference_data.py`` fetches this exact URL.
GNOMAD_URL = (
    "https://storage.googleapis.com/gcp-public-data--gnomad/"
    "release/4.1/constraint/gnomad.v4.1.constraint_metrics.tsv"
)
GNOMAD_RELEASE = "4.1"

#: The ClinVar GRCh38 VCF. **Not** versioned — this URL always serves the current
#: release, which is why the release below is read from the file's ``##fileDate``.
CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"

#: UCSC's GRCh38 cytogenetic band table. Not versioned by URL — hg38's bands have been
#: stable since the assembly was released, so the release below is the assembly name and
#: the digest of the downloaded bytes is what actually pins it.
CYTOBAND_URL = "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/cytoBand.txt.gz"
CYTOBAND_RELEASE = "hg38 / GRCh38"

GNOMAD_METHOD = (
    "One row per gene: the upstream file's Ensembl rows are kept where canonical == true "
    "and transcript_type == protein_coding, and 26 of its 55 columns are renamed onto a "
    "flat schema. The RefSeq (NM_/XM_) mirror rows are dropped because they carry neither "
    "a contig nor a transcript type, so the subset rule cannot be applied to them. "
    "constraint_flags is flattened from a quoted JSON array to a comma-separated string, "
    "because a TSV field containing a double quote is not readable by COPY ... FORMAT "
    "text. Scientific notation is rendered as a plain decimal and gnomAD's NA is passed "
    "through unchanged rather than becoming an empty field, so a missing metric stays "
    "distinguishable from a zero one. The panel BED is read only to report how many panel "
    "genes were found; it does not subset the output, which is genome-wide."
)

CLINVAR_METHOD = (
    "The panel BED's intervals, one bcftools region query each, projected onto ten "
    "columns. The BED's contig names carry a reference-style prefix and the ClinVar "
    "GRCh38 VCF's do not, so a stripped copy of the BED is written to scratch first: "
    "querying with the prefixed names returns zero rows, which is indistinguishable from "
    "'no variants here'. The gene column prefers the panel symbol when the record's "
    "GENEINFO lists it and falls back to the interval's own symbol, so a record annotated "
    "only to a neighbouring gene still names the interval it was pulled from. The "
    "intervals carry 20 kb of padding, so some rows legitimately fall in a flanking gene "
    "and the gene column must be filtered before any per-gene number is quoted."
)

QC_METHOD = (
    "Hand-curated from primary literature; there is no generator and no upstream file. "
    "Every row carries the PMID/DOI it came from and a paraphrase of the sentence the "
    "number was taken from, and a metric with no citable range is absent rather than "
    "guessed. This manifest's inputs are the table's own distinct source/url pairs, "
    "extracted from the file, so a citation has exactly one owner and cannot drift."
)

GNOMAD_LICENCE = (
    "gnomAD's primary data are released under the Creative Commons Zero Public Domain "
    "Dedication (CC0); attribution is requested, not required. This repository includes "
    "data from the gnomAD v4.1 release."
)
CLINVAR_LICENCE = (
    "ClinVar is a US-government public resource; NCBI asks for attribution on "
    "redistribution and states the data are not intended for direct diagnostic use "
    "without review by a genetics professional. Cite PMID 29165669."
)
QC_LICENCE = (
    "No data are redistributed: every row is a number quoted from a published paper, "
    "cited by PMID and DOI. The paraphrases are this repository's own text."
)

CYTOBAND_LICENCE = (
    "UCSC Genome Browser data are free for any use; the cytogenetic band table is derived "
    "from published ideograms and carries no restriction on redistribution."
)

PATIENT_DATA = (
    "none. Public reference data only - a gene, a transcript, a published classification "
    "or a literature range. This manifest records URLs, releases, digests and counts."
)

#: The role each committed input plays, so a reader of the manifest alone knows why the
#: file is listed rather than only that it was read.
BED_ROLE = "the gene panel: the intervals queried, and the symbols coverage is reported against"


CYTOBAND_METHOD = (
    "One row per canonical contig, reduced from the band table's ~1,200 rows. The "
    "centromere is the span of the bands stained acen — there are always two, one either "
    "side of the constriction — so p_end is the first acen start and q_start is the last "
    "acen end; that is the definition of an arm boundary rather than a threshold. "
    "chrom_length is the largest band end on the contig, which is the assembly length the "
    "band table itself asserts. acrocentric is read from the file's own stain column: a "
    "chromosome carrying a stalk band on its short arm (13, 14, 15, 21, 22) has no "
    "callable p arm, and step 8 reports it q-arm-only. Alternate haplotypes and patch "
    "contigs are dropped: they have no centromere and no arms."
)


def clinvar_release(vcf: Path) -> str | None:
    """The VCF's own ``##fileDate``, or ``None`` when the file is absent or unreadable.

    The only authoritative release for ClinVar. The FTP mirror's ``Last-Modified`` names
    when the mirror was written, not which release it holds, and the URL carries no
    version at all.
    """
    try:
        with gzip.open(vcf, "rt") as stream:
            for line in stream:
                if not line.startswith("##"):
                    return None
                if line.startswith("##fileDate="):
                    return line.strip().split("=", 1)[1]
    except OSError:
        return None
    return None


def bcftools_version() -> str | None:
    """``bcftools 1.24 / htslib 1.24``, or ``None`` when the tool is not on PATH.

    Recorded because the extract is that tool's output: a region query is not a pure
    function of the VCF alone, and a reader reproducing the row count needs to know which
    binary produced it.
    """
    try:
        done = subprocess.run(
            ["bcftools", "--version"], capture_output=True, text=True, check=False, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = [
        line.strip().removeprefix("Using ") for line in done.stdout.splitlines() if line.strip()
    ]
    return " / ".join(lines[:2]) or None


def gnomad(out: Path, source: Path, bed: Path) -> dict:
    """The manifest for ``gnomad_constraint.tsv``."""
    written = output(out)
    return envelope("gnomad_constraint", "tools/build_reference_data.py gnomad") | {
        "method": GNOMAD_METHOD,
        "inputs": [
            fileinput(
                source,
                "gnomAD v4.1 constraint metrics",
                GNOMAD_URL,
                "observed-vs-expected damage counts per transcript",
                release=GNOMAD_RELEASE,
            ),
            committed(bed, BED_ROLE),
        ],
        "outputs": [written],
        "licence": GNOMAD_LICENCE,
        "patient_data": PATIENT_DATA,
        "note": (
            f"{written['rows']:,} genes from gnomAD v{GNOMAD_RELEASE}, one canonical "
            "protein-coding Ensembl transcript each. Autosomes only upstream: the file "
            "carries no sex-chromosome row at all, so a gene absent from it is not "
            "unconstrained."
        ),
    }


def clinvar(out: Path, source: Path, index: Path, bed: Path) -> dict:
    """The manifest for ``clinvar_panel.tsv``."""
    written = output(out)
    release = clinvar_release(source)
    vcf = fileinput(
        source,
        "ClinVar GRCh38 VCF",
        CLINVAR_URL,
        "the germline classification a clinical laboratory has already submitted",
        release=release,
    )
    vcf["digest_scope"] = (
        "the digest is of the scratch copy present when this manifest was written. The "
        "extract run recorded none, so the tie between that download and the committed "
        "extract is file identity on disk, not a digest captured at extract time."
    )
    if release is None:
        vcf["known_gap"] = (
            "the release could not be read: ClinVar's URL carries no version, so "
            "##fileDate is the only authoritative release and the file was not readable "
            "when this manifest was written. "
        ) + str(vcf.get("known_gap", ""))
    return envelope("clinvar_panel", "tools/build_reference_data.py clinvar") | {
        "method": CLINVAR_METHOD,
        "inputs": [
            vcf,
            fileinput(
                index,
                "ClinVar GRCh38 VCF index",
                CLINVAR_URL + ".tbi",
                "the tabix index the region queries need",
                release=release,
            ),
            committed(bed, BED_ROLE),
        ],
        "outputs": [written],
        "tool": bcftools_version(),
        "licence": CLINVAR_LICENCE,
        "patient_data": PATIENT_DATA,
        "note": (
            f"{written['rows']:,} ClinVar records over the {_bed_genes(bed)} panel "
            f"intervals, release {release or 'unknown'}. The intervals are padded, so "
            "some rows fall in a flanking gene; filter the gene column before quoting a "
            "per-gene number."
        ),
    }


def cytobands(out: Path, source: Path) -> dict:
    """The manifest for ``cytoband_arms.tsv``."""
    written = output(out)
    return envelope("cytoband_arms", "tools/build_cytobands.py") | {
        "method": CYTOBAND_METHOD,
        "inputs": [
            fileinput(
                source,
                "UCSC hg38 cytoBand",
                CYTOBAND_URL,
                "cytogenetic band intervals and stains, from which the arm boundaries come",
                release=CYTOBAND_RELEASE,
            )
        ],
        "outputs": [written],
        "licence": CYTOBAND_LICENCE,
        "patient_data": PATIENT_DATA,
        "note": (
            f"{written['rows']} contigs: 22 autosomes plus X and Y. The positions here are "
            "reference geometry — where a centromere sits in GRCh38 — and say nothing about "
            "any sample, which is why the table is committed while every table derived from "
            "the child's callset is not."
        ),
    }


def qc_norms(out: Path) -> dict:
    """The manifest for ``qc_norms.tsv``, whose inputs are the citations it carries."""
    written = output(out)
    inputs = list(citations(out))
    return envelope("qc_norms", "tools/build_reference_data.py qc-norms") | {
        "method": QC_METHOD,
        "inputs": inputs,
        "outputs": [written],
        "licence": QC_LICENCE,
        "patient_data": PATIENT_DATA,
        "known_gap": (
            "no input carries a digest, legitimately: each is a published paper, not a "
            "download. There is nothing to hash and no release to name."
        ),
        "note": (
            f"{written['rows']} literature-derived expected ranges from {len(inputs)} "
            "primary sources, hand-curated with no generator. This manifest is written "
            "from the table's own source and url columns; the numbers are not."
        ),
    }


def citations(table: Path) -> Iterable[dict]:
    """One input per distinct ``(source, url)`` in ``qc_norms.tsv``, in first-seen order.

    ``sha256``, ``bytes`` and ``release`` are ``null`` and mean it: a citation names a
    paper, and a paper has no digest. ``metrics`` says which rows the source supplies, so
    a reader can check a number against the right paper without opening the table.
    """
    seen: dict[tuple[str, str], dict] = {}
    with table.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            key = (row["source"], row["url"])
            entry = seen.setdefault(
                key,
                {
                    "name": row["source"],
                    "url": row["url"],
                    "release": None,
                    "sha256": None,
                    "bytes": None,
                    "role": "cited expected range",
                    "metrics": [],
                },
            )
            entry["metrics"].append(row["metric"])
    return seen.values()


def _bed_genes(bed: Path) -> int:
    """How many intervals the panel BED declares. Comment and track lines do not count."""
    if not bed.is_file():
        return 0
    return sum(
        1
        for line in bed.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith(("#", "track", "browser"))
    )
