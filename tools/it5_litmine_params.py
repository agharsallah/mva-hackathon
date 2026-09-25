"""The case card for route R3 (iteration 5): every BUB1B-specific word the driver passes.

The modules under ``mva.drugs.litmine_*`` are case-agnostic; this file is the only place the
gene, its aliases, the topic words, the screen lexicons, the positive control and the
direction rules are written. Changing the case means writing a new file like this one.

No PMID is used to build a query. ``CONTROLS`` is read only by the verify stage, to *score*
retrieval and extraction after the fact.
"""

from __future__ import annotations

from mva.drugs.litmine_corpus import CorpusSpec
from mva.drugs.litmine_screen import Lexicon

__all__ = [
    "ANALOGUES",
    "BRANCH_BY_EFFECT",
    "CONTROLS",
    "DESIRED",
    "DIRECTNESS",
    "DISEASE_MARKERS",
    "EFFECT_ON",
    "EXPOSURE_LEXICON",
    "EXTRACTOR",
    "INTERVENTION_LEXICON",
    "SPEC",
]

SPEC = CorpusSpec(
    gene="BUB1B",
    aliases=("BubR1", "Bub1b", "BUBR1"),
    topics={
        "level": (
            "protein level",
            "protein levels",
            "protein abundance",
            "stability",
            "stabilization",
            "degradation",
            "half-life",
            "expression level",
        ),
        "modification": (
            "acetylation",
            "acetylated",
            "deacetylation",
            "ubiquitination",
            "ubiquitin",
            "ubiquitylation",
            "phosphorylation",
        ),
        "rescue": (
            "rescue",
            "rescued",
            "restore",
            "restored",
            "restores",
            "overexpression",
            "transgenic",
        ),
        "ageing": (
            "lifespan",
            "life span",
            "longevity",
            "senescence",
            "senescent",
            "progeroid",
            "ageing",
            "aging",
            "sarcopenia",
        ),
        "aneuploidy": ("aneuploidy", "aneuploid", "chromosomal instability"),
    },
    disease_phrases=("mosaic variegated aneuploidy",),
    max_records=1000,
)

INTERVENTION_LEXICON = Lexicon(
    name="interventions",
    subject=("bubr1", "bub1b"),
    effect=(
        "level",
        "abundance",
        "stabil",
        "degrad",
        "half-life",
        "acetyl",
        "ubiquitin",
        "lifespan",
        "life span",
        "longevity",
        "senescen",
        "aneuploid",
        "progeroid",
        "ageing",
        "aging",
        "sarcopenia",
        "muscle",
        "cataract",
        "lordokyphosis",
        "tumor",
        "tumour",
        "rescue",
        "restor",
        "delay",
        "extend",
        "attenuat",
        "prevent",
    ),
    cue=(
        "overexpress",
        "transgen",
        "knockout",
        "knock-out",
        "knockdown",
        "deletion",
        "deleted",
        "deficien",
        "inactivat",
        "ablat",
        "treat",
        "administ",
        "supplement",
        "inhibit",
        "activat",
        "clearance",
        "eliminat",
        "sirna",
        "shrna",
        "nad",
        "nmn",
        "nicotinamide",
        "drug",
        "compound",
        "sirt",
        "diet",
        "exercise",
        "rapamycin",
        "metformin",
    ),
)

EXPOSURE_LEXICON = Lexicon(
    name="exposures",
    subject=(
        "chemotherap",
        "vincristine",
        "actinomycin",
        "dactinomycin",
        "cyclophosphamide",
        "ifosfamide",
        "doxorubicin",
        "etoposide",
        "carboplatin",
        "cisplatin",
        "irinotecan",
        "radiotherap",
        "radiation",
        "irradiat",
        "regimen",
        "growth hormone",
        "transplant",
        "treated with",
        "treatment",
        "therapy",
        "drug",
        "GH ",
        "conditioning",
        "HSCT",
        "antimitotic",
        "taxol",
        "paclitaxel",
    ),
    effect=(
        "toxic",
        "tolerat",
        "neutropen",
        "myelosuppress",
        "pancytopen",
        "sepsis",
        "death",
        "died",
        "remission",
        "relapse",
        "respon",
        "adverse",
        "complication",
        "neuropath",
        "mucositis",
        "recurren",
        "surviv",
        "fatal",
        "sensitiv",
        "well",
        "success",
        "grade",
        "hepatotox",
        "veno-occlusive",
        "cardiotox",
        "infection",
        "outcome",
        "complete",
        "reduc",
        "dose",
        "ineffective",
        "benefit",
        "unsatisfactory",
        "did not change",
        "rejection",
        "avoid",
    ),
    cue=(
        "patient",
        "child",
        "boy",
        "girl",
        "proband",
        "case",
        "tumor",
        "tumour",
        "wilms",
        "rhabdomyosarcoma",
        "leukemia",
        "leukaemia",
        "sibling",
    ),
)

