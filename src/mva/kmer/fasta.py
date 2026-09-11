"""Read a reference FASTA without loading the genome.

A **FASTA** file is the plainest format in genomics: a ``>name`` line, then the bases of
that sequence wrapped over many lines, repeated per contig. There is no index and no
record boundary other than the next ``>``, so this module does the one thing the rest of
the package needs — hand back one contig at a time as a flat ``uint8`` array of ASCII,
streaming, so peak memory is one chromosome (~250 MB) rather than 3.1 GB.

``.gz`` is transparent. Contig names are taken up to the first space, which is what turns
``>chr1  AC:CM000663.2  …`` into ``chr1``; :func:`rename` then maps that to the spelling
the rest of this project uses (bare ``1``, matching the delivered VCF and
``ressources/reference/coding_regions.tsv``).
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, cast

import numpy as np

#: Bytes read from disk at a time while assembling one contig.
CHUNK = 1 << 22


@dataclass(frozen=True)
class Contig:
    """One reference sequence: its name and its bases as ASCII codes."""

    name: str
    bases: np.ndarray

    def __len__(self) -> int:
        return int(self.bases.size)


def rename(name: str) -> str:
    """The bare-contig spelling: ``chr1`` -> ``1``, ``chrM``/``chrMT`` -> ``MT``.

    The delivered callset was produced against a *no-chr* reference
    (``ideation/data-findings.md`` §2) and the gene model in
    ``ressources/reference/coding_regions.tsv`` is Ensembl, also bare. Renaming here means
    no coordinate ever crosses a naming boundary later, which is the class of bug that
    silently shifts a whole analysis by one contig.
    """
    bare = name[3:] if name.startswith("chr") else name
    return "MT" if bare in {"M", "MT"} else bare


def _open(path: Path) -> BinaryIO:
    if path.suffix == ".gz":
        # GzipFile satisfies the binary-stream protocol but is not declared as BinaryIO.
        return cast(BinaryIO, gzip.open(path, "rb"))
    return path.open("rb")


def contigs(path: Path, *, wanted: set[str] | None = None) -> Iterator[Contig]:
    """Yield every contig in the file, or only those named in ``wanted`` (bare spelling).

    Skipping an unwanted contig still costs the decompression of its bytes — there is no
    index to seek with — but not the memory of assembling it, which is the expensive half.
    """
    handle = _open(path)
    try:
        name: str | None = None
        keep = True
        parts: list[bytes] = []
        for raw in handle:
            if raw.startswith(b">"):
                if name is not None and keep:
                    yield Contig(name, np.frombuffer(b"".join(parts), dtype=np.uint8))
                name = rename(raw[1:].split()[0].decode("ascii"))
                keep = wanted is None or name in wanted
                parts = []
                continue
            if keep:
                parts.append(raw.strip())
        if name is not None and keep:
            yield Contig(name, np.frombuffer(b"".join(parts), dtype=np.uint8))
    finally:
        handle.close()


def names(path: Path) -> list[str]:
    """Every contig name, bare-spelled, without assembling a single sequence."""
    handle = _open(path)
    try:
        return [
            rename(line[1:].split()[0].decode("ascii")) for line in handle if line.startswith(b">")
        ]
    finally:
        handle.close()
