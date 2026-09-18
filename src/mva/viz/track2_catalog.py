"""What every column of every Track 2 table means, in plain English.

``ressources/track2/*.tsv`` are flat text files: a header line and tab-separated fields,
with lists joined by ``|`` and unknowns left empty. That is a fine wire format and a poor
explanation — ``max_phase``, ``st_id`` and ``action_type`` mean nothing to a reader who has
not worked with drug databases. This module is the dictionary the ``/api/track2`` catalogue
serves beside each table, so the page can label a column instead of showing its raw name.

Two conventions, both load-bearing.

**A type here is a parsing instruction, not a claim about the file.** Every field in a TSV
is text. ``"integer"``, ``"boolean"`` and ``"list"`` say how :mod:`mva.viz.track2_reader`
turns that text into JSON — ``int`` or ``None``, ``true``/``false`` or ``None``, split on
``|``. Keeping the rule in one table means the API and the page cannot disagree about
whether ``approved`` is a string.

**An empty field means unknown, and that is not the same as false.** ``fda_label`` empty is
"never checked"; ``approved`` false is a checked negative. The descriptions say so, because
a page that renders both as an empty cell has told the reader a falsehood.

The column *order* is not defined here: it is read from the header of the file on disk, so
a table that gains a column shows it (with a null description, visibly missing) rather than
silently dropping it. ``mva.drugs.tables`` owns the writer's order; this owns the meanings.
"""

from __future__ import annotations

from typing import Any

from .track2_catalog_step7 import COLUMNS_STEP7

#: ``table → column → (type, description)``. Types: ``string``, ``integer``, ``boolean``,
#: ``list`` — see the module docstring for what a type is and is not.
COLUMNS: dict[str, dict[str, tuple[str, str]]] = {
    "targets": {
        "symbol": ("string", "the gene, by its approved HGNC symbol — e.g. BUB1B, AURKB"),
        "role": (
            "string",
            (
                "'seed' when the mechanism card named this gene itself, 'pathway' when the "
                "Reactome expansion added it as a member of a matching pathway"
            ),
        ),
        "direction_ids": (
            "list",
            (
                "which of the card's repurposing directions (D1-D4) this gene serves; empty "
                "for a gene the pathway expansion added under no particular direction"
            ),
        ),
        "pathways": (
            "list",
            "the Reactome pathway ids (R-HSA-...) that put this gene in the target set",
        ),
        "uniprot": (
            "string",
            (
                "the UniProt accession of the protein the gene codes for — the stable id drug "
                "databases key their target records on"
            ),
        ),
    },
    "drug_candidates": {
        "drug_name": ("string", "the molecule, by its preferred name (upper case in ChEMBL)"),
        "drug_id": ("string", "its ChEMBL id — the stable key across all three drug sources"),
        "target_symbol": ("string", "the gene from targets.tsv this drug acts on"),
        "target_role": ("string", "that gene's role: 'seed' or 'pathway' — see targets.role"),
        "direction_ids": ("list", "the card directions the target serves (D1-D4)"),
        "source": (
            "list",
            (
                "which public sources reported this drug-target pair: opentargets, chembl, "
                "dgidb. Several means several agreed, which is corroboration, not a duplicate"
            ),
        ),
        "interaction_or_moa": (
            "string",
            (
                "how the drug acts on the target, in the source's own words — a ChEMBL "
                "mechanism of action, or a DGIdb interaction type"
            ),
        ),
        "action_type": (
            "string",
            "the direction of the effect: INHIBITOR, AGONIST, ANTAGONIST, and so on",
        ),
        "max_phase": (
            "integer",
            (
                "the furthest clinical trial phase this molecule has reached, 1-4; 4 means "
                "market-approved. Empty when no source stated one"
            ),
        ),
        "approved": (
            "boolean",
            (
                "market-approved somewhere: ChEMBL max_phase 4, or an Open Targets clinical "
                "stage of APPROVAL, or DGIdb's own approved flag. This is the Track 2 filter"
            ),
        ),
        "fda_label": (
            "string",
            (
                "the openFDA label id, when one was found. **Empty means not checked** — only "
                "approved drugs were queried — which is not the same as 'no label exists'"
            ),
        ),
        "pmids": ("list", "PubMed ids the source cited for this drug-target pair"),
        "first_approval": ("integer", "the year the drug was first approved, per ChEMBL"),
        "atc": (
            "list",
            (
                "ATC codes — the WHO's therapeutic classification of the drug, e.g. L01 for "
                "antineoplastics; useful for grouping candidates by what they are normally for"
            ),
        ),
    },
    "trials": {
        "nct_id": (
            "string",
            "the ClinicalTrials.gov registration id (NCT...), the primary key of a study",
        ),
        "title": ("string", "the study's brief title as registered"),
        "phase": ("string", "PHASE1..PHASE4, or NA for a study with no phase (observational)"),
        "overall_status": (
            "string",
            "recruitment state as registered: RECRUITING, COMPLETED, TERMINATED, ...",
        ),
        "conditions": ("list", "the diseases the study enrols for"),
        "interventions": ("list", "what the study administers — drugs, procedures, devices"),
        "start_date": ("string", "when the study started, as registered (often year-month only)"),
        "study_type": ("string", "INTERVENTIONAL (a trial) or OBSERVATIONAL (a cohort study)"),
        "query": (
            "string",
            (
                "which snapshot query returned this study — the disease query, or a "
                "per-drug query against the tumour context. Lets a disease hit be told from a "
                "drug hit without re-running anything"
            ),
        ),
    },
    "literature": {
        "pmid": ("string", "the PubMed id — the stable citation key for a paper"),
        "title": ("string", "the paper's title"),
        "journal": ("string", "the journal it appeared in"),
        "year": ("integer", "publication year"),
        "doi": ("string", "the DOI, when PubMed states one"),
        "query": (
            "string",
            (
                "which of the four query families found this paper: the gene family, the "
                "pathway family, one direction's family, or the card's own citations"
            ),
        ),
    },
    "pathways": {
        "st_id": ("string", "the Reactome pathway id (R-HSA-...)"),
        "display_name": ("string", "the pathway's name as Reactome states it"),
        "matched": (
            "boolean",
            (
                "true when the name matched the expansion pattern "
                "(checkpoint|kinetochore|mitotic) and its members were therefore pulled in as "
                "targets; false when the pathway contains the gene but was not expanded"
            ),
        ),
        "n_participants": (
            "integer",
            (
                "how many human gene products the expansion took from this pathway; 0 for an "
                "unmatched pathway"
            ),
        ),
    },
}

COLUMNS.update(COLUMNS_STEP7)


def describe(table: str, header: list[str]) -> list[dict[str, Any]]:
    """One ``{name, type, description}`` per column of a table, in the file's own order.

    A column the dictionary does not know gets ``type`` ``"string"`` and a **null**
    description, which the page renders as a visible gap. Guessing a meaning from a column
    name would be the one failure mode this module exists to prevent.
    """
    known = COLUMNS.get(table, {})
    rows = []
    for name in header:
        kind, description = known.get(name, ("string", ""))
        rows.append({"name": name, "type": kind, "description": description or None})
    return rows


def column_type(table: str, name: str) -> str:
    """How to parse one column's text, defaulting to ``string`` for an unknown column."""
    return COLUMNS.get(table, {}).get(name, ("string", ""))[0]
