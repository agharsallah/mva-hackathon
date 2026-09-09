"""The research steps, and the one goal each of them exists to answer.

A step is the unit the whole record hangs off. Every hypothesis names one, every
methodology entry names one, and the report groups by one. Without that binding the log
becomes what it was before: a pile of findings with no statement of what question they
were answering.

**Steps are code, not rows.** They are few, they change rarely, and a reviewer should see
the whole map in a diff — the same reasoning that puts :data:`mva.warehouse.analysis.
DERIVATIONS` in a module instead of a table. Hypotheses and evidence accumulate at
runtime and belong in the warehouse; the map they hang off does not.

Two kinds of step, and the distinction matters:

``platform``
    Machinery. It has a goal, but the goal is "does this work", answered by building it
    and checking it. No hypotheses. Step 0 is the only one.
``research``
    A question about the world whose answer is not known in advance. Hypotheses live
    here, and a step is finished when its hypotheses have verdicts — not when its code
    runs.

The order and the goals are read from ``docs/roadmap.md`` §1; that page owns the
sequencing argument, this module owns the machine-readable form of it.
"""

from dataclasses import dataclass

PLATFORM = "platform"
RESEARCH = "research"

#: The submission iteration the research steps currently contribute to: steps 1-8 are filed
#: under ``docs/<ITERATION>/step-<n>/``; a new iteration starts a new folder.
ITERATION = "iteration2"

#: A step that has been finished, is being worked, or has not been opened.
STATUSES = ("done", "open", "planned")


@dataclass(frozen=True)
class Step:
    """One step: its research goal, and where its record lives."""

    slug: str
    title: str
    goal: str
    kind: str = RESEARCH
    status: str = "planned"
    unblocks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in (PLATFORM, RESEARCH):
            raise ValueError(f"{self.slug}: kind must be {PLATFORM} or {RESEARCH}")
        if self.status not in STATUSES:
            raise ValueError(f"{self.slug}: status must be one of {STATUSES}")
        if not self.goal.strip():
            raise ValueError(f"{self.slug}: a step without a goal is a folder, not a step")

    @property
    def folder(self) -> str:
        """The step's folder under ``docs/``: the platform stands alone, research steps are
        grouped under the submission iteration they contribute to."""
        return self.slug if self.kind == PLATFORM else f"{ITERATION}/{self.slug}"

    @property
    def docs(self) -> str:
        """Where this step's pages, notes and methodology entries live."""
        return f"docs/{self.folder}"

    @property
    def takes_hypotheses(self) -> bool:
        """Whether a hypothesis may name this step.

        Platform steps may not. "Postgres is the right database" is a decision with
        alternatives, recorded as a note; it is not a claim about the patient that
        evidence can refute.
        """
        return self.kind == RESEARCH


#: The map. Ordered by dependency, which is also the order they are worked.
STEPS: tuple[Step, ...] = (
    Step(
        slug="step-0",
        title="The platform",
        goal="Can the delivered bytes be trusted, stored without loss, and queried in SQL?",
        kind=PLATFORM,
        status="done",
        unblocks=("step-1",),
    ),
    Step(
        slug="step-1",
        title="Normalize the callset",
        goal=(
            "Does every variant in the callset have exactly one spelling, so that an "
            "exact-string-matching scorer can be trusted with an indel?"
        ),
        status="open",
        unblocks=("step-2", "step-4"),
    ),
    Step(
        slug="step-2",
        title="Annotate the callset",
        goal=(
            "Which variants are rare enough and damaging enough to cause an ultra-rare "
            "recessive disease, and in which gene?"
        ),
        # Open, not planned: the eight-gene panel is annotated (VEP REST, step-0 entry 031)
        # and reduces to one BUB1B pair. The genome-wide pass has not run.
        status="open",
        unblocks=("step-3", "step-6"),
    ),
    Step(
        slug="step-3",
        title="Rank by phenotype",
        goal=(
            "Does an unbiased genome-wide ranking driven by the child's HPO terms agree "
            "with the panel-first candidate list?"
        ),
        # Open, not planned: the ranking is built and has run. It needed neither step 1 nor
        # step 2 - ranking genes by symptoms reads no callset - so the dependency the
        # roadmap assumed turned out not to exist. See docs/iteration1/step-3/methodology/067.
        status="open",
        unblocks=("step-6",),
    ),
    Step(
        slug="step-4",
        title="Mine the suppressed calls",
        goal=(
            "Is one of the two alleles hiding in a call the quality filters discarded, "
            "rather than absent from the sample?"
        ),
        # Open, not planned: the panel's non-PASS calls were mined in step-0 entry 049 and
        # held nothing rare and protein-altering. Genome-wide, the question is untested.
        status="open",
        unblocks=("step-6",),
    ),
    Step(
        slug="step-5",
        title="Recover the second allele from the reads",
        goal=(
            "Is the missing allele a variant the caller could not emit at all — a "
            "structural variant, a deep intronic call, or a low-fraction mosaic?"
        ),
        unblocks=("step-6",),
    ),
    Step(
        slug="step-6",
        title="Spend the oracle budget",
        goal=(
            "Which candidate pair does the scorer confirm, and what does each reply "
            "tell us that the next submission should exploit?"
        ),
    ),
    Step(
        slug="step-7",
        title="Knowledge and literature",
        goal=(
            "Does public knowledge - published MVA cases, ClinVar, protein-model scores - "
            "name an allele or a pair the data-driven steps missed, or independently "
            "corroborate the one they found?"
        ),
        unblocks=("step-6",),
    ),
    Step(
        slug="step-8",
        title="Track 2 - drug repurposing",
        # Opens for desk research in parallel with steps 1-7; its verdicts wait for the
        # pair step-6 confirms, because a mechanism argued from an unconfirmed allele is a
        # guess dressed as rigour.
        goal=(
            "Which market-approved drugs act on the mechanism the confirmed alleles imply, "
            "and how strong is the evidence for each?"
        ),
    ),
)

_BY_SLUG = {step.slug: step for step in STEPS}


def by_slug(slug: str) -> Step:
    """The step with this slug, or a ``KeyError`` naming the ones that exist."""
    try:
        return _BY_SLUG[slug]
    except KeyError:
        raise KeyError(f"unknown step {slug!r}; known steps: {', '.join(_BY_SLUG)}") from None


def research_steps() -> tuple[Step, ...]:
    """Only the steps a hypothesis may be filed under."""
    return tuple(step for step in STEPS if step.takes_hypotheses)


def slugs() -> tuple[str, ...]:
    """Every step slug, in dependency order — the CLI's ``choices``."""
    return tuple(_BY_SLUG)
