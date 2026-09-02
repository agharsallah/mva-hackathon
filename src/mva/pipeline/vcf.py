"""Reading the proband callset into per-ALT-allele calls.

Deliberately a plain-text reader over VCF/BGZF rather than a pysam binding: the whole
challenge rests on four fields (GT, AD, PGT, PID) and a hand-rolled reader keeps the
pipeline installable anywhere, including a bare Modal container.

Two decisions are load-bearing:

* **One call per ALT allele.** A ``1/2`` record carries two different alternate alleles
  in one row. The scorer has no notion of a comma-separated ALT, and biologically a 1/2
  site *is* a compound heterozygote, so it must reach the pair finder as two calls.
* **Nothing is filtered or rewritten here.** Non-PASS records are exactly where a
  suppressed second allele would hide, and rewriting alleles would mask whether
  normalization ran. Both are ranking decisions, made downstream.
"""

import gzip
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .variant import Variant


@dataclass(frozen=True)
class Call:
    """One ALT allele of one VCF record, with the genotype evidence for it."""

    variant: Variant
    genotype: str
    filters: tuple[str, ...]
    depth: int | None
    ref_depth: int | None
    alt_depth: int | None
    phase_set: str | None
    phase_gt: str | None

    @property
    def is_pass(self) -> bool:
        """True when the caller flagged no problem with this record."""
        return self.filters == ("PASS",)

    @property
    def is_het(self) -> bool:
        """True when this ALT allele is present on exactly one of the two haplotypes."""
        alleles = _alleles(self.genotype)
        return len(set(alleles)) > 1 and alleles.count(self._allele_index) == 1

    @property
    def is_hom_alt(self) -> bool:
        """True when both haplotypes carry this ALT — its own second hit, not half a pair."""
        alleles = _alleles(self.genotype)
        return bool(alleles) and set(alleles) == {self._allele_index}

    @property
    def vaf(self) -> float | None:
        """Variant allele fraction — the allele-balance signal for mosaic or noisy calls."""
        if self.alt_depth is None or not self.depth:
            return None
        return self.alt_depth / self.depth

    # Which ALT this call represents, 1-based as genotypes index them.
    _allele_index: int = 1


def read_calls(path: str | Path) -> list[Call]:
    """Read every call in ``path`` into memory. See :func:`iter_calls` to stream."""
    return list(iter_calls(path))


def iter_calls(path: str | Path) -> Iterator[Call]:
    """Yield one :class:`Call` per ALT allele of every record in ``path``."""
    for fields in _iter_records(path):
        yield from _split_record(fields)


def _open(path: str | Path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt")
    return open(path)


def _iter_records(path: str | Path) -> Iterator[list[str]]:
    with _open(path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            yield line.rstrip("\n").split("\t")


def _split_record(fields: list[str]) -> Iterator[Call]:
    chrom, pos, _id, ref, alt, _qual, filt = fields[:7]
    fmt_keys = fields[8].split(":")
    sample = dict(zip(fmt_keys, fields[9].split(":")))

    filters = tuple(filt.split(";")) if filt not in (".", "") else ()
    genotype = sample.get("GT", "./.")
    depths = _ints(sample.get("AD"))
    depth = _int(sample.get("DP"))

    for index, allele in enumerate(alt.split(","), start=1):
        if allele == "." or allele == "*":
            continue
        yield Call(
            variant=Variant.from_vcf(chrom, int(pos), ref, allele),
            genotype=genotype,
            filters=filters,
            depth=depth,
            ref_depth=depths[0] if depths else None,
            alt_depth=depths[index] if depths and index < len(depths) else None,
            phase_set=sample.get("PID"),
            phase_gt=sample.get("PGT"),
            _allele_index=index,
        )


def _alleles(genotype: str) -> list[int]:
    out = []
    for part in genotype.replace("|", "/").split("/"):
        if part.isdigit():
            out.append(int(part))
    return out


def _int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def _ints(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(v) if v.isdigit() else 0 for v in value.split(",")]
