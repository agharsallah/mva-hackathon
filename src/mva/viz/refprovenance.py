"""Where every committed reference file and offline fixture came from, in one row shape.

The warehouse has :mod:`mva.warehouse.lineage_edges`: an append-only edge list saying
which *table* was derived from which object, at which version, by which transform. It
cannot cover the other half of the repository's inputs, because those are not derivations
at all. A gnomAD constraint table, an HPO release, an Ensembl gene record and an AlphaFold
model are **fetched**, not computed — there is no upstream table and no transform, so a
lineage edge for them would be a fabricated one.

What they have instead is a **manifest** committed next to the bytes: a small JSON file
saying what was fetched, from where, at which release, with which digest, by which tool at
which commit. Two families exist and they were written independently, so their shapes
differ:

* ``ressources/reference/*provenance.json`` — one manifest per reference build
  (``hpo_provenance.json``, ``structure_genes.provenance.json``).
* ``app/src/fixtures/data/**/_provenance.json`` — one manifest per fixture directory,
  written by ``tools/build_protein_fixture.py``, carrying a per-gene block and a
  REAL-vs-SYNTHETIC map for every top-level field of the payload.

This module is the *reader*: it normalises both families onto the single row shape
``ReferenceProvenanceRow`` in ``app/src/api/types/provenance.ts`` so one page can list
them side by side. It also owns the two primitives the *writers* need — a file digest and
the current commit — so the tools and the route cannot disagree about how a sha256 is
computed.

A missing directory yields no rows rather than an error: a checkout that has not built its
reference tables has nothing to declare, which is a true statement, not a failure.
"""

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Where the committed reference tables and their manifests live.
REFERENCE_DIR = Path("ressources/reference")

#: Fixture directories that carry a manifest. Each holds one JSON file per gene.
FIXTURE_DIRS = (
    Path("app/src/fixtures/data/protein"),
    Path("app/src/fixtures/data/gene-structure"),
)

#: The manifest filename inside a fixture directory. Leading underscore so it sorts away
#: from the per-gene files and cannot be mistaken for a gene called "provenance".
FIXTURE_MANIFEST = "_provenance.json"

#: How a reference manifest is recognised: ``hpo_provenance.json``,
#: ``structure_genes.provenance.json``. Matched as a suffix so both spellings are found.
REFERENCE_SUFFIX = "provenance.json"

#: Bytes per read when digesting. Reference tables reach a few megabytes; the AlphaFold
#: fixtures reach ~180 kB each. Neither is worth holding whole in memory.
CHUNK = 1 << 20


# ── the primitives both the writers and the reader use ───────────────────────────────


def digest(path: Path) -> tuple[str, int]:
    """``(sha256 hex, byte count)`` for one file. The one definition in the repository.

    The tools that *write* a manifest and the route that *reads* one both call this, so a
    digest recorded at build time and a digest computed later cannot differ because two
    call sites chose different chunking or a different algorithm.
    """
    sha = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            sha.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), size


def code_version() -> str:
    """The short commit the build ran at, or ``"unknown"``.

    Shelling out to git is deliberate and is only ever done by a build tool: the value
    belongs in the manifest, not in the request path. ``unknown`` rather than an
    exception, because a manifest built from a tarball with no ``.git`` is still a
    manifest — it simply cannot name a commit, and saying so beats guessing one.

    Like ``hpo_provenance.json``'s own note says, this is the commit *at build time*,
    which precedes the commit that lands the built files.
    """
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown"


def now() -> str:
    """The build instant, as the ISO-8601 UTC string every manifest's ``built_at`` uses."""
    return datetime.now(UTC).isoformat(timespec="seconds")


# ── the reader ───────────────────────────────────────────────────────────────────────


def rows(
    reference_dir: Path | None = None,
    fixture_dirs: tuple[Path, ...] | None = None,
) -> list[dict]:
    """Every manifest found, normalised, reference tables first then fixtures.

    Ordered by ``(kind, path)`` so the list is stable across filesystems: a page that
    renders it must not reorder itself because one machine's ``iterdir`` differs from
    another's.
    """
    directory = REFERENCE_DIR if reference_dir is None else reference_dir
    found = [_reference_row(path) for path in sorted(_manifests(directory))]
    for fixtures in FIXTURE_DIRS if fixture_dirs is None else fixture_dirs:
        row = _fixture_row(fixtures / FIXTURE_MANIFEST)
        if row is not None:
            found.append(row)
    return [row for row in found if row is not None]


