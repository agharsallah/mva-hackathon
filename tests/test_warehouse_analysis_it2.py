"""Step 2's SQL, executed against tables small enough to reason about by hand.

The derivations in :mod:`mva.warehouse.analysis_it2` and
:mod:`mva.warehouse.analysis_it2_sv` decide three things the step's verdicts rest on:

* **the biallelic rule** — two rare protein-altering heterozygous alleles, or one such
  allele homozygous, and nothing else counts (H016);
* **filter symmetry** — targets and decoys go through exactly the same filter, because a
  null that is scored more leniently than the thing it is a null for is not a null (H020);
* **two boundaries** — ``MIN_SV_LENGTH`` and ``MIN_BAITED_SPAN``, the constants that
  separate a structural variant from an indel and a real event from a baited-alignment
  artefact (H023).

Each is tested by running the real SQL, unmodified, over a handful of rows in an in-memory
DuckDB — the same hermetic pattern the other warehouse tests use, so no Postgres and no
patient data is needed. ``resolve`` points both the source and the result placeholder at
one schema; the query text is otherwise exactly what runs in production.

**What this does not test.** These are fixtures, not the child's data: they prove the rule
the SQL implements, never a number in the report. A regression here means the rule changed;
a number in `docs/iteration2/step-2/` is only ever evidence from an executed run.
"""

import duckdb
import pytest

from mva.warehouse.analysis_it2 import IT2_READ_PAIRS, IT2_SCORED_PAIRS
from mva.warehouse.analysis_it2_sv import (
    IT2_SV_CONSENSUS,
    IT2_SV_LEADS,
    MIN_BAITED_SPAN,
    MIN_SV_LENGTH,
)
from mva.warehouse.derivation import resolve

#: One contig, one place, for every fixture. A position here is an arbitrary small integer
#: chosen for arithmetic that is easy to check, and is not a coordinate of anybody.
CONTIG = "T1"

SCHEMA = """
CREATE TABLE it2_read_alleles (
    caller VARCHAR, chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR,
    genotype VARCHAR, filters VARCHAR
);
CREATE TABLE coding_annotations (
    chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR, gene VARCHAR,
    consequence VARCHAR, impact VARCHAR, gnomad_af DOUBLE, clin_sig VARCHAR
);
CREATE TABLE it2_read_annotations (
    chrom VARCHAR, pos BIGINT, ref VARCHAR, alt VARCHAR, gene VARCHAR,
    consequence VARCHAR, impact VARCHAR, gnomad_af DOUBLE, clin_sig VARCHAR
);
CREATE TABLE coding_regions (chrom VARCHAR, start BIGINT, "end" BIGINT, gene VARCHAR);
CREATE TABLE it2_bait_density (symbol VARCHAR, tier VARCHAR, density DOUBLE);
CREATE TABLE it2_exon_depth (chrom VARCHAR, start BIGINT, "end" BIGINT,
                             symbol VARCHAR, mean_depth DOUBLE);
CREATE TABLE it2_sv_calls (
    caller VARCHAR, method_class VARCHAR, chrom VARCHAR, pos BIGINT, end_pos BIGINT,
    sv_type VARCHAR, sv_len BIGINT, filters VARCHAR, genotype VARCHAR,
    bait_edge BOOLEAN, precision_prior DOUBLE
);
"""


@pytest.fixture
def db():
    connection = duckdb.connect()
    connection.execute(SCHEMA)
    return connection


def run(connection, derivation):
    """Execute a derivation against the one-schema fixture database."""
    sql = resolve(derivation.sql, "main", "main")
    cursor = connection.execute(sql)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def add_gene(
    connection, symbol, tier, *, exon=(1_000, 2_000), density=0.9, depth=40.0, baited=True
):
    """A gene: one coding interval, a bait density, and by default one baited interval.

    ``baited=False`` leaves ``it2_exon_depth`` empty for the gene, which is what the
    structural-variant tests need — that table is also what says where the bait reached,
    so a test about baited span has to place those intervals itself.
    """
    connection.execute(
        "INSERT INTO coding_regions VALUES (?, ?, ?, ?)", [CONTIG, exon[0], exon[1], symbol]
    )
    connection.execute("INSERT INTO it2_bait_density VALUES (?, ?, ?)", [symbol, tier, density])
    if baited:
        connection.execute(
            "INSERT INTO it2_exon_depth VALUES (?, ?, ?, ?, ?)",
            [CONTIG, exon[0], exon[1], symbol, depth],
        )


def add_allele(
    connection,
    gene,
    pos,
    *,
    genotype="0/1",
    impact="HIGH",
    gnomad_af=0.0001,
    clin_sig="",
    novel=False,
):
    """One allele, called by one caller, annotated in one of the two annotation tables."""
    connection.execute(
        "INSERT INTO it2_read_alleles VALUES ('freebayes', ?, ?, 'A', 'G', ?, '')",
        [CONTIG, pos, genotype],
    )
    table = "it2_read_annotations" if novel else "coding_annotations"
    connection.execute(
        f"INSERT INTO {table} VALUES (?, ?, 'A', 'G', ?, 'missense_variant', ?, ?, ?)",
        [CONTIG, pos, gene, impact, gnomad_af, clin_sig],
    )


