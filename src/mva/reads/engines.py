"""The conversion engines, behind one contract.

An engine turns a ``.fastq.gz`` into a DuckDB view named by the caller with exactly three
columns — ``header`` (name line, ``@`` stripped), ``sequence``, ``quality`` — and nothing
else. Everything downstream (projection, sharding, verification) is engine-agnostic, so
engines can be raced against each other without touching the rest of the pipeline.

Three of them, none of which parses a record in Python:

**pipe** — no dependency at all. A decompressor streams into ``paste - - - -``, which
folds the four-line FASTQ record into one tab-separated row (FASTQ bodies never contain
tabs), and DuckDB's CSV reader consumes the FIFO. The decompressor is whichever of
``igzip`` (ISA-L, fastest), ``pigz`` or ``gzip`` is installed. This is the floor: it works
on a bare machine and is the fallback when a wheel will not build.

**oxbow** — Rust (``noodles``) reader that exposes the file as a PyArrow dataset; DuckDB
scans it in batches, so memory stays bounded regardless of file size.

**polars_bio** — Rust + DataFusion reader exposed as a Polars ``LazyFrame``, which DuckDB
picks up through its replacement scan.

Both third-party engines are optional: an import failure makes the engine report itself
unavailable rather than breaking the module, and ``pipe`` always remains.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

#: Decompressors in preference order; each is invoked as ``<name> -dc <file>``.
DECOMPRESSORS = ("igzip", "pigz", "gzip")


def find_decompressor() -> str:
    """The fastest installed gzip decompressor."""
    for name in DECOMPRESSORS:
        if shutil.which(name):
            return name
    raise RuntimeError("no gzip decompressor found (looked for: "
                       + ", ".join(DECOMPRESSORS) + ")")


@dataclass
class Raw:
    """A live raw-contract view plus whatever must stay alive while it is read.

    Single-consumption: every engine streams, so the view supports exactly one full read
    (the ``COPY`` that converts it). Query it twice and the second pass may see nothing —
    re-create the engine instead.
    """

    view: str
    _cleanup: list = field(default_factory=list)

    def close(self) -> None:
        for step in self._cleanup:
            step()
        self._cleanup.clear()

    def __enter__(self) -> "Raw":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def pipe(connection, fastq: Path, view: str = "raw_reads") -> Raw:
    """The decompressor → ``paste`` → FIFO → DuckDB CSV path."""
    decompressor = find_decompressor()
    workdir = tempfile.mkdtemp(prefix="mva-reads-")
    fifo = os.path.join(workdir, "reads.tsv")
    os.mkfifo(fifo)
    producer = subprocess.Popen(
        f"{decompressor} -dc {shlex_quote(fastq)} | paste - - - - > {shlex_quote(fifo)}",
        shell=True, stderr=subprocess.PIPE)
    connection.execute(f"""
        CREATE OR REPLACE VIEW {view} AS
        SELECT substr(column0, 2) AS header, column1 AS sequence, column3 AS quality
        FROM read_csv('{fifo}',
                      header=false, auto_detect=false, parallel=false,
                      delim='\t', quote='', escape='',
                      columns={{'column0':'VARCHAR','column1':'VARCHAR',
                                'column2':'VARCHAR','column3':'VARCHAR'}})
    """)

    def finish():
        code = producer.wait()
        stderr = producer.stderr.read().decode(errors="replace") if producer.stderr else ""
        shutil.rmtree(workdir, ignore_errors=True)
        if code != 0:
            raise RuntimeError(f"decompress pipeline failed ({code}): {stderr.strip()}")

    return Raw(view=view, _cleanup=[finish])


def oxbow(connection, fastq: Path, view: str = "raw_reads",
          batch_size: int = 131_072) -> Raw:
    """The ``noodles`` reader → PyArrow dataset → DuckDB path."""
    import oxbow as ox

    handle = ox.from_fastq(str(fastq), batch_size=batch_size)
    connection.register("oxbow_reads", handle.dataset())
    connection.execute(f"""
        CREATE OR REPLACE VIEW {view} AS
        SELECT name || ' ' || coalesce(description, '') AS header, sequence, quality
        FROM oxbow_reads
    """)
    return Raw(view=view, _cleanup=[lambda: connection.unregister("oxbow_reads")])


def polars_bio(connection, fastq: Path, view: str = "raw_reads") -> Raw:
    """The DataFusion reader → Polars ``LazyFrame`` → DuckDB path."""
    import polars_bio as pb

    frame = pb.scan_fastq(str(fastq))
    connection.register("polars_reads", frame)
    connection.execute(f"""
        CREATE OR REPLACE VIEW {view} AS
        SELECT name || ' ' || coalesce(description, '') AS header,
               sequence, quality_scores AS quality
        FROM polars_reads
    """)
    return Raw(view=view, _cleanup=[lambda: connection.unregister("polars_reads")])


def available(engine: str) -> bool:
    """Whether ``engine`` can run here — a missing wheel is a fact, not a failure."""
    module = {"oxbow": "oxbow", "polars_bio": "polars_bio"}.get(engine)
    if module is None:
        return True
    try:
        __import__(module)
        return True
    except ImportError:
        return False


#: Engine name → factory. The bake-off and the CLI both index into this.
ENGINES = {"pipe": pipe, "oxbow": oxbow, "polars_bio": polars_bio}


def shlex_quote(value) -> str:
    import shlex
    return shlex.quote(str(value))
