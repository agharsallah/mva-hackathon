"""Decoding the colon-packed genotype pair the warehouse stores per variant.

``variants_raw`` keeps a VCF record's last two columns verbatim: ``format`` is the key
order (always ``GT:AD:DP:GQ:PL`` in this callset) and ``sample_call`` the values packed
in that order. It is a self-describing row format — the header travels with every row —
so the decoder must read the keys rather than assume positions.

The awkward case is real and appears 66,860 times: a ``1/2`` site has two different ALT
alleles in one record, so ``AD`` carries **three** depths (ref, alt1, alt2) and "the"
alternate depth is not a single number. Rather than pick one and produce a plausible
wrong allele fraction, this module reports ``ad_alt`` and ``vaf`` as null there. A blank
in a chart is a question; a silently halved VAF is a wrong answer.
"""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Genotype:
    """The genotype evidence for one variant row, ready for JSON."""

    gt: str | None
    dp: int | None
    ad_ref: int | None
    ad_alt: int | None
    vaf: float | None
    gq: int | None

    def as_dict(self) -> dict:
        return asdict(self)


def decode(format_keys: str | None, sample_call: str | None) -> Genotype:
    """Decode one ``(format, sample_call)`` pair.

    Tolerant by design: a missing field, a ``.`` placeholder or a truncated call yields
    nulls for what is absent instead of raising. These rows come from a five-million-row
    text table, and one malformed record must not fail a whole locus request.
    """
    keys = (format_keys or "").split(":")
    values = (sample_call or "").split(":")
    # A truncated call is tolerated by design (see module docstring): fewer values than
    # keys just means the trailing fields decode to missing, not a raised error.
    fields = dict(zip(keys, values, strict=False))

    depths = _depths(fields.get("AD"))
    # Two depths means one unambiguous ALT; anything else (a 1/2 site, a truncated AD)
    # leaves no single alternate allele to attribute reads to.
    ad_ref, ad_alt = (
        [*depths, None, None][:2] if len(depths) == 2 else ((depths[0] if depths else None), None)
    )

    total = (ad_ref or 0) + (ad_alt or 0)
    return Genotype(
        gt=fields.get("GT") or None,
        dp=_int(fields.get("DP")),
        ad_ref=ad_ref,
        ad_alt=ad_alt,
        # Denominator is ref+alt, not DP: DP includes reads supporting neither allele,
        # which would depress the fraction the allele-balance check reads.
        vaf=round(ad_alt / total, 4) if ad_alt is not None and total else None,
        gq=_int(fields.get("GQ")),
    )


def _int(value: str | None) -> int | None:
    return int(value) if value and value.lstrip("-").isdigit() else None


def _depths(value: str | None) -> list[int]:
    """``AD`` as a list of integers; a non-numeric entry becomes 0, as in the pipeline."""
    if not value or value == ".":
        return []
    return [int(part) if part.isdigit() else 0 for part in value.split(",")]
