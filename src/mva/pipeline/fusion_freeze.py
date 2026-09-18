"""Turning a fused ranking into the exact bytes whose digest is written down.

The blind protocol asks for a ranking that is **frozen and hashed before the comparison**, so
the artifact has to be the thing that is hashed: same rows, same order, same formatting,
therefore the same digest on any machine and on any re-run. A hash of an in-memory object
would prove nothing a reader could check; a hash of this file is one ``shasum`` away from
being checked by anybody.

Kept apart from :mod:`mva.pipeline.fusion` because it is a serialisation format, not the
arithmetic — and because a column added here changes a digest quoted in an append-only
methodology entry, which is a reason to touch it deliberately.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from .fusion import MISSING_RANK, FusedPair, Route

__all__ = ["COLUMNS", "Frozen", "freeze"]


@dataclass(frozen=True)
class Frozen:
    """A fused ranking, exported and hashed before anybody compares it to anything."""

    text: str
    sha256: str
    rows: int


#: The frozen export's columns. Written out rather than derived from the dataclass, because
#: the hash of this file is quoted in a methodology entry and a silent column change would
#: invalidate it without anybody noticing.
COLUMNS = (
    "rank",
    "pair_id",
    "gene",
    "score",
    "independent_evidence",
    "inputs",
    # Named apart from a route called "confirmation": the route columns are appended after
    # these, and two columns with one name in a TSV is a defect nobody notices until a
    # reader picks the wrong one.
    "confirmation_flags",
)


def freeze(fused: Sequence[FusedPair], *, routes: Sequence[Route] = ()) -> Frozen:
    """Serialise a fused ranking to canonical TSV and hash it.

    The text is the artifact: same rows, same order, same formatting, therefore same digest.
    Scores are printed at 12 significant digits — enough that two orderings which differ
    cannot hash the same, few enough that platform float formatting cannot make an identical
    run differ from itself.
    """
    header = list(COLUMNS) + [route.name for route in routes]
    lines = ["\t".join(header)]
    for row in fused:
        confirmation = "".join(
            flag
            for flag, on in (
                ("R", row.confirmation.read_confirmed),
                ("1", row.confirmation.single_copy),
                ("C", row.confirmation.no_cn_loss),
            )
            if on
        )
        cells = [
            str(row.rank),
            row.pair.id,
            row.pair.gene,
            f"{row.score:.12g}",
            str(row.independent_evidence),
            ",".join(row.inputs),
            confirmation or "-",
        ]
        cells.extend(str(row.per_route.get(route.name, MISSING_RANK)) for route in routes)
        lines.append("\t".join(cells))
    text = "\n".join(lines) + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return Frozen(text=text, sha256=digest, rows=len(fused))
