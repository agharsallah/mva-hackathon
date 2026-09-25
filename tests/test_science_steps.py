"""One step map per iteration, and the rule that keeps a frozen record readable.

Slugs restart at ``step-1`` every iteration, so a slug alone does not identify a step.
The tests below pin the two consequences of that: a step resolves its folder from *its
own* iteration, and a claim filed in an earlier iteration keeps rendering that
iteration's goal after the current one moves on.
"""

import pytest

from mva.science import steps
from mva.science.hypothesis import Hypothesis, _hydrate


def test_every_iteration_has_a_map_and_the_current_one_is_selected():
    assert steps.ITERATION in steps.STEPS_BY_ITERATION
    assert steps.STEPS is steps.STEPS_BY_ITERATION[steps.ITERATION]
    assert steps.iterations() == ("iteration1", "iteration2", "iteration4", "iteration5")


def test_a_research_step_folders_under_its_own_iteration():
    """The frozen record must not follow the current iteration into a new folder."""
    first = steps.by_slug("step-1", iteration="iteration1")
    current = steps.by_slug("step-1")
    assert first.docs == "docs/iteration1/step-1"
    assert current.docs == f"docs/{steps.ITERATION}/step-1"
    assert first.goal != current.goal


def test_the_platform_step_belongs_to_no_iteration():
    assert steps.by_slug("step-0").docs == "docs/step-0"
    assert steps.by_slug("step-0", iteration="iteration1").docs == "docs/step-0"


def test_every_map_declares_a_goal_for_every_step():
    for iteration, map_ in steps.STEPS_BY_ITERATION.items():
        assert map_, iteration
        for step in map_:
            assert step.goal.strip(), f"{iteration}/{step.slug}"
            assert step.iteration in ("", iteration)


def test_unknown_iteration_names_the_ones_that_exist():
    with pytest.raises(KeyError, match="iteration1"):
        steps.steps_for("iteration99")


def test_a_claim_renders_the_goal_of_the_iteration_it_was_filed_in():
    filed = Hypothesis(
        step="step-1",
        statement="s",
        prediction="p",
        refuted_by="r",
        iteration="iteration1",
    )
    assert filed.goal == steps.by_slug("step-1", iteration="iteration1").goal


def test_a_new_claim_defaults_to_the_current_iteration():
    fresh = Hypothesis(step="step-1", statement="s", prediction="p", refuted_by="r")
    assert fresh.filed_under == steps.ITERATION


def test_a_row_written_before_the_column_existed_reads_as_iteration_one():
    """Every claim filed before the column existed was filed in iteration 1."""
    row = ("H001", 1, "step-1", "s", "p", "r", "", "", "proposed", None, "", "", None)
    assert _hydrate(row).filed_under == steps.FIRST_ITERATION
