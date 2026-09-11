"""Which copy is each allele on — from the reads, and from a direct count of fragments.

**The question.** A recessive disease needs both copies of a gene broken. Two heterozygous
alleles in one gene are either on the same copy (**cis** — one copy broken, one intact, and
the person is a carrier) or on different copies (**trans** — both broken, and the person is
affected). Without parents, the only direct evidence is physical: a sequencing read comes
from one molecule, so two alleles seen on the same fragment are in cis, and two alleles that
never share a fragment while each shares fragments with the other's reference base are in
trans.

**Why it usually fails, and why that is worth reporting.** A 150 bp read and a ~266 bp
fragment reach nowhere near two alleles kilobases apart. The chain has to run through the
heterozygous positions in between — allele 1 phases to the SNV next door, that to the next,
and so on to allele 2 — and whether the chain closes depends on how densely heterozygous
this child happens to be across that gene. That is measurable, not assumable, which is why
H019 asks for *either* a closed chain *or* the exact gap that prevents one.

**Two readings of the same reads.** WhatsHap solves a weighted minimum-error-correction
problem over the whole block structure; :func:`fragment_support` just counts, per allele
pair, how many fragments carry both alternates, both references, or one of each. The
counter cannot phase a distant pair at all — but where it can speak, it is auditable line
by line, which a reader can check in a way they cannot check an optimiser's output. A phase
claim wants both to agree.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tools import run, started_now


@dataclass(frozen=True)
class PhaseBlock:
    """A stretch over which WhatsHap resolved a consistent haplotype assignment."""

    contig: str
    start: int
    end: int
    variants: int

    @property
    def span(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Phasing:
    """The phased VCF and the block structure read back out of it."""

    vcf: Path
    blocks: tuple[PhaseBlock, ...]
    manifest: Path

    def block_containing(self, contig: str, position: int) -> PhaseBlock | None:
        for block in self.blocks:
            if block.contig == contig and block.start <= position <= block.end:
                return block
        return None

    def same_block(self, contig: str, first: int, second: int) -> bool:
        """Whether two positions are in one block — the precondition for a phase claim.

        Two alleles in different blocks are **not** unphased by accident: the phaser is
        saying the reads gave it no path between them. Reporting that as "cis unknown" is
        correct; reporting it as "trans" is the mistake this method exists to prevent.
        """
        left = self.block_containing(contig, first)
        right = self.block_containing(contig, second)
        return left is not None and left == right


def whatshap(
    reference: Path,
    bam: Path,
    vcf: Path,
    out_dir: Path,
    *,
    stem: str = "baited",
    indels: bool = True,
) -> Phasing:
    """Phase a callset against the alignments it came from.

    ``--indels`` is on by default: an indel is often the only heterozygous position
    between two distant alleles, and dropping it can break a chain that the reads
    actually support. It is a flag because WhatsHap's own default is off, and a run that
    differs from a tool's default should say so rather than inherit ours silently.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{stem}.phased.vcf"
    provenance = started_now("whatshap")
    provenance.inputs = {"reference": str(reference), "bam": str(bam), "vcf": str(vcf)}
    provenance.parameters = {
        "tool": "whatshap phase",
        "model": "weighted minimum error correction over read-backed haplotypes",
        "indels": indels,
    }
    argv = [
        "whatshap",
        "phase",
        "--reference",
        str(reference),
        "-o",
        str(target),
        str(vcf),
        str(bam),
    ]
    if indels:
        argv.insert(2, "--indels")
    provenance.invocations.append(run(argv))
    blocks = read_blocks(target)
    provenance.outputs = {"vcf": str(target), "blocks": str(len(blocks))}
    manifest = provenance.write(out_dir / f"{stem}.whatshap.provenance.json")
    return Phasing(vcf=target, blocks=blocks, manifest=manifest)


def read_blocks(vcf: Path) -> tuple[PhaseBlock, ...]:
    """Block structure from a phased VCF's ``PS`` (phase set) sample field.

    ``PS`` holds the position of the first variant in the block, so every record sharing a
    ``PS`` value belongs to one block and the block's extent is the span of those records.
    """
    import gzip
    from collections import defaultdict

    spans: dict[tuple[str, str], list[int]] = defaultdict(list)
    opener = gzip.open if vcf.suffix == ".gz" else open
    with opener(vcf, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                continue
            keys = fields[8].split(":")
            if "PS" not in keys:
                continue
            values = fields[9].split(":")
            if len(values) != len(keys):
                continue
            phase_set = values[keys.index("PS")]
            if phase_set in {".", ""}:
                continue
            spans[(fields[0], phase_set)].append(int(fields[1]))
    return tuple(
        PhaseBlock(contig=contig, start=min(positions), end=max(positions), variants=len(positions))
        for (contig, _), positions in sorted(spans.items())
    )


@dataclass(frozen=True)
class FragmentSupport:
    """How many fragments carry each combination of two alleles.

    ``both_alt`` is direct evidence of cis. ``alt_ref`` plus ``ref_alt`` with no
    ``both_alt`` is evidence of trans — but only when the fragment count is high enough
    that seeing zero cis fragments means something, which is what :attr:`informative` is
    for. Two alleles no fragment spans give all zeros, and that is the honest answer.
    """

    both_alt: int = 0
    both_ref: int = 0
    alt_ref: int = 0
    ref_alt: int = 0

    @property
    def spanning(self) -> int:
        return self.both_alt + self.both_ref + self.alt_ref + self.ref_alt

    @property
    def informative(self) -> bool:
        """Whether any fragment saw both positions at all."""
        return self.spanning > 0

    @property
    def verdict(self) -> str:
        if not self.informative:
            return "no spanning fragment"
        if self.both_alt and not (self.alt_ref or self.ref_alt):
            return "cis"
        if (self.alt_ref or self.ref_alt) and not self.both_alt:
            return "trans"
        return "conflicting"
