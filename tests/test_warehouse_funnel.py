"""The candidate funnel derivation, against a miniature warehouse built in memory.

Hermetic: no database, no network. The real SQL from
:mod:`mva.warehouse.analysis_funnel` runs against a DuckDB schema of a dozen synthetic
rows chosen so that **every stage drops exactly one thing for exactly one reason** — a
homozygous call, a common allele, a filtered record, a MODIFIER consequence, an annotation
with no callset record, a contig outside the panel. If a stage stops filtering, or starts
filtering something it should not, one of the counts below moves.

Positions here are fabricated. No real patient coordinate appears in this repository.
"""

import duckdb
import pytest

from mva.warehouse.analysis import DERIVATIONS, by_name
from mva.warehouse.analysis_funnel import CANDIDATE_FUNNEL, het
from mva.warehouse.derivation import resolve


@pytest.fixture()
def warehouse():
    """The three tables the funnel reads, sized so each stage's drop is attributable.

    ``variants_raw`` is all-text with a per-record ``FORMAT``, exactly as the delivery is.
    Row by row: a plain heterozygote, a multi-allelic ``1/2``, a homozygote, a common
    allele, a record the caller filtered, a record whose ``FORMAT`` does not start with
    ``GT``, two records off the panel contig, a *phased* heterozygote and a no-call.
    """
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA src")
    connection.execute("""
        CREATE TABLE src.variants_raw AS SELECT * FROM (VALUES
            ('15', '100',  'G', 'A',   'PASS',    'GT:AD:DP', '0/1:20,18:38'),
            -- multi-allelic: ALT comma-packed, two annotations point at this one record
            ('15', '200',  'C', 'T,G', 'PASS',    'GT:AD:DP', '1/2:5,7,9:21'),
            ('15', '300',  'T', 'C',   'PASS',    'GT:AD:DP', '1/1:1,37:38'),
            ('15', '400',  'A', 'G',   'PASS',    'GT:AD:DP', '0/1:19,17:36'),
            ('15', '500',  'A', 'T',   'LowQual', 'GT:AD:DP', '0/1:9,8:17'),
            -- FORMAT in a different order: assuming GT is first would read the depth
            ('15', '600',  'G', 'C',   'PASS',    'DP:GT:AD', '30:0/1:15,15'),
            ('7',  '700',  'A', 'G',   'PASS',    'GT:AD:DP', '0/1:11,12:23'),
            ('7',  '800',  'A', 'G',   'MQ40',    'GT:AD:DP', '1/1:0,30:30'),
            -- phased: still a heterozygote
            ('15', '1000', 'A', 'C',   'PASS',    'GT:AD:DP', '0|1:12,13:25'),
            ('7',  '1100', 'A', 'C',   'PASS',    'GT:AD:DP', './.:0,0:0'))
        AS t(chrom, pos, ref, alt, filter, format, sample_call);

        CREATE TABLE src.panel_variant_counts AS SELECT * FROM (VALUES
            ('GENE1', 'chr15', 90,  250, 3, 3),
            ('GENE2', 'chr15', 290, 650, 4, 3))
        AS t(gene, chrom, start, "end", n_all, n_pass);

        CREATE TABLE src.panel_annotations AS SELECT * FROM (VALUES
            ('15', 100,  'G', 'A', 'GENE1', 'stop_gained',      'HIGH',     NULL::DOUBLE),
            ('15', 200,  'C', 'T', 'GENE1', 'missense_variant', 'MODERATE', 0.001),
            ('15', 200,  'C', 'G', 'GENE1', 'missense_variant', 'MODERATE', 0.002),
            ('15', 300,  'T', 'C', 'GENE2', 'stop_gained',      'HIGH',     NULL),
            ('15', 400,  'A', 'G', 'GENE2', 'missense_variant', 'MODERATE', 0.4),
            ('15', 500,  'A', 'T', 'GENE2', 'stop_gained',      'HIGH',     NULL),
            ('15', 600,  'G', 'C', 'GENE2', 'intron_variant',   'MODIFIER', NULL),
            -- annotated, but no callset record carries it
            ('15', 900,  'A', 'G', 'GENE2', 'stop_gained',      'HIGH',     NULL))
        AS t(chrom, pos, ref, alt, gene, consequence, impact, gnomad_af);
    """)
    yield connection
    connection.close()


def funnel(connection) -> dict[int, dict]:
    """Run the real derivation SQL and index its rows by stage number."""
    relation = connection.sql(resolve(CANDIDATE_FUNNEL.sql, "src"))
    columns = relation.columns
    return {row[0]: dict(zip(columns, row, strict=True)) for row in relation.fetchall()}


# ── the heterozygosity predicate ─────────────────────────────────────────────────────

#: Every genotype shape the predicate has to bucket, with whether it is a heterozygote.
GT_CASES = [
    ("0/1", True),
    ("1/0", True),
    ("1/2", True),
    ("0/2", True),
    ("2/3", True),
    ("0|1", True),  # phased, after the caller normalises the separator
    ("0/0", False),
    ("1/1", False),
    ("2/2", False),
    ("./.", False),
    ("0/.", False),
    ("./1", False),
    ("1", False),
    ("", False),
]


@pytest.mark.parametrize("gt,expected", GT_CASES)
def test_the_het_predicate_is_two_different_real_alleles(gt, expected):
    """Not `gt IN ('0/1','1/2')`: a callset emitting 0/2 or 2/3 must still be read right,
    and a homozygote can never be half of a compound heterozygote."""
    normalised = gt.replace("|", "/")
    got = duckdb.sql(f"SELECT ({het('gt')}) FROM (SELECT ? AS gt)", params=[normalised]).fetchone()[
        0
    ]
    assert bool(got) is expected


