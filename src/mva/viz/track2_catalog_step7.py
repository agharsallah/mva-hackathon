"""What every column of the step-7 enrichment tables means, in plain English.

The second half of :mod:`mva.viz.track2_catalog`: the same ``table → column → (type,
description)`` shape, for the seven tables ``tools/track2_enrich.py`` writes beside the
snapshot's five. Kept apart only for size; :data:`mva.viz.track2_catalog.COLUMNS` merges it.

The one convention worth stating twice: a **rung** is a claim about the *best test the drug
passed*, not a score. Two drugs on rung 2 are not equally good; a reader needs the
``curated_pmids`` and the ``proxy`` flag beside the rung to tell them apart, and the
descriptions below say so.
"""

from __future__ import annotations

_RUNG = (
    "the evidence-ladder rung, 1-5: 5 approved for a related indication with paediatric "
    "use, 4 clinical trial in a related indication, 3 in-vivo model, 2 cell model, 1 "
    "mechanism only (named, never submitted). The highest test the drug passed - not a score"
)

COLUMNS_STEP7: dict[str, dict[str, tuple[str, str]]] = {
    "evidence": {
        "drug_name": ("string", "the approved drug the cited result is attached to (base name)"),
        "direction_id": ("string", "which repurposing direction (D1-D4) the result speaks to"),
        "rung": ("integer", _RUNG),
        "model": ("string", "'cell' or 'in vivo': what kind of experiment the paper reports"),
        "pmid": ("string", "the PubMed id of the paper, resolved against E-utilities"),
        "target": ("string", "the gene the drug acts on for this direction"),
        "claim": ("string", "what the paper showed, in one sentence written by a person"),
        "proxy": (
            "boolean",
            (
                "true when the cited result is for a same-axis compound rather than this "
                "drug - the evidence is inherited, and the report says so"
            ),
        ),
        "proxy_of": ("string", "the compound actually tested when proxy is true"),
    },
    "drug_mechanism_literature": {
        "drug_name": ("string", "the approved drug, folded to its base name"),
        "family": (
            "string",
            "'mechanism' (drug AND gene/protein/pathway/disease) or 'context' (drug AND tumour)",
        ),
        "term": ("string", "the PubMed query exactly as sent"),
        "hits": ("integer", "how many PubMed records match; descriptive, never a rung"),
        "pmids": ("list", "a head of at most 10 matching PubMed ids, so the count can be opened"),
    },
    "pediatric_trials": {
        "drug_name": ("string", "the approved drug asked about"),
        "nct_id": ("string", "the ClinicalTrials.gov study id"),
        "title": ("string", "the study's brief title"),
        "phase": ("list", "the registered phase(s)"),
        "overall_status": ("string", "the registry's status word"),
        "conditions": ("list", "what the study treats - any indication, not only this one"),
        "min_age": ("string", "the minimum age the registry states, verbatim"),
        "max_age": ("string", "the maximum age the registry states, verbatim"),
        "std_ages": ("list", "the registry's age groups; CHILD is what the filter asked for"),
        "query": ("string", "the query that found the study"),
    },
    "evidence_ladder": {
        "drug_name": ("string", "the approved (or curated) drug, base name"),
        "direction_id": (
            "string",
            "D1-D4, or 'pathway' for a drug attached only through pathway-expansion targets",
        ),
        "rung": ("integer", _RUNG),
        "rung_label": ("string", "the rung's wording from the card"),
        "automated_rung": (
            "integer",
            (
                "the rung from approval, tumour-context trial and paediatric evidence alone - "
                "what a decoy card would also get"
            ),
        ),
        "curated_rung": (
            "integer",
            "the rung from evidence.tsv (a PMID read by a person), or empty",
        ),
        "approved": (
            "boolean",
            "market-approved by ChEMBL phase 4, Open Targets or DGIdb, or an FDA label",
        ),
        "fda_label": ("boolean", "a current US label exists"),
        "pediatric_label": ("boolean", "that label has a section 8.4 Pediatric Use"),
        "trial_in_context": ("boolean", "a registered study of the drug in the tumour context"),
        "pediatric_trial": (
            "boolean",
            "a registered study of the drug that admits children, any indication",
        ),
        "mechanism_hits": ("integer", "PubMed records for the drug AND the mechanism"),
        "context_hits": ("integer", "PubMed records for the drug AND the tumour context"),
        "curated_pmids": ("list", "the PubMed ids behind the curated rung"),
        "proxy": ("boolean", "true when every curated result is for a same-axis compound"),
        "targets": ("list", "the genes the drug attaches to in the target set"),
        "action_types": ("list", "the sources' action types for those attachments"),
        "flags": (
            "list",
            (
                "A1/A2 an anti-direction (the card's moa_pattern matched); standard_of_care; "
                "curated_only (no source drugs a target for it); approval_unverified"
            ),
        ),
    },
    "shortlist": {
        "rank": ("integer", "position in the shortlist; empty in the do-not table"),
        "drug_name": ("string", "the drug"),
        "direction_id": ("string", "the direction it is argued under"),
        "rung": ("integer", _RUNG),
        "verdict": (
            "string",
            (
                "'argue' for the shortlist; 'do not', 'caution' or 'standard of care' for the "
                "other table"
            ),
        ),
        "why": ("string", "the ordering reasons or the exclusion reason, in words"),
        "pediatric_evidence": (
            "string",
            "label section 8.4, a study admitting children, or 'none found'",
        ),
        "curated_pmids": ("list", "the PubMed ids behind the rung"),
        "targets": ("list", "the genes the drug attaches to"),
        "flags": ("list", "as in evidence_ladder"),
    },
    "decoy_comparison": {
        "decoy": ("string", "the decoy gene whose card the same pipeline ran on"),
        "direction_id": ("string", "one of the real card's directions, or 'all'"),
        "direction_approved": (
            "integer",
            "approved drugs (base names) the real direction returned",
        ),
        "decoy_approved": ("integer", "approved drugs the decoy card returned"),
        "shared": ("integer", "drugs in both sets"),
        "jaccard": (
            "string",
            "shared / union; the pre-registered non-specificity threshold is 0.10",
        ),
        "shared_drugs": ("list", "the drugs in both sets, so the overlap can be read"),
        "decoy_with_context_trial": (
            "integer",
            "decoy drugs with a tumour-context trial - the gene-independent part",
        ),
        "decoy_with_fda_label": ("integer", "decoy drugs with a US label"),
    },
}
COLUMNS_STEP7["do_not"] = COLUMNS_STEP7["shortlist"]

