"""The register's gates: what it refuses, and that it never rewrites what it stored.

Hermetic. The connection is the same hand-rolled fake the warehouse ledger tests use — a
statement recorder that answers ``SELECT``s from a queue — because every function here
takes ``connection`` as its first parameter and never opens one itself. That is the
convention worth preserving: it is what keeps the suite runnable with no Postgres.
"""

import pytest

from mva.science import steps
from mva.science.evidence import PRIOR, WEIGHT, Direction, Evidence, record, weigh
from mva.science.evidence import ensure_table as ensure_evidence
from mva.science.hypothesis import Hypothesis, Status, board, next_id, propose, revise
from mva.science.hypothesis import ensure_table as ensure_hypotheses


class FakeConnection:
    """Records every statement; answers SELECTs from a queue, in order."""

    def __init__(self, answers=None):
        self.statements: list[tuple[str, list]] = []
        self.answers = list(answers or [])
        self._last = None

    def execute(self, sql, params=None):
        self.statements.append((" ".join(sql.split()), list(params or [])))
        self._last = (self.answers.pop(0)
                      if sql.lstrip().upper().startswith("SELECT") and self.answers
                      else [])
        return self

    def fetchall(self):
        return self._last or []

    def fetchone(self):
        rows = self._last or []
        return rows[0] if rows else None

    @property
    def sql_text(self) -> str:
        return " ".join(sql for sql, _ in self.statements)

    def inserts(self):
        return [(sql, params) for sql, params in self.statements
                if sql.upper().startswith("INSERT")]


CLAIM = dict(
    step="step-1",
    statement="The causal pair sits in BUB1B.",
    prediction="Two rare damaging alleles in BUB1B, one on each copy.",
    refuted_by="Both BUB1B alleles turn out common in gnomAD, or phase them onto one copy.",
)


# --- the gates -------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["statement", "prediction", "refuted_by"])
def test_a_claim_missing_a_required_sentence_is_rejected(field):
    """A claim you cannot test, or cannot disprove, is not a hypothesis."""
    with pytest.raises(ValueError, match=field):
        Hypothesis(**{**CLAIM, field: "   "})


def test_a_claim_cannot_be_filed_under_a_platform_step():
    """Step 0 records decisions with alternatives, not claims evidence can refute."""
    with pytest.raises(ValueError, match="platform"):
        Hypothesis(**{**CLAIM, "step": "step-0"})


def test_a_claim_cannot_be_filed_under_a_step_that_does_not_exist():
    with pytest.raises(KeyError, match="known steps"):
        Hypothesis(**{**CLAIM, "step": "step-99"})


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_outside_zero_to_one_is_rejected(confidence):
    with pytest.raises(ValueError, match="confidence"):
        Hypothesis(**CLAIM, confidence=confidence)


def test_an_observation_with_no_source_is_rejected():
    """The load-bearing rule: an unverifiable observation is not evidence."""
    with pytest.raises(ValueError, match="source_ref"):
        Evidence(hypothesis_id="H001", direction=Direction.SUPPORTS,
                 claim="Looks right.", source_ref="  ")


def test_an_observation_with_no_claim_is_rejected():
    with pytest.raises(ValueError, match="claim"):
        Evidence(hypothesis_id="H001", direction=Direction.SUPPORTS,
                 claim="", source_ref="methodology/003")


def test_a_revision_with_no_reasoning_is_rejected():
    """A confidence with no stated basis is a number nobody can check."""
    connection = FakeConnection()
    with pytest.raises(ValueError, match="reasoning"):
        revise(connection, "warehouse", "H001", status=Status.SUPPORTED, reasoning=" ")
    assert not connection.inserts(), "a rejected revision must not reach the table"


# --- append-only -----------------------------------------------------------------------

def test_the_register_never_updates_or_deletes():
    """Both tables are append-only. A changed belief is a new row, never an edit."""
    connection = FakeConnection([[("",)], [(0,)]])
    ensure_hypotheses(connection, "warehouse")
    ensure_evidence(connection, "warehouse")
    propose(connection, "warehouse", Hypothesis(**CLAIM))
    record(connection, "warehouse", Evidence(
        hypothesis_id="H001", direction=Direction.SUPPORTS, claim="Observed.",
        source_ref="methodology/003"))
    text = connection.sql_text.upper()
    for forbidden in ("UPDATE ", "DELETE ", "DROP "):
        assert forbidden not in text, f"the register emitted {forbidden.strip()}"


def test_a_verdict_is_a_new_revision_carrying_the_original_wording():
    """A verdict must not be able to silently reword the claim it is a verdict on."""
    stored = Hypothesis(**CLAIM, hypothesis_id="H001", revision=1)
    connection = FakeConnection([[(
        stored.hypothesis_id, stored.revision, stored.step, stored.statement,
        stored.prediction, stored.refuted_by, "", "", stored.status.value, None, "", "")]])
    revised = revise(connection, "warehouse", "H001", status=Status.SUPPORTED,
                     confidence=0.8, reasoning="Two paths agreed.")
    assert revised.revision == 2
    assert revised.statement == stored.statement
    assert revised.refuted_by == stored.refuted_by
    assert revised.confidence == 0.8


