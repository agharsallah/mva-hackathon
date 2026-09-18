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
    #: The submission iteration this step contributes to. Empty means "the current one",
    #: which is what a platform step wants: it belongs to no iteration.
    iteration: str = ""

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
        grouped under the submission iteration they contribute to.

        The iteration is carried by the step, not read from :data:`ITERATION`, so that a
        frozen iteration's steps keep resolving to their own folder after the current
        iteration moves on.
        """
        if self.kind == PLATFORM:
            return self.slug
        return f"{self.iteration or ITERATION}/{self.slug}"

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


#: Iteration 1 — the top-down route that produced submission 1: trust the caller's VCF,
#: filter hard, check convergence. Frozen; kept importable so its record still resolves.
ITERATION1: tuple[Step, ...] = (
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
        iteration="iteration1",
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
        iteration="iteration1",
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
        iteration="iteration1",
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
        iteration="iteration1",
    ),
    Step(
        slug="step-5",
        title="Recover the second allele from the reads",
        goal=(
            "Is the missing allele a variant the caller could not emit at all — a "
            "structural variant, a deep intronic call, or a low-fraction mosaic?"
        ),
        unblocks=("step-6",),
        iteration="iteration1",
    ),
    Step(
        slug="step-6",
        title="Spend the oracle budget",
        goal=(
            "Which candidate pair does the scorer confirm, and what does each reply "
            "tell us that the next submission should exploit?"
        ),
        iteration="iteration1",
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
        iteration="iteration1",
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
        iteration="iteration1",
    ),
)


#: Iteration 2 — the mirror of iteration 1, run blind: start from the raw reads, the VCF
#: and the eight HPO terms as if no candidate were known, and rediscover the pair by
#: routes that share no code with iteration 1. The plan is ``docs/iteration2/plan.md``;
#: the goals below are its §2 table.
ITERATION2: tuple[Step, ...] = (
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
        title="The blind target set",
        goal=(
            "Which genes do the child's symptoms alone nominate — a target set chosen "
            "with the DNA never read?"
        ),
        # Done: all four claims (H012-H015) carry committed verdicts in entry 084, and
        # the full-population re-test of H012 is entry 091.
        status="done",
        unblocks=("step-2", "step-3", "step-4"),
        iteration="iteration2",
    ),
    Step(
        slug="step-2",
        title="Discover the alleles from the reads",
        goal=(
            "Which alleles do the raw reads carry in the target set, discovered without "
            "the vendor caller — small variants, structural variants, per-exon coverage, "
            "and read-backed phase?"
        ),
        # Done: the five claims filed for this step carry committed verdicts and the
        # step README records the completion audit.
        status="done",
        unblocks=("step-3", "step-6", "step-7"),
        iteration="iteration2",
    ),
    Step(
        slug="step-3",
        title="Alignment-free genotype and copy number",
        goal=(
            "Read without an aligner or a caller, are the discovered alleles at "
            "heterozygous multiplicity, is every target-gene exon at two copies, and "
            "which public ClinVar P/LP alleles are present at all?"
        ),
        # Done: six claims filed before the run, six settled - four refuted, two
        # supported. H027, the step's own headline, is one of the refutations and is
        # the most useful thing it produced.
        status="done",
        unblocks=("step-4", "step-6", "step-7"),
        iteration="iteration2",
    ),
    Step(
        slug="step-4",
        title="Likelihood-ratio ranking over the VCF",
        goal=(
            "Over every protein-coding gene in the VCF, with no hard filter, which "
            "biallelic pair has the highest posterior, and what is its P(trans)?"
        ),
        # Done: six claims filed before the run, six settled. The leader is the gene
        # step 1 nominated blind with the DNA unread; the margin claim is what failed,
        # and the runner-up is a gene nobody has ever curated a phenotype for.
        status="done",
        unblocks=("step-5", "step-6"),
        iteration="iteration2",
    ),
    Step(
        slug="step-5",
        title="Knowledge engine",
        goal=(
            "Does public knowledge — published alleles, case reports, protein-language "
            "models — nominate or corroborate a pair for this phenotype?"
        ),
        unblocks=("step-6", "step-7"),
        iteration="iteration2",
    ),
    Step(
        slug="step-6",
        title="Fusion and unblinding",
        goal=(
            "Fused across steps 2-5 and then unblinded, does iteration 2 rediscover "
            "iteration 1's pair, and is a second upload informative?"
        ),
        unblocks=("step-7",),
        iteration="iteration2",
    ),
    Step(
        slug="step-7",
        title="Track 2 enrichment",
        goal=(
            "Which mechanism facts from steps 2-5 and 8 revise the Track 2 card, and "
            "what does the drug evidence say for each direction?"
        ),
        iteration="iteration2",
    ),
    Step(
        slug="step-8",
        title="The mosaic aneuploidy bound",
        goal=(
            "Is mosaic aneuploidy detectable in the sequenced sample with a statistic "
            "that has power, and what cell-fraction bound does the data set per "
            "chromosome?"
        ),
        unblocks=("step-7",),
        iteration="iteration2",
    ),
)

#: Every iteration's map, by name. One map per iteration: an iteration is a new
#: exploration with its own questions, not a replay of the previous one's steps.
STEPS_BY_ITERATION: dict[str, tuple[Step, ...]] = {
    "iteration1": ITERATION1,
    "iteration2": ITERATION2,
}

#: The iteration that was being worked before the column recording it existed: a claim
#: with no iteration on it was filed then.
FIRST_ITERATION = "iteration1"

#: The current iteration's map — what every caller that does not name an iteration means.
STEPS: tuple[Step, ...] = STEPS_BY_ITERATION[ITERATION]

_BY_SLUG = {step.slug: step for step in STEPS}


def by_slug(slug: str, *, iteration: str = "") -> Step:
    """The step with this slug, or a ``KeyError`` naming the ones that exist.

    ``iteration`` selects the map to read; the current one by default. A frozen
    iteration's record asks for its own map, because the slugs are reused.
    """
    index = _BY_SLUG if not iteration else {s.slug: s for s in steps_for(iteration)}
    try:
        return index[slug]
    except KeyError:
        raise KeyError(f"unknown step {slug!r}; known steps: {', '.join(index)}") from None


def research_steps() -> tuple[Step, ...]:
    """Only the steps a hypothesis may be filed under."""
    return tuple(step for step in STEPS if step.takes_hypotheses)


def slugs() -> tuple[str, ...]:
    """Every step slug, in dependency order — the CLI's ``choices``."""
    return tuple(_BY_SLUG)


def steps_for(iteration: str) -> tuple[Step, ...]:
    """The step map of one iteration, or a ``KeyError`` naming the ones that exist."""
    try:
        return STEPS_BY_ITERATION[iteration]
    except KeyError:
        known = ", ".join(STEPS_BY_ITERATION)
        raise KeyError(f"unknown iteration {iteration!r}; known: {known}") from None


def iterations() -> tuple[str, ...]:
    """Every iteration that has a step map, oldest first."""
    return tuple(STEPS_BY_ITERATION)
