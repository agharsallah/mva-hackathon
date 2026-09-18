"""The HGVS pass: ask VEP how each allele is spelled, and never ask twice.

Step 1 of iteration 4 builds one :class:`~mva.zoo.types.AlleleRecord` per allele from
tables the warehouse already holds. One thing those tables do **not** hold is **HGVS
notation** — the Human Genome Variation Society's standard text spelling of a change, at
cDNA level (``ENST…:c.2211C>G``) and at protein level (``ENSP…:p.Tyr737Ter``). Iteration 2
asked VEP without ``hgvs=1`` reaching the record, so the columns were dropped on the floor
(`docs/iteration4/todo.md`). Every tier-1 precomputed score table is keyed on one of those
two strings, so the zoo cannot look anything up without them.

This module is that one extra pass, and it is deliberately dull:

* **It is a pure re-request.** Nothing is recomputed; VEP is asked the same question again
  with the transcript and the two HGVS strings kept this time.
* **It is checkpointed.** Every answered batch is written to a JSONL file under ``build/``
  before the next one is asked, through the same
  :class:`~mva.warehouse.annotate_coding.Checkpoint` the genome-wide annotation pass uses.
  A rerun loads the files, subtracts what they answered, and asks only the remainder — so
  a crash 90 % of the way through costs one batch, not a morning.
* **It holds the coordinate.** :class:`Coordinate` is the only place in the zoo where a
  genomic position is carried, because VEP's query line needs one. It travels to
  ``build/`` and no further; ``allele_id`` is what leaves.

The annotator is injected — anything with ``annotate_many(variants) -> [VepRecord]`` will
do — so every test here runs without a network.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

import httpx

from ..pipeline.annotate_vep import QUERY_PARAMS, VepError, VepRestAnnotator, batches
from ..pipeline.variant import Variant
from ..pipeline.vep_response import VepRecord, query_line
from ..warehouse.annotate_coding import Checkpoint
from .types import AlleleRecord

__all__ = [
    "DEFAULT_CHECKPOINT",
    "EXTRA_PARAMS",
    "Annotates",
    "Coordinate",
    "HgvsAnnotator",
    "HgvsPass",
    "hgvs_pass",
]


class Annotates(Protocol):
    """The one method this pass needs from an annotator — the seam the tests replace.

    :class:`~mva.pipeline.annotate_vep.VepRestAnnotator` satisfies it; so does a five-line
    fake that returns canned records, which is why nothing here touches the network.
    """

    def annotate_many(self, variants: Sequence[Variant]) -> Sequence[VepRecord]: ...


#: Gitignored, and the only directory in this step that holds patient positions.
DEFAULT_CHECKPOINT = Path("build/it4/vep-hgvs")

#: VEP's documented POST ceiling, mirrored from :mod:`mva.pipeline.annotate_vep`.
DEFAULT_BATCH = 200

#: Response options this pass needs on top of
#: :data:`mva.pipeline.annotate_vep.QUERY_PARAMS`. ``hgvs`` is already in that set;
#: ``uniprot`` is not, and without it ``transcript_consequences[].swissprot`` is absent and
#: the ESM1b lane has nothing to join on.
EXTRA_PARAMS = {"uniprot": 1}


class HgvsAnnotator(VepRestAnnotator):
    """The REST client with :data:`EXTRA_PARAMS` added to every batch.

    A subclass rather than an edit because ``QUERY_PARAMS`` is a module-level constant of
    :mod:`mva.pipeline.annotate_vep` with no per-instance override, and that module belongs
    to another owner this wave. The override duplicates four lines of transport; the
    durable fix is to fold ``uniprot`` into ``QUERY_PARAMS`` and delete this class, which
    ``build/it4/agents/record.md`` asks the main thread to do.
    """

    def _post_batch(self, chunk: Sequence[Variant]) -> list[dict]:
        payload = {
            "variants": [query_line(variant) for variant in chunk],
            **QUERY_PARAMS,
            **EXTRA_PARAMS,
        }
        body = self._request("POST", "/vep/homo_sapiens/region", json=payload)
        return body if isinstance(body, list) else []


@dataclass(frozen=True)
class Coordinate:
    """Where an allele sits, in the callset's own spelling.

    Kept beside the record rather than inside it: the record is what leaves (a table, a
    report, a model input), and the repository's coordinate gate says a position may not.
    """

    chrom: str
    pos: int
    ref: str
    alt: str

    @property
    def variant(self) -> Variant:
        """The same allele as the pipeline's :class:`~mva.pipeline.variant.Variant` key."""
        return Variant.from_vcf(self.chrom, self.pos, self.ref, self.alt)