# ── the nine stages ──────────────────────────────────────────────────────────────────

#: ``stage_no -> (n, of_previous_pct)`` for the fixture above. Every number is arithmetic
#: over the rows in :func:`warehouse`, not a snapshot of a previous run.
EXPECTED = {
    1: (10, None),  # every record
    2: (8, 80.0),  # LowQual and MQ40 drop out
    3: (6, 75.0),  # the two homozygotes and the no-call drop out
    4: (6, None),  # scope change: PASS records inside the two panel intervals
    5: (6, 100.0),  # 8 annotated: 1 matches no record, 1 matches only a filtered one
    6: (5, 83.3333),  # AF 0.4 is common
    7: (4, 80.0),  # MODIFIER cannot change the protein
    8: (3, 75.0),  # the homozygote leaves; the rest are all in GENE1
    9: (3, None),  # 3 alleles in one gene = 3 within-gene pairings
}


@pytest.mark.parametrize("stage_no,expected", sorted(EXPECTED.items()))
def test_each_stage_counts_what_it_claims(warehouse, stage_no, expected):
    row = funnel(warehouse)[stage_no]
    n, share = expected
    assert row["n"] == n
    if share is None:
        assert row["of_previous_pct"] is None
    else:
        assert float(row["of_previous_pct"]) == pytest.approx(share, abs=1e-4)


def test_the_funnel_has_one_row_per_stage_in_order(warehouse):
    rows = funnel(warehouse)
    assert sorted(rows) == list(range(1, 10))
    assert all(rows[i]["stage"] for i in rows)


def test_the_scope_column_names_where_the_boundary_is(warehouse):
    rows = funnel(warehouse)
    assert [rows[i]["scope"] for i in sorted(rows)] == ["genome"] * 3 + ["panel"] * 6


def test_the_first_panel_stage_reports_no_share_of_the_row_above(warehouse):
    """It counts PASS records of every genotype, so it is not a subset of the het row —
    a percentage there would divide two different populations."""
    assert funnel(warehouse)[4]["of_previous_pct"] is None
    assert "SCOPE CHANGE" in funnel(warehouse)[4]["note"]


def test_the_genome_stages_read_the_callset_not_a_summary_table(warehouse):
    """Stage 1 must be COUNT(*) over the records, so adding a record moves it."""
    warehouse.execute(
        "INSERT INTO src.variants_raw VALUES "
        "('15', '1200', 'A', 'G', 'PASS', 'GT:AD:DP', '0/1:5,5:10')"
    )
    assert funnel(warehouse)[1]["n"] == 11


def test_a_multiallelic_record_is_matched_by_membership_not_substring(warehouse):
    """`200` is `C -> T,G` in one record and two annotations ask about it separately.
    A substring test would also match an annotation the record does not carry."""
    warehouse.execute(
        "INSERT INTO src.panel_annotations VALUES "
        "('15', 200, 'C', 'TG', 'GENE1', 'missense_variant', "
        "'MODERATE', 0.001)"
    )
    assert funnel(warehouse)[5]["n"] == 6, "the invented TG allele must not join"


def test_a_homozygous_allele_survives_rarity_but_not_the_compound_het_shape(warehouse):
    """The stop_gained homozygote is rare and protein-altering, so it must be inside
    stage 7 and outside stage 8 — that is the whole point of the het requirement."""
    rows = funnel(warehouse)
    assert rows[7]["n"] - rows[8]["n"] == 1


def test_the_notes_carry_the_numbers_they_claim(warehouse):
    rows = funnel(warehouse)
    assert "1 gene(s) carrying at least two" in rows[8]["note"]
    assert "8 alleles are annotated in total" in rows[5]["note"]
    assert "1 match no callset record" in rows[5]["note"]
    assert "1 matched only a filtered one" in rows[5]["note"]


def test_the_pair_count_is_every_within_gene_pairing(warehouse):
    """3 surviving alleles in one gene is 3 pairs, not 3 alleles carried forward — and a
    fourth would make 6, which is why the last stage is allowed to widen."""
    warehouse.execute(
        "INSERT INTO src.variants_raw VALUES "
        "('15', '150', 'A', 'G', 'PASS', 'GT:AD:DP', '0/1:5,5:10')"
    )
    warehouse.execute(
        "INSERT INTO src.panel_annotations VALUES "
        "('15', 150, 'A', 'G', 'GENE1', 'stop_gained', 'HIGH', NULL)"
    )
    rows = funnel(warehouse)
    assert rows[8]["n"] == 4 and rows[9]["n"] == 6


def test_a_callset_with_no_surviving_pair_reports_zero_not_null(warehouse):
    """An empty result is a finding. It must not arrive as a NULL a chart renders blank."""
    warehouse.execute("DELETE FROM src.panel_annotations WHERE gene = 'GENE1'")
    rows = funnel(warehouse)
    assert rows[8]["n"] == 0 and rows[9]["n"] == 0


def test_the_funnel_is_in_the_one_registry(warehouse):
    assert by_name("candidate_funnel") is CANDIDATE_FUNNEL
    assert CANDIDATE_FUNNEL in DERIVATIONS


def test_the_derivation_declares_every_table_its_sql_reads():
    for table in ("variants_raw", "panel_variant_counts", "panel_annotations"):
        assert table in CANDIDATE_FUNNEL.depends_on


def test_the_declared_question_names_the_scope_limit_rather_than_implying_a_ranking():
    """The question ships in the catalogue and in the API's ``/docs``. Anyone reading it
    must learn that six of the nine stages are panel-only before they read a number."""
    question = CANDIDATE_FUNNEL.question
    assert "panel" in question and "only" in question
    assert "NULL" in question, "the null convention has to be stated where it is declared"
