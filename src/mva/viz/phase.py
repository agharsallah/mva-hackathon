"""Turning one gene's heterozygous alleles into the compound-het pair matrix.

``results.panel_het_pairs`` stores the *members* of the grid, one row per heterozygous
ALT allele (see :mod:`mva.warehouse.analysis_pairs` for why the pairs themselves are not
stored). This module does the cross product and labels each cell.

**The phase rule is not re-implemented here.** It is owned by
:func:`mva.pipeline.compound_het.classify_phase`, and this module adapts a warehouse row
into the :class:`~mva.pipeline.vcf.Call` that function already takes. A second copy of
"same PID, same PGT means cis" is exactly the drift the repo's one-owner rule forbids.

Only the **resolved** cells travel over HTTP. Physical phasing reaches ~300 bp, so on a
real gene it resolves single digits out of thousands of pairs — sending ``n(n-1)/2``
"unknown" objects would be sending the same word ten thousand times. The payload carries
every variant, the handful of resolved pairs, and the counts; the client fills the rest
of the grid with the honest default, which is *unknown*.
"""

from itertools import combinations

from ..pipeline.compound_het import Phase, classify_phase
from ..pipeline.variant import Variant
from ..pipeline.vcf import Call

#: The columns of ``panel_het_pairs`` the pair classifier reads. Anything else in the row
#: is display, not evidence.
PHASE_FIELDS = ("chrom", "pos", "ref", "alt", "allele_ix", "gt", "pgt", "pid")


def as_call(row: dict) -> Call:
    """Adapt one ``panel_het_pairs`` row into the Call the phase rule takes.

    Depths are left null on purpose: :func:`classify_phase` reads position, ALT allele,
    ``PID`` and ``PGT`` and nothing else, so filling the rest would invent fields that no
    decision depends on.
    """
    return Call(
        variant=Variant.from_vcf(row["chrom"], int(row["pos"]), row["ref"], row["alt"]),
        genotype=row.get("gt") or "./.",
        filters=("PASS",),
        depth=None,
        ref_depth=None,
        alt_depth=None,
        phase_set=row.get("pid") or None,
        phase_gt=row.get("pgt") or None,
        _allele_index=int(row.get("allele_ix") or 1),
    )


def is_auto_trans(left: dict, right: dict) -> bool:
    """True for the pair a ``1/2`` genotype resolves on its own.

    One copy of each of two different ALT alleles at one site means one per haplotype —
    compound heterozygosity stated by the genotype, with no phasing involved. It is worth
    naming separately from a PGT-resolved trans pair because it is a different kind of
    evidence and the matrix colours it differently.
    """
    return left["pos"] == right["pos"] and left["alt"] != right["alt"]


def classify(left: dict, right: dict) -> str:
    """Phase of one pair of het alleles, as ``"cis"``, ``"trans"`` or ``"unknown"``."""
    return classify_phase(as_call(left), as_call(right)).value


def resolved(variants: list[dict]) -> list[dict]:
    """Every pair the callset actually resolves, as indices into ``variants``.

    ``i`` and ``j`` are positions in the given order (the endpoint orders by position),
    which is the order the matrix axes use, so a cell is addressed without repeating the
    coordinates that must never leave the server twice.
    """
    calls = [as_call(row) for row in variants]
    out = []
    for i, j in combinations(range(len(variants)), 2):
        phase = classify_phase(calls[i], calls[j])
        if phase is Phase.UNKNOWN:
            continue
        out.append({"i": i, "j": j, "phase": phase.value,
                    "auto": is_auto_trans(variants[i], variants[j])})
    return out


def summarise(n_variants: int, pairs: list[dict]) -> dict:
    """Counts for the exhibit's honesty line: how little of the grid is resolved."""
    total = n_variants * (n_variants - 1) // 2
    trans = [p for p in pairs if p["phase"] == "trans"]
    return {
        "n_het": n_variants,
        "n_pairs": total,
        "n_trans": len(trans),
        "n_auto_trans": len([p for p in trans if p["auto"]]),
        "n_cis": len([p for p in pairs if p["phase"] == "cis"]),
        "n_unknown": total - len(pairs),
        "pct_unknown": round(100.0 * (total - len(pairs)) / total, 2) if total else None,
    }


def matrix(gene: str, variants: list[dict]) -> dict:
    """The whole payload for one gene: the axis, the resolved cells, and the counts."""
    pairs = resolved(variants)
    return {"gene": gene, "variants": variants, "pairs": pairs,
            "summary": summarise(len(variants), pairs)}
