"""The ``Step`` dataclass and its vocabulary — the shape every iteration's map is made of.

Split out of :mod:`mva.science.steps` so the maps (:mod:`mva.science.step_maps`) can import
the type without importing the API that reads them.
"""

from dataclasses import dataclass

PLATFORM = "platform"
RESEARCH = "research"


#: A step that has been finished, is being worked, or has not been opened.
STATUSES = ("done", "open", "planned")

#: The submission iteration the research steps currently contribute to: steps 1-8 are filed
#: under ``docs/<ITERATION>/step-<n>/``; a new iteration starts a new folder.
ITERATION = "iteration2"


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