def row_for(rows, symbol):
    return next(row for row in rows if row["symbol"] == symbol)


# --------------------------------------------------------------------------- biallelic


@pytest.mark.parametrize(
    ("genotypes", "expected"),
    [
        (["0/1"], False),
        (["0/1", "0/1"], True),
        (["0|1", "1|0"], True),
        (["1/1"], True),
        (["0/0", "0/0"], False),
    ],
    ids=["one-het", "two-hets", "two-phased-hets", "one-hom-alt", "no-alt-genotype"],
)
def test_the_biallelic_rule_is_two_rare_hets_or_one_rare_hom_alt(db, genotypes, expected):
    add_gene(db, "GENEA", "core")
    for index, genotype in enumerate(genotypes):
        add_allele(db, "GENEA", 1_100 + index * 10, genotype=genotype)
    assert row_for(run(db, IT2_SCORED_PAIRS), "GENEA")["biallelic"] is expected


def test_two_hets_in_different_genes_are_not_a_biallelic_candidate(db):
    """The rule is per gene. Two broken genes is not two broken copies of one gene."""
    add_gene(db, "GENEA", "core", exon=(1_000, 2_000))
    add_gene(db, "GENEB", "core", exon=(3_000, 4_000))
    add_allele(db, "GENEA", 1_100)
    add_allele(db, "GENEB", 3_100)
    rows = run(db, IT2_SCORED_PAIRS)
    assert [row["biallelic"] for row in rows] == [False, False]


def test_an_allele_only_the_read_callers_saw_still_counts(db):
    """The bug entry 090 found: an allele with no row in the delivered callset's
    annotation table was invisible to the score, so the route could only rediscover what
    the vendor already reported."""
    add_gene(db, "GENEA", "core")
    add_allele(db, "GENEA", 1_100, novel=False)
    add_allele(db, "GENEA", 1_110, novel=True)
    row = row_for(run(db, IT2_SCORED_PAIRS), "GENEA")
    assert row["biallelic"] is True
    assert row["novel_qualifying"] == 1


# ------------------------------------------------------------------- filter symmetry


def _identical_target_and_decoy(connection, **allele):
    add_gene(connection, "TARGET", "core", exon=(1_000, 2_000))
    add_gene(connection, "DECOY", "decoy", exon=(3_000, 4_000))
    for gene, base in (("TARGET", 1_100), ("DECOY", 3_100)):
        add_allele(connection, gene, base, **allele)
        add_allele(connection, gene, base + 10, **allele)


COMPARED = (
    "rare_het",
    "rare_hom_alt",
    "truncating",
    "clinvar_flagged",
    "novel_qualifying",
    "biallelic",
    "unannotated_alleles",
)


@pytest.mark.parametrize(
    "allele",
    [
        {},
        {"impact": "MODERATE"},
        {"impact": "LOW"},
        {"gnomad_af": 0.5},
        {"gnomad_af": None},
        {"genotype": "1/1"},
        {"clin_sig": "pathogenic"},
        {"novel": True},
    ],
    ids=["high", "moderate", "low", "common", "no-af", "hom-alt", "clinvar", "novel"],
)
def test_a_target_and_a_decoy_with_identical_alleles_score_identically(db, allele):
    """H020's null is only a null if the two sets meet the same SQL. The tier column is
    carried through to the output and is never read by the filter — this is that claim,
    executed rather than asserted about the query text."""
    _identical_target_and_decoy(db, **allele)
    rows = run(db, IT2_SCORED_PAIRS)
    target, decoy = row_for(rows, "TARGET"), row_for(rows, "DECOY")
    assert {key: target[key] for key in COMPARED} == {key: decoy[key] for key in COMPARED}
    assert (target["tier"], decoy["tier"]) == ("core", "decoy")


@pytest.mark.parametrize("derivation", [IT2_SCORED_PAIRS, IT2_READ_PAIRS])
def test_no_filtering_stage_mentions_the_tier(derivation):
    """A structural companion to the row test: ``tier`` may appear only where the result is
    assembled, never inside a WHERE or a JOIN that could select on it."""
    body = derivation.sql
    assert body.count("tier") == body.count("d.tier AS tier") + body.count("d.tier,")


@pytest.mark.parametrize(
    ("allele", "qualifies"),
    [
        ({"impact": "HIGH", "gnomad_af": 0.0001}, True),
        ({"impact": "MODERATE", "gnomad_af": 0.0001}, True),
        ({"impact": "LOW", "gnomad_af": 0.0001}, False),
        ({"impact": "MODIFIER", "gnomad_af": 0.0001}, False),
        ({"impact": "HIGH", "gnomad_af": 0.0099}, True),
        ({"impact": "HIGH", "gnomad_af": 0.01}, False),
        ({"impact": "HIGH", "gnomad_af": None}, True),
    ],
    ids=["high", "moderate", "low", "modifier", "just-rare", "at-the-cut", "unknown-af"],
)
def test_the_rarity_and_consequence_filter_boundaries(db, allele, qualifies):
    """``gnomad_af < 0.01`` is strict, and an absent frequency is treated as rare — a
    variant nobody has catalogued is a candidate, not a common variant."""
    add_gene(db, "GENEA", "core")
    add_allele(db, "GENEA", 1_100, **allele)
    add_allele(db, "GENEA", 1_110, **allele)
    assert row_for(run(db, IT2_SCORED_PAIRS), "GENEA")["biallelic"] is qualifies


