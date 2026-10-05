"""Where the repository root is, so a relative default path means the same thing everywhere.

Most default paths in this package are written relative — ``data/raw/...``,
``build/api-cache``, ``docs/``. That is deliberate: they name positions in *this*
repository, not absolute locations on one machine, so a checkout anywhere works and
nothing committed carries a developer's home directory.

The cost is that they only resolve when the working directory is the repository root. A
server started from ``app/`` reads the same code and finds nothing: every input table is
"missing", and the symptom is not an error but an **empty answer** — a route serving
``[]``. Silent emptiness is the worst failure shape available, because it looks like a
finding.

So a long-running entry point anchors itself: :func:`anchor_cwd` moves the process to the
repository root once, at startup, before any module reads a default path. It is done there
rather than by rewriting every default to an absolute path because the relative spellings
are the contract the module docstrings state, and one ``chdir`` in an entry point is a
smaller, more reviewable thing than a hundred call sites.

Nothing here reads a file: it is directory arithmetic.
"""

import os
from functools import lru_cache
from pathlib import Path

#: Files and directories that together identify a checkout of *this* repository rather
#: than any Python project that happens to sit above the installed package. All must be
#: present, so a stray ``pyproject.toml`` in a parent directory cannot claim the root.
MARKERS = ("pyproject.toml", "src/sepiq", "docs")


@lru_cache(maxsize=1)
def repo_root() -> Path | None:
    """The repository root, or ``None`` when this package is not running from a checkout.

    Found by walking up from this file, which is what makes it independent of the working
    directory. ``None`` is a real answer, not a failure: a wheel installed into
    site-packages has no repository above it, and the caller then keeps the working
    directory it was given rather than inventing one.
    """
    for directory in Path(__file__).resolve().parents:
        if all((directory / marker).exists() for marker in MARKERS):
            return directory
    return None


def resolve(path: Path | str) -> Path:
    """``path`` made absolute against the repository root, or against the cwd without one.

    For a caller that wants one path anchored without moving the whole process. An
    already-absolute path is returned unchanged.
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    root = repo_root()
    return (root / candidate) if root else candidate.resolve()


def anchor_cwd() -> Path | None:
    """Move the process to the repository root. Returns the previous cwd if it moved.

    Called once by a long-running entry point, before the first module reads a relative
    default. Returns ``None`` when nothing moved — either the cwd is already the root, or
    there is no checkout to move to — so a caller can print the change and stay quiet
    otherwise.
    """
    root = repo_root()
    if root is None:
        return None
    previous = Path.cwd().resolve()
    if previous == root:
        return None
    os.chdir(root)
    return previous
