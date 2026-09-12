"""Call small variants twice, with two models that fail differently.

**What a variant caller does.** Given aligned reads, decide at every position whether the
sample differs from the reference and with what genotype. The hard part is not spotting a
mismatch — it is telling a real allele from a sequencing error, a misalignment near an
indel, or a read from a paralogue that landed here.

**Why two callers, and which two.** The delivered callset came from Sentieon's Haplotyper,
a reimplementation of GATK's local-reassembly model. A second caller is only worth running
if it can fail where that one fails *differently*, so both of these were chosen for having
a different model rather than for being newer:

``freebayes``     a Bayesian caller over haplotypes observed directly in the reads, with no
                  local reassembly. Different from GATK's model in the step that matters
                  most for indels, and its own author's stated design point.
``bcftools call`` the pileup model: per-base likelihoods accumulated column by column, no
                  haplotype notion at all. The oldest and most different of the three.

Where all three agree, the allele is as close to certain as a single sample allows. Where
they disagree, the disagreement is the finding — which is exactly what H022 measures, and
why concordance is computed **after** the calls exist rather than used to filter them.

**No filtering happens here.** These adapters emit what the callers emit. Rarity,
consequence and pair enumeration are later stages over a table, because a hard filter
applied at the point of calling cannot be revisited without re-calling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tools import Invocation, capture, pipe, run, sha256, started_now

#: Minimum mapping quality a read needs to contribute. The same 20 the coverage stage
#: uses, for the same reason, and stated in both manifests rather than shared by import
#: from one of them — they are separate decisions that happen to agree today.
MIN_MAPQ = 20

#: Minimum base quality. Below this the machine's own confidence is too low for the base
#: to distinguish an allele from an error.
MIN_BASEQ = 20


@dataclass(frozen=True)
class Callset:
    """One caller's output: the VCF, its index, and how many records it holds."""

    caller: str
    vcf: Path
    index: Path
    records: int
    manifest: Path


def _index(vcf: Path) -> tuple[Path, list[Invocation]]:
    """Sort, compress and index — the three things every downstream tool assumes.

    The sort is not defensive tidiness. A caller given a target list walks it in the order
    it was handed, and baited intervals of two overlapping genes are not in coordinate
    order globally however carefully the list is sorted by start: a long interval emits
    calls past the start of the next one. tabix then refuses the file with "Unsorted
    positions on sequence", after the calling has already been paid for.
    """
    invocations = []
    sorted_vcf = vcf.with_suffix("") if vcf.suffix == ".gz" else vcf
    sorted_vcf = sorted_vcf.with_name(f"{sorted_vcf.stem}.sorted.vcf.gz")
    invocations.append(run(["bcftools", "sort", "-Oz", "-o", str(sorted_vcf), str(vcf)]))
    vcf.unlink(missing_ok=True)
    invocations.append(run(["tabix", "-f", "-p", "vcf", str(sorted_vcf)]))
    return sorted_vcf, invocations


def _count(vcf: Path) -> int:
    text = capture(["bcftools", "index", "--nrecords", str(vcf)]).strip()
    return int(text) if text.isdigit() else 0


