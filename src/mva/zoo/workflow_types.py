"""The shapes the workflow passes around: config, state, stage result, manifest, deps.

Split out of :mod:`mva.zoo.workflow` so the runner file stays short and the stage file can
import these without an import cycle. Nothing here runs a stage; it is all data plus the one
bundle of injected callables (:class:`Deps`) that decides whether a run reads the warehouse or
``fixtures/it4/``.
"""

from __future__ import annotations

import csv
import hashlib
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import rank as rank_module

__all__ = ["STAGES", "Config", "Deps", "Manifest", "RunState", "StageResult"]

#: The stage names, in order. ``--from <stage>`` names one of these.
STAGES: tuple[str, ...] = (
    "normalize",
    "registry_check",
    "fan_out",
    "collect",
    "rank_per_model",
    "report_per_model",
    "merge",
    "render",
)


@dataclass(frozen=True)
class Config:
    """One run's configuration, read from ``zoo.example.toml`` (or a copy of it)."""

    path: Path
    digest: str = ""
    mode: str = "catalogue-free"
    models: tuple[str, ...] = ()
    out_dir: Path = Path("build/it4")
    schema: str = "results"
    method: str = "fusion"
    rrf_k: int = 60
    llm_mode: str = "none"
    reports_dir: Path = Path("docs/iteration4/reports")
    docs_runs_dir: Path = Path("docs/iteration4/runs")
    merged_path: Path = Path("docs/iteration4/report.md")
    fixtures: Path | None = None

    @classmethod
    def load(cls, path: str | Path, **overrides: Any) -> Config:
        """Parse the TOML and hash its bytes — the digest is what the manifest records."""
        file = Path(path)
        raw = file.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        run_block = data.get("run", {})
        merge_block = data.get("merge", {})
        llm_block = data.get("llm", {})
        paths = data.get("paths", {})
        values: dict[str, Any] = {
            "path": file,
            "digest": hashlib.sha256(raw).hexdigest(),
            "mode": run_block.get("mode", "catalogue-free"),
            "models": tuple(run_block.get("models", ())),
            "out_dir": Path(run_block.get("out_dir", "build/it4")),
            "schema": run_block.get("schema", "results"),
            "method": merge_block.get("method", "fusion"),
            "rrf_k": int(merge_block.get("rrf_k", 60)),
            "llm_mode": llm_block.get("mode", "none"),
            "reports_dir": Path(paths.get("reports_dir", "docs/iteration4/reports")),
            "docs_runs_dir": Path(paths.get("docs_runs_dir", "docs/iteration4/runs")),
            "merged_path": Path(paths.get("merged_report", "docs/iteration4/report.md")),
        }
        values.update(overrides)
        return cls(**values)

    @property
    def run_id(self) -> str:
        """Deterministic in the config: the same config re-run is the same run, not a new one."""
        return f"it4-{self.digest[:12]}"


@dataclass(frozen=True)
class StageResult:
    """What one stage did: how long it took, how many rows it wrote, and one sentence."""

    stage: str
    seconds: float
    rows: int = 0
    note: str = ""
    skipped: bool = False


@dataclass
class RunState:
    """What the stages hand each other. Mutable on purpose: it is the DAG's working memory."""

    records: list[Any] = field(default_factory=list)
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    scores: dict[str, dict[str, float]] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    pairs: list[rank_module.Pair] = field(default_factory=list)
    ranks: dict[str, rank_module.ModelRank] = field(default_factory=dict)
    reports: list[dict[str, Any]] = field(default_factory=list)
    merged: dict[str, Any] = field(default_factory=dict)
    venues: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Manifest:
    """The run's receipt: what ran, from what, where, for how long, at what cost."""

    run_id: str
    config_path: str
    config_digest: str
    mode: str
    method: str
    models: dict[str, str]
    venues: dict[str, str]
    stages: list[dict[str, Any]]
    dollars: float = 0.0
    started_at: str = ""
    finished_at: str = ""
    outputs: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "config_path": self.config_path,
            "config_digest": self.config_digest,
            "mode": self.mode,
            "merge_method": self.method,
            "models": self.models,
            "venues": self.venues,
            "stages": self.stages,
            "dollars": self.dollars,
            "wall_clock_seconds": round(sum(s["seconds"] for s in self.stages), 3),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "outputs": self.outputs,
        }

    def public(self) -> dict[str, Any]:
        """The coordinate-free copy: identical minus the local output paths."""
        payload = self.to_json()
        payload["outputs"] = [p for p in self.outputs if not p.startswith("build/")]
        return payload