def test_the_unfiltered_derivation_counts_what_the_filtered_one_rejects(db):
    """C1: without the rarity and consequence filter the same alleles are biallelic. The
    two derivations disagreeing on the same rows is the finding, not a bug."""
    add_gene(db, "GENEA", "core")
    add_allele(db, "GENEA", 1_100, impact="LOW", gnomad_af=0.5)
    add_allele(db, "GENEA", 1_110, impact="LOW", gnomad_af=0.5)
    assert row_for(run(db, IT2_READ_PAIRS), "GENEA")["biallelic"] is True
    assert row_for(run(db, IT2_SCORED_PAIRS), "GENEA")["biallelic"] is False


# ------------------------------------------------------------------ the two boundaries


def add_sv(connection, caller, method_class, *, pos, end_pos, sv_type="DEL", bait_edge=False):
    connection.execute(
        "INSERT INTO it2_sv_calls VALUES (?, ?, ?, ?, ?, ?, ?, 'PASS', '0/1', ?, 0.74)",
        [caller, method_class, CONTIG, pos, end_pos, sv_type, -(end_pos - pos), bait_edge],
    )


def add_consensus_pair(connection, *, pos, end_pos, sv_type="DEL"):
    """The same event from two different method classes — what a consensus call is."""
    add_sv(connection, "delly", "read-pair", pos=pos, end_pos=end_pos, sv_type=sv_type)
    add_sv(connection, "dysgu", "assembly", pos=pos, end_pos=end_pos, sv_type=sv_type)


def add_baited(connection, start, end):
    connection.execute(
        "INSERT INTO it2_exon_depth VALUES (?, ?, ?, 'GENEA', 40.0)", [CONTIG, start, end]
    )


@pytest.mark.parametrize(
    ("length", "kept"),
    [(MIN_SV_LENGTH - 1, False), (MIN_SV_LENGTH, True), (MIN_SV_LENGTH + 1, True)],
    ids=["below", "at-the-boundary", "above"],
)
def test_min_sv_length_is_inclusive_at_fifty_bases(db, length, kept):
    """Below 50 bp an event is an indel the small-variant callers already counted, and
    letting it into the consensus would let H023 be refuted by a non-SV."""
    add_consensus_pair(db, pos=1_000, end_pos=1_000 + length)
    add_baited(db, 0, 10_000)
    assert bool(run(db, IT2_SV_CONSENSUS)) is kept


@pytest.mark.parametrize(
    ("baited_share", "spans_unbaited"),
    [(0.25, True), (MIN_BAITED_SPAN - 0.01, True), (MIN_BAITED_SPAN, False), (1.0, False)],
    ids=["quarter", "just-below", "at-the-boundary", "fully-baited"],
)
def test_min_baited_span_flags_the_island_spanning_artefact(db, baited_share, spans_unbaited):
    """A call whose span is mostly unbaited is the emptiness between coverage islands being
    reported as one event — the class that produced a 13 Mb deletion in a living child."""
    length = 1_000
    add_consensus_pair(db, pos=1_000, end_pos=1_000 + length)
    add_baited(db, 1_000, 1_000 + int(length * baited_share))
    rows = run(db, IT2_SV_CONSENSUS)
    assert [row["spans_unbaited"] for row in rows] == [spans_unbaited]


@pytest.mark.parametrize(
    ("baited_share", "reaches_a_lead"),
    [(MIN_BAITED_SPAN - 0.01, False), (MIN_BAITED_SPAN, True)],
    ids=["just-below", "at-the-boundary"],
)
def test_the_lead_query_admits_a_call_exactly_at_the_baited_span_boundary(
    db, baited_share, reaches_a_lead
):
    """``it2_sv_leads`` keeps ``baited_share >= MIN_BAITED_SPAN`` where the consensus table
    flags ``< MIN_BAITED_SPAN``. The two must agree exactly at the boundary or a call can be
    a lead and an artefact at once."""
    add_gene(db, "GENEA", "core", exon=(1_000, 2_200), baited=False)
    add_allele(db, "GENEA", 1_100)
    add_allele(db, "GENEA", 1_110)
    db.execute("CREATE TABLE it2_scored_pairs AS " + resolve(IT2_SCORED_PAIRS.sql, "main", "main"))
    length = 1_000
    add_consensus_pair(db, pos=1_000, end_pos=1_000 + length)
    add_baited(db, 1_000, 1_000 + int(length * baited_share))
    assert bool(run(db, IT2_SV_LEADS)) is reaches_a_lead
