"""Tier-1 lane, remote: a VEP plugin score fetched from Ensembl's REST service.

REVEL and CADD are **catalogue-adjacent** — their training sets included ClinVar, the very
catalogue of known-pathogenic variants this case is trying not to lean on. They may already
"know" the answer, so every lane built here is flagged ``catalogue_adjacent = True`` and the
merged ranking is printed with *and* without them. That flag is the whole reason this lane
is separate from the two offline ones.

Mechanically it is still a lookup: Ensembl runs the plugin, we read one JSON field. The
request layer is the one the repo already has
(:class:`~mva.pipeline.annotate_vep.VepRestAnnotator` — retries, rate-limit obedience,
bisecting a batch the server refuses). ``annotate_vep`` is not edited: :class:`PluginAsker`
subclasses it and overrides the single method that builds the request body, adding
``{plugin: 1}`` to the query parameters, and adds a raw-JSON accessor because the parsed
:class:`~mva.pipeline.vep_response.VepRecord` has no slot for a plugin's field.

This is the only lane that needs a **coordinate**: Ensembl is asked about a position, not
about an id. The coordinates are read from ``build/it4/records.parquet`` and never leave
the process — the checkpoint file written under ``build/it4/vep-<plugin>/`` holds ids and
numbers only, so a resumed run re-reads answers rather than re-asking for them.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..types import Adapter, AlleleRecord, Coverage, RemoteJob, ScoreRow, Tier
from . import DEFAULT_RECORDS, allele_id_sql, coverage_from_ids

__all__ = ["PluginAsker", "VepRestAdapter", "build"]

#: Where a run's answers are checkpointed, one JSON object per line, ``<plugin>`` filled in.
CHECKPOINT_ROOT = Path("build/it4")


class PluginAsker:
    """:class:`~mva.pipeline.annotate_vep.VepRestAnnotator` with one plugin switched on.

    Built as a *subclass created at call time* rather than at import time so that importing
    this module costs no ``httpx`` import — the same reason every other heavy dependency in
    this repository is imported inside the function that needs it.
    """

    def __init__(self, plugin: str, **kwargs: Any) -> None:
        from mva.pipeline.annotate_vep import QUERY_PARAMS, VepRestAnnotator
        from mva.pipeline.vep_response import query_line

        class _Annotator(VepRestAnnotator):
            """Adds ``{plugin: 1}`` to the POST body; everything else is inherited."""

            def _post_batch(self, chunk: Sequence[Any]) -> list[dict[str, Any]]:
                payload = {
                    "variants": [query_line(variant) for variant in chunk],
                    **QUERY_PARAMS,
                    plugin: 1,
                }
                body = self._request("POST", "/vep/homo_sapiens/region", json=payload)
                return body if isinstance(body, list) else []

        self.plugin = plugin
        self._query_line = query_line
        self.annotator = _Annotator(**kwargs)

    def raw_many(self, variants: Sequence[Any]) -> dict[str, dict[str, Any]]:
        """The server's raw JSON per variant, keyed by its query line.

        The parsed record shape has no field for a plugin's output, so the adapter reads
        the JSON itself. Batching, retries and the bisect-around-a-bad-allele behaviour all
        come from the inherited ``_ask``.
        """
        from mva.pipeline.annotate_vep import batches

        found: dict[str, dict[str, Any]] = {}
        annotator = self.annotator
        for chunk in batches(list(variants), annotator.batch_size):
            for item in annotator._ask(chunk):  # noqa: SLF001 — the batch entry point of the
                # base class is protected but is exactly the seam this subclass exists to use.
                key = item.get("input")
                if key:
                    found[key] = item
        return found

    def close(self) -> None:
        self.annotator.close()


@dataclass
class VepRestAdapter:
    """A plugin score read from Ensembl VEP REST, checkpointed to disk as it arrives."""

    name: str
    version: str
    plugin: str
    field_name: str
    records_parquet: Path = DEFAULT_RECORDS
    batch_size: int = 200
    licence: str = ""
    tier: Tier = 1
    catalogue_adjacent: bool = True
    venue: str = "vep-rest"
    digest: str = ""
    asker: Any = None
    connection: Any = None
    _answers: dict[str, float | None] = field(default_factory=dict)
    _loaded: bool = False

    @property
    def checkpoint(self) -> Path:
        return CHECKPOINT_ROOT / f"vep-{self.plugin.lower()}" / "answers.jsonl"

    @property
    def source_ref(self) -> str:
        return f"ensembl-vep-rest:{self.plugin}"

    # ── the Adapter protocol ─────────────────────────────────────────────────────────

    def coverage(self, records: Sequence[AlleleRecord]) -> Coverage:
        """An *upper bound*: the alleles this lane can ask about at all.

        A remote lane cannot know its true coverage without spending the requests, so
        coverage here is "has a coordinate in the record set". The realised coverage is
        whatever :meth:`score` yields, and the report prints that one.
        """
        return coverage_from_ids(self.name, records, set(self._coordinates(records)))

    def score(self, records: Sequence[AlleleRecord]) -> Iterator[ScoreRow]:
        """Ask the server about every allele not already in the checkpoint, then yield."""
        self._load_checkpoint()
        coordinates = self._coordinates(records)
        pending = {key: value for key, value in coordinates.items() if key not in self._answers}
        if pending:
            self._ask(pending)
        for record in records:
            value = self._answers.get(record.allele_id)
            if value is None:
                continue
            yield ScoreRow(
                allele_id=record.allele_id,
                model=self.name,
                version=self.version,
                score=value,
                aux={"plugin": self.plugin, "field": self.field_name},
                digest=self.digest,
                venue=self.venue,
                licence=self.licence,
            )

    def submit(self, records: Sequence[AlleleRecord]) -> RemoteJob:
        raise NotImplementedError(f"{self.name} answers synchronously — call score()")

    # ── coordinates, checkpoint, transport ───────────────────────────────────────────

    def _coordinates(self, records: Sequence[AlleleRecord]) -> dict[str, tuple[str, int, str, str]]:
        """``allele_id → (chrom, pos, ref, alt)``, read from the record Parquet.

        The id is recomputed in SQL from the coordinate columns rather than trusted from
        the file, so this lane and the warehouse lane agree on the key by construction.
        """
        import duckdb

        if not self.records_parquet.exists():
            raise FileNotFoundError(
                f"{self.name} needs coordinates: no record set at {self.records_parquet}"
            )
        connection = self.connection or duckdb.connect()
        wanted = [record.allele_id for record in records]
        found: dict[str, tuple[str, int, str, str]] = {}
        for start in range(0, len(wanted), 5_000):
            chunk = wanted[start : start + 5_000]
            marks = ", ".join("?" for _ in chunk)
            rows = connection.execute(
                f"SELECT {allele_id_sql()} AS aid, chrom, pos, ref, alt "
                f"FROM read_parquet(?) WHERE {allele_id_sql()} IN ({marks})",
                [str(self.records_parquet), *chunk],
            ).fetchall()
            for row in rows:
                found[str(row[0])] = (str(row[1]), int(row[2]), str(row[3]), str(row[4]))
        return found

    def _load_checkpoint(self) -> None:
        """Replay what an earlier run already asked. Makes a resumed run free."""
        if self._loaded:
            return
        self._loaded = True
        path = self.checkpoint
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            self._answers[str(entry["allele_id"])] = entry.get("score")

    def _append_checkpoint(self, answers: dict[str, float | None]) -> None:
        path = self.checkpoint
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for allele, value in answers.items():
                handle.write(json.dumps({"allele_id": allele, "score": value}) + "\n")

    def _ask(self, coordinates: dict[str, tuple[str, int, str, str]]) -> None:
        from mva.pipeline.variant import Variant
        from mva.pipeline.vep_response import query_line

        asker = self.asker or PluginAsker(self.plugin, batch_size=self.batch_size)
        variants = {
            allele: Variant.from_vcf(chrom, pos, ref, alt)
            for allele, (chrom, pos, ref, alt) in coordinates.items()
        }
        raw = asker.raw_many(list(variants.values()))
        fresh = {
            allele: _pick(raw.get(query_line(variant)), self.field_name)
            for allele, variant in variants.items()
        }
        self._answers.update(fresh)
        self._append_checkpoint(fresh)


def _pick(reply: dict[str, Any] | None, field_name: str) -> float | None:
    """The largest numeric value of ``field_name`` anywhere in one VEP reply.

    VEP answers per transcript, and a plugin fills its field on each consequence block. The
    maximum is the conventional read of a per-transcript score: the worst thing this change
    does to any transcript of the gene.
    """
    if not reply:
        return None
    blocks: list[dict[str, Any]] = [reply]
    blocks += [item for item in reply.get("transcript_consequences", []) if isinstance(item, dict)]
    values = [_number(block.get(field_name)) for block in blocks]
    numbers = [value for value in values if value is not None]
    return max(numbers) if numbers else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, list):
        numbers = [_number(item) for item in value]
        present = [item for item in numbers if item is not None]
        return max(present) if present else None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build(card: Any, *, connection: Any = None, records_parquet: Path = DEFAULT_RECORDS) -> Adapter:
    """Build the lane one model card describes."""
    params = dict(getattr(card, "params", {}) or {})
    plugin = str(params["plugin"])
    return VepRestAdapter(
        name=str(card.key),
        version=str(card.version),
        plugin=plugin,
        field_name=str(params.get("field", plugin.lower())),
        records_parquet=Path(records_parquet),
        batch_size=int(params.get("batch", 200) or 200),
        licence=str(getattr(card, "licence", "") or ""),
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", True)),
        connection=connection,
    )
