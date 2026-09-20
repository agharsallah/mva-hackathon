"""The protein windows: the input a model that *runs* needs, rather than one that looks up.

Every MVP lane is a lookup — a published table joined on a string. A **protein language
model** (ESM2, ESM-C) is the other kind: it reads the actual amino-acid sequence around the
change and scores the substitution itself, having never seen a variant catalogue. That makes
it the zoo's only genuinely catalogue-free opinion on a missense allele, and it needs an
input the MVP record does not carry.

That input is a **window**: the protein's own letters for ``radius`` residues either side of
the changed one, twice — once as the reference protein (``protein_window_ref``) and once
with the one letter swapped (``protein_window_alt``). A window, not the whole protein,
because the model's cost grows with the square of the length and BubR1 alone is 1,050
residues.

Where the pieces come from:

* the **which protein** and **which residue** are already in ``hgvs_p``, the HGVS protein
  spelling VEP returned — ``ENSP00000287598.7:p.Asn1002Lys`` is "on protein ENSP…, residue
  1002, asparagine becomes lysine". Entries 114 and 119 record that the ``ENSP`` accession
  is this string's own prefix, which is why no extra lookup is needed;
* the **letters** come from Ensembl REST (``GET/POST /sequence/id``, ``type=protein``),
  batched and cached one file per accession under ``build/<prefix>/protein-seq/`` so a
  re-run asks only for what is missing.

**A window is patient sequence.** It is written to ``build/<prefix>/records.parquet`` and
nowhere else — never to a warehouse table, never into a methodology entry, never printed.
The repository's coordinate gate treats a long sequence like a coordinate, and so does this
module: it returns windows to its caller, and the only writer is :func:`write_windows`,
whose target is under ``build/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sequence_fetch import (
    DEFAULT_BATCH,
    DEFAULT_CACHE,
    ENSEMBL_SEQUENCE,
    PAUSE_SECONDS,
    RETRYABLE,
    Fetcher,
    SequenceCache,
    ensembl_sequences,
    fetch_sequences,
)
from .types import AlleleRecord

__all__ = [
    "AMINO_ACIDS",
    "DEFAULT_BATCH",
    "DEFAULT_CACHE",
    "DEFAULT_RADIUS",
    "ENSEMBL_SEQUENCE",
    "PAUSE_SECONDS",
    "RETRYABLE",
    "ProteinChange",
    "SequenceCache",
    "WindowReport",
    "ensembl_sequences",
    "fetch_sequences",
    "parse_protein_change",
    "protein_windows",
    "write_windows",
]

#: How many residues either side of the change. 64 gives a 129-residue window, which is
#: what the ESM2 lane scores; the number is a run parameter, not a constant of the method.
DEFAULT_RADIUS = 64

#: HGVS spells a residue with three letters; a sequence uses one. ``Ter`` is a stop codon,
#: which is why a nonsense allele has an ``hgvs_p`` but no meaningful mutant window.
AMINO_ACIDS: dict[str, str] = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
    "Sec": "U", "Pyl": "O", "Asx": "B", "Glx": "Z", "Xaa": "X",
    "Ter": "*",
}  # fmt: skip


@dataclass(frozen=True)
class ProteinChange:
    """One missense substitution, read out of an ``hgvs_p`` string.

    ``accession`` keeps Ensembl's version suffix off: ``ENSP00000287598.7`` names the same
    protein as ``ENSP00000287598``, and the REST endpoint is happier without it.
    """

    accession: str
    position: int
    ref_aa: str
    alt_aa: str


@dataclass(frozen=True)
class WindowReport:
    """What one windowing pass managed, per reason — the numbers a claim is judged on."""

    considered: int = 0
    parsed: int = 0
    sequence_missing: int = 0
    residue_mismatch: int = 0
    complete: int = 0
    truncated_at_terminus: int = 0

    def as_dict(self) -> dict[str, int | float]:
        return {
            "considered": self.considered,
            "parsed": self.parsed,
            "sequence_missing": self.sequence_missing,
            "residue_mismatch": self.residue_mismatch,
            "complete": self.complete,
            "truncated_at_terminus": self.truncated_at_terminus,
            "fraction_complete": round(self.complete / self.considered, 5)
            if self.considered
            else 0.0,
        }


def parse_protein_change(hgvs_p: str | None) -> ProteinChange | None:
    """``ENSP00000287598.7:p.Asn1002Lys`` → the accession, 1002, ``N``, ``K``.

    Returns ``None`` for anything that is not a plain one-residue substitution: a frameshift
    (``p.Arg12fs``), a stop (``p.Leu737Ter``), a synonymous change spelled ``p.Leu5=``, an
    in-frame indel (``p.Ala5_Gly7del``). Those alleles are real and they are *not* missense
    substitutions, so a protein-substitution model has nothing to say about them; refusing
    here is what keeps that visible instead of inventing a window.
    """
    if not hgvs_p or ":p." not in hgvs_p:
        return None
    accession, _, change = hgvs_p.partition(":p.")
    accession = accession.split(".")[0].strip()
    if not accession or len(change) < 7:
        return None
    ref, digits, alt = change[:3], change[3:-3], change[-3:]
    if not digits.isdigit() or ref not in AMINO_ACIDS or alt not in AMINO_ACIDS:
        return None
    ref_aa, alt_aa = AMINO_ACIDS[ref], AMINO_ACIDS[alt]
    if "*" in (ref_aa, alt_aa) or ref_aa == alt_aa:
        return None
    return ProteinChange(accession, int(digits), ref_aa, alt_aa)


# ── the windows ───────────────────────────────────────────────────────────────────────


def window_pair(
    sequence: str, change: ProteinChange, radius: int = DEFAULT_RADIUS
) -> tuple[str, str] | None:
    """``(reference window, mutant window)``, or ``None`` if the sequence disagrees.

    The check that earns its keep is ``sequence[position - 1] == change.ref_aa``. Ensembl
    serves the protein of the accession ``hgvs_p`` names, so a mismatch means the record and
    the sequence are on different isoforms or different assembly versions — and a window
    built anyway would be a window of the wrong protein, scored with full confidence.
    """
    index = change.position - 1
    if index < 0 or index >= len(sequence) or sequence[index] != change.ref_aa:
        return None
    start = max(0, index - radius)
    stop = min(len(sequence), index + radius + 1)
    reference = sequence[start:stop]
    offset = index - start
    mutant = reference[:offset] + change.alt_aa + reference[offset + 1 :]
    return reference, mutant


def protein_windows(
    records: Sequence[AlleleRecord],
    *,
    sequences: dict[str, str] | None = None,
    cache: SequenceCache | None = None,
    fetcher: Fetcher = ensembl_sequences,
    radius: int = DEFAULT_RADIUS,
    batch: int = DEFAULT_BATCH,
    progress: Any = None,
) -> tuple[dict[str, tuple[str, str]], WindowReport]:
    """Build a window pair for every record whose ``hgvs_p`` is a missense substitution.

    Returns ``({allele_id: (ref_window, alt_window)}, report)``. The report is what a claim
    is judged on: how many were considered, how many parsed, how many the sequence server
    could not answer, how many disagreed with the reference residue, how many are complete.

    ``sequences`` short-circuits the network entirely — that is the seam the tests use.
    """
    changes = {
        record.allele_id: change
        for record in records
        if (change := parse_protein_change(record.hgvs_p)) is not None
    }
    known = sequences
    if known is None:
        known = fetch_sequences(
            sorted({change.accession for change in changes.values()}),
            cache=cache,
            fetcher=fetcher,
            batch=batch,
            progress=progress,
        )
    windows: dict[str, tuple[str, str]] = {}
    missing = mismatch = truncated = 0
    for allele, change in changes.items():
        sequence = known.get(change.accession)
        if not sequence:
            missing += 1
            continue
        pair = window_pair(sequence, change, radius)
        if pair is None:
            mismatch += 1
            continue
        windows[allele] = pair
        if len(pair[0]) < 2 * radius + 1:
            truncated += 1
    report = WindowReport(
        considered=len(records),
        parsed=len(changes),
        sequence_missing=missing,
        residue_mismatch=mismatch,
        complete=len(windows),
        truncated_at_terminus=truncated,
    )
    return windows, report


# ── writing them where they are allowed to live ───────────────────────────────────────


def write_windows(
    records_parquet: Path | str,
    windows: dict[str, tuple[str, str]],
    *,
    connection: Any = None,
) -> int:
    """Fill ``protein_window_ref``/``protein_window_alt`` in the record Parquet, in place.

    The Parquet under ``build/`` is *extended*, not a new table: the warehouse's
    ``it4_allele_records`` deliberately has no window column, because a window is patient
    sequence and the warehouse is not where patient sequence lives. Returns the rows filled.
    """
    import duckdb

    target = Path(records_parquet)
    if not target.exists():
        raise FileNotFoundError(f"no record set at {target}; run `mva-zoo records` first")
    con = connection or duckdb.connect()
    con.execute(
        "CREATE OR REPLACE TEMP TABLE zoo_windows (allele_id VARCHAR, w_ref VARCHAR, w_alt VARCHAR)"
    )
    if windows:
        con.executemany(
            "INSERT INTO zoo_windows VALUES (?, ?, ?)",
            [[allele, pair[0], pair[1]] for allele, pair in windows.items()],
        )
    staged = target.with_suffix(".windows.parquet")
    con.execute(
        f"COPY (SELECT r.* REPLACE ("
        f"  w.w_ref AS protein_window_ref, w.w_alt AS protein_window_alt) "
        f"FROM read_parquet('{target}') r LEFT JOIN zoo_windows w USING (allele_id)) "
        f"TO '{staged}' (FORMAT parquet)"
    )
    filled = con.execute(
        "SELECT count(*) FROM read_parquet(?) WHERE protein_window_ref IS NOT NULL", [str(staged)]
    ).fetchone()
    con.execute("DROP TABLE IF EXISTS zoo_windows")
    staged.replace(target)
    return int(filled[0]) if filled else 0
