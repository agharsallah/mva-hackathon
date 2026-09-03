"""The invented alleles the offline gene-structure fixture carries. **Never the proband's.**

The offline `/api/panel/gene-structure` payload needs a ``candidates[]`` list, and it must
not be a real one: a fixture is committed, browsed and screenshotted, and a patient allele
in it is a data-perimeter breach. So three are invented here, and marked unmistakably.

Its own module because it is the one part of ``tools/build_protein_fixture.py`` that is
pure and worth reading on its own — what is fabricated, why, and how a reader can tell.
Nothing here reads a file or calls anything but the shared label formatter.
"""

from . import genestructure

#: The three synthetic alleles, as *fractions* of the protein's length rather than fixed
#: offsets, so a 393-residue protein and a 2,537-residue one both get a readable lollipop
#: instead of three marks crowded into the first sixth of the axis.
#:
#: One HIGH truncating, one MODERATE missense, one LOW splice-region with no amino-acid
#: position at all — the last exists so the offline exhibit has to render the "placed
#: nowhere, and here is why" state, which is the state a real callset produces most often.
SYNTHETIC = (
    ("stop_gained", "HIGH", 0.70, True),
    ("missense_variant", "MODERATE", 0.95, True),
    ("splice_region_variant", "LOW", 0.0, False),
)


#: The identifier written into every synthetic allele's ``rsid``, ``n`` being its 1-based
#: index in :data:`SYNTHETIC`.
#:
#: Deliberately **not** ``rs``-shaped. The previous convention was ``rs00000000n``, which
#: is not an issued dbSNP accession but reads as one everywhere the label is rendered
#: verbatim — the lollipop tooltip, the distance table, the unplaced list — and only the
#: exhibit's ``source`` chip said otherwise. ``synthetic-n`` cannot be mistaken for a
#: dbSNP rsID by a reader or by a grep. See ``docs/step-0/methodology/063``.
SYNTHETIC_ID = "synthetic-{index}"


def candidates(protein_length: int | None, transcript: str | None) -> list[dict]:
    """Three invented alleles, scaled to this protein. **Never the proband's.**

    Marked unmistakably: every ``rsid`` is :data:`SYNTHETIC_ID` — ``synthetic-1`` and up,
    which is not the shape of a dbSNP accession at all — so the rendered label reads
    ``stop gained · synthetic-1`` and carries its own disclaimer. The registry's ``source``
    line also says SYNTHETIC. The consequences and the impact ladder are real vocabulary
    (VEP's terms) so the offline exhibit exercises the same colour and sort rules the live
    payload will.
    """
    out = []
    for index, (consequence, impact, fraction, placed) in enumerate(SYNTHETIC, start=1):
        position = max(1, round(protein_length * fraction)) if placed and protein_length else None
        identifier = SYNTHETIC_ID.format(index=index)
        out.append(
            {
                "consequence": consequence,
                "impact": impact,
                "rsid": identifier,
                "rare": placed,
                "clin_sig": None,
                "gt": "0/1",
                "filter": "PASS",
                "label": genestructure.label(consequence, identifier),
                "protein_pos": position,
                "reason": None
                if position is not None
                else (
                    f"VEP reports no amino-acid position for a {consequence} on "
                    f"{transcript or 'the canonical transcript'}"
                ),
            }
        )
    return out
