"""The CLI's promises: what it refuses, and what it declines to write.

Hermetic by the same mechanism the warehouse ledger CLI tests use — ``attached`` and
``_settings`` are imported into the module namespace, so a test replaces them and no
database is touched.

The load-bearing test in here is that ``verdict`` writes nothing without ``--commit``. A
tool that silently records the number it computed would make every confidence in the
register the tool's opinion rather than a human's.
"""

import contextlib

import pytest

from mva.science import cli
from mva.science.hypothesis import Hypothesis, Status
from mva.warehouse.settings import Postgres
from test_science_register import FakeConnection

CLAIM = Hypothesis(
    step="step-1",
    statement="The causal pair sits in BUB1B.",
    prediction="Two rare damaging alleles in BUB1B, one on each copy.",
    refuted_by="Both alleles turn out common in gnomAD.",
    hypothesis_id="H001", revision=1)


def _row(claim: Hypothesis = CLAIM) -> tuple:
    """One hypothesis row in the SELECT column order the reader expects."""
    return (claim.hypothesis_id, claim.revision, claim.step, claim.statement,
            claim.prediction, claim.refuted_by, claim.path, claim.gene,
            claim.status.value, claim.confidence, claim.reasoning, claim.author)


class Args:
    """A stand-in for the argparse namespace."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


@pytest.fixture
def wired(monkeypatch):
    """Point the CLI at a fake connection and return it for inspection."""
    def _wire(answers=None):
        connection = FakeConnection(answers)

        @contextlib.contextmanager
        def fake_attached(settings, read_only=False):
            yield connection

        monkeypatch.setattr(cli, "attached", fake_attached)
        monkeypatch.setattr(cli, "_settings",
                            lambda: Postgres(schema="warehouse", result_schema="results"))
        return connection
    return _wire


# --- verdict --------------------------------------------------------------------------

def test_verdict_writes_nothing_without_commit(wired, capsys):
    """The tool suggests a number; a human commits it. Otherwise it is the tool's opinion."""
    connection = wired([[_row()], []])
    assert cli.do_verdict(Args(hypothesis="H001", commit=False, status="supported",
                               confidence=None, reasoning="", by="")) == 0
    assert not connection.inserts()
    assert "nothing written" in capsys.readouterr().out


def test_verdict_prints_the_arithmetic(wired, capsys):
    wired([[_row()], []])
    cli.do_verdict(Args(hypothesis="H001", commit=False, status="supported",
                        confidence=None, reasoning="", by=""))
    out = capsys.readouterr().out
    assert "prior 0.50" in out
    assert "suggested confidence" in out


def test_verdict_refuses_to_commit_without_a_reason(wired, capsys):
    connection = wired([[_row()], []])
    assert cli.do_verdict(Args(hypothesis="H001", commit=True, status="supported",
                               confidence=None, reasoning="", by="")) == 1
    assert not connection.inserts()
    assert "requires --reasoning" in capsys.readouterr().err


def test_verdict_with_commit_appends_one_revision(wired):
    connection = wired([[_row()], [], [_row()]])
    assert cli.do_verdict(Args(hypothesis="H001", commit=True, status="supported",
                               confidence=0.8, reasoning="Two paths agreed.",
                               by="a member")) == 0
    inserts = connection.inserts()
    assert len(inserts) == 1
    assert 2 in inserts[0][1], "the commit must append revision 2, not overwrite revision 1"


# --- hypothesis-add -------------------------------------------------------------------

def test_hypothesis_add_refuses_a_claim_with_no_refutation_condition(wired, capsys):
    connection = wired()
    assert cli.do_hypothesis_add(Args(
        step="step-1", statement="BUB1B is causal.", prediction="Two alleles.",
        refuted_by="  ", gene="", path="", by="")) == 1
    assert not connection.inserts()
    assert "refuted_by" in capsys.readouterr().err


def test_hypothesis_add_refuses_a_platform_step(wired, capsys):
    connection = wired()
    assert cli.do_hypothesis_add(Args(
        step="step-0", statement="BUB1B is causal.", prediction="Two alleles.",
        refuted_by="Both common.", gene="", path="", by="")) == 1
    assert not connection.inserts()
    assert "platform" in capsys.readouterr().err