#: Scored after the fact, never used to build a query (see the entry's positive control).
#: pmid → the (effect_on, direction) pairs that state the paper's known finding.
CONTROLS: dict[str, list[tuple[str, str]]] = {
    "24825348": [("bubr1_level", "increase")],
    "18516091": [("senescence", "decrease"), ("other", "decrease")],
    "22048312": [("senescence", "decrease"), ("other", "decrease")],
}

#: The ``effect_on`` vocabulary of this case: what an extracted row is allowed to be about.
#: The quote gate rejects a row outside it, so a new category is a card change, not a guess.
EFFECT_ON: tuple[str, ...] = (
    "bubr1_level",
    "acetylation",
    "function",
    "aneuploidy",
    "senescence",
    "lifespan",
    "tumour",
    "other",
)

#: How directly each effect speaks to the amount of working protein (the rubric's second axis).
DIRECTNESS: dict[str, float] = {
    "bubr1_level": 1.0,
    "function": 0.9,
    "acetylation": 0.8,
    "aneuploidy": 0.8,
    "lifespan": 0.7,
    "senescence": 0.6,
    "tumour": 0.6,
    "other": 0.6,
}

#: For a hypomorphic (too-little-protein) gene, which direction of each effect is the goal.
#: ``other`` is left out too: a row whose effect the vocabulary cannot name has no agreed
#: good direction, so it is recorded and never turned into a candidate.
#: ``acetylation`` is left out on purpose: the corpus holds BubR1 acetylation sites whose
#: loss and gain both stabilise the protein, so its desired direction is not one word.
DESIRED: dict[str, str] = {
    "bubr1_level": "increase",
    "function": "increase",
    "aneuploidy": "decrease",
    "senescence": "decrease",
    "lifespan": "increase",
    "tumour": "decrease",
}

#: Which of the child's allele branches an effect can help (the stop allele makes no
#: protein to stabilise; an unstable missense protein can be kept longer; an inactive one
#: needs its activity raised; a downstream phenotype is allele-agnostic).
BRANCH_BY_EFFECT: dict[str, str] = {
    "bubr1_level": "missense_unstable",
    "acetylation": "missense_unstable",
    "function": "missense_inactive",
    "aneuploidy": "any",
    "senescence": "any",
    "lifespan": "any",
    "tumour": "any",
    "other": "any",
}

#: Genetic interventions whose target is not one protein (a cell population, a metabolite):
#: the drug class that performs the same act, and the act it performs. A *class* mapping,
#: stated here so the entry can show it, and scored lower than a gene → ChEMBL mapping.
ANALOGUES: dict[str, dict[str, object]] = {
    "p16Ink4a-positive senescent cells": {
        "act": "loss",
        "drugs": ["dasatinib", "quercetin", "navitoclax", "fisetin"],
        "class": "senolytic (kills senescent cells)",
    },
    "NAD+": {
        "act": "gain",
        "drugs": ["nicotinamide", "niacin", "nicotinamide riboside"],
        "class": "NAD+ precursor",
    },
    "protein deacetylases (HDAC)": {
        "act": "loss",
        "drugs": ["vorinostat", "romidepsin", "belinostat", "panobinostat", "valproic acid"],
        "class": "histone deacetylase inhibitor",
    },
    "26S proteasome": {
        "act": "loss",
        "drugs": ["bortezomib", "carfilzomib", "ixazomib"],
        "class": "proteasome inhibitor",
    },
    "BUB1B promoter methylation": {
        "act": "loss",
        "drugs": ["decitabine", "azacitidine"],
        "class": "hypomethylating agent (DNA methyltransferase inhibitor)",
    },
    "farnesyltransferase": {
        "act": "loss",
        "drugs": ["lonafarnib", "tipifarnib"],
        "class": "farnesyltransferase inhibitor",
    },
}

#: Text markers that make a paper a disease (MVA) paper for the exposure screen, beside the
#: disease phrases of ``SPEC``: the cytogenetic sign MVA is diagnosed by.
DISEASE_MARKERS = ("premature chromatid separation", "PCS syndrome", "MVA syndrome")

EXTRACTOR = {
    "model": "claude-opus-5-5",
    "role": "iteration-5 route R3 subagent",
    "date": "2026-09-25",
    "method": "read the screened sentences (build/it5/r3/reading/*.md) with their context "
    "and wrote each row by hand, copying the quote from the cached text",
}
