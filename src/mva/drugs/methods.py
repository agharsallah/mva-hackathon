"""How each enrichment table was built, in one sentence — the text the manifests print.

Split out of :mod:`mva.drugs.enrich` so the pipeline module stays under the repository's
400-line limit, and because this is a different kind of thing: prose a human reads in a
provenance manifest, not logic. One dictionary, keyed by table name, so the manifest, the
dashboard catalogue and the documentation cannot drift from each other.

A **method** here describes the *stage*, not the case. Nothing below names a gene, a
disease or a drug: the same sentences are true for the real card, a decoy card and a
transfer card (a different case entirely, :mod:`mva.drugs.transfer`). Where a stage
behaves differently on a card with no curated evidence, the sentence says so rather than
being rewritten per card.
"""

from __future__ import annotations

__all__ = ["METHODS"]

#: Methods, as the manifests print them. One place, so the manifest and the docs agree.
METHODS: dict[str, str] = {
    "drug_mechanism_literature": (
        "two PubMed questions per approved drug, derived from the card: the drug AND the "
        "mechanism (gene, protein, pathway head, disease anchor), and the drug AND the tumour "
        "context; hits is the PubMed record count, pmids a head of at most 10"
    ),
    "pediatric_trials": (
        "ClinicalTrials.gov v2, query.intr=<drug> with aggFilters=ages:child, first page of "
        "100, any indication; a study that admits children, not proof one enrolled any"
    ),
    "evidence_ladder": (
        "one row per (approved drug, direction): automated rung from approval, tumour-context "
        "trial and paediatric evidence (5 = approved AND context trial AND paediatric "
        "label-or-study; 4 = context trial; else 1), and — only where the card folder carries "
        "an evidence.tsv — a curated rung from it (a PMID read by a person, rung 2 cell / 3 in "
        "vivo); rung = max of the two, both printed. A card with no evidence.tsv is graded on "
        "the automated rungs alone and every curated_rung is empty, which is the honest "
        "reading for an uncurated card, not a zero. Flags name anti-directions (card "
        "moa_pattern), standard of care, curated-only and unverified approval"
    ),
    "shortlist": (
        "ladder rows at rung >= 2 that are neither standard of care nor anti-direction nor "
        "pathway-only, ranked: rung, molecule-level before proxy evidence, paediatric "
        "evidence, mechanism literature"
    ),
    "do_not": (
        "every ladder drug carrying an anti-direction flag (with the card's status for it) or "
        "the standard-of-care flag, once each"
    ),
    "decoy_comparison": (
        "per real direction and per decoy card: Jaccard between the approved drug sets (base "
        "names), the shared drugs, and the decoy's own automated flags; automated stages only"
    ),
    "evidence": (
        "curated by a person: one cited PubMed result per row, rung 2 (cell) or 3 (in vivo), "
        "proxy=true when the result is for a same-axis compound named in proxy_of; every PMID "
        "was resolved against PubMed E-utilities before the row was written"
    ),
}
