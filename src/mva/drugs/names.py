"""One drug, one name.

The sources spell a drug several ways - ``ATORVASTATIN``, ``ATORVASTATIN CALCIUM``,
``METFORMIN HYDROCHLORIDE`` - and every one of them is the same molecule for the purposes of a
mechanism argument, a label lookup or a literature count. Counting them separately would make
a drug with five salts look like five candidates. This module folds the salt and formulation
words off the end of a name and upper-cases what is left; nothing else is normalised, so two
genuinely different molecules never collapse.
"""

from __future__ import annotations

__all__ = ["SALT_WORDS", "base_name"]

#: Trailing words that name a salt, a hydrate or a formulation rather than the molecule.
SALT_WORDS = frozenset(
    {
        "HYDROCHLORIDE",
        "DIHYDROCHLORIDE",
        "CALCIUM",
        "SODIUM",
        "POTASSIUM",
        "MAGNESIUM",
        "SULFATE",
        "SULPHATE",
        "MESYLATE",
        "MESILATE",
        "CITRATE",
        "TARTRATE",
        "DITARTRATE",
        "ACETATE",
        "MALEATE",
        "FUMARATE",
        "SUCCINATE",
        "PHOSPHATE",
        "LACTATE",
        "BROMIDE",
        "CHLORIDE",
        "ANHYDROUS",
        "MONOHYDRATE",
        "DIHYDRATE",
        "TRIHYDRATE",
        "HYDRATE",
        "D-MANNITOL",
        "PROTEIN-BOUND",
        "LIPOSOMAL",
        "LIPOSOME",
        "ALBUMIN-BOUND",
        "NANOPARTICLES",
        "POLIGLUMEX",
        "PEGYLATED",
    }
)


def base_name(name: str) -> str:
    """``METFORMIN HYDROCHLORIDE`` → ``METFORMIN``; a bare name is returned upper-cased.

    Words are stripped from the right only while they are salt words, so ``SODIUM
    PHENYLBUTYRATE`` keeps its leading ``SODIUM`` - there the word is part of the molecule's
    conventional name, not a suffix.
    """
    words = name.strip().upper().split()
    while len(words) > 1 and words[-1] in SALT_WORDS:
        words.pop()
    return " ".join(words)
