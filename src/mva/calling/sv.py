"""Call structural variants with two method classes, and say how much to trust each type.

**What a structural variant is.** A change of 50 bases or more — a deleted exon, a
duplicated segment, an inverted stretch, an insertion of sequence that is not in the
reference. They matter here because the delivered callset contains none: its provenance
shows no SV caller ran at all (``ideation/data-findings.md``). If the second allele of a
recessive pair is structural, this is the only stage that can find it.

**Two callers, chosen by method class rather than by name.** Kosugi 2019 benchmarked
69 short-read SV callers and found that pairing callers from *different* method classes
buys far more precision than pairing two of the same class (1.82x versus 1.63x, Fig. 6-7).
So the pair here is deliberately heterogeneous:

``delly``  read-pair plus split-read: infers a variant from mates that map too far apart
           or in the wrong orientation, and from reads whose two halves map to two places.
``dysgu``  local assembly plus a learned classifier: rebuilds the sequence around a
           candidate breakpoint and scores it, which is the class GRIDSS belongs to and the
           one the read-pair tools cannot substitute for.

**Precision is type-specific and is printed with every call.** On real data Kosugi's best
duplication caller reached 57.1 % precision and the best inversion caller 49.1 %; deletions
are far better behaved. Simulation-to-real rank correlation was strong for deletions
(rho 0.72) and weak for duplications (0.48) and inversions (0.57). A duplication supported
by two method classes is therefore near-coin-flip evidence, and this module attaches that
prior to the call rather than leaving a reader to assume all SV types are equal.

**Bait-edge calls are flagged, not deleted.** A baited alignment has a coverage cliff at
every padding boundary and unpaired mates wherever a fragment straddles one — the exact
signature a read-pair or read-depth caller reads as a deletion. Flagging rather than
dropping keeps the artefact visible and lets the positive control count how many such
calls the edges alone produce.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .tools import capture, run, sha256, started_now

#: Kosugi 2019, Table 1 and Fig. 6-7: the best short-read precision observed per type on
#: real data, used as a prior printed beside every consensus call. These are *ceilings*
#: from a 2019 benchmark on GRCh37 with that era's tool versions, not our measurements —
#: the entry says so wherever they are quoted.
TYPE_PRECISION_PRIOR: dict[str, float] = {
    "DEL": 0.74,
    "INS": 0.66,
    "DUP": 0.571,
    "INV": 0.491,
    "BND": 0.0,
}

#: Method class per caller — the thing the two-caller rule is actually about.
METHOD_CLASS: dict[str, str] = {
    "delly": "read-pair + split-read",
    "dysgu": "local assembly + learned classifier",
}

#: A call this close to a bait boundary is flagged. One insert-size is the distance over
#: which a read-pair caller can see a boundary at all; the delivery's insert is ~266 bp,
#: so 1000 is comfortably outside it.
BAIT_EDGE_BP = 1_000


@dataclass(frozen=True)
class SvCallset:
    """One SV caller's output."""

    caller: str
    method_class: str
    vcf: Path
    records: int
    manifest: Path


def delly(
    reference: Path, bam: Path, out_dir: Path, *, stem: str = "baited", exclude: Path | None = None
) -> SvCallset:
    """Call with delly — the read-pair and split-read class."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{stem}.delly.bcf"
    provenance = started_now("delly")
    provenance.inputs = {"reference": str(reference), "bam": str(bam)}
    provenance.parameters = {
        "caller": "delly sr",
        "method_class": METHOD_CLASS["delly"],
        "excluded_regions": str(exclude) if exclude else "none",
    }
    # Delly 2.x renamed the short-read caller from `call` to `sr`; 1.x's spelling exits 1
    # with "Unrecognized command", which is the kind of failure that looks like a broken
    # BAM until you read the stderr.
    argv = ["delly", "sr", "-g", str(reference), "-o", str(target)]
    if exclude is not None:
        argv += ["-x", str(exclude)]
    argv.append(str(bam))
    provenance.invocations.append(run(argv))
    records = _count(target)
    provenance.outputs = {
        "vcf": str(target),
        "records": str(records),
        "sha256": sha256(target, limit=1 << 24),
    }
    manifest = provenance.write(out_dir / f"{stem}.delly.provenance.json")
    return SvCallset(
        caller="delly",
        method_class=METHOD_CLASS["delly"],
        vcf=target,
        records=records,
        manifest=manifest,
    )


def dysgu(
    reference: Path, bam: Path, out_dir: Path, *, stem: str = "baited", threads: int = 4
) -> SvCallset:
    """Call with dysgu — the local-assembly class, and the reason the consensus is valid.

    dysgu needs a scratch directory of its own for the read clusters it builds; it is
    given one inside ``out_dir`` rather than a temporary path so a failed run leaves its
    working state where it can be looked at.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    # dysgu creates its own working directory and refuses one that already exists, so it
    # is named here and not made here.
    scratch = out_dir / f"{stem}.dysgu.tmp"
    if scratch.exists():
        shutil.rmtree(scratch)
    target = out_dir / f"{stem}.dysgu.vcf"
    provenance = started_now("dysgu")
    provenance.inputs = {"reference": str(reference), "bam": str(bam)}
    provenance.parameters = {
        "caller": "dysgu run",
        "method_class": METHOD_CLASS["dysgu"],
        "threads": threads,
    }
    provenance.invocations.append(
        run(
            [
                "dysgu",
                "run",
                "-p",
                str(threads),
                "-o",
                str(target),
                str(reference),
                str(scratch),
                str(bam),
            ]
        )
    )
    records = _records_in_vcf(target)
    provenance.outputs = {"vcf": str(target), "records": str(records)}
    manifest = provenance.write(out_dir / f"{stem}.dysgu.provenance.json")
    return SvCallset(
        caller="dysgu",
        method_class=METHOD_CLASS["dysgu"],
        vcf=target,
        records=records,
        manifest=manifest,
    )


