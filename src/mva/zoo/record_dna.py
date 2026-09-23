"""The DNA windows: the input a genomic language model reads (plan B1, step 1's DNA half).

A **DNA language model** (Evo 2, Nucleotide Transformer v2) is a next-token model over the
four bases. It scores a variant by comparing how plausible the reference stretch of genome
is against the same stretch with the allele swapped in — so it needs the letters *around*
the variant, not an HGVS string. That stretch is a **window**: ``length`` bases of the
pinned reference genome (``build/reference/GRCh38.fa``) centred on the allele, twice —

* ``dna_window_ref``: ``left flank + REF + right flank``, exactly ``length`` bases;
* ``dna_window_alt``: ``left flank + ALT + right flank`` — the same flanks, so an indel's
  window is ``len(ALT) - len(REF)`` bases longer or shorter, never re-centred.

The allele always starts at offset ``length // 2``; both windows carry it there, so a model
never needs the coordinate to find the change.

**Quality check that earns its keep:** the reference genome must spell ``REF`` at the
position. A mismatch means the record and the FASTA disagree on assembly or normalisation,
and a window built anyway would score the wrong sequence with full confidence — so it is
counted and skipped, never built.

**A window is patient sequence and a coordinate proxy.** It is written to
``build/<prefix>/dna-windows.parquet`` (keyed by ``allele_id``) and nowhere else. A separate
file, not new columns in ``records.parquet``: that file's bytes feed the workflow's content
chain (entry 135), and 640 MB of windows would re-key every stage that never reads them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "DEFAULT_DNA_WINDOWS",
    "DEFAULT_LENGTH",
    "DEFAULT_REFERENCE",
    "DnaReport",
    "Reference",
    "dna_window_pair",
    "dna_windows",
    "write_dna_windows",
]

#: 8,192 bases — Evo 2's context length and plan §5's number; a lane that wants less crops
#: the centre (the allele sits at ``length // 2`` so a central crop keeps it).
DEFAULT_LENGTH = 8192

DEFAULT_REFERENCE = Path("build/reference/GRCh38.fa")
DEFAULT_DNA_WINDOWS = Path("build/it4/dna-windows.parquet")


class Reference(Protocol):
    """The slice of ``pysam.FastaFile`` this module reads — the seam the tests replace."""

    @property
    def references(self) -> Sequence[str]: ...

    def get_reference_length(self, reference: str) -> int: ...

    def fetch(self, reference: str, start: int, end: int) -> str: ...


@dataclass(frozen=True)
class DnaReport:
    """What one windowing pass managed, per reason — the numbers the claim is judged on."""

    considered: int = 0
    contig_missing: int = 0
    ref_mismatch: int = 0
    clipped_at_contig_end: int = 0
    complete: int = 0

    def as_dict(self) -> dict[str, int | float]:
        return {
            "considered": self.considered,
            "contig_missing": self.contig_missing,
            "ref_mismatch": self.ref_mismatch,
            "clipped_at_contig_end": self.clipped_at_contig_end,
            "complete": self.complete,
            "fraction_complete": round(self.complete / self.considered, 5)
            if self.considered
            else 0.0,
        }


def _contig(reference: Reference, chrom: str) -> str | None:
    """The FASTA's spelling of ``chrom`` — ``1`` and ``chr1`` name one contig."""
    names = set(reference.references)
    bare = chrom.removeprefix("chr")
    for candidate in (chrom, bare, f"chr{bare}"):
        if candidate in names:
            return candidate
    return None


