"""The sequence facts a premature stop codon is judged by, derived from a transcript model.

A **premature termination codon** (PTC — a stop codon that appears before the one the gene is
supposed to end on) is not one fact but four, and every therapeutic question about it reads a
different one:

* **which stop codon it is** (``TGA``/``TAG``/``TAA``, read as UGA/UAG/UAA on the mRNA) and
  **what sits next to it** — the base immediately after the codon (the *+4 base*) and the base
  immediately before it (*-1*). Ribosomes misread the three stops at very different rates, and
  the +4 base changes that rate again; this is the substrate of *nonsense readthrough* drugs;
* **where it sits in the exon structure** — the *50-55 nt rule*: a stop more than ~50-55
  nucleotides upstream of the **last exon-exon junction** (the last seam between two exons in the
  spliced message) is normally recognised as premature and the whole transcript is destroyed by
  **nonsense-mediated decay** (NMD — the cell's quality filter on messages that stop early).
  A stop downstream of that point escapes NMD and a truncated protein is actually made;
* **how much protein is lost** — residues kept over the full length;
* **which domains are lost** — the annotated features that fall after the stop.

The module is deliberately case-agnostic: it takes a transcript (its coding sequence plus the
coding length of each exon) and a coding-sequence offset, and knows nothing about any patient.
For a software engineer: :class:`TranscriptModel` is a parsed record format, the functions on it
are pure, and nothing here performs I/O or holds state.

**No genomic position can be written by this module.** Coding-sequence offsets are positions in
a transcript, not in the genome, and they stay inside the caller's build directory; what comes
out are codon identities, counts and fractions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

__all__ = [
    "NMD_RULE_NT",
    "STOP_CODONS",
    "CodingSubstitution",
    "Domain",
    "NmdCall",
    "StopContext",
    "TranscriptModel",
    "Truncation",
    "nmd_call",
    "parse_hgvs_c",
    "stop_context",
    "transcript_from_ensembl",
    "truncation",
]

#: ``ENST00000123456.7:c.910G>T`` - transcript, coding offset, reference base, alternate base.
#: Only a plain substitution in the coding region; anything else (indel, intronic ``+``/``-``
#: offset, UTR ``*``/``-`` offset) is refused rather than half-understood.
HGVS_C = re.compile(
    r"^(?:(?P<transcript>[^:]+):)?c\.(?P<offset>\d+)(?P<ref>[ACGT])>(?P<alt>[ACGT])$"
)

#: The three stop codons, spelled in the DNA alphabet the coding sequence uses. On the mRNA the
#: T reads as U, so ``TGA`` is the UGA of the readthrough literature.
STOP_CODONS = ("TAA", "TAG", "TGA")

#: The **50-55 nt rule**. A stop codon further than this many nucleotides upstream of the last
#: exon-exon junction is NMD-competent. The literature states the boundary as a range, not a
#: point, so the caller gets both ends and the verdict says which one it used.
NMD_RULE_NT = 55


@dataclass(frozen=True)
class CodingSubstitution:
    """One single-base change, in transcript coordinates. Never a genomic position."""

    transcript: str
    offset: int
    ref: str
    alt: str


def parse_hgvs_c(spelling: str) -> CodingSubstitution:
    """Parse a coding **HGVS** spelling (the standard text form of a change) into its parts.

    A coding offset is a place in a transcript, not in the genome: two people with the same
    change share it, and it cannot be turned back into a chromosome position without the gene
    model. It is still derived from the patient's callset, so callers keep it under ``build/``.
    """
    match = HGVS_C.match(spelling.strip())
    if match is None:
        raise ValueError(f"{spelling!r} is not a plain coding substitution this parser handles")
    return CodingSubstitution(
        transcript=match.group("transcript") or "",
        offset=int(match.group("offset")),
        ref=match.group("ref"),
        alt=match.group("alt"),
    )


@dataclass(frozen=True)
class Domain:
    """One annotated protein feature, in residue coordinates (1-based, inclusive)."""

    name: str
    start: int
    end: int

    def lost_after(self, residue: int) -> str:
        """``"lost"``, ``"kept"`` or ``"truncated"`` for a protein that stops at ``residue``."""
        if self.start > residue:
            return "lost"
        if self.end <= residue:
            return "kept"
        return "truncated"


@dataclass(frozen=True)
class TranscriptModel:
    """A transcript reduced to what a stop-codon question needs.

    ``cds`` is the reference coding sequence, start codon first. ``cds_exon_ends`` holds the
    cumulative coding length after each exon that carries coding sequence, so
    ``cds_exon_ends[-1] == len(cds)`` and the seams between consecutive entries are the
    exon-exon junctions *in coding coordinates*. ``exons_total`` is the transcript's exon count
    including any that are pure UTR, because that is the number a clinician reads.
    """

    transcript_id: str
    cds: str
    cds_exon_ends: tuple[int, ...]
    exons_total: int
    protein_length: int
    domains: tuple[Domain, ...] = ()

    def __post_init__(self) -> None:
        if len(self.cds) % 3:
            raise ValueError(f"{self.transcript_id}: coding sequence is not a multiple of 3")
        if not self.cds_exon_ends or self.cds_exon_ends[-1] != len(self.cds):
            raise ValueError(f"{self.transcript_id}: exon ends do not cover the coding sequence")
        if list(self.cds_exon_ends) != sorted(set(self.cds_exon_ends)):
            raise ValueError(f"{self.transcript_id}: exon ends are not strictly increasing")

    @property
    def coding_exons(self) -> int:
        """How many exons carry coding sequence."""
        return len(self.cds_exon_ends)

    @property
    def last_junction(self) -> int | None:
        """Coding offset of the last exon-exon junction; ``None`` for a single-exon transcript.

        The junction is *between* the returned offset and the next base, so a stop whose last
        base is at ``x`` sits ``last_junction - x`` nucleotides upstream of it.
        """
        return self.cds_exon_ends[-2] if len(self.cds_exon_ends) >= 2 else None

    def exon_of(self, cds_offset: int) -> int:
        """Which coding exon (1-based, counted over coding exons) holds ``cds_offset``."""
        if not 1 <= cds_offset <= len(self.cds):
            raise ValueError(f"offset {cds_offset} outside the coding sequence")
        for index, end in enumerate(self.cds_exon_ends, start=1):
            if cds_offset <= end:
                return index
        raise AssertionError("unreachable: offsets are bounded above")


@dataclass(frozen=True)
class StopContext:
    """The local sequence a readthrough model reads, plus the codon it replaced."""

    codon_index: int
    reference_codon: str
    stop_codon: str
    plus4: str
    minus1: str
    upstream: str
    downstream: str

    @property
    def rna_stop(self) -> str:
        """The stop as the readthrough literature spells it: ``UGA``, ``UAG`` or ``UAA``."""
        return self.stop_codon.replace("T", "U")

    @property
    def tetranucleotide(self) -> str:
        """Stop codon plus its +4 base — the ``UGA A`` key the context rules are stated in."""
        return f"{self.rna_stop} {self.plus4.replace('T', 'U')}"


@dataclass(frozen=True)
class NmdCall:
    """Whether the message carrying this stop is destroyed before it can be translated."""

    exon_index: int
    coding_exons: int
    exons_total: int
    nt_to_last_junction: int | None
    junctions_downstream: int
    rule_nt: int
    competent: bool
    reason: str


@dataclass(frozen=True)
class Truncation:
    """How much protein a stop removes, and which annotated features go with it."""

    residues_kept: int
    protein_length: int
    fraction_lost: float
    domains_lost: tuple[str, ...]
    domains_truncated: tuple[str, ...]
    domains_kept: tuple[str, ...]


def stop_context(
    model: TranscriptModel, cds_offset: int, alt_base: str, *, flank: int = 6
) -> StopContext:
    """The stop a single-base substitution at ``cds_offset`` creates, with its local context.

    ``flank`` nucleotides either side are returned so the caller can show the context; keep it
    small — a long run of bases in a committed file is patient sequence and the repository's
    coordinate gate rejects it.
    """
    alt_base = alt_base.upper()
    if alt_base not in "ACGT":
        raise ValueError(f"alt base {alt_base!r} is not a single DNA base")
    if not 1 <= cds_offset <= len(model.cds):
        raise ValueError(f"offset {cds_offset} outside the coding sequence")
    mutated = model.cds[: cds_offset - 1] + alt_base + model.cds[cds_offset:]
    codon_index = (cds_offset - 1) // 3 + 1
    start = (codon_index - 1) * 3
    stop = mutated[start : start + 3]
    if stop not in STOP_CODONS:
        raise ValueError(f"substitution makes codon {stop!r}, which is not a stop codon")
    return StopContext(
        codon_index=codon_index,
        reference_codon=model.cds[start : start + 3],
        stop_codon=stop,
        plus4=mutated[start + 3 : start + 4],
        minus1=mutated[start - 1 : start] if start else "",
        upstream=mutated[max(start - flank, 0) : start],
        downstream=mutated[start + 3 : start + 3 + flank],
    )


def nmd_call(model: TranscriptModel, codon_index: int, *, rule_nt: int = NMD_RULE_NT) -> NmdCall:
    """Apply the 50-55 nt rule to a stop at ``codon_index`` (1-based residue)."""
    last_base = codon_index * 3
    exon_index = model.exon_of(last_base)
    junction = model.last_junction
    downstream = sum(1 for end in model.cds_exon_ends[:-1] if end >= last_base)
    if junction is None:
        return NmdCall(
            exon_index,
            model.coding_exons,
            model.exons_total,
            None,
            0,
            rule_nt,
            competent=False,
            reason=(
                "single-exon transcript: no exon junction complex is deposited, so NMD has "
                "no mark to read"
            ),
        )
    distance = junction - last_base
    competent = distance > rule_nt
    if competent:
        reason = (
            f"the stop's last base is {distance} nt upstream of the last exon-exon junction, "
            f"more than the {rule_nt} nt the rule allows, so the message is NMD-competent"
        )
    elif distance < 0:
        reason = "the stop lies in the last exon, downstream of every junction: NMD-escaping"
    else:
        reason = (
            f"the stop's last base is {distance} nt upstream of the last junction, inside the "
            f"{rule_nt} nt window, so the message escapes NMD"
        )
    return NmdCall(
        exon_index,
        model.coding_exons,
        model.exons_total,
        distance,
        downstream,
        rule_nt,
        competent,
        reason,
    )


def truncation(model: TranscriptModel, codon_index: int) -> Truncation:
    """Residues kept, fraction lost, and each annotated domain's fate."""
    kept = codon_index - 1
    fates: dict[str, list[str]] = {"lost": [], "truncated": [], "kept": []}
    for domain in model.domains:
        fates[domain.lost_after(kept)].append(domain.name)
    return Truncation(
        residues_kept=kept,
        protein_length=model.protein_length,
        fraction_lost=1.0 - kept / model.protein_length,
        domains_lost=tuple(fates["lost"]),
        domains_truncated=tuple(fates["truncated"]),
        domains_kept=tuple(fates["kept"]),
    )