#: The cross-case comparison: one row per case, not per drug. It answers "does this
#: pipeline run on a case it was not written for", so every column is a count of what the
#: same code produced, and ``curated_rows`` is the boundary of what may be compared.
COLUMNS_STEP7["transfer_comparison"] = {
    "case": ("string", "which case the row is about, by gene and disease"),
    "role": (
        "string",
        "'real case' (the proband's card) or 'transfer case' (a second case, public data only)",
    ),
    "gene": ("string", "the gene the card names"),
    "disease": ("string", "the disease the card names, as the search query was derived from it"),
    "tumour_context": ("string", "the reported malignancy the trial queries used"),
    "card_version": ("integer", "the version of the mechanism card the run read"),
    "targets": ("integer", "genes in the target set: the card's seeds plus pathway expansion"),
    "candidate_rows": ("integer", "rows in drug_candidates.tsv - one per (drug, target)"),
    "approved_drugs": ("integer", "distinct market-approved drugs, folded to base names"),
    "drugs_rung_5": ("integer", "drugs whose best rung is 5 (approved, context trial, paediatric)"),
    "drugs_rung_4": ("integer", "drugs whose best rung is 4 (a registered trial in the tumour)"),
    "drugs_rung_3": (
        "integer",
        "drugs whose best rung is 3 (an in-vivo result) - curated, so always 0 for a transfer card",
    ),
    "drugs_rung_2": (
        "integer",
        "drugs whose best rung is 2 (a cell result) - curated, so always 0 for a transfer card",
    ),
    "drugs_rung_1": ("integer", "drugs at rung 1: named by the mechanism and nothing more"),
    "shortlist": ("integer", "rows in shortlist.tsv"),
    "do_not": ("integer", "rows in do_not.tsv: anti-direction or standard-of-care drugs"),
    "curated_rows": (
        "integer",
        (
            "rows in evidence.tsv - hand-read literature. 0 for a transfer card by "
            "construction, which is why only the automated rungs are comparable"
        ),
    ),
    "live_requests": ("integer", "HTTP requests that reached a public API, snapshot + enrichment"),
    "cached_replies": ("integer", "replies served from the on-disk cache: replies minus live"),
    "wall_seconds": (
        "string",
        (
            "measured wall clock of the pass this table was written from; empty for a case "
            "this run did not execute"
        ),
    ),
}
