"""The wording every R1 manifest carries: assumptions, limits, column notes, the rubric.

A provenance manifest is only useful if it says, in words, what was assumed, what the numbers
cannot support, and what each column means. Keeping that prose here rather than inline in the
driver means the three tables of this route say the same thing in the same words, and a review
of the wording is a review of one file.

Separate from :mod:`mva.drugs.readthrough_case` (which holds the *numbers* and their PMIDs)
only because both together exceed the repository's module-size limit.
"""

from __future__ import annotations

__all__ = [
    "CANDIDATE_ASSUMPTIONS",
    "CANDIDATE_COLUMN_NOTES",
    "CANDIDATE_LIMITATIONS",
    "DOSAGE_ASSUMPTIONS",
    "DOSAGE_COLUMN_NOTES",
    "DOSAGE_LIMITATIONS",
    "DOSAGE_VALIDATION",
    "READTHROUGH_ASSUMPTIONS",
    "READTHROUGH_COLUMN_NOTES",
    "READTHROUGH_LIMITATIONS",
    "SOURCES",
    "STRENGTH_RUBRIC",
]


SOURCES = {
    "genomic": (
        "the child's own callset, read only as: gene, consequence class, and the coding-sequence "
        "offset of the stop, which is used inside build/ to derive the codon and its context. "
        "No genomic position appears in any row"
    ),
    "clinical": (
        "the proband's 8 HPO terms (Challenge_Clinical_Phenotype_1.md), used to decide which "
        "adverse-effect axes disqualify a candidate: nephrocalcinosis HP:0000121 against "
        "aminoglycoside tubular nephrotoxicity, failure to thrive HP:0001508 and short stature "
        "HP:0004322 against chronic parenteral dosing, rhabdomyosarcoma HP:0002859 against "
        "agents whose class is cytotoxic or which stabilise oncogenic nonsense transcripts"
    ),
    "public": (
        "Ensembl REST release 116 (gene model, coding sequence), UniProt O60566 (domains), "
        "Toledano et al. Nat Genet 2024 PMID 39174735 supplementary table 3 (measured "
        "readthrough), and the BubR1 dosage literature cited per row"
    ),
}

STRENGTH_RUBRIC = {
    "0.8": (
        "measured in a living BubR1-deficient animal or in human MVA patient cells for this exact "
        "lever"
    ),
    "0.6": (
        "model prediction for this child's exact stop context from a measured dataset whose "
        "declared positive control passed on both held-out sets"
    ),
    "0.4": (
        "measured for this gene or protein but not for this allele, or a clinical-grade fact about "
        "the agent that bears on use"
    ),
    "0.3": (
        "model prediction for this stop context whose positive control failed or was mixed: not "
        "interpretable as a number"
    ),
    "0.2": "mechanism-level rationale only, with no measurement in this gene",
    "0.0": "ruled out: regulatorily withdrawn, or predicted to act in the harmful direction",
}

READTHROUGH_ASSUMPTIONS = (
    "readthrough measured in a HEK293T fluorescent reporter, with 144 nt of native context "
    "around the stop, transfers to the same stop in its own gene in the child's tissues; the "
    "stop codon, its +4 base and its -1 base capture the part of the context that generalises"
)

READTHROUGH_LIMITATIONS = (
    "one cell line, one assay, one concentration per compound; 431 of 52,062 values are "
    "censored at the assay ceiling and are read as their lower bound, so the means are lower "
    "bounds; the untreated column sits at the assay floor (~0.18 %), so any prediction near it "
    "is noise rather than a small effect; reporter readthrough is not functional protein "
    "rescue, which also needs the message to survive NMD and the near-cognate amino acid to be "
    "tolerated at that position; nothing has been measured in this child"
)

READTHROUGH_COLUMN_NOTES = {
    "predicted_readthrough": "percent of the no-PTC control, the unit the source dataset reports",
    "evidence_level": "which backoff level answered: stop+4-1, stop+4, stop, or drug",
    "rows_behind_it": (
        "measured contexts in that cell of the full fit (the control refits without the panel)"
    ),
    "control_passed": (
        "the declared benchmark-panel control for this drug; false means the row is not "
        "interpretable as a number"
    ),
    "contexts_behind_it": (
        "up to six example PTC contexts from the cell, so a reader can spot-check the group"
    ),
}

DOSAGE_ASSUMPTIONS = (
    "BubR1 function is proportional to the amount of working protein, and the two alleles add; "
    "a missense allele that is merely unstable has normal specific activity once present, which "
    "is what forced overexpression of I909T and L1012P showed (PMID 20516114); the readthrough "
    "product is half as good as wild type, which is a stated guess and not a measurement"
)

DOSAGE_LIMITATIONS = (
    "the child's own BubR1 protein level has never been measured, so every scenario is an "
    "arithmetic over other people's alleles; PMID 31738183 is a direct caution against the "
    "model's own premise - H/H and H/L1002P mice carry indistinguishable total BubR1 yet differ "
    "by 147 days of median lifespan, so total level is not a sufficient predictor of phenotype; "
    "the two branches (unstable vs inactive) are not decided by any measurement in this case"
)

DOSAGE_VALIDATION = (
    "the untreated scenarios are checked against published genotypes rather than asserted: the "
    "base case lands between the mouse H/H level (~10 %) and the upper lip of the human "
    "segregation-fidelity cliff (~13 %), which is where a viable MVA child should land"
)

DOSAGE_COLUMN_NOTES = {
    "total_pct_of_wild_type": "percent of the wild-type diploid amount of working BubR1",
    "gain_pct_points": (
        "percentage points this scenario's drug adds over the same scenario untreated"
    ),
    "nearest_published_genotype": (
        "the published genotype whose measured level is closest, as a yardstick only"
    ),
}

CANDIDATE_ASSUMPTIONS = (
    "a route is only as good as its positive control; a drug whose control failed is listed so "
    "that the failure is on the record, with evidence_strength at the rubric's 0.3 band"
)

CANDIDATE_LIMITATIONS = (
    "no readthrough or NMD-modulating agent has ever been tested in BUB1B/MVA, in a patient or "
    "in an animal model; every row is extrapolation from other nonsense-mutation diseases, and "
    "the notes say which"
)

CANDIDATE_COLUMN_NOTES = {
    "branch": (
        "which allele or allele-state the row acts on: stop_allele, missense_unstable, "
        "missense_inactive, any"
    ),
    "evidence_kind": "what kind of evidence stands behind the row, from the rubric in the entry",
    "evidence_strength": "the rubric band in [0, 1]; a triage aid, not a probability",
    "positive_control_passed": (
        "true/false for a row whose number came from this route's model; n/a for a literature "
        "statement"
    ),
}
