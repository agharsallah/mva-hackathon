"""Everything known about one claim, in one object — and the bridge to a submission row.

Two jobs that belong together because they are the same seam:

**Assembly.** A :class:`Dossier` is a hypothesis, its full revision history, its evidence,
and the weighing over that evidence. It is what the export writes, what the report renders,
and what a reviewer reads. Assembling it once here means the Markdown file and the HTML
page cannot drift apart — they are two renderings of one object.

**The bridge.** A supported hypothesis eventually becomes a row in the submission CSV, and
the moment it does, the reasoning has to survive the crossing. :func:`to_row` stamps the
hypothesis id into ``Row.notes``, so a row the scorer sees can be traced back to the claim
that produced it and the evidence behind that claim. :func:`evidence_from_pair` runs the
crossing the other way: it turns the ranking arithmetic that
:class:`~mva.pipeline.ranking.PairEvidence` captured into evidence rows, so "the ranker put
this first" becomes a recorded observation rather than a fact buried in a sort order.

Nothing here writes to the warehouse. Assembly reads, the bridge builds objects, and the
caller decides what to persist.
"""

from dataclasses import dataclass

from ..pipeline.ranking import RankedPair
from ..pipeline.submission import Row
from . import evidence as evidence_module
from . import steps
from .evidence import Direction, Evidence, Weighing, weigh
from .hypothesis import Hypothesis, Status
from .hypothesis import all_revisions as read_all_revisions
from .hypothesis import history as read_history

#: Marker opening every generated ``Row.notes``, so a submitted row names its own claim.
#: Kept short: the notes column travels to the scorer and there is no reason to spend it
#: on prose.
NOTE_PREFIX = "H:"


@dataclass(frozen=True)
class Dossier:
    """One claim, everything recorded about it, and what that adds up to."""

    hypothesis: Hypothesis
    history: tuple[Hypothesis, ...]
    evidence: tuple[Evidence, ...]
    weighing: Weighing

    @property
    def step(self) -> steps.Step:
        """The step whose goal this claim serves."""
        return steps.by_slug(self.hypothesis.step)

    @property
    def supports(self) -> tuple[Evidence, ...]:
        return tuple(e for e in self.evidence if e.direction is Direction.SUPPORTS)

    @property
    def refutes(self) -> tuple[Evidence, ...]:
        return tuple(e for e in self.evidence if e.direction is Direction.REFUTES)

    @property
    def is_untested(self) -> bool:
        """Whether anything at all has been observed about this claim yet."""
        return not self.evidence

    @property
    def confidence_gap(self) -> float | None:
        """How far the recorded confidence sits from what the evidence suggests.

        A large gap is not an error — a human may have good reason to discount the
        arithmetic — but it is the thing a reviewer should be shown rather than left to
        compute. ``None`` when no confidence has been committed.
        """
        if self.hypothesis.confidence is None:
            return None
        return self.hypothesis.confidence - self.weighing.confidence

    @property
    def slug(self) -> str:
        """Filename stem for the exported dossier."""
        stem = self.hypothesis.gene or self.hypothesis.step
        return f"{self.hypothesis.hypothesis_id.lower()}-{_slugify(stem)}"


def _slugify(text: str) -> str:
    """Lowercase alphanumerics and hyphens, matching the exhibit-slug rule."""
    kept = [c.lower() if c.isalnum() else "-" for c in text]
    return "-".join(part for part in "".join(kept).split("-") if part) or "untitled"


def assemble(connection, schema: str, hypothesis_id: str) -> Dossier:
    """Read one claim and everything recorded about it out of the warehouse."""
    revisions = read_history(connection, schema, hypothesis_id)
    if not revisions:
        raise KeyError(f"no hypothesis {hypothesis_id!r} in {schema}")
    rows = evidence_module.listing(connection, schema, hypothesis_id)
    return Dossier(
        hypothesis=revisions[-1], history=tuple(revisions), evidence=tuple(rows),
        weighing=weigh(rows, hypothesis_id))


