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
        from mva.pipeline.annotate_vep import VepRestAnnotator
        from mva.pipeline.vep_response import query_line

        class _Annotator(VepRestAnnotator):
            """Sends **only** ``{plugin: 1}``; everything else is inherited.

            Not ``QUERY_PARAMS + {plugin: 1}``, which is what this class first sent: that
            set asks for the AlphaMissense and SpliceAI plugins and two gnomAD frequency
            joins *per allele* on top of this lane's own plugin, and a 200-allele batch
            then read-timed out on every one of five attempts (measured 2026-09-19,
            methodology entry 119 — the same wall
            :data:`mva.zoo.record_hgvs.LEAN_PARAMS` was written for). This lane reads one
            field off the reply (:func:`_pick` on ``field_name``), so one option is all it
            needs.
            """

            def _post_batch(self, chunk: Sequence[Any]) -> list[dict[str, Any]]:
                payload = {
                    "variants": [query_line(variant) for variant in chunk],
                    plugin: 1,
                }
                body = self._request("POST", "/vep/homo_sapiens/region", json=payload)
                return body if isinstance(body, list) else []

        self.plugin = plugin
        self._query_line = query_line
        self.annotator = _Annotator(**kwargs)

    def raw_batches(self, variants: Sequence[Any]) -> Iterator[dict[str, dict[str, Any]]]:
        """One dict of raw JSON per **batch**, keyed by each variant's query line.

        A generator rather than one big dict so the caller can write a checkpoint after
        every batch. That matters: a 197-batch pass over this callset met a ``500`` on a
        late batch and, when the answers were only written at the end, **twenty minutes of
        replies were lost** (measured 2026-09-19, entry 122).

        The parsed record shape has no field for a plugin's output, so the adapter reads
        the JSON itself. Batching, retries and the bisect-around-a-bad-allele behaviour all
        come from the inherited ``_ask``.
        """
        from mva.pipeline.annotate_vep import batches

        annotator = self.annotator
        for chunk in batches(list(variants), annotator.batch_size):
            found: dict[str, dict[str, Any]] = {}
            for item in annotator._ask(chunk):  # noqa: SLF001 — the batch entry point of the
                # base class is protected but is exactly the seam this subclass exists to use.
                key = item.get("input")
                if key:
                    found[key] = item
            yield found

    def raw_many(self, variants: Sequence[Any]) -> dict[str, dict[str, Any]]:
        """Every batch's JSON in one dict — the shape a small caller (and a test) wants."""
        found: dict[str, dict[str, Any]] = {}
        for batch in self.raw_batches(variants):
            found.update(batch)
        return found

    def close(self) -> None:
        self.annotator.close()


#: Which VEP consequence terms a card's ``input_class`` is worth asking about. ``any`` is
#: absent on purpose: a lane that scores anything gets an empty set, which means "ask about
#: every record". The terms are the ones this callset actually carries (entry 114's
#: ``by_consequence``), so a class added later must be added here too rather than silently
#: skipped — the lane prints what it asked about, so a mistake shows up as coverage.
CONSEQUENCES_FOR_CLASS: dict[str, tuple[str, ...]] = {
    "missense": ("missense_variant",),
    "splice": (
        "splice_acceptor_variant",
        "splice_donor_variant",
        "splice_donor_5th_base_variant",
        "splice_donor_region_variant",
        "splice_polypyrimidine_tract_variant",
        "splice_region_variant",
    ),
}


@dataclass
class VepRestAdapter:
    """A plugin score read from Ensembl VEP REST, checkpointed to disk as it arrives."""

    name: str
    version: str
    plugin: str
    field_name: str
    records_parquet: Path = DEFAULT_RECORDS
    batch_size: int = 200
    #: Seconds per request. The 60 s the transport defaults to is not enough for a
    #: 200-allele plugin batch on the public endpoint; iteration 2's own pass uses 300
    #: (``tools/annotate_it2_insilico.py --timeout``).
    timeout: float = 300.0
    licence: str = ""
    tier: Tier = 1
    catalogue_adjacent: bool = True
    venue: str = "vep-rest"
    digest: str = ""
    asker: Any = None
    connection: Any = None
    #: Set when a pass stopped early: the server's message and how far it got. Empty means
    #: the lane answered for every allele it was asked about.
    incomplete: str = ""
    #: Which consequence classes this lane is asked about at all, from the card's
    #: ``input_class``. Empty means every record. **This is the only lane where asking is
    #: expensive** — one HTTPS round trip per batch — and a missense-only plugin returns a
    #: guaranteed null for a synonymous or intronic allele. Skipping those is not a
    #: shortcut: it is not spending a request on an answer that is already known.
    consequences: frozenset[str] = frozenset()
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
        return coverage_from_ids(self.name, records, set(self._coordinates(self._askable(records))))

    def score(self, records: Sequence[AlleleRecord]) -> Iterator[ScoreRow]:
        """Ask the server about every allele not already in the checkpoint, then yield."""
        self._load_checkpoint()
        coordinates = self._coordinates(self._askable(records))
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

    def _askable(self, records: Sequence[AlleleRecord]) -> list[AlleleRecord]:
        """The records worth a request, per the card's ``input_class``."""
        if not self.consequences:
            return list(records)
        return [record for record in records if record.consequence in self.consequences]

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
        from mva.pipeline.annotate_vep import VepError
        from mva.pipeline.variant import Variant
        from mva.pipeline.vep_response import query_line

        asker = self.asker or PluginAsker(
            self.plugin, batch_size=self.batch_size, timeout=self.timeout
        )
        variants = {
            allele: Variant.from_vcf(chrom, pos, ref, alt)
            for allele, (chrom, pos, ref, alt) in coordinates.items()
        }
        by_line = {query_line(variant): allele for allele, variant in variants.items()}
        asked = 0
        try:
            for batch in asker.raw_batches(list(variants.values())):
                fresh = {
                    by_line[line]: _pick(reply, self.field_name)
                    for line, reply in batch.items()
                    if line in by_line
                }
                self._answers.update(fresh)
                self._append_checkpoint(fresh)
                asked += len(fresh)
        except VepError as error:
            # A server-side failure is not a reason to throw away the batches that did
            # answer. What was written stays written, the lane scores what it has, and the
            # next run resumes from the checkpoint instead of re-asking.
            self.incomplete = f"{error} — {asked:,} of {len(variants):,} alleles answered"


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
    declared = params.get("consequences") or CONSEQUENCES_FOR_CLASS.get(
        str(getattr(card, "input_class", "any")), ()
    )
    return VepRestAdapter(
        name=str(card.key),
        version=str(card.version),
        plugin=plugin,
        field_name=str(params.get("field", plugin.lower())),
        records_parquet=Path(records_parquet),
        batch_size=int(params.get("batch", 200) or 200),
        timeout=float(params.get("timeout", 300.0) or 300.0),
        consequences=frozenset(declared),
        licence=str(getattr(card, "licence", "") or ""),
        catalogue_adjacent=bool(getattr(card, "catalogue_adjacent", True)),
        connection=connection,
    )