def freebayes(
    reference: Path,
    bam: Path,
    regions: Path,
    out_dir: Path,
    *,
    stem: str = "baited",
    min_mapq: int = MIN_MAPQ,
    min_baseq: int = MIN_BASEQ,
) -> Callset:
    """Call with freebayes over the baited intervals only.

    ``--targets`` is not an optimisation here, it is a correctness boundary: the recovered
    reads were aligned to the whole genome so they could land where they belong, and
    calling genome-wide over a baited BAM would report "variants" in every region that
    happens to have caught a stray read at 1x.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"{stem}.freebayes.vcf"
    provenance = started_now("freebayes")
    provenance.inputs = {"reference": str(reference), "bam": str(bam), "targets": str(regions)}
    provenance.parameters = {
        "caller": "freebayes",
        "model": "Bayesian over directly observed haplotypes, no local reassembly",
        "min_mapq": min_mapq,
        "min_baseq": min_baseq,
        "filtering": "none — every emitted record is kept",
    }
    provenance.invocations.append(
        run(
            [
                "freebayes",
                "-f",
                str(reference),
                "-t",
                str(regions),
                "--min-mapping-quality",
                str(min_mapq),
                "--min-base-quality",
                str(min_baseq),
                str(bam),
            ],
            stdout=raw,
        )
    )
    vcf, more = _index(raw)
    provenance.invocations.extend(more)
    records = _count(vcf)
    provenance.outputs = {
        "vcf": str(vcf),
        "sha256": sha256(vcf, limit=1 << 24),
        "records": str(records),
    }
    manifest = provenance.write(out_dir / f"{stem}.freebayes.provenance.json")
    return Callset(
        caller="freebayes",
        vcf=vcf,
        index=Path(f"{vcf}.tbi"),
        records=records,
        manifest=manifest,
    )


def bcftools(
    reference: Path,
    bam: Path,
    regions: Path,
    out_dir: Path,
    *,
    stem: str = "baited",
    min_mapq: int = MIN_MAPQ,
    min_baseq: int = MIN_BASEQ,
) -> Callset:
    """Call with the pileup model: ``bcftools mpileup | bcftools call -m``.

    Run as one pipeline because the intermediate pileup is tens of gigabytes of text that
    exists only to be consumed by the next process. ``-m`` is the multiallelic caller,
    which supersedes the original consensus model and is what bcftools recommends.
    ``-a AD,DP`` keeps the per-allele depths, without which a genotype cannot be
    re-examined later.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"{stem}.bcftools.vcf.gz"
    provenance = started_now("bcftools-call")
    provenance.inputs = {"reference": str(reference), "bam": str(bam), "targets": str(regions)}
    provenance.parameters = {
        "caller": "bcftools mpileup | bcftools call -m",
        "model": "per-base pileup likelihoods, multiallelic caller, no haplotypes",
        "min_mapq": min_mapq,
        "min_baseq": min_baseq,
        "annotations": "AD,DP",
        "filtering": "none — every emitted record is kept",
    }
    provenance.invocations.extend(
        pipe(
            [
                [
                    "bcftools",
                    "mpileup",
                    "-f",
                    str(reference),
                    "-R",
                    str(regions),
                    "-q",
                    str(min_mapq),
                    "-Q",
                    str(min_baseq),
                    "-a",
                    "AD,DP",
                    "-Ou",
                    str(bam),
                ],
                ["bcftools", "call", "-m", "-v", "-Oz"],
            ],
            stdout=raw,
        )
    )
    provenance.invocations.append(run(["tabix", "-f", "-p", "vcf", str(raw)]))
    records = _count(raw)
    provenance.outputs = {
        "vcf": str(raw),
        "sha256": sha256(raw, limit=1 << 24),
        "records": str(records),
    }
    manifest = provenance.write(out_dir / f"{stem}.bcftools.provenance.json")
    return Callset(
        caller="bcftools",
        vcf=raw,
        index=Path(f"{raw}.tbi"),
        records=records,
        manifest=manifest,
    )


def normalise(reference: Path, callset: Callset, out_dir: Path) -> Callset:
    """Split multiallelic records and left-align indels, so two callers can be compared.

    Without this, comparing callers compares spellings: one may write an insertion as a
    single record with two alternates where another writes two records, and the same
    deletion can be placed at either end of a homopolymer. `bcftools norm -m -both -f` is
    the same normalisation the delivered callset was put through
    (``ideation/data-findings.md``), which is what makes H022's concordance a statement
    about the callers rather than about their formatting.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{callset.vcf.name.replace('.vcf.gz', '')}.norm.vcf.gz"
    provenance = started_now(f"normalise-{callset.caller}")
    provenance.inputs = {"vcf": str(callset.vcf), "reference": str(reference)}
    provenance.parameters = {"command": "bcftools norm -m -both -f <reference>"}
    provenance.invocations.append(
        run(
            [
                "bcftools",
                "norm",
                "-m",
                "-both",
                "-f",
                str(reference),
                "-Oz",
                "-o",
                str(target),
                str(callset.vcf),
            ]
        )
    )
    provenance.invocations.append(run(["tabix", "-f", "-p", "vcf", str(target)]))
    records = _count(target)
    provenance.outputs = {"vcf": str(target), "records": str(records)}
    manifest = provenance.write(out_dir / f"{target.name}.provenance.json")
    return Callset(
        caller=callset.caller,
        vcf=target,
        index=Path(f"{target}.tbi"),
        records=records,
        manifest=manifest,
    )