def assemble_all(connection, schema: str, step: str | None = None) -> list[Dossier]:
    """Every claim, assembled. One query per table, then grouped in memory.

    Written this way rather than as a loop of :func:`assemble` calls because the report
    needs all of them and a per-hypothesis round trip over an attached database is the
    kind of cost that only shows up once the register is large.
    """
    revisions = read_all_revisions(connection, schema, step)

    grouped: dict[str, list[Hypothesis]] = {}
    for revision in revisions:
        grouped.setdefault(revision.hypothesis_id, []).append(revision)

    all_evidence = evidence_module.by_hypothesis(
        evidence_module.listing(connection, schema))

    return [
        Dossier(hypothesis=history[-1], history=tuple(history),
                evidence=tuple(all_evidence.get(hypothesis_id, ())),
                weighing=weigh(all_evidence.get(hypothesis_id, []), hypothesis_id))
        for hypothesis_id, history in grouped.items()
    ]


def tally(dossiers: list[Dossier]) -> dict[Status, int]:
    """How many claims sit at each status — the step cards' headline number."""
    counts = {status: 0 for status in Status}
    for dossier in dossiers:
        counts[dossier.hypothesis.status] += 1
    return counts


# --------------------------------------------------------------------------------------
# The bridge to submission
# --------------------------------------------------------------------------------------

def to_row(pair: RankedPair, hypothesis_id: str, epcr: float,
           finding_type: str = "primary", note: str = "") -> Row:
    """Turn a ranked pair into a submission row that names the claim behind it.

    ``notes`` is the only column that survives to the scorer carrying free text, and it is
    unvalidated, so it is the one place a row can say why it exists. Format is
    ``H:H003 | BUB1B | <note>`` — the id first, so the tie back to the register is the part
    that survives any truncation.
    """
    parts = [f"{NOTE_PREFIX}{hypothesis_id}"]
    if pair.gene:
        parts.append(pair.gene)
    if note:
        parts.append(note)
    return Row(variant=pair.left, partner=pair.right, epcr=epcr,
               finding_type=finding_type, notes=" | ".join(parts))


def hypothesis_of(row: Row) -> str:
    """Read the claim id back out of a submission row, or ``""`` if it names none.

    The inverse of :func:`to_row`, so a submission file recovered from disk — or an oracle
    reply naming a rank — can be tied back to the register without a side table.
    """
    head = row.notes.split("|", 1)[0].strip()
    return head[len(NOTE_PREFIX):].strip() if head.startswith(NOTE_PREFIX) else ""


def evidence_from_pair(pair: RankedPair, hypothesis_id: str, source_ref: str,
                       author: str = "") -> list[Evidence]:
    """Turn the ranking arithmetic into recorded observations.

    Emits at most three rows and only for terms that actually carry information:

    * both alleles rare — the strongest single filter for an ultra-rare recessive disease;
    * both alleles loss-of-function — the shape a biallelic diagnosis takes;
    * a gene prior other than 1.0 — recorded explicitly, because a prior applied silently
      is an assumption buried in a threshold.

    A pair carrying no :class:`~mva.pipeline.ranking.PairEvidence` yields nothing rather
    than a guess.
    """
    if pair.evidence is None:
        return []

    detail = pair.evidence
    rows: list[Evidence] = []
    gene = pair.gene or "the gene"

    if detail.both_rare:
        rows.append(Evidence(
            hypothesis_id=hypothesis_id, direction=Direction.SUPPORTS, strength=0.7,
            kind="annotation", author=author, source_ref=source_ref,
            claim=(f"Both alleles in {gene} are below the ultra-rare frequency "
                   f"threshold used for ranking.")))
    elif detail.left_rarity < 1.0 and detail.right_rarity < 1.0:
        rows.append(Evidence(
            hypothesis_id=hypothesis_id, direction=Direction.REFUTES, strength=0.6,
            kind="annotation", author=author, source_ref=source_ref,
            claim=(f"Neither allele in {gene} is rare enough for a disease with fewer "
                   f"than 50 known patients.")))

    if detail.both_loss_of_function:
        rows.append(Evidence(
            hypothesis_id=hypothesis_id, direction=Direction.SUPPORTS, strength=0.6,
            kind="annotation", author=author, source_ref=source_ref,
            claim=f"Both alleles in {gene} are predicted loss-of-function."))

    if detail.gene_prior != 1.0:
        rows.append(Evidence(
            hypothesis_id=hypothesis_id, direction=Direction.NEUTRAL,
            strength=0.0, kind="annotation", author=author, source_ref=source_ref,
            claim=(f"A gene prior of {detail.gene_prior:g} was applied to {gene}; the "
                   f"ranking reflects a stated assumption, not the data alone.")))

    return rows
