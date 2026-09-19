"""The shapes the workflow passes around: config, state, stage result, manifest, deps.

Split out of :mod:`mva.zoo.workflow` so the runner file stays short and the stage file can
import these without an import cycle. Nothing here runs a stage; it is all data plus the one
bundle of injected callables (:class:`Deps`) that decides whether a run reads the warehouse or
a fixture directory.

The configuration itself — what a *case* is — lives in :mod:`mva.zoo.case_config` and is
re-exported here, so ``from .workflow_types import Config`` keeps working for every caller.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import rank as rank_module
from .case_config import DEFAULT_ITERATION, DEFAULT_PREFIX, Config

__all__ = [
    "DEFAULT_ITERATION",
    "DEFAULT_PREFIX",
    "STAGES",
    "Config",
    "Deps",
    "Manifest",
    "RunState",
    "StageResult",
    "consequence_map",
]

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
    #: What building the pairs found beside the pairs themselves: how many genes and
    #: heterozygous calls were read, which genes were skipped as too dense to pair, and the
    #: sentence saying how the confirmed pair was flagged. Computed by
    #: :func:`mva.zoo.pairs.pairs_from_alleles` and dropped on the floor until the API needed
    #: a real ``skipped_genes`` list to serve.
    pair_build: dict[str, Any] = field(default_factory=dict)
    ranks: dict[str, rank_module.ModelRank] = field(default_factory=dict)
    reports: list[dict[str, Any]] = field(default_factory=list)
    merged: dict[str, Any] = field(default_factory=dict)
    venues: dict[str, str] = field(default_factory=dict)
    #: ``--force``: recompute regardless of what the checkpoints hold. Carried on the state
    #: rather than passed, because only ``fan_out`` looks at a checkpoint from inside a stage.
    force: bool = False


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
    #: The pair-building bookkeeping of the ``rank_per_model`` stage: ``genes``, ``het_calls``,
    #: ``skipped_genes`` and ``confirmed_note``. Empty for a run whose ``load_pairs`` returned
    #: bare pairs (a fixture run), never invented.
    pairs: dict[str, Any] = field(default_factory=dict)
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
            "pairs": self.pairs,
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
    #: Returns either the pairs alone or a :class:`mva.zoo.pairs.PairBuild`, which carries the
    #: skipped genes and the confirmed-pair note as well. The stage accepts both, so a test may
    #: hand back a plain list.
    load_pairs: Callable[[Config, Sequence[Any]], list[rank_module.Pair] | rank_module.PairBuild]
    hpo_row: Callable[[Config, str], Mapping[str, Any] | None] = lambda _c, _g: None
    venue: Callable[[str], str] = lambda _m: "laptop"
    #: A **cheap** hash of what a stage would read from outside the process, given its name —
    #: the row count of the source table, the digest of the roster files. The resume folds it
    #: into the stage's input digest, so a source that changed under a finished checkpoint
    #: invalidates it instead of being silently reused (:mod:`mva.zoo.checkpoint`). An empty
    #: string means "this bundle cannot say", and then only ``--force`` or ``--from`` will
    #: re-read that source — which is the documented limitation of the resume, not a bug.
    fingerprint: Callable[[Config, str], str] = lambda _c, _s: ""

    @classmethod
    def warehouse(cls, connection: Any) -> Deps:
        """The real bundle: records from the warehouse, scores through the adapters + cache."""

        def records(config: Config) -> list[Any]:
            from . import record as record_module

            return list(
                record_module.build_records(
                    connection,
                    record_module.Schemas(warehouse=config.warehouse_schema, results=config.schema),
                    mask_catalogue=config.mode == "catalogue-free",
                )
            )

        def registry(_config: Config) -> dict[str, dict[str, Any]]:
            from . import registry as registry_module

            return {key: card.as_dict() for key, card in registry_module.load().items()}

        def score(config: Config, model: str, _records: Sequence[Any]) -> dict[str, float]:
            from . import cache as cache_module

            rows = cache_module.read(connection, config.warehouse_schema, model=model)
            return {row.allele_id: row.score for row in rows if row.score is not None}

        def pairs(config: Config, records_in: Sequence[Any]) -> rank_module.PairBuild:
            from ..warehouse.postgres import ALIAS, safe_identifier

            safe = safe_identifier(config.schema)
            rows = connection.execute(
                f"SELECT gene, chrom, pos, ref, alt, gt, pgt, pid FROM "
                f"{ALIAS}.{safe}.coding_alleles WHERE zygosity = 'het'"
            ).fetchall()
            columns = ("gene", "chrom", "pos", "ref", "alt", "gt", "pgt", "pid")
            return rank_module.pairs_from_alleles(
                [dict(zip(columns, row, strict=True)) for row in rows],
                confirmed_gene=config.confirmed_gene,
                consequences=consequence_map(records_in),
                rule=config.confirmed_pair_rule,
            )

        def hpo(config: Config, gene: str) -> Mapping[str, Any] | None:
            """The gene's row in the phenotype-only ranking, or ``None`` if it has none.

            This is the *clinical* half of the evidence (the repository's standing
            two-sources rule): the eight HPO terms rank every gene without seeing the DNA,
            and section 5 of every model report quotes that rank whether or not the model
            can see a phenotype. Unwired until the first real run, which printed "produced
            no `BUB1B` row" for a gene the table ranks #14 (entry 128).
            """
            from ..warehouse.postgres import ALIAS, safe_identifier

            if not gene:
                return None
            safe = safe_identifier(config.warehouse_schema)
            table = safe_identifier(config.hpo_table)
            found = connection.execute(
                f"SELECT gene_symbol, rank, score, genes_considered FROM "
                f"{ALIAS}.{safe}.{table} WHERE gene_symbol = ? AND term_set = ?",
                [gene, config.phenotype_term_set],
            ).fetchone()
            if not found:
                return None
            names = ("gene_symbol", "rank", "score", "genes_considered")
            return dict(zip(names, found, strict=True))

        def fingerprint(config: Config, stage: str) -> str:
            """What the stage's source looks like right now, in one cheap statement.

            ``normalize`` and ``rank_per_model`` both read ``<results>.coding_alleles``: its
            row count plus the catalogue mode is enough to notice that step 1 was re-run
            under a finished checkpoint. ``registry_check`` reads files, so its fingerprint
            is their bytes. Anything unreadable answers ``""`` — "cannot say" — and the stage
            then rests on the chain alone.
            """
            from .checkpoint import digest_of

            if stage == "registry_check":
                from .registry import DEFAULT_FRAGMENTS_DIR, DEFAULT_MODELS_TOML

                files = [DEFAULT_MODELS_TOML, *sorted(DEFAULT_FRAGMENTS_DIR.glob("*.toml"))]
                return digest_of(
                    [(f.name, f.read_bytes().hex()) for f in files if f.is_file()],
                )
            if stage in ("normalize", "rank_per_model"):
                from ..warehouse.postgres import ALIAS, safe_identifier

                safe = safe_identifier(config.schema)
                try:
                    found = connection.execute(
                        f"SELECT count(*) FROM {ALIAS}.{safe}.coding_alleles"
                    ).fetchone()
                # Any failure here means "this bundle cannot say", never a failed run: the
                # fingerprint is an optimisation guard, not a result.
                except Exception:
                    return ""
                return digest_of(stage, config.mode, found and found[0])
            return ""

        return cls(
            load_records=records,
            load_registry=registry,
            score=score,
            load_pairs=pairs,
            hpo_row=hpo,
            fingerprint=fingerprint,
        )

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

        def pairs(config: Config, _records: Sequence[Any]) -> list[rank_module.Pair]:
            return rank_module.pairs_from_fixture(
                base / "pairs.tsv",
                confirmed_gene=config.confirmed_gene,
                rule=config.confirmed_pair_rule,
            )

        return cls(load_records=records, load_registry=registry, score=score, load_pairs=pairs)


def consequence_map(records: Sequence[Any]) -> dict[str, str]:
    """``allele_id`` → consequence, for the confirmed-pair rule.

    The rule that picks one of several candidate pairs ("a truncating allele plus a missense
    allele") needs to know what each allele *is*. The records already say, so the workflow
    hands them over rather than making :mod:`mva.zoo.pairs` query anything.
    """
    out: dict[str, str] = {}
    for record in records:
        key = (
            record.get("allele_id")
            if isinstance(record, Mapping)
            else getattr(record, "allele_id", None)
        )
        value = (
            record.get("consequence")
            if isinstance(record, Mapping)
            else getattr(record, "consequence", None)
        )
        if key:
            out[str(key)] = str(value or "")
    return out


def _read_tsv(path: Path) -> list[dict[str, Any]]:

    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    for row in rows:
        if "is_read_only" in row:
            row["is_read_only"] = str(row["is_read_only"]).lower() == "true"
    return rows
