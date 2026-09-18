"""Decoy mechanism cards: the same child, a different gene.

Track 2's rigor rests on qualitative evidence rungs while Track 1 gets permutation nulls, and
that asymmetry was flagged in the iteration-2 plan (§10, gap N3). The control this module
supplies is the cheapest honest one: **hold the clinical side fixed and swap the genomic
answer.** A decoy card keeps the disease, the tumour context and the clinical terms of the real
card, replaces the gene with one that is *not* the answer, and names a single direction — the
decoy gene and its own Reactome neighbourhood. The same ``mva-drugs snapshot`` then runs on it
unchanged.

What the comparison can show: which drug classes the automated stages nominate *whatever the
gene is*. A direction whose approved drugs appear for a decoy as readily as for the real gene
is non-specific, and the report says so rather than counting it as support.

What it cannot show: that the real card's *curated* rungs are right — a decoy gets no hand-read
literature, so only the automated stages (approval, label, trials, mechanism-literature counts)
are comparable. The comparison table prints that boundary.

Two decoys are the pre-registered minimum: one drawn by a stated rule from the step-2 decoy set
(a gene chosen to be *like* the targets in size and structure but not phenotype-linked), and one
deliberately unrelated, well-drugged metabolic enzyme.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from .mechanism import MechanismCard

__all__ = ["DecoySpec", "decoy_card"]


class DecoySpec:
    """What a decoy is made of: the gene, how it was picked, and how its pathways are matched."""

    def __init__(
        self,
        symbol: str,
        uniprot: str,
        protein: str,
        pathway_pattern: str,
        picked_by: str,
        *,
        ensembl_gene_id: str | None = None,
    ) -> None:
        self.symbol = symbol
        self.uniprot = uniprot
        self.protein = protein
        self.pathway_pattern = pathway_pattern
        self.picked_by = picked_by
        self.ensembl_gene_id = ensembl_gene_id


def decoy_card(
    template: MechanismCard, spec: DecoySpec, *, today: str | None = None
) -> dict[str, Any]:
    """A card for ``spec``'s gene that keeps the template's clinical side verbatim.

    The gene block, the alleles, the mechanism and the directions are replaced; ``case`` and
    ``constraints`` are copied, because the child is the same child. The result carries a
    ``decoy`` block naming what it is a control for and how the gene was chosen, so the card
    can never be mistaken for a finding.
    """
    date = today or datetime.now(tz=UTC).date().isoformat()
    raw = template.raw
    card: dict[str, Any] = {
        "_standing": (
            f"DECOY CARD - a pipeline control, not a finding. Same clinical side as the "
            f"{template.gene_symbol} card version {template.version}; gene replaced by "
            f"{spec.symbol} ({spec.picked_by}). Written {date}."
        ),
        "version": 1,
        "decoy": {
            "control_for": template.gene_symbol,
            "template_card_version": template.version,
            "picked_by": spec.picked_by,
            "pathway_pattern": spec.pathway_pattern,
            "comparable": (
                "automated stages only: approval, label, trial activity, mechanism-literature "
                "counts. Curated rungs are read by a person and exist for the real card alone."
            ),
        },
        "case": copy.deepcopy(raw.get("case", {})),
        "gene": {
            "symbol": spec.symbol,
            "ensembl_gene_id": spec.ensembl_gene_id,
            "uniprot": spec.uniprot,
            "protein": spec.protein,
        },
        "alleles": [],
        "mechanism": {
            "class": "none claimed - decoy",
            "status": "control: no variant in this gene is asserted for the proband",
            "pathway": (
                f"Reactome pathways containing {spec.uniprot} whose name matches "
                f"/{spec.pathway_pattern}/i"
            ),
            "downstream": [],
            "literature": [],
        },
        "repurposing_directions": [
            {
                "id": "D1",
                "name": f"{spec.symbol} and its pathway neighbours",
                "rationale": (
                    "the decoy's only direction: whatever the automated stages return for this "
                    "gene and the pathways it sits in, with the clinical queries held fixed"
                ),
                "seed_targets": [spec.symbol],
            }
        ],
        "constraints": copy.deepcopy(raw.get("constraints", {})),
        "history": [{"version": 1, "date": date, "change": f"decoy card for {spec.symbol}"}],
    }
    return card
