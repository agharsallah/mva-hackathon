"""The read store, end to end, on synthetic reads (no patient data — repo rule).

One synthetic delivery is built per test session: an R1/R2 pair with realistic NovaSeq
headers, 4-level quality strings, and one planted 31-mer. Every layer is exercised
against it: engines, conversion, the describing tables, verification, and the scan verbs.
"""

import gzip
import random
import shutil
import subprocess

import pytest

from mva.reads import bench, scan, schema, store, verify
from mva.reads.convert import convert_file, peek
from mva.reads.engines import biobear_available

READS = 5_000
PLANTED = "AGAGATAGGAAGCGGGACGAGGAAAGGAACA"  # 31-mer planted in read #123 of R1
QUALITY_CHARS = "F,:#"


def _record(rng, lane, tile, x, y, read_num, index, sequence=None):
    sequence = sequence or "".join(rng.choice("ACGT") for _ in range(149))
    quality = "".join(rng.choices(QUALITY_CHARS, weights=[93, 3, 3, 1], k=len(sequence)))
    name = f"@A01973:164:HGWCNDSX7:{lane}:{tile}:{x}:{y} {read_num}:N:0:{index}"
    return f"{name}\n{sequence}\n+\n{quality}\n"


def _write_fastq(path, read_num, rng):
    with gzip.open(path, "wt") as handle:
        for i in range(READS):
            tile = 1101 + (i % 2)
            planted = PLANTED + "".join(rng.choice("ACGT") for _ in range(118))
            handle.write(_record(
                rng, lane=1, tile=tile, x=1000 + i, y=2000 + i, read_num=read_num,
                index="GTGACGGAGC+NGGACCGCCA",
                sequence=planted if (read_num == 1 and i == 123) else None))


@pytest.fixture(scope="session")
def delivery(tmp_path_factory):
    directory = tmp_path_factory.mktemp("delivery")
    rng = random.Random(7)
    for read_num in (1, 2):
        _write_fastq(directory / f"WGS_TEST_S16_L001_R{read_num}_001.fastq.gz",
                     read_num, rng)
    return directory


@pytest.fixture(scope="session")
def built(delivery, tmp_path_factory):
    """The store built once with the pipe engine; most tests read from it."""
    staging = tmp_path_factory.mktemp("staging")
    results = store.convert_all(store.discover(delivery), staging,
                                engine="pipe", jobs=2, report=lambda *_: None)
    store.write_tables(staging, results)
    return staging / schema.PREFIX, results


def test_lane_and_read_parses_delivered_names():
    assert schema.lane_and_read(
        "WGS_EX2312012_HGWCNDSX7_S16_L003_R2_001.fastq.gz") == (3, 2)
    with pytest.raises(ValueError):
        schema.lane_and_read("random.txt")


def test_peek_reads_the_run_constants(delivery):
    facts = peek(store.discover(delivery)[0])
    assert (facts.instrument, facts.run, facts.flowcell) == ("A01973", "164", "HGWCNDSX7")
    assert (facts.lane, facts.read_num, facts.read_length) == (1, 1, 149)


def test_pipe_engine_converts_and_shards(delivery, tmp_path):
    fastq = store.discover(delivery)[0]
    done = convert_file(fastq, tmp_path, engine="pipe",
                        row_group_size=2048, row_groups_per_file=1)
    assert done.rows == READS
    assert len(done.shards) == 3  # ceil(5000 / 2048) row groups, one per file
    assert done.out_dir.name == "read=1" and done.out_dir.parent.name == "lane=1"


@pytest.mark.skipif(not biobear_available(), reason="biobear not installed")
def test_biobear_engine_agrees_with_pipe(delivery, built, tmp_path):
    import duckdb

    fastq = store.discover(delivery)[0]
    done = convert_file(fastq, tmp_path, engine="biobear")
    assert done.rows == READS
    root, _ = built
    connection = duckdb.connect()
    mismatch = connection.execute(f"""
        SELECT count(*) FROM
            read_parquet('{tmp_path}/{schema.PREFIX}/lane=1/read=1/*.parquet') b
        FULL JOIN (SELECT * FROM read_parquet('{root}/lane=1/read=1/*.parquet')) p
        USING (tile, x, y)
        WHERE b.sequence IS DISTINCT FROM p.sequence
           OR b.quality IS DISTINCT FROM p.quality
           OR b.is_filtered IS DISTINCT FROM p.is_filtered
           OR b.index_pair IS DISTINCT FROM p.index_pair
    """).fetchone()[0]
    assert mismatch == 0


def test_verify_passes_on_honest_store(delivery, built):
    root, _ = built
    report = verify.run(str(root), store.discover(delivery),
                        expected_total=2 * READS)
    assert report.ok, report.failures
    assert report.total_rows == 2 * READS


def test_verify_catches_missing_rows(delivery, built, tmp_path):
    root, _ = built
    broken = tmp_path / "broken"
    shutil.copytree(root, broken)
    shard = next((broken / "lane=1" / "read=1").glob("part-*.parquet"))
    import duckdb
    duckdb.connect().execute(f"""
        COPY (SELECT * FROM read_parquet('{shard}') LIMIT 10)
        TO '{shard}' (FORMAT parquet)""")
    report = verify.run(str(broken), [], deep=False)
    assert not report.ok


def test_scan_finds_planted_kmer_both_strands(built):
    import duckdb

    root, _ = built
    connection = duckdb.connect()
    hits = scan.kmer(connection, str(root), PLANTED)
    assert len(hits) == 1 and hits[0].strand == "+" and hits[0].position == 1
    hits = scan.kmer(connection, str(root), scan.reverse_complement(PLANTED))
    assert len(hits) == 1 and hits[0].strand == "-"


def test_qc_shape(built):
    import duckdb

    root, _ = built
    rows = scan.qc(duckdb.connect(), str(root))
    assert [(r[0], r[1], r[2]) for r in rows] == [(1, 1, READS), (1, 2, READS)]


def test_round_trip_rebuilds_exact_name(delivery, built):
    fastq = store.discover(delivery)[0]
    facts = peek(fastq)
    with gzip.open(fastq, "rt") as handle:
        name = handle.readline().rstrip("\n")
    assert facts.rebuild_name(1101, 1000, 2000, False,
                              "GTGACGGAGC+NGGACCGCCA") == name


def test_bench_race_reports_all_engines(delivery):
    timings = bench.race(store.discover(delivery)[0], reads=500,
                         report=lambda *_: None)
    finished = [t for t in timings if not t.error]
    assert finished, [t.error for t in timings]
    assert all(t.rows == 500 for t in finished)
    assert bench.winner(timings).engine in {"pipe", "biobear"}


def test_manifest_and_runs_tables(built):
    import duckdb

    root, results = built
    connection = duckdb.connect()
    runs = connection.execute(f"SELECT source, reads FROM '{root}/runs.parquet' "
                              f"ORDER BY read_num").fetchall()
    assert [r[1] for r in runs] == [READS, READS]
    total = connection.execute(
        f"SELECT sum(rows) FROM '{root}/manifest.parquet'").fetchone()[0]
    assert total == 2 * READS
    assert all(len(r.shards) >= 1 for r in results)
