"""The one shape a derivation has, and the placeholder that points it at a schema.

Split out of :mod:`mva.warehouse.analysis` so that a second registry module
(:mod:`mva.warehouse.analysis_reference`) can declare derivations without importing the
module that collects them — which would be a cycle. Nothing here knows what any
particular analysis does; it is the type plus one string substitution.
"""

from dataclasses import dataclass

#: Placeholder replaced with the fully-qualified ingest schema before execution.
SOURCE = "{src}"

#: Placeholder for the fully-qualified *result* schema, so a derivation can build on an
#: earlier derivation's table instead of re-deriving it. Only sound because ``pg-derive``
#: runs the registry in declaration order: a derivation naming ``{res}.x`` must be declared
#: after ``x``. Layer 2 (``coding_alleles`` → ``coding_candidates`` → ``gene_biallelic``)
#: is the first user; before it, every derivation read the ingest schema alone.
RESULT = "{res}"


@dataclass(frozen=True)
class Derivation:
    """One analysis: a name, what it answers, and the SELECT that answers it."""

    name: str
    question: str
    sql: str
    depends_on: tuple[str, ...] = ()
    #: Result-schema tables this derivation reads that were **loaded** rather than
    #: ingested or derived — written by a loader from files a pipeline outside SQL
    #: produced (an aligner, a caller, a k-mer sweep). They are dependencies exactly like
    #: :attr:`depends_on`, but they live in ``{res}`` and no staging verb makes them, so
    #: the registry's invariants have to be able to tell the two apart rather than
    #: treating an unrecognised name as a mistake.
    reads_loaded: tuple[str, ...] = ()


def resolve(sql: str, source_schema: str, result_schema: str | None = None) -> str:
    """Point a derivation's SQL at concrete schemas.

    ``result_schema`` defaults to ``source_schema`` so a caller that only knows one schema
    (the hermetic tests build both layers in one DuckDB schema) still resolves every
    placeholder; leaving ``{res}`` in the text would be a syntax error at run time.
    """
    return sql.replace(SOURCE, source_schema).replace(RESULT, result_schema or source_schema)