def test_hypothesis_add_appends_at_revision_one(wired):
    connection = wired([[("",)]])
    assert cli.do_hypothesis_add(Args(
        step="step-1", statement="BUB1B is causal.", prediction="Two rare alleles.",
        refuted_by="Both turn out common.", gene="BUB1B", path="1", by="a member")) == 0
    inserts = connection.inserts()
    assert len(inserts) == 1
    assert inserts[0][1][:2] == ["H001", 1]


# --- evidence-add ---------------------------------------------------------------------

def test_evidence_add_refuses_an_observation_with_no_source(wired, capsys):
    connection = wired()
    assert cli.do_evidence_add(Args(
        hypothesis="H001", direction="supports", claim="Looks right.", source_ref="",
        kind="measurement", strength=0.5, lineage_ref="", by="")) == 1
    assert not connection.inserts()
    assert "source_ref" in capsys.readouterr().err


def test_evidence_add_appends_one_sourced_row(wired):
    connection = wired([[(0,)]])
    assert cli.do_evidence_add(Args(
        hypothesis="H001", direction="supports",
        claim="BUB1B is depleted of loss-of-function variants.",
        source_ref="methodology/003", kind="annotation", strength=0.7,
        lineage_ref="data_lineage:7", by="a member")) == 0
    assert len(connection.inserts()) == 1


# --- probe-link -----------------------------------------------------------------------

def test_probe_link_records_the_reply_as_sourced_evidence(wired):
    """The ledger is append-only, so what a reply *means* goes in the evidence ledger."""
    connection = wired([[(0,)], [(1,)]])
    assert cli.do_probe_link(Args(
        probe="4", hypothesis=["H001", "H002"], direction="refutes",
        claim="No partial match at any rank.", strength=0.9, by="a member")) == 0
    inserts = connection.inserts()
    assert len(inserts) == 2
    assert all("probe:4" in params for _, params in inserts)


# --- check ----------------------------------------------------------------------------

def test_check_passes_on_an_empty_register(wired, capsys):
    wired([[], []])
    assert cli.do_check(Args()) == 0
    assert "check passed" in capsys.readouterr().out


def test_check_fails_a_verdict_reached_with_no_evidence(wired, capsys):
    """A claim settled without an observation is a conclusion nobody can audit."""
    settled = Hypothesis(**{**CLAIM.__dict__, "status": Status.SUPPORTED,
                            "confidence": 0.9, "reasoning": "Felt right."})
    wired([[_row(settled)], []])
    assert cli.do_check(Args()) == 1
    assert "no evidence recorded" in capsys.readouterr().out


def test_check_fails_when_a_coordinate_would_reach_the_repository(wired, capsys):
    leaking = Hypothesis(**{**CLAIM.__dict__,
                            "statement": "chr15:40142000 A>G is one of the alleles"})
    wired([[_row(leaking)], []])
    assert cli.do_check(Args()) == 1
    assert "statement" in capsys.readouterr().out


# --- export ---------------------------------------------------------------------------

def test_export_refuses_and_writes_nothing_when_a_coordinate_is_present(
        wired, tmp_path, capsys):
    leaking = Hypothesis(**{**CLAIM.__dict__,
                            "statement": "chr15:40142000 A>G is one of the alleles"})
    wired([[_row(leaking)], []])
    assert cli.do_export(Args(root=str(tmp_path))) == 1
    assert "refusing to export" in capsys.readouterr().err
    assert not list(tmp_path.rglob("*.md"))


def test_export_writes_the_mirror_when_the_register_is_clean(wired, tmp_path):
    wired([[_row()], []])
    assert cli.do_export(Args(root=str(tmp_path))) == 0
    assert (tmp_path / "science-register.json").exists()


# --- steps ----------------------------------------------------------------------------

def test_steps_prints_every_goal(capsys):
    assert cli.do_steps(Args()) == 0
    out = capsys.readouterr().out
    assert out.count("goal:") == 7
    assert "step-0" in out and "step-6" in out
