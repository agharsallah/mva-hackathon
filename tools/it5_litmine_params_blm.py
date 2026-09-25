"""The R3 case card for the **transfer** case: Bloom syndrome (`BLM`).

Same contract as :mod:`it5_litmine_params` (the BUB1B card) and the only new file route R3's
transfer needed. The modules under ``mva.drugs.litmine_*`` and the driver
``tools/it5_litmine.py`` are shared; this file holds every BLM-specific word.

Two things are reused rather than rewritten, and both are stated here so a reader can argue:

* ``EXPOSURE_LEXICON`` is the BUB1B card's lexicon with three cancer words added. The
  vocabulary of "what was this child given and what happened" is oncological, not
  gene-specific, so it transfers as-is; only the tumour names change.
* ``ANALOGUES`` is a *class* mapping, the same device the BUB1B card uses, and it is small
  here because Bloom syndrome has very few reported interventions that act on BLM at all.

**A known weakness of this case, declared:** `BLM` is an ambiguous token. It is also the
common abbreviation for the drug bleomycin and appears in unrelated senses. The corpus query
therefore adds the unambiguous aliases, and the two later stages — the lexical screen (a
sentence must name the subject *and* an effect *and* a cue) and the verbatim quote gate —
are what keep a wrong-sense paper out of the tables. Precision is not assumed; it is measured
by the rejected table and by the positive control.

No PMID is used to build a query. ``CONTROLS`` is read only by the verify stage, to *score*
retrieval and extraction after the fact.
"""

from __future__ import annotations

from dataclasses import replace

from it5_litmine_params import EXPOSURE_LEXICON as BUB1B_EXPOSURE_LEXICON
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
    gene="BLM",
    aliases=("RECQL3", "RECQ2", "BLM helicase", "Bloom helicase"),
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
            "phosphorylation",
            "ubiquitination",
            "ubiquitylation",
            "sumoylation",
            "acetylation",
        ),
        "rescue": (
            "rescue",
            "rescued",
            "restore",
            "restored",
            "restores",
            "complementation",
            "overexpression",
            "transgenic",
        ),
        "function": (
            "helicase activity",
            "unwinding",
            "ATPase",
            "double Holliday junction",
            "dissolution",
            "resolvase",
        ),
        "instability": (
            "sister chromatid exchange",
            "sister chromatid exchanges",
            "genome instability",
            "genomic instability",
            "chromosomal instability",
            "micronuclei",
        ),
        # Narrowed on purpose: the generic ("inhibitor" OR "inhibition") form returns 1,297
        # records, above Europe PMC's 1,000-record page, and a truncated query is a silent
        # recall loss. This form returns 512 and is reported un-truncated.
        "perturbation": (
            "knockdown",
            "knockout",
            "depletion",
            "silencing",
            "small molecule inhibitor",
            "ML216",
        ),
    },
    disease_phrases=("bloom syndrome", "bloom's syndrome"),
    max_records=1000,
)

INTERVENTION_LEXICON = Lexicon(
    name="interventions",
    subject=("blm", "recql3", "bloom syndrome", "bloom's syndrome"),
    effect=(
        "level",
        "abundance",
        "stabil",
        "degrad",
        "half-life",
        "ubiquitin",
        "sumoyl",
        "phosphoryl",
        "helicase activity",
        "unwind",
        "atpase",
        "sister chromatid exchange",
        "genome instability",
        "genomic instability",
        "chromosomal instability",
        "micronucle",
        "quadriradial",
        "cancer",
        "tumor",
        "tumour",
        "growth",
        "lifespan",
        "surviv",
        "rescue",
        "restor",
        "correct",
        "reduc",
        "prevent",
        "sensiti",
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
        "complement",
        "cdna",
        "treat",
        "administ",
        "supplement",
        "inhibit",
        "activat",
        "sirna",
        "shrna",
        "ml216",
        "drug",
        "compound",
        "small molecule",
        "olaparib",
        "parp",
        "cisplatin",
        "hydroxyurea",
        "aphidicolin",
    ),
)

