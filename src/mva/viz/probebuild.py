"""Turn dashboard candidates into a validated Track 1 submission CSV.

The dashboard already knows which alleles are interesting. What it could not do is turn a
handful of them into the file that gets uploaded — that step was a human retyping
coordinates into a spreadsheet, which is the one place in this project where a single
mistyped digit costs a whole submission out of eighteen. This endpoint removes the typing.

**It owns no format rules.** Every rule lives in :mod:`mva.pipeline.submission` and every
score in :mod:`mva.pipeline.scorer`; this module converts JSON into ``Row`` objects, asks
those two what they think, and hands back what they said. The two things it does add are
both about the browser: it enumerates *all* the problems instead of raising on the first,
and it labels each one ``error`` (the file cannot be written) or ``warning`` (it can, but
the payload is not what you probably meant).

**Contig spelling.** Requests carry the **bare** contig the panel endpoints serve
(``"15"``), because that is how the callset spells it; the template is chr-prefixed.
:meth:`Variant.from_vcf` is the only thing here that bridges that — strip on the way in,
add on the way out, decided once in :mod:`mva.pipeline.variant`.

**The self-test.** There is no ground truth, so nothing here can tell you whether a
candidate is right. What it *can* prove is that the bytes parse the way the scorer parses
them: the emitted CSV is read back with :func:`~mva.pipeline.submission.read_submission`
(verbatim strings, no normalization, exactly the scorer's key) and scored against a
synthetic truth equal to row 1's own alleles. A correct file scores ``rank_points 100``
and ``f_max 1.0``; anything less means the round trip lost or changed something —
a chr prefix, a case, a number — and the real submission would silently miss.

**Nothing is written to disk.** The CSV is a string in the response; the browser saves it.
"""

from io import StringIO

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..pipeline import scorer, submission
from ..pipeline.variant import Variant
from .response import Envelope, live

#: No table is read: the payload is the request, put through the pipeline's own rules.
SOURCE = "mva.pipeline.submission + mva.pipeline.scorer (no table read)"

ERROR = "error"
WARNING = "warning"


class VariantIn(BaseModel):
    """One allele as the panel endpoints serve it — **bare** contig, VCF spelling."""

    chrom: str = Field(min_length=1, description='bare contig as the callset spells it, '
                                                 'e.g. "15"; "chr15" is accepted too')
    pos: int = Field(ge=1, description="1-based VCF position")
    ref: str = Field(min_length=1, description="reference allele")
    alt: str = Field(min_length=1, description="alternate allele")

    def variant(self) -> Variant:
        """Convert to submission representation. The one legal place that adds ``chr``."""
        return Variant.from_vcf(self.chrom, self.pos, self.ref, self.alt)


class RowIn(BaseModel):
    """One hypothesis: a single allele, or a compound-heterozygous pair in ONE row."""

    variant_1: VariantIn
    variant_2: VariantIn | None = Field(
        default=None, description="the second allele of a pair; omit for a single")
    epcr: float = Field(description="estimated probability the row is causal, in (0, 1]")
    finding_type: str = Field(default="primary", description="primary or secondary")
    notes: str = Field(default="", description="free text; free points on qualitative review")


class BuildRequest(BaseModel):
    """The payload under construction, in the order it will appear in the file."""

    rows: list[RowIn] = Field(description="file order; must already be rank order")


def build(request: BuildRequest) -> dict:
    """Validate a payload, render it, and prove the rendering round-trips."""
    rows, warnings = _rows(request)
    found = warnings + [_problem(ERROR, message)
                        for message in submission.problems(rows, require_descending=True)]
    valid = not any(item["severity"] == ERROR for item in found)
    text = _csv(rows) if valid else ""
    return {
        "csv": text,
        "valid": valid,
        "problems": found,
        "self_test": _self_test(rows, text) if valid else None,
    }


def _rows(request: BuildRequest) -> tuple[list[submission.Row], list[dict]]:
    """Build the pipeline rows, warning about anything the scorer will quietly reshape."""
    rows: list[submission.Row] = []
    warnings: list[dict] = []

    for index, incoming in enumerate(request.rows, start=1):
        first = incoming.variant_1.variant()
        second = incoming.variant_2.variant() if incoming.variant_2 else None
        if second == first:
            warnings.append(_problem(WARNING, f"row {index}: variant 2 is the same allele as "
                                              "variant 1, so the scorer sees a single-variant "
                                              "row — it holds a set, not a list"))
            second = None
        rows.append(submission.Row(variant=first, partner=second, epcr=incoming.epcr,
                                   finding_type=incoming.finding_type, notes=incoming.notes))

    warnings.extend(_repeat_warnings(rows))
    return rows, warnings


def _repeat_warnings(rows: list[submission.Row]) -> list[dict]:
    """A row claiming an allele set an earlier row already claims spends a rank for nothing."""
    seen: dict[frozenset, int] = {}
    out = []
    for index, row in enumerate(rows, start=1):
        claim = row.variants()
        first = seen.setdefault(claim, index)
        if first != index:
            out.append(_problem(WARNING, f"row {index}: same allele set as row {first} — the "
                                         "scorer reports the better rank only, so this row "
                                         "spends one of ten slots on nothing"))
    return out


def _csv(rows: list[submission.Row]) -> str:
    """Render through the pipeline's own writer, so the header can only ever be its header."""
    buffer = StringIO()
    submission.write_submission(rows, buffer)
    return buffer.getvalue()


def _self_test(rows: list[submission.Row], text: str) -> dict:
    """Score the emitted bytes against a synthetic truth equal to row 1's own alleles.

    Not a claim about the biology — row 1 is *assumed* right here, which is exactly what
    makes the result a statement about the file rather than about the candidates. The pass
    condition is the maximum score the scorer can give (§9.3): full match at rank 1.
    """
    truth = rows[0].variants()
    parsed = submission.read_submission(StringIO(text))
    result = scorer.score(parsed, truth)
    return {
        "rank_points": result.rank_points,
        "f_max": result.f_max,
        "full_match_rank": result.full_match_rank,
        "passed": result.rank_points == 100.0 and result.f_max == 1.0,
    }


def _problem(severity: str, message: str) -> dict:
    return {"severity": severity, "message": message}


def router() -> APIRouter:
    """The one route. Registered in :mod:`mva.viz.app` beside the other routers."""
    api = APIRouter(prefix="/api")

    @api.post("/probe/build", response_model=Envelope, tags=["probe"],
              summary="validate and render a Track 1 submission CSV")
    def probe_build(request: BuildRequest) -> dict:
        """Build the submission CSV for a set of candidate rows, and check it round-trips.

        Contigs go **in** bare, the way ``/api/panel/annotations`` serves them, and come
        **out** ``chr``-prefixed, the way the template spells them. Nothing is written to
        disk and nothing is submitted: building a CSV spends none of the eighteen oracle
        submissions, and uploading the result to the HF Space spends exactly one.

        ``data`` is ``{csv, valid, problems, self_test}``. ``csv`` is empty and
        ``self_test`` is **null** whenever ``valid`` is false — a file that breaks a rule
        is not rendered, because the only thing anyone would do with it is upload it.
        ``problems`` carries ``error`` (blocks the file) and ``warning`` (the scorer will
        read the payload differently than it looks) entries; a malformed *body* is a 422
        from the schema instead, and never reaches these rules.
        """
        return live(build(request), SOURCE)

    return api
