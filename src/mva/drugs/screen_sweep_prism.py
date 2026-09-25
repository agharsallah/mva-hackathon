"""PRISM-specific pieces of the sweep: which compounds are ``Launched``, and one join key.

**Launched.** The 24Q2 extended primary compound list carries no clinical phase (checked in
``docs/iteration4/step-9/research/data-sources.md`` §1). PRISM's own phase label lives in
the 20Q2 treatment-info files, both copied from the Broad Drug Repurposing Hub: the
*primary* file (5,274 rows) and the *secondary* file (1,448 compounds, the one entry 151
used for its control universe). A 24Q2 compound is ``Launched`` here when its
release-independent core BRD id is marked ``Launched`` in **either** file. The rule never
consults a drug name, so two salts of one molecule cannot disagree about approval.

**Join key.** The step-10 generators join on :func:`mva.drugs.names.base_name`. PRISM
writes ``VALPROIC-ACID`` and ``CYPROTERONE-ACETATE`` where every other source writes spaces,
and ``base_name`` only folds a salt word that stands alone. The key is therefore
``base_name(name.replace("-", " "))`` — the rule step 10's convergence join uses on every
generator (``PLX-4720`` becomes ``PLX 4720``) — after one PRISM-only step: a trailing
racemate marker ``-(+/-)`` is dropped first (the racemate is the marketed form), because
the blanket replace would otherwise turn it into ``(+/ )``. Single-enantiomer markers such
as ``-(+)`` are kept: that is a different substance from the marketed racemate.

No patient data is read here; the identifiers are drug names and BRD ids.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

import polars as pl

from mva.drugs.names import base_name
from mva.drugs.screen_replication_prism import CompoundIndex, core_broad_id

__all__ = [
    "launched_cores",
    "launched_items",
    "load_phase_table",
    "phase_disagreements",
    "prism_join_key",
]

_RACEMATE = re.compile(r"-?\(\+/-\)$")


def prism_join_key(name: str) -> str:
    """``CYPROTERONE-ACETATE`` -> ``CYPROTERONE``; ``LEVOBUNOLOL-(+/-)`` -> ``LEVOBUNOLOL``.

    ``PLX-4720`` -> ``PLX 4720``; ``ATENOLOL-(+)`` -> ``ATENOLOL (+)``.
    """
    text = _RACEMATE.sub("", name.strip().upper()).strip()
    return base_name(text.replace("-", " "))


def load_phase_table(path: Path, *, release: str) -> pl.DataFrame:
    """``(broad_core, phase, release)`` from one 20Q2 treatment-info file (primary or secondary)."""
    raw = pl.read_csv(path, infer_schema_length=0, columns=["broad_id", "phase"])
    return (
        raw.drop_nulls()
        .with_columns(
            broad_core=pl.col("broad_id").map_elements(core_broad_id, return_dtype=pl.String),
            release=pl.lit(release),
        )
        .select("broad_core", "phase", "release")
        .unique()
    )


def launched_cores(phases: Sequence[pl.DataFrame]) -> dict[str, str]:
    """``{core BRD id: the release(s) that mark it Launched}`` — a union over the tables."""
    out: dict[str, set[str]] = {}
    for table in phases:
        for core, release in (
            table.filter(pl.col("phase") == "Launched").select("broad_core", "release").rows()
        ):
            out.setdefault(str(core), set()).add(str(release))
    return {core: " | ".join(sorted(rels)) for core, rels in out.items()}


def phase_disagreements(phases: Sequence[pl.DataFrame]) -> list[dict[str, str]]:
    """Cores whose phase differs between (or within) the tables; reported, never resolved."""
    stacked = pl.concat(list(phases)).unique()
    multi = stacked.group_by("broad_core").agg(pl.col("phase").unique().sort(), pl.len())
    bad = multi.filter(pl.col("phase").list.len() > 1).sort("broad_core")
    return [{"broad_core": str(core), "phases": " | ".join(p)} for core, p, _ in bad.rows()]


def launched_items(index: CompoundIndex, launched: Mapping[str, str]) -> dict[str, str]:
    """``{24Q2 item id: Launched source}`` for every 24Q2 compound whose core is Launched."""
    return {
        item: launched[core]
        for item, core in index.table.select("item_id", "broad_core").rows()
        if core in launched
    }
