"""The gate that keeps the table catalogue current.

A registry of prose about a database rots the moment somebody adds a table and forgets the
sentence. Documentation discipline cannot be asked for in a README; it has to fail a
build. So :func:`test_every_declared_table_is_described` walks every table name declared
anywhere in the code — the staged catalogue specs, the reference specs, every derivation,
the ledgers, the raw layer, the annotation table and the research register — and refuses
any of them without a ``created_by`` and a ``why``.

Hermetic: no database, no network. Everything here is read from module constants.
"""

import pytest

from mva.viz import catalog_semantics as semantics
from mva.viz.catalog_columns import BY_TABLE, SHARED, meaning
from mva.warehouse.analysis import DERIVATIONS

#: Columns that recur across tables and must be covered once, by the shared map, so that a
#: new table carrying them is described without a new entry.
RECURRING = ("chrom", "pos", "ref", "alt", "gene", "rsid", "qual", "filter",
             "sha256", "object_key", "file_name", "size_bytes", "version_id",
             "line_no", "line", "n_all", "n_pass", "start", "end")


# ── the enforcement gate ─────────────────────────────────────────────────────────────

def test_every_declared_table_is_described():
    """Adding a table without describing it fails here, with the edit to make.

    The message is the point: it names the table, where the name was declared, and the
    exact registry entry to add.
    """
    gaps = semantics.undescribed()
    if gaps:
        listed = "\n".join(
            f"  - {table!r} (declared in {source})" for table, source in gaps.items())
        pytest.fail(
            f"{len(gaps)} table(s) exist in code with no semantics:\n{listed}\n\n"
            "Add a TableFact for each in src/mva/viz/catalog_semantics.py:\n"
            '    "<table>": TableFact("<the verb that writes it>", "<why it exists>"),\n'
            "A derivation needs no entry — its `why` is the question declared beside its "
            "SQL in src/mva/warehouse/analysis.py. Every other table needs one, and the "
            "columns need a sentence each in src/mva/viz/catalog_columns_ingest.py or "
            "catalog_columns_results.py.")


def test_the_gate_would_actually_catch_a_new_table(monkeypatch):
    """The gate is only worth having if an undescribed table trips it."""
    monkeypatch.setitem(semantics.NOTES, "brand_new_table", "somebody just added this")
    gaps = semantics.undescribed()
    assert gaps["brand_new_table"] == "mva.warehouse.catalog.NOTES"


def test_declared_tables_names_where_each_name_came_from():
    where = semantics.declared_tables()
    assert where["variants_raw"] == "mva.warehouse.annotate.RAW_TABLE"
    assert where["gnomad_constraint"] == "mva.warehouse.reference.datasets()"
    assert where["contig_density"] == "mva.warehouse.analysis.DERIVATIONS"


def test_every_derivation_and_every_ledger_is_covered():
    """The two families that grow: one per analysis, one per hand-written record."""
    declared = semantics.declared_tables()
    for item in DERIVATIONS:
        assert item.name in declared
    for ledger in ("source_files", "data_lineage", "probe_ledger", "derivation_runs",
                   "hypotheses", "evidence"):
        assert ledger in declared


# ── how a table is created ───────────────────────────────────────────────────────────

def test_a_derivations_why_is_its_declared_question_not_a_restatement():
    """Copying the question into the registry would create a second version to drift."""
    found = semantics.facts("contig_density")
    declared = next(d for d in DERIVATIONS if d.name == "contig_density")
    assert found.why == declared.question
    assert "pg-derive" in found.created_by


def test_a_staged_table_names_both_halves_of_the_verb_that_writes_it():
    """`stage` writes Parquet locally; `pg-ingest` loads it. Neither alone is the answer."""
    found = semantics.facts("contig_counts")
    assert found.created_by == "mva-warehouse stage + pg-ingest"


def test_an_append_only_table_says_so_where_a_replaced_one_does_not():
    """What a re-run does to the table is the fact a reader needs before re-running."""
    assert semantics.facts("data_lineage").created_by.startswith("append-only ledger")
    assert "replaces the table wholesale" in semantics.facts("variants_raw").created_by
    assert "rebuilt from scratch" in semantics.facts("contig_density").created_by


def test_an_unknown_table_is_none_rather_than_a_guess():
    assert semantics.facts("something_nobody_added") is None


# ── what a column means ──────────────────────────────────────────────────────────────

def test_the_shared_map_covers_the_columns_that_recur_across_tables():
    """One entry per recurring column, so a new table carrying them needs no new entry."""
    absent = [name for name in RECURRING if name not in SHARED]
    assert absent == [], f"shared columns with no meaning: {absent}"


def test_a_recurring_column_resolves_in_every_table_that_carries_it():
    for table in ("variants_raw", "panel_annotations", "clinvar_panel",
                  "panel_candidates", "variant_density_bins"):
        assert meaning(table, "chrom")


def test_a_table_specific_meaning_beats_the_shared_one():
    """`length` is the contig's size in one table and the indel's in another."""
    assert "contig" in meaning("contig_counts", "length")
    assert "deletion" in meaning("stats_idd", "length")
    assert "length" not in SHARED


def test_a_column_nothing_describes_is_none():
    assert meaning("variants_raw", "a_column_that_does_not_exist") is None


def test_no_meaning_is_empty_and_none_writes_a_genomic_position():
    """A meaning describes what a column holds; it never carries a value from the data."""
    for text in list(SHARED.values()) + list(BY_TABLE.values()):
        assert text.strip()
        assert text[-1] in ".)"
