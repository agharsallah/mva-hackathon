"""Signature reversal, the plan and the inputs: every choice in one object, every source cached.

:class:`ReversalPlan` is what ``tools/signature_reversal.py`` configures and what the
provenance manifest records verbatim. :func:`fetch_inputs` downloads the file sources
(one manifest each, via :func:`mva.drugs.screen_replication_plan.fetch_files`) and crawls
the library metadata of both engines into the shared API cache, so ``run`` can replay
offline. :class:`Clients` opens one polite :class:`~mva.drugs.cache.Fetcher` per API.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .cache import DEFAULT_CACHE_DIR, Fetcher
from .screen_replication_plan import SourceFile, fetch_files
from .sources import ilincs, sigcom

__all__ = [
    "Clients",
    "Libraries",
    "ReversalPlan",
    "fetch_inputs",
    "landmark_genes",
    "load_libraries",
    "stream_lines",
]


@dataclass(frozen=True)
class ReversalPlan:
    """Every analysis choice of one reversal run, fixed before any drug query."""

    perturbation: str
    consensus: SourceFile
    gene_info: SourceFile
    per_signature_database: str
    """SigCom library whose per-cell-line signatures the consensus is checked against."""
    gene_space: str
    size: int
    decoys: int
    seed: int
    top_n: int
    decoy_max_hits: int
    sigcom_limit: int
    drug_database: str
    control_databases: tuple[str, ...]
    control_genes: tuple[str, ...]
    control_cut: float
    raw_dir: Path
    build_dir: Path
    out: Path
    generator_dir: Path
    entry: str
    claim: str
    mechanism_note: str
    patient_data: str
    cache_dir: Path = DEFAULT_CACHE_DIR
    refresh: bool = False
    notes: tuple[str, ...] = field(default=())

    def parameters(self) -> dict[str, Any]:
        """The plan as JSON-safe parameters for the manifest."""
        loaded: dict[str, Any] = json.loads(json.dumps(asdict(self), default=str))
        return loaded


@dataclass
class Clients:
    """One cached fetcher per API; ``close`` releases their sockets."""

    sigcom: Fetcher
    ilincs: Fetcher
    chembl: Fetcher
    openfda: Fetcher

    @classmethod
    def open(cls, plan: ReversalPlan) -> Clients:
        def make(source: str, interval: float, timeout: float = 120.0) -> Fetcher:
            return Fetcher(
                source=source,
                cache_dir=plan.cache_dir,
                min_interval_s=interval,
                refresh=plan.refresh,
                timeout=timeout,
            )

        return cls(
            sigcom=make("sigcom-lincs", 1.0, timeout=600.0),
            ilincs=make("ilincs", 1.0, timeout=600.0),
            chembl=make("chembl", 0.34),
            openfda=make("openfda", 0.34),
        )

    def close(self) -> None:
        for fetcher in (self.sigcom, self.ilincs, self.chembl, self.openfda):
            fetcher.close()


@dataclass(frozen=True)
class Libraries:
    """Signature id → label maps for every library the run reads."""

    sigcom_ids: dict[str, str]
    """dataset (``l1000_cp`` …) → library uuid."""
    sigcom_labels: dict[str, dict[str, str]]
    """dataset → signature uuid → ``pert_name``."""
    sigcom_contexts: dict[str, dict[str, str]]
    ilincs_labels: dict[str, str]
    """LINCSCP id → compound."""
    counts: dict[str, int]


def stream_lines(path: Path) -> Iterator[str]:
    """Text lines of a plain or gzipped file, streamed."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        yield from handle


def landmark_genes(path: Path, space: str) -> frozenset[str]:
    """Gene symbols whose ``feature_space`` equals ``space`` in the LINCS gene info table."""
    lines = stream_lines(path)
    header = next(lines).rstrip("\n").split("\t")
    symbol, feature = header.index("gene_symbol"), header.index("feature_space")
    out = set()
    for line in lines:
        cells = line.rstrip("\n").split("\t")
        if len(cells) > feature and cells[feature] == space:
            out.add(cells[symbol])
    return frozenset(out)


def per_signature_sources(plan: ReversalPlan, clients: Clients, libraries: Libraries) -> list[Any]:
    """The per-cell-line signature files of the perturbation (for the consensus check)."""
    library = libraries.sigcom_ids[plan.per_signature_database]
    payload = clients.sigcom.post_json(
        f"{sigcom.METADATA}/signatures/find",
        {
            "filter": {
                "where": {"library": library, "meta.pert_name": plan.perturbation},
                "fields": ["id", "meta.persistent_id", "meta.local_id", "meta.pert_type"],
                "limit": 1000,
            }
        },
    )
    out = []
    for row in payload or []:
        meta = row.get("meta") or {}
        url = str(meta.get("persistent_id") or "")
        if url:
            out.append(
                SourceFile(
                    role=f"per-signature {meta.get('pert_type', '')}",
                    name=f"{plan.perturbation}-{meta.get('local_id')}.tsv",
                    url=url,
                    release="LINCS L1000 2021 (SigCom LINCS)",
                    licence="LINCS data: public (no licence stated by SigCom)",
                )
            )
    return sorted(out, key=lambda source: source.name)


def load_libraries(plan: ReversalPlan, clients: Clients) -> Libraries:
    """Crawl (or replay from cache) every library's signature → label map."""
    datasets = (plan.drug_database, plan.per_signature_database, *plan.control_databases)
    ids = sigcom.library_ids(clients.sigcom, sorted(set(datasets)))
    labels: dict[str, dict[str, str]] = {}
    contexts: dict[str, dict[str, str]] = {}
    counts: dict[str, int] = {}
    for dataset in sorted(set(datasets)):
        expected = sigcom.signature_count(clients.sigcom, ids[dataset])
        rows = sigcom.crawl_library(clients.sigcom, ids[dataset], expected=expected)
        labels[dataset] = {
            str(r["id"]): str((r.get("meta") or {}).get("pert_name") or "") for r in rows
        }
        contexts[dataset] = {
            str(r["id"]): str((r.get("meta") or {}).get("cell_line") or "") for r in rows
        }
        counts[f"sigcom:{dataset}"] = len(rows)
    expected = ilincs.signature_count(clients.ilincs)
    il_rows = ilincs.crawl_library(clients.ilincs, expected=expected)
    counts[f"ilincs:{ilincs.CHEMICAL_LIBRARY}"] = len(il_rows)
    return Libraries(
        sigcom_ids=ids,
        sigcom_labels=labels,
        sigcom_contexts=contexts,
        ilincs_labels={str(r["signatureid"]): str(r.get("compound") or "") for r in il_rows},
        counts=counts,
    )


def fetch_inputs(plan: ReversalPlan) -> int:
    """Files first (consensus matrix, gene info, per-cell signatures), then the crawls."""
    fetch_files((plan.consensus, plan.gene_info), plan.raw_dir)
    clients = Clients.open(plan)
    try:
        libraries = load_libraries(plan, clients)
        fetch_files(per_signature_sources(plan, clients, libraries), plan.raw_dir / "per-signature")
        for key, value in sorted(libraries.counts.items()):
            print(f"{key}: {value} signatures")
    finally:
        clients.close()
    return 0
