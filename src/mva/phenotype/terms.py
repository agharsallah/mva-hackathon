"""The child's phenotype, declared once.

The challenge delivers the phenotype as eight **HPO terms** (Human Phenotype Ontology —
a controlled vocabulary of clinical features, where each feature is a stable id rather
than free text, the way an enum value beats a string literal). Until now those eight ids
lived only in prose: ``ressources/hackathon-rules/README.md`` and ``docs/dictionary.md``.
That file says it plainly — *"Write them once; never retype them."* A term set retyped per
tool is a term set that silently diverges, and a ranking driven by a typo is worse than no
ranking, because it looks like a result.

So this module is the single owner, and the two questions that actually matter about the
set are answered in code rather than in a comment:

**One term does not describe the child.** ``HP:0200067`` (recurrent spontaneous abortion)
is the *parents'* reproductive history. Every phenotype ranker assumes each term describes
the patient, so feeding it a parental feature is a modelling choice, not a data entry.
Recurrent miscarriage is nonetheless a direct read-out of the same chromosome-instability
mechanism under test, and the challenge document says to treat it as evidence rather than
background. Both readings are defensible, so the module ships **both sets** and the run
reports the difference. :data:`WITH_PARENTAL` and :data:`PROBAND_ONLY` exist so that
"with and without" is two constants, never two hand-edits of one list.

**Two features are absent, and the absence is informative.** No microcephaly, no reported
intellectual disability — the two features textbooks most associate with MVA1. HPO has no
way to say "asked and not present" in a plain term list, so the absence cannot be scored;
it is recorded here as a note so the report flags the tension rather than letting the gene
prior quietly override it.
"""

from dataclasses import dataclass

#: The parental term. Named rather than inlined so every reference to "the parental one"
#: resolves to the same string.
PARENTAL_TERM = "HP:0200067"


@dataclass(frozen=True)
class Term:
    """One HPO term as the challenge delivered it.

    ``note`` is the clinical detail from the phenotype document, kept because it is what
    makes a term readable to someone who is not looking at the source file, and
    ``proband`` is the flag that decides which of the two term sets this term joins.
    """

    hpo_id: str
    label: str
    note: str
    #: False only for a feature belonging to the parents rather than the child.
    proband: bool = True


#: The eight terms, verbatim from ``Challenge_Clinical_Phenotype_1.docx`` as transcribed
#: in ``ressources/hackathon-rules/``. Order is the document's, not an importance ranking.
TERMS: tuple[Term, ...] = (
    Term(
        "HP:0002859",
        "Rhabdomyosarcoma",
        "primary oncological event; triggered the investigation",
    ),
    Term("HP:0000121", "Nephrocalcinosis", "present since birth"),
    Term("HP:0004322", "Short stature", "below expected for age and family background"),
    Term("HP:0001508", "Failure to thrive", "repeatedly documented"),
    Term("HP:0003202", "Skeletal muscle atrophy", "reduced muscle bulk"),
    Term("HP:0001622", "Premature birth", "32 weeks gestation"),
    Term("HP:0001518", "Small for gestational age", "~1 kg at birth (IUGR)"),
    Term(
        PARENTAL_TERM,
        "Recurrent spontaneous abortion",
        "parental history, multiple losses - NOT a feature of the child",
        proband=False,
    ),
)


@dataclass(frozen=True)
class TermSet:
    """A named set of HPO ids, and why it is drawn the way it is.

    Named rather than a bare ``frozenset`` because every result this package produces has
    to say which set produced it. Two rankings that differ only by one term are two
    different claims, and a float with no term set attached cannot be told apart from the
    other one.
    """

    name: str
    terms: tuple[Term, ...]
    rationale: str

    @property
    def ids(self) -> tuple[str, ...]:
        """The HPO ids, in declaration order."""
        return tuple(term.hpo_id for term in self.terms)

    @property
    def id_set(self) -> frozenset[str]:
        """The ids as a set, for the similarity math."""
        return frozenset(self.ids)

    def __len__(self) -> int:
        return len(self.terms)


#: Every delivered term, the parental one included.
WITH_PARENTAL = TermSet(
    name="with-parental",
    terms=TERMS,
    rationale=(
        "All eight delivered terms. Recurrent parental miscarriage is a read-out of the "
        "same chromosome-instability mechanism under test, and the challenge document "
        "says to treat it as evidence rather than background."
    ),
)

#: Only the features of the child.
PROBAND_ONLY = TermSet(
    name="proband-only",
    terms=tuple(term for term in TERMS if term.proband),
    rationale=(
        "The seven features of the child. Every phenotype ranker assumes each term "
        "describes the patient, so a parental feature is a modelling choice; this set is "
        "the reading that declines to make it."
    ),
)

#: Both sets, in the order a run reports them. The delta between them is a result.
TERM_SETS: tuple[TermSet, ...] = (WITH_PARENTAL, PROBAND_ONLY)

#: Features a textbook would expect for MVA1 and the document does not list. HPO cannot
#: express "asked and absent" in a term list, so these are never scored - they exist so
#: the write-up flags the tension instead of ignoring it.
NOTABLY_ABSENT: tuple[tuple[str, str], ...] = (
    ("HP:0000252", "Microcephaly"),
    ("HP:0001249", "Intellectual disability"),
)


def by_id(hpo_id: str) -> Term:
    """The delivered term with this id, or a ``KeyError`` naming the ones that exist."""
    for term in TERMS:
        if term.hpo_id == hpo_id:
            return term
    raise KeyError(
        f"unknown term {hpo_id!r}; delivered terms: {', '.join(t.hpo_id for t in TERMS)}"
    )


def term_set(name: str) -> TermSet:
    """The term set with this name, or a ``KeyError`` naming the ones that exist."""
    for candidate in TERM_SETS:
        if candidate.name == name:
            return candidate
    raise KeyError(f"unknown term set {name!r}; known: {', '.join(s.name for s in TERM_SETS)}")
