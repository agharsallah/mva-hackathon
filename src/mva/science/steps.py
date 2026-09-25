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

from importlib import import_module

from .step import ITERATION, PLATFORM, RESEARCH, STATUSES, Step
from .step_maps import ITERATION1, ITERATION2, ITERATION4, ITERATION5

__all__ = [
    "FIRST_ITERATION",
    "ITERATION",
    "ITERATION1",
    "ITERATION2",
    "ITERATION4",
    "ITERATION5",
    "PLATFORM",
    "RESEARCH",
    "STATUSES",
    "STEPS",
    "STEPS_BY_ITERATION",
    "Step",
    "by_slug",
    "iterations",
    "research_slugs_everywhere",
    "research_steps",
    "slugs",
    "steps_for",
    "summary",
]

#: Every iteration's map, by name. One map per iteration: an iteration is a new
#: exploration with its own questions, not a replay of the previous one's steps.
STEPS_BY_ITERATION: dict[str, tuple[Step, ...]] = {
    "iteration1": ITERATION1,
    "iteration2": ITERATION2,
    "iteration4": ITERATION4,
    "iteration5": ITERATION5,
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


def research_slugs_everywhere() -> tuple[str, ...]:
    """Every slug a hypothesis may name in *any* declared iteration, deduplicated and in
    dependency order — the ``--step`` choices once ``--iteration`` can pick the map."""
    seen: dict[str, None] = {}
    for iteration_steps in STEPS_BY_ITERATION.values():
        for step in iteration_steps:
            if step.takes_hypotheses:
                seen.setdefault(step.slug, None)
    return tuple(seen)


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


def summary(iteration: str) -> str:
    """One line saying what an iteration *is*, read from its map module's own docstring.

    Not a second place to maintain prose: the module that declares the steps already opens
    by saying what route it declares, and that sentence is what a reader choosing between
    iterations needs. A map without a docstring contributes an empty string rather than an
    invented description.
    """
    module = import_module(f"{__package__}.step_maps.{iteration}")
    return (module.__doc__ or "").strip().splitlines()[0] if module.__doc__ else ""


def iterations() -> tuple[str, ...]:
    """Every iteration that has a step map, oldest first."""
    return tuple(STEPS_BY_ITERATION)
