"""The write verbs: ``hypothesis-add``, ``hypothesis-revise``, ``evidence-add``, ``probe-link``.

Every one appends; none updates. The refusals live in the register's constructors, not
here — a claim without a prediction and a refutation condition, or an observation without
a source, raises before it reaches a table.
"""

import sys

from .. import evidence as evidence_module
from .. import hypothesis as hypothesis_module
from ..evidence import Direction, Evidence
from ..hypothesis import Hypothesis, Status
from . import context


def do_hypothesis_add(args) -> int:
    settings = context.settings()
    try:
        claim = Hypothesis(
            step=args.step,
            statement=args.statement,
            prediction=args.prediction,
            refuted_by=args.refuted_by,
            gene=args.gene or "",
            path=args.path or "",
            author=args.by or "",
            iteration=getattr(args, "iteration", "") or "",
        )
    except (ValueError, KeyError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1

    with context.attached(settings) as connection:
        hypothesis_module.ensure_table(connection, settings.schema)
        stored = hypothesis_module.propose(connection, settings.schema, claim)
    print(f"recorded {stored.hypothesis_id} under {stored.filed_under}/{stored.step}")
    return 0


def do_hypothesis_revise(args) -> int:
    settings = context.settings()
    with context.attached(settings) as connection:
        hypothesis_module.ensure_table(connection, settings.schema)
        try:
            revised = hypothesis_module.revise(
                connection,
                settings.schema,
                args.hypothesis,
                status=Status(args.status),
                confidence=args.confidence,
                reasoning=args.reasoning,
                author=args.by or "",
            )
        except (ValueError, KeyError) as problem:
            print(f"error: {problem}", file=sys.stderr)
            return 1
    print(f"recorded {revised.hypothesis_id} revision {revised.revision}: {revised.status.value}")
    return 0


def do_evidence_add(args) -> int:
    settings = context.settings()
    try:
        observation = Evidence(
            hypothesis_id=args.hypothesis,
            direction=Direction(args.direction),
            claim=args.claim,
            source_ref=args.source_ref,
            kind=args.kind,
            strength=args.strength,
            lineage_ref=args.lineage_ref or "",
            author=args.by or "",
        )
    except ValueError as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 1

    with context.attached(settings) as connection:
        evidence_module.ensure_table(connection, settings.schema)
        evidence_id = evidence_module.record(connection, settings.schema, observation)
    print(f"recorded evidence {evidence_id} against {observation.hypothesis_id}")
    return 0


def do_probe_link(args) -> int:
    """Tie a spent probe to the hypotheses it was fired to test.

    The ledger is append-only, so this does not edit the probe row. It records the tie as
    evidence — which is the honest shape anyway: what a reply *means* for a belief is a
    judgment, and judgments belong in the evidence ledger with a source, not silently
    inside the record of what was uploaded.
    """
    settings = context.settings()
    rows = []
    with context.attached(settings) as connection:
        evidence_module.ensure_table(connection, settings.schema)
        for hypothesis_id in args.hypothesis:
            observation = Evidence(
                hypothesis_id=hypothesis_id,
                direction=Direction(args.direction),
                claim=args.claim,
                source_ref=f"probe:{args.probe}",
                kind="oracle",
                strength=args.strength,
                author=args.by or "",
            )
            rows.append(evidence_module.record(connection, settings.schema, observation))
    print(
        f"recorded {len(rows)} oracle observation(s) from probe {args.probe}: "
        + ", ".join(str(row) for row in rows)
    )
    return 0
