"""Ask questions of the read store — the payoff for building it.

The headline verb is the **k-mer strike**: does an exact subsequence appear anywhere in
the reads, on either strand? A variant allele that is real must leave its surrounding
sequence in the raw reads; a 31-mer centred on it is specific enough that one hit is
signal. Reads are stored as they came off the machine, so the reverse strand is checked
by also searching the k-mer's reverse complement (reverse the string, swap A↔T and C↔G)
rather than by touching the data.

Everything here works identically over a local staging directory and over
``s3://…/reads`` — the caller supplies the root and, for S3, a connection that already
carries the store secret.
"""

from dataclasses import dataclass

#: DNA complement, N maps to itself.
COMPLEMENT = str.maketrans("ACGTN", "TGCAN")


def reverse_complement(kmer: str) -> str:
    """The same physical sequence read off the opposite strand."""
    return kmer.upper().translate(COMPLEMENT)[::-1]


def glob(root: str) -> str:
    """The shard glob for one store root."""
    return f"{root.rstrip('/')}/lane=*/read=*/part-*.parquet"


@dataclass(frozen=True)
class Hit:
    """One read containing the probe."""

    lane: int
    read_num: int
    tile: int
    x: int
    y: int
    position: int
    strand: str
    sequence: str


def kmer(connection, root: str, probe: str, limit: int = 100) -> list[Hit]:
    """Every read containing ``probe`` on either strand (up to ``limit`` reported)."""
    probe = probe.upper()
    if set(probe) - set("ACGTN"):
        raise ValueError(f"not a DNA sequence: {probe!r}")
    reverse = reverse_complement(probe)
    rows = connection.execute(f"""
        SELECT lane, read, tile, x, y,
               position(? IN sequence) AS fwd, position(? IN sequence) AS rev,
               sequence
        FROM read_parquet('{glob(root)}', hive_partitioning=true)
        WHERE contains(sequence, ?) OR contains(sequence, ?)
        LIMIT {int(limit)}
    """, [probe, reverse, probe, reverse]).fetchall()
    return [Hit(lane=r[0], read_num=r[1], tile=r[2], x=r[3], y=r[4],
                position=(r[5] or r[6]), strand="+" if r[5] else "-",
                sequence=r[7])
            for r in rows]


def qc(connection, root: str) -> list[tuple]:
    """Per-lane run quality: reads, filter rate, and the high-quality-base fraction.

    Quality is the NovaSeq 4-level binning (``methodology/012``): ``F`` is Q37, so the
    share of ``F`` characters is the share of bases the machine was most confident in.
    """
    return connection.execute(f"""
        SELECT lane, read,
               count(*) AS reads,
               round(100.0 * sum(is_filtered::INT) / count(*), 3) AS filtered_pct,
               round(100.0 * sum(length(replace(quality, 'F', ''))) /
                     sum(length(quality)), 2) AS below_q37_pct
        FROM read_parquet('{glob(root)}', hive_partitioning=true)
        GROUP BY lane, read ORDER BY lane, read
    """).fetchall()


def sql(connection, root: str, query: str) -> list[tuple]:
    """Arbitrary SQL with ``reads`` bound to the store — the escape hatch."""
    connection.execute(f"""
        CREATE OR REPLACE VIEW reads AS
        SELECT * FROM read_parquet('{glob(root)}', hive_partitioning=true)
    """)
    return connection.execute(query).fetchall()
