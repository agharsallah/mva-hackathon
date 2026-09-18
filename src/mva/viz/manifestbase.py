"""The shape every provenance manifest in this repository opens with.

A manifest says what a committed file was built from: the envelope (name, build time,
build command, code version), one entry per input with its digest, one per output, and
the JSON writer. Three builders need exactly this — :mod:`mva.viz.referencemanifest` for
the population-reference tables, :mod:`mva.viz.genesetmanifest` for the gene sets, and
``tools/build_coding_regions.py`` for the coding-region table — and a fourth arrived with
step 8's cytoband table. They were reaching into one module's private names to get it,
which is the signal that the shape is shared and the concern is its own.

**A digest is measured or it is null.** :func:`fileinput` hashes an input when the file is
on disk and writes ``sha256: null`` plus a ``known_gap`` sentence when it is not. A digest
copied out of a README would name bytes this run never saw, which is worse than a stated
gap because it looks checked.

**Every path is repository-relative where it can be.** An absolute path names one laptop.
:func:`repo_relative` converts what it can and leaves a path outside the tree alone, since
a relative form of that would be a lie about where the bytes were.

No genomic position is written here or can be: these functions record paths, URLs,
releases, digests, byte counts and row counts.
"""

import json
from pathlib import Path

from . import refprovenance


def repo_relative(path: Path) -> str:
    """``ressources/reference/qc_norms.tsv``, not ``/Users/someone/checkout/…``.

    Every path a manifest records is written relative to the repository root when it is
    under it, because an absolute path names one laptop. ``mva.viz.refprovenance`` reads
    the manifests through relative paths for the same reason. A path outside the tree —
    the gitignored scratch download, if it was pointed elsewhere — is kept as it is,
    since a relative form of it would be a lie about where the bytes were.
    """
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def fileinput(path: Path, name: str, url: str, role: str, release: str | None = None) -> dict:
    """One input, digested when the file is on disk and honestly empty when it is not."""
    sha, size = refprovenance.digest(path) if path.is_file() else (None, None)
    entry = {
        "name": name,
        "url": url,
        "release": release,
        "sha256": sha,
        "bytes": size,
        "role": role,
    }
    if sha is None:
        entry["known_gap"] = (
            f"{repo_relative(path)} was not on disk when this manifest was written, so its "
            "digest and byte count are null rather than copied from a previous run. "
            "Re-run the build with the scratch download present to record them."
        )
    return entry


def committed(path: Path, role: str) -> dict:
    """An input that lives in the repository, addressed as a ``file://`` URL."""
    where = repo_relative(path)
    return fileinput(path, where, f"file://{where}", role)


def output(path: Path) -> dict:
    """One output, as ``{path, sha256, bytes, rows}``. Rows exclude the header line."""
    sha, size = refprovenance.digest(path)
    with path.open(encoding="utf-8") as stream:
        rows = max(sum(1 for _ in stream) - 1, 0)
    return {"path": repo_relative(path), "sha256": sha, "bytes": size, "rows": rows}


def envelope(name: str, built_by: str) -> dict:
    """The five fields every manifest in this repository opens with."""
    return {
        "name": name,
        "built_at": refprovenance.now(),
        "built_by": built_by,
        "code_version": refprovenance.code_version(),
        "code_version_note": (
            "the commit at build time, which precedes the commit that lands this file"
        ),
    }


def write(manifest: dict, path: Path) -> Path:
    """Write one manifest as pretty JSON with a trailing newline. Returns ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path
