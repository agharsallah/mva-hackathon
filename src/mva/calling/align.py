"""Put the recovered reads back on the coordinate system, and measure how well they sat.

**What alignment is, and why it is a separate step from recovery.** The read store holds
fragments with no position: the sequencer reports what it read, not where in the genome it
came from. Recovery (:mod:`mva.reads.bait`) selects reads by sequence alone and still
knows no coordinate. Alignment is the stage that assigns one — it searches the reference
for where each read fits best and records that, plus how confident it is (**MAPQ**, a
phred-scaled probability the placement is wrong).

**Why the full reference and not just the baited regions.** Aligning to a 42 Mb subset
would force every recovered read to land somewhere inside it, including the reads that
came from a paralogue elsewhere and were recovered because they share a k-mer. Given the
whole genome those reads go where they belong and are then excluded by position, which is
the only way to tell "this gene has an extra allele" from "this gene has a cousin".

**minimap2 rather than bwa-mem2**, for a stated reason: bwa-mem2's index construction
needs tens of gigabytes of RAM, which this machine does not have. `minimap2 -ax sr` is its
short-read preset, indexes in minutes, and `-I` bounds the index batch so memory stays
predictable. The cost is recorded rather than hidden: minimap2's short-read mode is less
studied for indel-heavy loci than bwa-mem, and the alignment-derived indel calls carry
that caveat.

**Duplicates are marked, not removed.** Two fragments with identical outer coordinates are
usually one molecule amplified twice, and counting both inflates the evidence for whatever
allele it carried. Marking leaves the reads in the file for inspection while callers skip
them by flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .tools import capture, pipe, run, sha256, started_now

#: minimap2's short-read preset. `-a` asks for SAM, `-x sr` sets the seeding and scoring
#: for ~150 bp paired reads.
PRESET = ("-ax", "sr")

#: Index batch size. minimap2 loads this many reference bases at a time, so it is the knob
#: that sets peak memory. A whole human genome in one batch is ~8 GB resident, which this
#: machine does not have spare — measured 2026-09-12, minimap2 paged out to 0.3 GB with
#: swap at 24.9 of 26.6 GB and made almost no progress. 1G indexes in four batches at
#: ~2 GB each.
INDEX_BATCH = "1G"

#: **Required whenever the index is split.** With more than one batch minimap2 computes
#: mapping quality per batch, so a read mapping in two batches gets two records each
#: claiming high confidence — silently wrong MAPQ, which every downstream filter trusts.
#: `--split-prefix` makes it stage per-batch results and merge them, restoring the
#: single-index result at the cost of temporary files. Splitting without it would trade a
#: memory problem for a correctness one.
SPLIT_PREFIX = "mm2-split"


@dataclass(frozen=True)
class Alignment:
    """The sorted, indexed, duplicate-marked alignments and the manifest beside them."""

    bam: Path
    index: Path
    manifest: Path
    reads: int
    mapped: int
    properly_paired: int
    duplicates: int

    @property
    def mapped_fraction(self) -> float:
        return self.mapped / self.reads if self.reads else 0.0


def align(
    reference: Path,
    r1: Path,
    r2: Path,
    out_dir: Path,
    *,
    threads: int = 4,
    stem: str = "baited",
    index_batch: str = INDEX_BATCH,
    sort_memory: str = "512M",
    read_group: str = "@RG\\tID:baited\\tSM:proband\\tPL:ILLUMINA",
) -> Alignment:
    """Align a recovered pair of FASTQ files to the whole reference and index the result.

    The chain is minimap2 -> `samtools fixmate` -> `sort` -> `markdup` -> `index`, with
    the first three as one pipeline so no intermediate alignment file is ever written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = started_now("align")
    provenance.parameters = {
        "aligner": "minimap2",
        "preset": " ".join(PRESET),
        "index_batch": index_batch,
        "split_prefix": SPLIT_PREFIX,
        "threads": threads,
        "sort_memory_per_thread": sort_memory,
        "read_group": read_group,
        "duplicates": "marked, not removed",
    }
    provenance.inputs = {
        "reference": str(reference),
        "r1": str(r1),
        "r2": str(r2),
    }

    sorted_bam = out_dir / f"{stem}.sorted.bam"
    final = out_dir / f"{stem}.bam"

    # One pipeline, three tools, no intermediate SAM. A SAM of 15.7 million reads is ~8 GB
    # of text written only to be read back and deleted, and on a machine with 13 GB free
    # that is not a tidiness question — it is the difference between a run and a full disk.
    # `fixmate` must sit between the aligner and the sort: `markdup` decides what a
    # duplicate is from the mate coordinates and the template length, and both are only
    # filled in once `fixmate` has seen the pair together, which it can only do while the
    # records are still in name order.
    provenance.invocations.extend(
        pipe(
            [
                [
                    "minimap2",
                    *PRESET,
                    "-t",
                    str(threads),
                    "-I",
                    index_batch,
                    "--split-prefix",
                    str(out_dir / SPLIT_PREFIX),
                    "-R",
                    read_group,
                    str(reference),
                    str(r1),
                    str(r2),
                ],
                ["samtools", "fixmate", "-@", str(threads), "-u", "-m", "-", "-"],
                [
                    "samtools",
                    "sort",
                    "-@",
                    str(threads),
                    "-m",
                    sort_memory,
                    "-T",
                    str(out_dir / "sort-tmp"),
                    "-o",
                    str(sorted_bam),
                    "-",
                ],
            ],
            stdout=out_dir / f"{stem}.pipe.log",
        )
    )
    (out_dir / f"{stem}.pipe.log").unlink(missing_ok=True)
    provenance.invocations.append(
        run(["samtools", "markdup", "-@", str(threads), str(sorted_bam), str(final)])
    )
    sorted_bam.unlink(missing_ok=True)
    provenance.invocations.append(run(["samtools", "index", "-@", str(threads), str(final)]))

    stats = flagstat(final)
    provenance.outputs = {
        "bam": str(final),
        "bam_sha256": sha256(final, limit=1 << 26),
        "index": str(final.with_suffix(".bam.bai")),
    }
    provenance.parameters["flagstat"] = stats
    manifest = provenance.write(out_dir / f"{stem}.align.provenance.json")
    return Alignment(
        bam=final,
        index=final.with_suffix(".bam.bai"),
        manifest=manifest,
        reads=stats.get("total", 0),
        mapped=stats.get("mapped", 0),
        properly_paired=stats.get("properly_paired", 0),
        duplicates=stats.get("duplicates", 0),
    )


def flagstat(bam: Path) -> dict[str, int]:
    """Read counts from ``samtools flagstat``, as the numbers the alignment gate reads.

    Parsed from the machine-readable JSON rather than the human table, so a change in
    wording cannot silently turn a count into zero.
    """
    import json

    payload = json.loads(capture(["samtools", "flagstat", "-O", "json", str(bam)])).get(
        "QC-passed reads", {}
    )
    return {
        "total": int(payload.get("total", 0)),
        "mapped": int(payload.get("mapped", 0)),
        "properly_paired": int(payload.get("properly paired", 0)),
        "duplicates": int(payload.get("duplicates", 0)),
        "singletons": int(payload.get("singletons", 0)),
    }
