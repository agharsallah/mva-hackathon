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

from mva.reads import bench, engines, scan, schema, store, verify
from mva.reads import source as source_mod
from mva.reads.convert import convert_file, peek

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


@pytest.mark.parametrize("engine", ["oxbow", "polars_bio"])
def test_engines_agree_with_pipe(engine, delivery, built, tmp_path):
    """Every engine must produce byte-identical rows — the contract, enforced."""
    import duckdb

    if not engines.available(engine):
        pytest.skip(f"{engine} not installed")
    fastq = store.discover(delivery)[0]
    done = convert_file(fastq, tmp_path, engine=engine)
    assert done.rows == READS
    root, _ = built
    connection = duckdb.connect()
    mismatch = connection.execute(f"""
        SELECT count(*) FROM
            read_parquet('{tmp_path}/{schema.PREFIX}/lane=1/read=1/*.parquet') other
        FULL JOIN (SELECT * FROM read_parquet('{root}/lane=1/read=1/*.parquet')) reference
        USING (tile, x, y)
        WHERE other.sequence IS DISTINCT FROM reference.sequence
           OR other.quality IS DISTINCT FROM reference.quality
           OR other.is_filtered IS DISTINCT FROM reference.is_filtered
           OR other.index_pair IS DISTINCT FROM reference.index_pair
    """).fetchone()[0]
    assert mismatch == 0


def test_available_reports_missing_engine_without_raising(monkeypatch):
    assert engines.available("pipe")
    monkeypatch.setitem(engines.ENGINES, "nonexistent", None)
    assert engines.available("nonexistent")  # unknown names are not import-gated


def test_streams_flags_memory_growth():
    small = bench.Timing("x", 1_000, 1_000, 1.0, 0, peak_rss=100 * 2**20)
    flat = bench.Timing("x", 10_000, 10_000, 1.0, 0, peak_rss=110 * 2**20)
    grows = bench.Timing("x", 10_000, 10_000, 1.0, 0, peak_rss=1_000 * 2**20)
    assert bench.streams(small, flat)
    assert not bench.streams(small, grows)


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
    with gzip.open(fastq.path, "rt") as handle:
        name = handle.readline().rstrip("\n")
    assert facts.rebuild_name(1101, 1000, 2000, False,
                              "GTGACGGAGC+NGGACCGCCA") == name


def test_bench_race_reports_all_engines(delivery):
    timings = bench.race(store.discover(delivery)[0], reads=500,
                         report=lambda *_: None)
    assert {t.engine for t in timings} == set(engines.ENGINES)
    finished = [t for t in timings if t.ok]
    assert finished, [t.error for t in timings]
    assert all(t.rows == 500 for t in finished)
    assert bench.winner(timings).engine in engines.ENGINES


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


def test_machine_share_divides_the_box(monkeypatch):
    monkeypatch.setattr(store.os, "cpu_count", lambda: 16)
    threads, memory = store.machine_share(jobs=4)
    assert threads == 4
    assert memory.endswith("GB") and int(memory[:-2]) >= 1
    assert store.machine_share(jobs=1)[0] == 16


def test_memory_limit_is_applied(delivery, tmp_path):
    """A tight limit must not break a streaming conversion."""
    fastq = store.discover(delivery)[0]
    done = convert_file(fastq, tmp_path, engine="pipe", memory_limit="512MB")
    assert done.rows == READS


def test_minio_storage_directory_is_diagnosed(tmp_path):
    """The exact shape that produced an IndexError on the server."""
    fake = tmp_path / "objects"
    obj = fake / "WGS_TEST_S16_L001_R1_001.fastq.gz"
    (obj / "a1b2").mkdir(parents=True)
    (obj / "xl.meta").write_bytes(b"XL2 ")
    (obj / "a1b2" / "part.1").write_bytes(b"\x1f\x8b nonsense")
    with pytest.raises(source_mod.NotADelivery) as caught:
        source_mod.resolve(str(fake))
    message = str(caught.value)
    assert "MinIO's internal storage" in message
    assert "--source s3" in message


def test_empty_directory_says_what_it_looked_for(tmp_path):
    with pytest.raises(source_mod.NotADelivery, match="_L00"):
        source_mod.resolve(str(tmp_path))