@dataclass(frozen=True)
class HgvsPass:
    """What one pass did: the filled records, plus how much work it actually cost."""

    records: list[AlleleRecord]
    asked: int
    resumed: int
    answered: int
    source: str = ""


def hgvs_pass(
    records: Sequence[AlleleRecord],
    coordinates: Mapping[str, Coordinate],
    annotator: Annotates,
    *,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT,
    batch_size: int = DEFAULT_BATCH,
    progress: Callable[[str], None] | None = None,
) -> HgvsPass:
    """Fill ``transcript``, ``hgvs_c``, ``hgvs_p`` and ``uniprot`` for every placed record.

    A record whose allele the server had nothing to say about comes back unchanged rather
    than dropped, so the row count never silently shrinks. A field the record already
    carries is never overwritten: this pass adds, it does not correct.
    """
    say = progress or (lambda _line: None)
    store = Checkpoint(checkpoint_dir)
    answered = store.load()
    wanted = {
        record.allele_id: coordinates[record.allele_id].variant
        for record in records
        if record.allele_id in coordinates
    }
    todo = sorted({variant for variant in wanted.values() if variant not in answered})
    resumed = len(set(wanted.values())) - len(todo)
    say(f"alleles {len(wanted):,}  checkpointed {resumed:,}  to ask {len(todo):,}")

    index = store.next_index()
    chunks = batches(todo, batch_size)
    for offset, chunk in enumerate(chunks):
        got = list(annotator.annotate_many(chunk))
        store.append(index + offset, got)
        answered.update({item.variant: item for item in got})
        say(f"  batch {offset + 1}/{len(chunks)}  answered {len(answered):,}")

    filled = [
        _fill(record, answered.get(wanted.get(record.allele_id, _MISSING))) for record in records
    ]
    return HgvsPass(
        records=filled,
        asked=len(todo),
        resumed=resumed,
        answered=sum(1 for record in filled if record.hgvs_c or record.hgvs_p),
        source=version_label(annotator),
    )


#: A key no real variant equals, so ``answered.get`` misses cleanly for a record with no
#: coordinate instead of needing a second branch.
_MISSING = Variant("", 1, "", "")


def _fill(record: AlleleRecord, found: VepRecord | None) -> AlleleRecord:
    """One record with VEP's spellings added where the record had none."""
    if found is None:
        return record
    return replace(
        record,
        transcript=record.transcript or found.transcript,
        hgvs_c=record.hgvs_c or found.hgvsc,
        hgvs_p=record.hgvs_p or found.hgvsp,
        uniprot=record.uniprot or found.uniprot,
        consequence=record.consequence or found.consequence,
    )


def version_label(annotator: object) -> str:
    """Which Ensembl release and assembly answered — the fact that makes the pass repeatable.

    Read from the server, never hard-coded: the same query against a later release can
    legitimately return a different transcript, and a stored HGVS string without its
    release is not reproducible. An annotator that cannot say (a fake, an offline run)
    yields an empty label rather than a guess.
    """
    getter = getattr(annotator, "version", None)
    if not callable(getter):
        return ""
    try:
        info = getter() or {}
    except (VepError, httpx.HTTPError, OSError):
        return ""
    return (
        f"ensembl-vep-rest release={info.get('release', '?')} assembly={info.get('assembly', '?')}"
    )