@pytest.mark.parametrize("ensure", [ensure_hypotheses, ensure_evidence])
def test_creation_is_idempotent(ensure):
    connection = FakeConnection()
    ensure(connection, "warehouse")
    assert "CREATE TABLE IF NOT EXISTS" in connection.sql_text


@pytest.mark.parametrize("ensure,table", [(ensure_hypotheses, "hypotheses"),
                                          (ensure_evidence, "evidence")])
def test_tables_live_in_the_ingest_schema_they_are_given(ensure, table):
    connection = FakeConnection()
    ensure(connection, "warehouse")
    assert f"pg.warehouse.{table}" in connection.sql_text


@pytest.mark.parametrize("schema", ["drop table x", "a-b", ""])
@pytest.mark.parametrize("ensure", [ensure_hypotheses, ensure_evidence])
def test_rejects_an_unsafe_schema_name(ensure, schema):
    from mva.warehouse.postgres import InvalidIdentifier
    with pytest.raises(InvalidIdentifier):
        ensure(FakeConnection(), schema)


# --- ids and reads ---------------------------------------------------------------------

def test_the_first_hypothesis_is_h001_and_the_next_follows_it():
    assert next_id(FakeConnection([[("",)]]), "warehouse") == "H001"
    assert next_id(FakeConnection([[("H009",)]]), "warehouse") == "H010"


def test_the_board_reads_only_the_latest_revision_of_each_claim():
    connection = FakeConnection([[]])
    board(connection, "warehouse")
    sql = connection.statements[-1][0]
    assert "max(revision)" in sql, "the board must not show superseded revisions"


def test_the_board_can_be_narrowed_to_one_step():
    connection = FakeConnection([[]])
    board(connection, "warehouse", step="step-1")
    sql, params = connection.statements[-1]
    assert "h.step = ?" in sql and params == ["step-1"]


# --- the weighing ----------------------------------------------------------------------

def _observation(direction, strength=1.0):
    return Evidence(hypothesis_id="H001", direction=direction, strength=strength,
                    claim="Observed.", source_ref="methodology/003")


def test_no_evidence_leaves_the_confidence_at_the_prior():
    assert weigh([], "H001").confidence == pytest.approx(PRIOR)


def test_supporting_and_refuting_evidence_of_equal_strength_cancel():
    weighing = weigh([_observation(Direction.SUPPORTS),
                      _observation(Direction.REFUTES)], "H001")
    assert weighing.confidence == pytest.approx(PRIOR)
    assert (weighing.supports, weighing.refutes) == (1, 1)


def test_neutral_evidence_is_recorded_but_moves_nothing():
    """"We looked and it told us nothing" is a finding, and it must not tip the balance."""
    weighing = weigh([_observation(Direction.NEUTRAL)], "H001")
    assert weighing.confidence == pytest.approx(PRIOR)
    assert weighing.neutral == 1
    assert not weighing.is_decided


def test_one_decisive_observation_is_strong_but_never_certain():
    confidence = weigh([_observation(Direction.SUPPORTS)], "H001").confidence
    assert 0.85 < confidence < 1.0


def test_the_arithmetic_shows_one_line_per_observation_plus_prior_and_total():
    rows = [_observation(Direction.SUPPORTS, 0.6), _observation(Direction.REFUTES, 0.3)]
    lines = weigh(rows, "H001").arithmetic()
    assert len(lines) == len(rows) + 2
    assert lines[0].startswith("prior")
    assert lines[-1].startswith("suggested confidence")


def test_strength_scales_the_contribution_linearly_in_log_odds():
    assert _observation(Direction.SUPPORTS, 0.5).contribution == pytest.approx(0.5 * WEIGHT)
    assert _observation(Direction.REFUTES, 0.5).contribution == pytest.approx(-0.5 * WEIGHT)


@pytest.mark.parametrize("strength", [-0.1, 1.1])
def test_strength_outside_zero_to_one_is_rejected(strength):
    with pytest.raises(ValueError, match="strength"):
        _observation(Direction.SUPPORTS, strength)


# --- the step map ----------------------------------------------------------------------

def test_every_step_declares_a_goal():
    assert all(step.goal.strip() for step in steps.STEPS)


def test_exactly_one_platform_step_and_it_takes_no_hypotheses():
    platform = [s for s in steps.STEPS if s.kind == steps.PLATFORM]
    assert [s.slug for s in platform] == ["step-0"]
    assert not platform[0].takes_hypotheses


def test_every_unblocked_step_exists():
    known = set(steps.slugs())
    for step in steps.STEPS:
        assert set(step.unblocks) <= known, f"{step.slug} unblocks an unknown step"


def test_step_slugs_are_unique():
    assert len(steps.slugs()) == len(set(steps.slugs()))