def _count(path: Path) -> int:
    text = capture(["bcftools", "index", "-f", "--nrecords", str(path)], check=False).strip()
    return int(text) if text.isdigit() else _records_in_vcf(path)


def _records_in_vcf(path: Path) -> int:
    """Count non-header lines without loading the file."""
    try:
        return sum(1 for line in _lines(path) if not line.startswith("#"))
    except OSError:
        return 0


def near_bait_edge(
    contig: str,
    position: int,
    edges: dict[str, list[tuple[int, int]]],
    *,
    window: int = BAIT_EDGE_BP,
) -> bool:
    """Whether a breakpoint sits within ``window`` of a baited interval's boundary.

    ``edges`` is the merged bait plan per contig — the same intervals the pass was run
    with, so the flag describes the actual boundaries rather than an approximation of them.
    """
    for start, end in edges.get(contig, ()):
        if abs(position - start) <= window or abs(position - end) <= window:
            return True
    return False


@dataclass(frozen=True)
class SvCall:
    """One structural-variant record, with the fields a consensus needs to compare two."""

    caller: str
    method_class: str
    contig: str
    position: int
    end: int
    sv_type: str
    length: int
    filters: str
    genotype: str

    @property
    def precision_prior(self) -> float:
        return precision_prior(self.sv_type)

    def overlaps(self, other: SvCall, *, slop: int = 500, reciprocal: float = 0.5) -> bool:
        """Whether two calls describe the same event, by Truvari's own criteria.

        Same type, breakpoints within ``slop``, and — for calls with real extent —
        reciprocal overlap of at least ``reciprocal``. Written out rather than left to an
        ad-hoc distance test because "the callers agree" is the whole basis of the
        consensus, and an undefined agreement rule can be tuned after seeing the answer.
        """
        if self.sv_type != other.sv_type or self.contig != other.contig:
            return False
        if abs(self.position - other.position) > slop or abs(self.end - other.end) > slop:
            return False
        span, theirs = self.end - self.position, other.end - other.position
        if span <= 0 or theirs <= 0:
            return True
        shared = min(self.end, other.end) - max(self.position, other.position)
        return shared > 0 and shared / max(span, theirs) >= reciprocal


def _lines(path: Path) -> Iterator[str]:
    """Text lines of a VCF, whatever container it arrived in.

    ``.bcf`` is BGZF-compressed **binary**, not gzipped text — delly writes it by default,
    and reading it as text yields mojibake rather than an error, which is the worst of both.
    So a BCF is streamed through `bcftools view`, the tool that owns the format.
    """
    import gzip
    import subprocess

    if path.suffix == ".bcf":
        process = subprocess.Popen(
            ["bcftools", "view", str(path)], stdout=subprocess.PIPE, text=True
        )
        assert process.stdout is not None
        try:
            yield from process.stdout
        finally:
            process.stdout.close()
            process.wait()
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        yield from handle


def read_calls(vcf: Path, *, caller: str, method_class: str) -> tuple[SvCall, ...]:
    """Parse an SV VCF or BCF into rows. ``SVTYPE``, ``END`` and ``SVLEN`` live in INFO,
    which the small-variant reader does not touch, so they are pulled out here."""
    found: list[SvCall] = []
    for line in _lines(vcf):
        if line.startswith("#"):
            continue
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 8:
            continue
        info = _info(fields[7])
        position = int(fields[1])
        length = int(info.get("SVLEN", "0") or 0)
        end = int(info.get("END", position + abs(length)) or position)
        found.append(
            SvCall(
                caller=caller,
                method_class=method_class,
                contig=fields[0],
                position=position,
                end=end,
                sv_type=info.get("SVTYPE", "UNKNOWN"),
                length=length or (end - position),
                filters=fields[6],
                genotype=fields[9].split(":")[0] if len(fields) > 9 else "",
            )
        )
    return tuple(found)


def _info(field: str) -> dict[str, str]:
    """VCF INFO as a dict; a flag with no value maps to an empty string."""
    parsed: dict[str, str] = {}
    for item in field.split(";"):
        key, _, value = item.partition("=")
        if key:
            parsed[key] = value
    return parsed


def consensus(
    left: tuple[SvCall, ...], right: tuple[SvCall, ...], *, slop: int = 500
) -> list[tuple[SvCall, SvCall]]:
    """Calls supported by both method classes — the only SVs H023 is about.

    Quadratic on purpose: two short-read callers over 42 Mb produce hundreds of calls, not
    millions, and an index here would be machinery with nothing to do.
    """
    return [
        (first, second) for first in left for second in right if first.overlaps(second, slop=slop)
    ]


def precision_prior(sv_type: str) -> float:
    """Kosugi 2019's best observed short-read precision for this type, or 0 if unmeasured.

    Zero is the honest answer for a type the benchmark did not evaluate — translocations —
    and the caller of this function is expected to report it as "unmeasured", never as
    "impossible".
    """
    return TYPE_PRECISION_PRIOR.get(sv_type.upper(), 0.0)
