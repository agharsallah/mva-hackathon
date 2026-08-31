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

import re
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

    probe: str
    lane: int
    read_num: int
    tile: int
    x: int
    y: int
    position: int
    strand: str
    sequence: str


def clean(probe: str) -> str:
    """A probe, upper-cased and checked to be DNA."""
    probe = probe.strip().upper()
    if not probe or set(probe) - set("ACGTN"):
        raise ValueError(f"not a DNA sequence: {probe!r}")
    return probe


def probe_table(probes: list[str], names: list[str] | None = None) -> str:
    """The SQL ``VALUES`` list of (name, sequence, strand) every probe query joins to.

    Each probe becomes two rows — itself and its reverse complement — because a fragment
    is sequenced from whichever strand it came off, and the store keeps reads exactly as
    the machine emitted them.

    Interpolation is safe by construction: sequences are validated as DNA by
    :func:`clean`, and names are reduced to word characters here. Neither can carry a
    quote into the statement.
    """
    names = names or [f"probe{i + 1}" for i in range(len(probes))]
    if len(names) != len(probes):
        raise ValueError(f"{len(names)} names for {len(probes)} probes")
    rows = []
    for name, probe in zip(names, probes):
        safe = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(name))[:64] or "probe"
        probe = clean(probe)
        rows.append(f"('{safe}', '{probe}', '+')")
        rows.append(f"('{safe}', '{reverse_complement(probe)}', '-')")
    return ", ".join(rows)


def kmer(connection, root: str, probe: str, limit: int = 100) -> list[Hit]:
    """Every read containing ``probe`` on either strand (up to ``limit`` reported)."""
    return kmers(connection, root, [probe], limit=limit)


def kmers(connection, root: str, probes: list[str], limit: int = 100,
          names: list[str] | None = None) -> list[Hit]:
    """The same strike for many probes, in **one pass** over the reads.

    This is the difference between asking one question and asking fifty. A full scan is
    dominated by reading and decompressing the ``sequence`` column — ~46 GiB — and every
    extra probe only adds a substring search over bytes already in memory. Fifty probes
    in one pass therefore cost far less than fifty passes, which is the shape of the real
    question: *which of these candidate alleles appear in the reads at all?*

    Each probe is matched forward and reverse-complemented, because a fragment is
    sequenced from whichever strand it came off.
    """
    if not probes:
        return []
    values = probe_table(probes, names)
    found = connection.execute(f"""
        WITH probes(name, seq, strand) AS (VALUES {values}),
        matches AS (
            SELECT p.name, p.strand, r.lane, r.read, r.tile, r.x, r.y,
                   position(p.seq IN r.sequence) AS found_at, r.sequence,
                   row_number() OVER (PARTITION BY p.name ORDER BY r.lane, r.tile) AS rank
            FROM read_parquet('{glob(root)}', hive_partitioning=true) r, probes p
            WHERE contains(r.sequence, p.seq))
        SELECT name, strand, lane, read, tile, x, y, found_at, sequence
        FROM matches WHERE rank <= {int(limit)}
    """).fetchall()
    return [Hit(probe=r[0], strand=r[1], lane=r[2], read_num=r[3], tile=r[4],
                x=r[5], y=r[6], position=r[7], sequence=r[8])
            for r in found]


def counts(connection, root: str, probes: list[str],
           names: list[str] | None = None) -> list[tuple]:
    """How many reads carry each probe — the number, without the reads.

    The count is what decides whether an allele is real: at ~44x depth a true
    single-copy 31-mer is expected in roughly 35 reads (depth x (149 - k + 1) / 149),
    while a sequencing error appears in one or two and an absent allele in none.
    """
    if not probes:
        return []
    values = probe_table(probes, names)
    return connection.execute(f"""
        WITH probes(name, seq, strand) AS (VALUES {values})
        SELECT p.name,
               count(*) FILTER (p.strand = '+') AS forward,
               count(*) FILTER (p.strand = '-') AS reverse,
               count(*) AS total,
               count(DISTINCT r.lane) AS lanes
        FROM read_parquet('{glob(root)}', hive_partitioning=true) r, probes p
        WHERE contains(r.sequence, p.seq)
        GROUP BY p.name ORDER BY p.name
    """).fetchall()


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