def transcript_from_ensembl(
    lookup: dict[str, Any], cds: str, *, domains: tuple[Domain, ...] = ()
) -> TranscriptModel:
    """Build a :class:`TranscriptModel` from an Ensembl REST reply.

    ``lookup`` is ``/lookup/id/<transcript>?expand=1`` (it carries ``Exon`` and ``Translation``)
    and ``cds`` is the sequence from ``/sequence/id/<transcript>?type=cds``. Only the coding
    part of each exon counts, so the exon that holds the start codon contributes from the start
    codon on and the exon that holds the stop contributes up to it.
    """
    translation = lookup["Translation"]
    first, last = int(translation["start"]), int(translation["end"])
    exons = sorted(lookup["Exon"], key=lambda exon: int(exon["start"]))
    if int(lookup.get("strand", 1)) < 0:
        exons = list(reversed(exons))
    ends: list[int] = []
    total = 0
    for exon in exons:
        start, end = int(exon["start"]), int(exon["end"])
        coding = max(0, min(end, last) - max(start, first) + 1)
        if coding:
            total += coding
            ends.append(total)
    return TranscriptModel(
        transcript_id=str(lookup["id"]),
        cds=cds.upper(),
        cds_exon_ends=tuple(ends),
        exons_total=len(exons),
        protein_length=int(translation.get("length") or len(cds) // 3 - 1),
        domains=domains,
    )