#: The BUB1B card's exposure lexicon, plus the cancers Bloom syndrome patients actually get.
#: The oncology vocabulary of "given X, what happened" is not gene-specific, so it transfers.
EXPOSURE_LEXICON = replace(
    BUB1B_EXPOSURE_LEXICON,
    cue=(*BUB1B_EXPOSURE_LEXICON.cue, "lymphoma", "colorectal", "carcinoma"),
)

#: Scored after the fact, never used to build a query (see the entry's declared control).
#: pmid → the (effect_on, direction) pairs that state the paper's known finding.
CONTROLS: dict[str, list[tuple[str, str]]] = {
    # Chaganti 1974, PNAS: loss of BLM raises sister-chromatid exchange ~13-fold.
    "4140506": [("sce", "increase")],
    # Ellis 1995, Cell: chain-terminating mutations in BLM cause the syndrome.
    "7585968": [("function", "decrease")],
    # German 2007, Hum Mutat: 54 of 64 registry mutations terminate translation early.
    "17407155": [("function", "decrease")],
}

#: What an extracted row is allowed to be about. A row outside this vocabulary is rejected.
EFFECT_ON: tuple[str, ...] = (
    "blm_level",
    "function",
    "sce",
    "genome_instability",
    "cancer",
    "growth",
    "lifespan",
    "other",
)

#: How directly each effect speaks to the amount of working helicase (the rubric's 2nd axis).
DIRECTNESS: dict[str, float] = {
    "blm_level": 1.0,
    "function": 0.9,
    "sce": 0.8,
    "genome_instability": 0.8,
    "lifespan": 0.7,
    "cancer": 0.6,
    "growth": 0.6,
    "other": 0.6,
}

#: For a loss-of-function gene, which direction of each effect is the goal. ``other`` is left
#: out: an effect the vocabulary cannot name has no agreed good direction.
DESIRED: dict[str, str] = {
    "blm_level": "increase",
    "function": "increase",
    "sce": "decrease",
    "genome_instability": "decrease",
    "cancer": "decrease",
    "growth": "increase",
    "lifespan": "increase",
}

#: Which allele branch an effect can help. The genotype modelled here is **homozygous for a
#: premature stop** (see the R1 card ``mva.drugs.readthrough_case_blm``), so anything that acts
#: on the protein's amount or activity has to get past the stop first: branch ``stop_allele``.
#: Downstream phenotypes are allele-agnostic.
BRANCH_BY_EFFECT: dict[str, str] = {
    "blm_level": "stop_allele",
    "function": "stop_allele",
    "sce": "any",
    "genome_instability": "any",
    "cancer": "any",
    "growth": "any",
    "lifespan": "any",
    "other": "any",
}

#: Genetic interventions whose target is not one druggable protein: the drug class that
#: performs the same act. A *class* mapping, declared here so a reader can argue with it.
ANALOGUES: dict[str, dict[str, object]] = {
    "26S proteasome": {
        "act": "loss",
        "drugs": ["bortezomib", "carfilzomib", "ixazomib"],
        "class": "proteasome inhibitor",
    },
    "protein deacetylases (HDAC)": {
        "act": "loss",
        "drugs": ["vorinostat", "romidepsin", "belinostat", "panobinostat", "valproic acid"],
        "class": "histone deacetylase inhibitor",
    },
}

#: Text markers that make a paper a disease paper for the exposure screen, beside ``SPEC``'s
#: disease phrases: the cytogenetic signs Bloom syndrome is recognised by.
DISEASE_MARKERS = (
    "sister chromatid exchange",
    "quadriradial",
    "Bloom's Syndrome Registry",
    "BSyn",
)

EXTRACTOR = {
    "model": "claude-opus-5-5",
    "role": "iteration-5 scalability (transfer) subagent",
    "date": "2026-09-25",
    "method": "read the screened sentences (build/it5/transfer/r3/reading/*.md) with their "
    "context and wrote each row by hand, copying the quote from the cached text",
}