def test_missing_directory_is_named(tmp_path):
    with pytest.raises(source_mod.NotADelivery, match="not a directory"):
        source_mod.resolve(str(tmp_path / "nope"))


def test_peek_rejects_a_file_that_is_not_gzip(tmp_path):
    path = tmp_path / "WGS_TEST_S16_L001_R1_001.fastq.gz"
    path.write_text("not gzip at all")
    with pytest.raises(ValueError, match="not readable as gzip"):
        peek(path)


def test_peek_rejects_gzip_that_is_not_fastq(tmp_path):
    path = tmp_path / "WGS_TEST_S16_L001_R1_001.fastq.gz"
    with gzip.open(path, "wt") as handle:
        handle.write("chr1\t100\tA\tG\n")
    with pytest.raises(ValueError, match="does not start with a FASTQ record"):
        peek(path)


def test_peek_rejects_an_unparseable_read_name(tmp_path):
    path = tmp_path / "WGS_TEST_S16_L001_R1_001.fastq.gz"
    with gzip.open(path, "wt") as handle:
        handle.write("@shortname\nACGT\n+\nFFFF\n")
    with pytest.raises(ValueError, match="Illumina 8-field form"):
        peek(path)


def _streamed(fastq):
    """The same reads, presented the way an object-store source is: no local path."""
    return source_mod.Source(name=fastq.name, path=None, size=fastq.size,
                             open_stream=fastq.open_stream)


def test_pipe_engine_converts_a_stream_only_source(delivery, tmp_path):
    """The s3:// case, exercised offline: only `pipe` can take a non-seekable stream."""
    done = convert_file(_streamed(store.discover(delivery)[0]), tmp_path, engine="pipe")
    assert done.rows == READS


@pytest.mark.parametrize("engine,message", [("oxbow", "path or an s3:// URL"),
                                            ("polars_bio", "needs a local file")])
def test_seeking_engines_refuse_a_stream_clearly(engine, message, delivery, tmp_path):
    """A reader that must seek says so, and names the engine that can cope."""
    if not engines.available(engine):
        pytest.skip(f"{engine} not installed")
    with pytest.raises(RuntimeError, match=message):
        convert_file(_streamed(store.discover(delivery)[0]), tmp_path, engine=engine)


def _range_server(directory):
    """A localhost HTTP server that honours `Range:` — as MinIO does, and as
    `http.server` does **not**. Without range support a reader silently falls back to
    re-reading from the beginning, so a test built on the stock handler would prove
    nothing about the object-store path."""
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            payload = (directory / self.path.lstrip("/")).read_bytes()
            requested = self.headers.get("Range")
            status, body = 200, payload
            if requested and requested.startswith("bytes="):
                start, _, end = requested[6:].partition("-")
                first = int(start or 0)
                last = int(end) if end else len(payload) - 1
                status, body = 206, payload[first:last + 1]
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range",
                                 f"bytes {first}-{first + len(body) - 1}/{len(payload)}")
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_oxbow_converts_over_http_range_requests(delivery, tmp_path):
    """The object-store path, proven without an object store.

    A presigned URL is an ordinary HTTP GET, so serving the same file over localhost
    exercises what oxbow does against MinIO: open a URL and seek inside it.
    """
    if not engines.available("oxbow"):
        pytest.skip("oxbow not installed")
    fastq = store.discover(delivery)[0]
    server = _range_server(fastq.path.parent)
    try:
        remote = source_mod.Source(
            name=fastq.name, path=None, size=fastq.size,
            url=f"http://127.0.0.1:{server.server_port}/{fastq.name}",
            open_stream=fastq.open_stream)
        done = convert_file(remote, tmp_path, engine="oxbow")
        assert done.rows == READS
    finally:
        server.shutdown()


def test_presigned_url_is_generated_for_the_right_object():
    calls = {}

    class FakeS3:
        def generate_presigned_url(self, operation, ExpiresIn, Params):
            calls.update(operation=operation, expires=ExpiresIn, params=Params)
            return "https://minio.example/mva/source/x.fastq.gz?sig=abc"

    url = source_mod.presigned_url(FakeS3(), "mva", "source/x.fastq.gz")
    assert calls["operation"] == "get_object"
    assert calls["params"] == {"Bucket": "mva", "Key": "source/x.fastq.gz"}
    assert calls["expires"] == source_mod.PRESIGN_SECONDS
    assert url.startswith("https://")