# ---------------------------------------------------------------------------------------
# Injected dependencies
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Deps:
    """Everything the stages need from outside themselves, as callables.

    The production bundle (:meth:`warehouse`) reaches the other wave-1 modules lazily, so
    importing this module never pulls in a database driver; the fixture bundle
    (:meth:`fixtures`) reads ``fixtures/it4/`` and needs nothing at all.
    """

    load_records: Callable[[Config], list[Any]]
    load_registry: Callable[[Config], dict[str, dict[str, Any]]]
    score: Callable[[Config, str, Sequence[Any]], dict[str, float]]
    load_pairs: Callable[[Config, Sequence[Any]], list[rank_module.Pair]]
    hpo_row: Callable[[Config, str], Mapping[str, Any] | None] = lambda _c, _g: None
    venue: Callable[[str], str] = lambda _m: "laptop"

    @classmethod
    def warehouse(cls, connection: Any) -> Deps:
        """The real bundle: records from the warehouse, scores through the adapters + cache."""

        def records(config: Config) -> list[Any]:
            from . import record as record_module

            return list(
                record_module.build_records(
                    connection,
                    record_module.Schemas(warehouse="warehouse", results=config.schema),
                    mask_catalogue=config.mode == "catalogue-free",
                )
            )

        def registry(_config: Config) -> dict[str, dict[str, Any]]:
            from . import registry as registry_module

            return {key: card.as_dict() for key, card in registry_module.load().items()}

        def score(config: Config, model: str, _records: Sequence[Any]) -> dict[str, float]:
            from . import cache as cache_module

            rows = cache_module.read(connection, config.schema, model=model)
            return {row.allele_id: row.score for row in rows if row.score is not None}

        def pairs(config: Config, _records: Sequence[Any]) -> list[rank_module.Pair]:
            from ..warehouse.postgres import ALIAS, safe_identifier

            safe = safe_identifier(config.schema)
            rows = connection.execute(
                f"SELECT gene, chrom, pos, ref, alt, gt, pgt, pid FROM "
                f"{ALIAS}.{safe}.coding_alleles WHERE zygosity = 'het'"
            ).fetchall()
            columns = ("gene", "chrom", "pos", "ref", "alt", "gt", "pgt", "pid")
            return rank_module.pairs_from_alleles(
                [dict(zip(columns, row, strict=True)) for row in rows]
            ).pairs

        return cls(load_records=records, load_registry=registry, score=score, load_pairs=pairs)

    @classmethod
    def fixtures(cls, root: str | Path = "fixtures/it4") -> Deps:
        """The synthetic bundle: everything from ``fixtures/it4/``, no database, no network."""
        base = Path(root)

        def records(_config: Config) -> list[Any]:
            return _read_tsv(base / "records.tsv")

        def registry(config: Config) -> dict[str, dict[str, Any]]:
            return {
                model: {
                    "key": model,
                    "name": model,
                    "version": "fixture-1",
                    "tier": 1,
                    # The fixture registry marks REVEL adjacent because the real registry
                    # does; every other field here is synthetic and says so.
                    "catalogue_adjacent": model == "revel",
                    "enabled": True,
                    "licence": "fixture (synthetic, not a real licence)",
                    "notes": "Synthetic fixture card — no real model ran.",
                }
                for model in config.models
            }

        def score(_config: Config, model: str, _records: Sequence[Any]) -> dict[str, float]:
            path = base / "scores" / f"{model}.tsv"
            if not path.is_file():
                return {}
            return {
                row["allele_id"]: float(row["score"])
                for row in _read_tsv(path)
                if row.get("score") not in (None, "")
            }

        def pairs(_config: Config, _records: Sequence[Any]) -> list[rank_module.Pair]:
            return rank_module.pairs_from_fixture(base / "pairs.tsv")

        return cls(load_records=records, load_registry=registry, score=score, load_pairs=pairs)


def _read_tsv(path: Path) -> list[dict[str, Any]]:

    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    for row in rows:
        if "is_read_only" in row:
            row["is_read_only"] = str(row["is_read_only"]).lower() == "true"
    return rows