def _manifests(directory: Path) -> list[Path]:
    """Every ``*provenance.json`` in ``directory``. Empty when the directory is absent."""
    try:
        return [path for path in directory.iterdir() if path.name.endswith(REFERENCE_SUFFIX)]
    except OSError:
        return []


def _load(path: Path) -> dict | None:
    """One manifest as a dict, or ``None`` when it is missing or not an object.

    A corrupt manifest is skipped rather than raised: the endpoint's job is to list what
    can be vouched for, and a file that cannot be parsed vouches for nothing. It is not
    silent — the file simply does not appear, and the tool that writes it is what would
    fail loudly.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _reference_row(path: Path) -> dict | None:
    """Normalise a ``ressources/reference`` manifest onto the row shape."""
    payload = _load(path)
    if payload is None:
        return None
    return {
        "name": str(payload.get("name") or path.name.replace(REFERENCE_SUFFIX, "").strip("._")),
        "kind": "reference",
        "path": path.as_posix(),
        "built_at": _text(payload.get("built_at")),
        "built_by": _text(payload.get("built_by")),
        "code_version": _text(payload.get("code_version")),
        "inputs": [_input(entry) for entry in _list(payload.get("inputs"))],
        "outputs": _outputs(payload.get("outputs"), path.parent),
        "note": _note(payload),
    }


def _fixture_row(path: Path) -> dict | None:
    """Normalise a fixture directory's ``_provenance.json`` onto the row shape."""
    payload = _load(path)
    if payload is None:
        return None
    return {
        "name": str(payload.get("name") or path.parent.name),
        "kind": "fixture",
        "path": path.as_posix(),
        "built_at": _text(payload.get("built_at")),
        "built_by": _text(payload.get("built_by")),
        "code_version": _text(payload.get("code_version")),
        "inputs": [_input(entry) for entry in _list(payload.get("inputs"))],
        "outputs": _outputs(payload.get("outputs"), path.parent),
        "note": _note(payload),
    }


def _outputs(value: Any, beside: Path) -> list[dict]:
    """The files a build produced, as ``{path, sha256, bytes, rows}``.

    Two input spellings, because the two manifest families disagree and neither is being
    rewritten to suit the other:

    * a **list** of objects that already carry the digest — what this repository's own
      tools write, so the digest is the one measured at build time.
    * a **mapping** of filename → row count, which ``hpo_provenance.json`` uses. It
        records no digest, so one is computed from the file on disk *now*. That is a
      weaker statement and the difference is real: it says "this is what the file
        hashes to today", not "this is what the build wrote".
    """
    if isinstance(value, list):
        return [
            {
                "path": _text(entry.get("path")),
                "sha256": _text(entry.get("sha256")),
                "bytes": _int(entry.get("bytes")),
                "rows": _int(entry.get("rows")),
            }
            for entry in value
            if isinstance(entry, dict)
        ]
    if not isinstance(value, dict):
        return []
    out = []
    for name, count in value.items():
        path = beside / str(name)
        sha, size = digest(path) if path.is_file() else ("", None)
        out.append(
            {
                "path": path.as_posix(),
                "sha256": sha,
                "bytes": size,
                "rows": _int(count),
            }
        )
    return out


def _input(entry: Any) -> dict:
    """One upstream, as ``{name, url, release, sha256, bytes}``.

    ``release`` absorbs a ``version`` key as well: an ontology names a release, an
    AlphaFold model names a version, and a reader comparing two rows does not care which
    word the upstream chose for "which snapshot of it did we take".
    """
    if not isinstance(entry, dict):
        return {"name": str(entry), "url": "", "release": None, "sha256": None, "bytes": None}
    return {
        "name": _text(entry.get("name")),
        "url": _text(entry.get("url")),
        "release": _optional(entry.get("release") or entry.get("version")),
        "sha256": _optional(entry.get("sha256")),
        "bytes": _int(entry.get("bytes")),
    }


def _note(payload: dict) -> str:
    """The row's one-line explanation: an explicit ``note``, else the ``method``."""
    return _text(payload.get("note") or payload.get("method"))


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _optional(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
