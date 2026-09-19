"""The zoo roster: who is in it, what it costs, and what its licence lets us ship.

*Plain words.* A **model card** is the README of one model — the name, the exact version we
scored against, where its numbers come from, what its licence allows, and how much of our
data it can speak about. This module parses and validates the roster that holds those cards,
and generates one JSON card per model plus the repository's licence manifest.

The roster is two files deep on purpose: ``models.toml`` is the shared roster, edited only
when the roster itself changes, and ``models.d/<key>.toml`` is one fragment per later lane or
per measured digest. A fragment **adds** a model or **overrides** fields of one already there
(top-level fields replace, ``params`` merges key by key), so two agents adding two lanes never
edit one file, and a measured ``sha256`` arrives as a fragment. Two fragments claiming one key
is an error — that is a genuine collision.

Nothing here downloads, scores or touches patient data: a card is a declaration, and the
adapters in :mod:`mva.zoo.adapters` are what act on it.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .types import Coverage

__all__ = [
    "ADAPTER_FOR_SOURCE",
    "ADAPTER_PARAMS",
    "DEFAULT_FRAGMENTS_DIR",
    "DEFAULT_MODELS_TOML",
    "INPUT_CLASSES",
    "REGENERATE",
    "SCOPES",
    "SHIPS",
    "SOURCES",
    "ModelCard",
    "RegistryError",
    "card_with_coverage",
    "enabled",
    "licence_manifest",
    "load",
    "mvp",
    "with_digest",
    "write_cards",
]

#: The shared roster, and the folder of per-lane fragments beside it.
DEFAULT_MODELS_TOML = Path(__file__).with_name("models.toml")
DEFAULT_FRAGMENTS_DIR = Path(__file__).with_name("models.d")

#: Where a model's numbers come from. One adapter module speaks each of these.
SOURCES: tuple[str, ...] = ("warehouse-column", "table", "vep-rest", "local-process", "modal")

#: What a model will read: a protein change, a splice site, any variant, a structure, or —
#: for the Track 2 lanes — a disease node rather than an allele at all.
INPUT_CLASSES: tuple[str, ...] = ("missense", "splice", "any", "structure", "disease-node")

#: Plan §5 buckets: the MVP four, then the two optional widenings.
SCOPES: tuple[str, ...] = ("mvp", "opt-a", "opt-b")

#: One adapter per source — the roster may not pair them freely.
ADAPTER_FOR_SOURCE: Mapping[str, tuple[str, ...]] = {
    "warehouse-column": ("warehouse_column",),
    # A downloaded table has two shapes: keyed by the genomic change (`duckdb_lookup`) or
    # keyed by a protein accession and a one-letter residue change (`protein_table`).
    # Which one a table is, is a fact about the publisher, not about the source kind.
    # A third shape, added in wave 4: keyed on the genomic change itself
    # (`coordinate_table`), which is joined inside `build/` because the record set that
    # leaves this machine carries no coordinate.
    "table": ("duckdb_lookup", "protein_table", "coordinate_table"),
    "vep-rest": ("vep_rest",),
    "local-process": ("local_process",),
    "modal": ("modal",),
}

#: What each adapter needs in ``params`` before a lane may be enabled. Anything else in
#: ``params`` is the adapter's own business and is passed through untouched.
ADAPTER_PARAMS: Mapping[str, tuple[str, ...]] = {
    "warehouse_column": ("table", "column"),
    "duckdb_lookup": ("key", "url"),
    "protein_table": ("key", "url"),
    "coordinate_table": ("key", "url"),
    "vep_rest": ("plugin",),
    "local_process": ("entrypoint",),
    "modal": ("image",),
}

#: What the public repository is allowed to ship for each source. A non-commercial score
#: table is never committed; the fetch script and its digest are.
SHIPS: Mapping[str, str] = {
    "warehouse-column": "nothing to fetch — the score is already a warehouse column",
    "table": "fetch script + digest, never the score file",
    "vep-rest": "no file — scores are fetched per allele from the public REST service",
    "local-process": "no weights — the model's own installer fetches them; digest per run",
    "modal": "no weights — the remote image pulls them; digest and venue recorded per run",
}

#: The one command that writes the manifest, quoted in the manifest itself.
REGENERATE = (
    'uv run python -c "from mva.zoo import registry as r; '
    "r.write_cards(r.load(), 'docs/iteration4/cards')\""
)

_GENERATED = (
    f"**Generated**, not written: `{REGENERATE}`. Edit `src/mva/zoo/models.toml` (or a "
    "`models.d/*.toml` fragment), never this file."
)

_WHY = (
    "Hackathon use is non-commercial, so a non-commercial licence is not a blocker for "
    "*running* a model. It is a blocker for *shipping its file*: no score table, no weights "
    "and no derived dump of either is ever committed. The last column says what is "
    "committed instead."
)

#: Every field a card must carry. `pmid`, `notes` and `params` are the only optional ones.
_REQUIRED = (
    "name", "key", "version", "tier", "input_class", "source", "adapter",
    "licence", "licence_url", "non_commercial", "catalogue_adjacent", "scope", "enabled",
)  # fmt: skip


class RegistryError(ValueError):
    """A roster file that cannot be trusted: a missing field, an impossible pairing, or two
    fragments claiming one key. Raised at load time so no run starts on a bad card."""


@dataclass(frozen=True)
class ModelCard:
    """One model's declaration — the TOML table, parsed and checked.

    Frozen because a card is a fact about a published artefact: a run may read it, never
    edit it. ``params`` is whatever the adapter needs (a warehouse column name, a download
    URL, a REST plugin flag); :data:`ADAPTER_PARAMS` says which keys are mandatory.
    """

    name: str
    key: str
    version: str
    tier: int
    input_class: str
    source: str
    adapter: str
    licence: str
    licence_url: str
    non_commercial: bool
    catalogue_adjacent: bool
    scope: str
    enabled: bool
    pmid: str = ""
    notes: str = ""
    params: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """The card as plain JSON-able data, in a stable field order."""
        return {
            "key": self.key,
            "name": self.name,
            "version": self.version,
            "tier": self.tier,
            "input_class": self.input_class,
            "source": self.source,
            "adapter": self.adapter,
            "params": dict(self.params),
            "licence": self.licence,
            "licence_url": self.licence_url,
            "non_commercial": self.non_commercial,
            "catalogue_adjacent": self.catalogue_adjacent,
            "pmid": self.pmid,
            "scope": self.scope,
            "enabled": self.enabled,
            "ships": SHIPS[self.source],
            "notes": self.notes.strip(),
        }


def _as_table(raw: object, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RegistryError(f"{where}: expected a table, got {type(raw).__name__}")
    return dict(raw)


def _read(path: Path) -> dict[str, dict[str, Any]]:
    """Every ``[models.<key>]`` table in one TOML file, unvalidated."""
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    models = _as_table(document.get("models", {}), f"{path}: [models]")
    return {key: _as_table(table, f"{path}: [models.{key}]") for key, table in models.items()}


def _merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """A fragment over a roster entry: top-level fields replace, ``params`` merges by key.

    Merging ``params`` is what lets a one-line fragment carry a measured ``sha256`` without
    restating the URL and the join key.
    """
    merged = {**base, **{k: v for k, v in patch.items() if k != "params"}}
    if "params" in patch:
        merged["params"] = {**base.get("params", {}), **_as_table(patch["params"], "params")}
    return merged


def _check_str(table: dict[str, Any], name: str, key: str, allowed: tuple[str, ...]) -> str:
    value = table[name]
    if not isinstance(value, str) or value not in allowed:
        raise RegistryError(f"model {key!r}: {name}={value!r} is not one of {allowed}")
    return value


def _card(key: str, table: dict[str, Any], origin: str) -> ModelCard:
    """Validate one merged table and build its card, or say exactly what is wrong."""
    missing = [name for name in _REQUIRED if name not in table]
    if missing:
        raise RegistryError(f"model {key!r} ({origin}): missing field(s) {', '.join(missing)}")
    if table["key"] != key:
        raise RegistryError(f"model {key!r} ({origin}): key field says {table['key']!r}")
    tier = table["tier"]
    if tier not in (1, 2, 3):
        raise RegistryError(f"model {key!r}: tier={tier!r} is not 1, 2 or 3")
    source = _check_str(table, "source", key, SOURCES)
    adapter = table["adapter"]
    if adapter not in ADAPTER_FOR_SOURCE[source]:
        served = ", ".join(repr(name) for name in ADAPTER_FOR_SOURCE[source])
        raise RegistryError(
            f"model {key!r}: source={source!r} is served by {served}, not by adapter={adapter!r}"
        )
    card = ModelCard(
        name=str(table["name"]),
        key=key,
        version=str(table["version"]),
        tier=int(tier),
        input_class=_check_str(table, "input_class", key, INPUT_CLASSES),
        source=source,
        adapter=str(adapter),
        licence=str(table["licence"]),
        licence_url=str(table["licence_url"]),
        non_commercial=bool(table["non_commercial"]),
        catalogue_adjacent=bool(table["catalogue_adjacent"]),
        scope=_check_str(table, "scope", key, SCOPES),
        enabled=bool(table["enabled"]),
        pmid=str(table.get("pmid", "")),
        notes=str(table.get("notes", "")),
        params=_as_table(table.get("params", {}), f"model {key!r}: params"),
    )
    _check_params(card)
    _check_pmid(card)
    return card


def _check_params(card: ModelCard) -> None:
    """An enabled lane must carry every parameter its adapter reads. A disabled lane may be
    a stub — that is the point of declaring a model before it can run."""
    if not card.enabled:
        return
    needed = ADAPTER_PARAMS[card.adapter]
    absent = [name for name in needed if not card.params.get(name)]
    if absent:
        raise RegistryError(
            f"model {card.key!r} is enabled but its {card.adapter} adapter has no "
            f"{', '.join(absent)} in params"
        )


def _check_pmid(card: ModelCard) -> None:
    if card.pmid and not card.pmid.isdigit():
        raise RegistryError(
            f"model {card.key!r}: pmid={card.pmid!r} is not a PMID. Only verified numeric "
            "PMIDs belong here; leave it empty until the check has run."
        )


def load(
    path: Path | str = DEFAULT_MODELS_TOML,
    fragments_dir: Path | str | None = DEFAULT_FRAGMENTS_DIR,
) -> dict[str, ModelCard]:
    """Every model in the roster, keyed by ``key``, fragments applied.

    Fragments are read in sorted filename order. A fragment may add a model or override
    fields of a roster entry; two fragments claiming one key is an error, because that is
    two lanes disagreeing rather than one lane being refined.
    """
    base = _read(Path(path))
    tables = {key: dict(table) for key, table in base.items()}
    origins = dict.fromkeys(base, str(path))
    claimed: dict[str, str] = {}

    directory = Path(fragments_dir) if fragments_dir is not None else None
    if directory is not None and directory.is_dir():
        for fragment in sorted(directory.glob("*.toml")):
            for key, table in _read(fragment).items():
                if key in claimed:
                    raise RegistryError(
                        f"model {key!r} is claimed by two fragments: "
                        f"{claimed[key]} and {fragment.name}. One fragment per model."
                    )
                claimed[key] = fragment.name
                tables[key] = _merge(tables.get(key, {}), table)
                origins[key] = str(fragment)

    return {key: _card(key, table, origins[key]) for key, table in sorted(tables.items())}


def enabled(cards: Mapping[str, ModelCard]) -> dict[str, ModelCard]:
    """The lanes that actually run."""
    return {key: card for key, card in cards.items() if card.enabled}


def mvp(cards: Mapping[str, ModelCard]) -> dict[str, ModelCard]:
    """The lanes on the MVP critical path (plan §1b), enabled or not."""
    return {key: card for key, card in cards.items() if card.scope == "mvp"}


def with_digest(card: ModelCard, sha256: str) -> ModelCard:
    """The same card with a measured digest in ``params`` — what a fetch produces."""
    return replace(card, params={**card.params, "sha256": sha256})


def card_with_coverage(card: ModelCard, coverage: Coverage) -> dict[str, Any]:
    """The card plus how much of a record set this model could actually score.

    This is the shape the step-5 report renders: a declaration is not a result, and a model
    that covers 4 % of the callset is a different object from one that covers 94 %.
    """
    payload = card.as_dict()
    payload["coverage"] = {
        "model": coverage.model,
        "scored": coverage.scored,
        "total": coverage.total,
        "fraction": round(coverage.fraction, 6),
        "by_consequence": {
            consequence: {"scored": scored, "total": total}
            for consequence, (scored, total) in sorted(coverage.by_consequence.items())
        },
    }
    return payload


def licence_manifest(cards: Mapping[str, ModelCard]) -> str:
    """The licence page: one row per model, and what the public repo may ship for it."""
    lines = [
        "# Model licences — what this repository may ship",
        "",
        _GENERATED,
        "",
        _WHY,
        "",
        "| model | version | scope | licence | non-commercial | this repo ships | terms |",
        "|---|---|---|---|---|---|---|",
    ]
    for card in cards.values():
        flag = "**yes**" if card.non_commercial else "no"
        state = card.scope if card.enabled else f"{card.scope} (off)"
        lines.append(
            f"| {card.name} | {card.version} | {state} | {card.licence} | {flag} | "
            f"{SHIPS[card.source]} | [terms]({card.licence_url}) |"
        )
    lines += [
        "",
        (
            f"{len(cards)} models declared, {len(enabled(cards))} enabled,"
            f" {sum(1 for c in cards.values() if c.non_commercial)} under non-commercial"
            f" terms, {sum(1 for c in cards.values() if c.catalogue_adjacent)}"
            " catalogue-adjacent (trained on a variant catalogue, so the merge is printed"
            " with and without them)."
        ),
        "",
    ]
    return "\n".join(lines)


def write_cards(cards: Mapping[str, ModelCard], out_dir: Path | str) -> list[Path]:
    """One ``<key>.json`` per model plus ``licences.md``. Returns what it wrote.

    The JSON cards are the machine-readable half (the dashboard and the step-5 report read
    them); the manifest is the human half.
    """
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key, card in sorted(cards.items()):
        target = directory / f"{key}.json"
        payload = json.dumps(card.as_dict(), indent=2, sort_keys=False, ensure_ascii=False)
        target.write_text(payload + "\n", encoding="utf-8")
        written.append(target)
    manifest = directory / "licences.md"
    manifest.write_text(licence_manifest(cards), encoding="utf-8")
    written.append(manifest)
    return written
