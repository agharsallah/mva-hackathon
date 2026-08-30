"""The two conversion engines, behind one contract.

An engine turns a ``.fastq.gz`` into a DuckDB view named by the caller with exactly three
columns — ``header`` (name line, ``@`` stripped), ``sequence``, ``quality`` — and nothing
else. Everything downstream (projection, sharding, verification) is engine-agnostic, so
the bake-off swaps engines without touching the rest of the pipeline.

**pipe** — no per-record Python at all. A decompressor streams into ``paste - - - -``,
which folds the four-line FASTQ record into one tab-separated row (FASTQ bodies never
contain tabs), and DuckDB's CSV reader consumes the FIFO. The decompressor is whichever of
``igzip`` (ISA-L, fastest), ``pigz`` or ``gzip`` is installed — gzip is a single
compressed stream so the win is a faster codec and pipeline overlap, not sharding.

**biobear** — a Rust FASTQ reader (the exon engine) that emits Arrow record batches;
DuckDB scans them zero-copy. Optional dependency: if ``import biobear`` fails the engine
reports itself unavailable rather than breaking the module.
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

    Single-consumption: both engines stream, so the view supports exactly one full
    read (the ``COPY`` that converts it). Query it twice and the second pass sees
    nothing — re-create the engine instead.
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


def biobear(connection, fastq: Path, view: str = "raw_reads") -> Raw:
    """The Rust reader → Arrow → DuckDB path."""
    import biobear as bb

    session = bb.new_session()
    reader = session.read_fastq_file(str(fastq)).to_arrow_record_batch_reader()
    names = set(reader.schema.names)
    # biobear splits the name line at the first space; rejoin to meet the contract.
    header = ("name || ' ' || coalesce(description, '')"
              if "description" in names else "name")
    quality = "quality_scores" if "quality_scores" in names else "quality"
    connection.register("biobear_reads", reader)
    connection.execute(f"""
        CREATE OR REPLACE VIEW {view} AS
        SELECT {header} AS header, sequence, {quality} AS quality FROM biobear_reads
    """)
    return Raw(view=view, _cleanup=[lambda: connection.unregister("biobear_reads")])


def biobear_available() -> bool:
    try:
        import biobear  # noqa: F401
        return True
    except ImportError:
        return False


#: Engine name → factory. The bake-off and the CLI both index into this.
ENGINES = {"pipe": pipe, "biobear": biobear}


def shlex_quote(value) -> str:
    import shlex
    return shlex.quote(str(value))
