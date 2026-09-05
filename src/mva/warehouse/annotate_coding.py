"""Annotate every coding allele the proband carries, genome-wide, through VEP REST.

This is the genome-wide backend behind the annotation port — for the coding fraction of
the genome. It reads the distinct alleles of ``results.coding_alleles`` (layer 2, built by
:mod:`mva.warehouse.analysis_coding`), asks Ensembl VEP about each in batches of 200, and
lands the answers in ``warehouse.coding_annotations`` with the **same shape** as
``panel_annotations``, so every join written for the panel works genome-wide unchanged.

Two things distinguish it from :mod:`mva.warehouse.annotate`:

* **Scale.** Tens of thousands of alleles, a few hundred requests, a run measured in tens
  of minutes. So every batch is **checkpointed** to a gitignored directory as it arrives
  and a re-run resumes where the last one stopped instead of re-asking. The checkpoint
  holds real patient positions and lives under ``build/`` for that reason.
* **Source of the alleles.** Not an interval list compiled into a predicate, but a table
  already derived — which is what layer 2 is for.

``annotator`` is injectable, as in :mod:`mva.warehouse.annotate`, so the whole path runs
against a fake in tests.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ..pipeline.annotate_vep import DEFAULT_BASE_URL, VepRestAnnotator, batches
from ..pipeline.variant import Variant
from ..pipeline.vep_response import VepRecord
from . import lineage
from .annotate import write
from .postgres import ALIAS, attached, safe_identifier
from .settings import Postgres

__all__ = [
    "ALLELES_TABLE",
    "CODING_TABLE",
    "DEFAULT_CHECKPOINT",
    "TRANSFORM",
    "Checkpoint",
    "alleles",
    "plan",
    "run",
]

#: Where the genome-wide annotations land, in the ingest schema, panel-shaped.
CODING_TABLE = "coding_annotations"

#: The layer-2 table the alleles are read from, in the *result* schema.
ALLELES_TABLE = "coding_alleles"

#: Gitignored. Holds patient positions, so never anywhere the repository can pick up.
DEFAULT_CHECKPOINT = Path("build/coding-annotations")

#: Written into ``coding_annotations.source`` and the lineage edge's transform.
TRANSFORM = "annotate-coding"


def alleles(connection, result_schema: str) -> list[Variant]:
    """Every distinct ALT allele in ``coding_alleles``, sorted, in submission spelling."""
    safe = safe_identifier(result_schema)
    rows = connection.execute(
        f"SELECT DISTINCT chrom, pos, ref, alt FROM {ALIAS}.{safe}.{ALLELES_TABLE}"
    ).fetchall()
    return sorted(Variant.from_vcf(chrom, int(pos), ref, alt) for chrom, pos, ref, alt in rows)


class Checkpoint:
    """Batches already answered, as JSON lines on disk — one file per batch.

    A record round-trips through :func:`dataclasses.asdict`; the only non-scalar field,
    ``clin_sig``, is a tuple and comes back as a list, so it is re-tupled on read.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def load(self) -> dict[Variant, VepRecord]:
        found: dict[Variant, VepRecord] = {}
        if not self.directory.is_dir():
            return found
        for path in sorted(self.directory.glob("batch-*.jsonl")):
            with path.open(encoding="utf-8") as stream:
                for line in stream:
                    record = _from_json(json.loads(line))
                    found[record.variant] = record
        return found

    def append(self, index: int, records: Iterable[VepRecord]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"batch-{index:05d}.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for record in records:
                stream.write(json.dumps(_to_json(record)) + "\n")
        return path

    def next_index(self) -> int:
        if not self.directory.is_dir():
            return 0
        names = sorted(self.directory.glob("batch-*.jsonl"))
        return int(names[-1].stem.split("-")[1]) + 1 if names else 0


def _to_json(record: VepRecord) -> dict:
    data = asdict(record)
    data["variant"] = asdict(record.variant)
    data["clin_sig"] = list(record.clin_sig)
    return data


def _from_json(data: dict) -> VepRecord:
    variant = Variant(**data.pop("variant"))
    data["clin_sig"] = tuple(data.get("clin_sig") or ())
    return VepRecord(variant=variant, **data)


def plan(settings: Postgres, batch_size: int, checkpoint: Path = DEFAULT_CHECKPOINT) -> dict:
    """What a run would ask for, without asking. Backs ``--dry-run``."""
    with attached(settings, read_only=True) as connection:
        wanted = alleles(connection, settings.result_schema)
    done = Checkpoint(checkpoint).load()
    todo = [variant for variant in wanted if variant not in done]
    return {
        "alleles": len(wanted),
        "checkpointed": len(wanted) - len(todo),
        "todo": len(todo),
        "batches": len(batches(todo, batch_size)),
        "batch_size": min(batch_size, len(todo) or batch_size),
    }


def run(
    settings: Postgres,
    *,
    batch_size: int = 200,
    base_url: str = DEFAULT_BASE_URL,
    checkpoint: Path = DEFAULT_CHECKPOINT,
    annotator=None,
    progress: Callable[[str], None] | None = None,
    workers: int = 1,
) -> dict:
    """Read the coding alleles, annotate the ones not yet checkpointed, land the table.

    ``workers`` requests run concurrently. One VEP POST of 200 alleles takes ~30 s, almost
    all of it server time, so a few in flight cut the wall clock nearly linearly while
    staying far below Ensembl's 15 requests/s ceiling. Each batch keeps its own checkpoint
    index whatever order the replies arrive in.
    """
    say = progress or (lambda _line: None)
    store = Checkpoint(checkpoint)
    with attached(settings) as connection:
        wanted = alleles(connection, settings.result_schema)
        records = store.load()
        todo = [variant for variant in wanted if variant not in records]
        say(f"alleles {len(wanted):,}  checkpointed {len(records):,}  to ask {len(todo):,}")

        owned = annotator is None
        client = annotator or VepRestAnnotator(base_url=base_url, batch_size=batch_size)
        try:
            version = client.version()
            first = store.next_index()
            chunks = batches(todo, batch_size)
            lock = threading.Lock()
            done = 0

            def ask(item: tuple[int, Sequence[Variant]]) -> None:
                nonlocal done
                offset, chunk = item
                got = client.annotate_many(chunk)
                with lock:
                    store.append(first + offset, got)
                    records.update({record.variant: record for record in got})
                    done += 1
                    if done % 10 == 0 or done == len(chunks):
                        say(f"  batch {done}/{len(chunks)}  answered {len(records):,}")

            if workers > 1 and len(chunks) > 1:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    list(pool.map(ask, enumerate(chunks)))
            else:
                for item in enumerate(chunks):
                    ask(item)
        finally:
            if owned:
                client.close()

        ordered = [records[variant] for variant in wanted if variant in records]
        source = (
            f"ensembl-vep-rest release={version.get('release', '?')} "
            f"assembly={version.get('assembly', '?')}"
        )
        annotated_at = datetime.now(UTC).replace(tzinfo=None)
        rows = write(connection, settings.schema, ordered, source, annotated_at, CODING_TABLE)

        lineage.ensure_tables(connection, settings.schema)
        lineage.record(
            connection,
            settings.schema,
            target_schema=settings.schema,
            target_table=CODING_TABLE,
            target_rows=rows,
            source_kind="api",
            source_ref=f"{base_url}/vep/homo_sapiens/region",
            source_version=source,
            transform=f"{TRANSFORM}: every distinct allele of "
            f"{settings.result_schema}.{ALLELES_TABLE} (the proband's ALT alleles inside "
            "coding_regions), annotated by Ensembl VEP REST in batches of "
            f"{min(batch_size, 200)}; resumed from {len(wanted) - len(todo):,} "
            "checkpointed alleles",
            tool="mva-warehouse annotate-coding",
            notes=f"requests this run: {getattr(client, 'requests', 0)}; checkpoint {checkpoint}",
        )

    return {
        "version": version,
        "source": source,
        "rows": rows,
        "asked": len(todo),
        "annotated": sum(1 for r in ordered if r.consequence),
        "with_gnomad_af": sum(1 for r in ordered if r.gnomad_af is not None),
        "with_clin_sig": sum(1 for r in ordered if r.clin_sig),
        "genes": len({r.gene for r in ordered if r.gene}),
    }