def dna_window_pair(
    reference: Reference, chrom: str, pos: int, ref: str, alt: str, length: int = DEFAULT_LENGTH
) -> tuple[str, str, bool] | None:
    """``(ref window, alt window, clipped)`` for one VCF allele, or ``None`` if unbuildable.

    ``pos`` is VCF 1-based. ``None`` when the contig is absent or the genome disagrees with
    ``ref``. ``clipped`` is true when a contig end cut a flank short — the window is then
    shorter and the allele is no longer at the centre, so the flag travels with it.
    """
    contig = _contig(reference, chrom)
    if contig is None:
        return None
    start0 = pos - 1
    ref_u, alt_u = ref.upper(), alt.upper()
    left_start = max(0, start0 - length // 2)
    right_len = length - length // 2 - len(ref_u)
    contig_len = reference.get_reference_length(contig)
    right_end = min(contig_len, start0 + len(ref_u) + max(0, right_len))
    seq = reference.fetch(contig, left_start, right_end).upper()
    offset = start0 - left_start
    if seq[offset : offset + len(ref_u)] != ref_u:
        return None
    left, right = seq[:offset], seq[offset + len(ref_u) :]
    clipped = offset != length // 2 or len(right) != max(0, right_len)
    return left + ref_u + right, left + alt_u + right, clipped


def dna_windows(
    rows: Iterable[tuple[str, str, int, str, str]],
    reference: Reference,
    *,
    length: int = DEFAULT_LENGTH,
) -> tuple[dict[str, tuple[str, str, bool]], DnaReport]:
    """Build a window pair for every ``(allele_id, chrom, pos, ref, alt)`` row."""
    names = set(reference.references)
    windows: dict[str, tuple[str, str, bool]] = {}
    considered = missing = mismatch = clipped = 0
    for allele, chrom, pos, ref, alt in rows:
        considered += 1
        if not any(c in names for c in (chrom, chrom.removeprefix("chr"), f"chr{chrom}")):
            missing += 1
            continue
        pair = dna_window_pair(reference, chrom, int(pos), ref, alt, length)
        if pair is None:
            mismatch += 1
            continue
        windows[allele] = pair
        clipped += int(pair[2])
    report = DnaReport(
        considered=considered,
        contig_missing=missing,
        ref_mismatch=mismatch,
        clipped_at_contig_end=clipped,
        complete=len(windows),
    )
    return windows, report


def write_dna_windows(
    records_parquet: Path | str,
    out: Path | str = DEFAULT_DNA_WINDOWS,
    *,
    reference_fasta: Path | str = DEFAULT_REFERENCE,
    length: int = DEFAULT_LENGTH,
    connection: Any = None,
) -> DnaReport:
    """Read the coordinates from the record Parquet, write the windows beside it.

    The coordinates are read inside this function and never returned: the caller gets a
    :class:`DnaReport` and a file under ``build/``. A provenance manifest lands next to the
    file (``<out>.provenance.json``) naming the FASTA's own manifest, the length and counts.
    """
    import duckdb
    import pysam

    source, target = Path(records_parquet), Path(out)
    con = connection or duckdb.connect()
    rows = con.execute(
        "SELECT allele_id, chrom, pos, ref, alt FROM read_parquet(?) "
        "WHERE chrom IS NOT NULL AND pos IS NOT NULL AND ref IS NOT NULL AND alt IS NOT NULL",
        [str(source)],
    ).fetchall()
    with pysam.FastaFile(str(reference_fasta)) as fasta:
        windows, report = dna_windows(
            ((str(a), str(c), int(p), str(r), str(t)) for a, c, p, r, t in rows),
            fasta,
            length=length,
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        "CREATE OR REPLACE TEMP TABLE zoo_dna (allele_id VARCHAR, dna_window_ref VARCHAR, "
        "dna_window_alt VARCHAR, center INTEGER, clipped BOOLEAN)"
    )
    con.executemany(
        "INSERT INTO zoo_dna VALUES (?, ?, ?, ?, ?)",
        [[a, w[0], w[1], length // 2, w[2]] for a, w in windows.items()],
    )
    con.execute(f"COPY zoo_dna TO '{target}' (FORMAT parquet, COMPRESSION zstd)")
    con.execute("DROP TABLE IF EXISTS zoo_dna")
    provenance = {
        "file": target.name,
        "tool": "mva.zoo.record_dna.write_dna_windows",
        "inputs": {
            "records": str(source),
            "reference": str(reference_fasta),
            "reference_provenance": str(Path(reference_fasta).with_suffix(".provenance.json")),
        },
        "params": {"length": length, "center": length // 2},
        "report": report.as_dict(),
        "note": "patient sequence: stays under build/, never committed, never in a table",
    }
    target.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return report
