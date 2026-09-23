"""Helpers every lane container shares: the image base, the weights digest, the timer.

Imported inside Modal containers (the image carries ``mva`` via
``add_local_python_source``) and on the laptop at deploy time, so stdlib and ``modal`` only.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from ..modal_contract import WEIGHTS_VOLUME

__all__ = [
    "CONTAINER_MODULES",
    "MINUTES",
    "SCALEDOWN_SECONDS",
    "Timer",
    "sha256_tree",
    "timed",
    "weights_volume",
    "with_mva",
]

MINUTES = 60
#: Containers scale to zero one minute after the last call: idle GPU time is billed.
SCALEDOWN_SECONDS = 60


#: The only ``mva`` files a lane container needs, relative to ``src/mva``. Shipping the whole
#: package would re-upload (and fail on) any file another lane is editing mid-build.
CONTAINER_MODULES = (
    "__init__.py",
    "zoo/__init__.py",
    "zoo/types.py",
    "zoo/modal_contract.py",
    "zoo/modal_apps/__init__.py",
    "zoo/modal_apps/_common.py",
)


def with_mva(image: Any, lane: str) -> Any:
    """``image`` plus the contract modules and this lane's own file, nothing else of ``mva``."""
    keep = {*CONTAINER_MODULES, f"zoo/modal_apps/{lane}.py"}
    root = Path(__file__).resolve().parents[2]  # src/mva

    def ignore(path: Path) -> bool:
        full = path if path.is_absolute() else root / path
        try:
            rel = full.resolve().relative_to(root).as_posix()
        except ValueError:
            return True
        return full.is_file() and rel not in keep

    return image.add_local_python_source("mva", ignore=ignore)


def weights_volume(key: str) -> Any:
    """The lane's own weights volume, created on first use (listed in the deletion checklist)."""
    import modal

    return modal.Volume.from_name(WEIGHTS_VOLUME.format(key=key), create_if_missing=True)


def sha256_tree(
    root: Path, suffixes: tuple[str, ...] = (".safetensors", ".bin", ".pt", ".ckpt")
) -> str:
    """One digest over every weights file under ``root``, in sorted path order."""
    outer = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes):
        inner = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 22), b""):
                inner.update(block)
        outer.update(f"{path.relative_to(root)}:{inner.hexdigest()}\n".encode())
    return outer.hexdigest()


class Timer:
    seconds: float = 0.0


@contextmanager
def timed() -> Iterator[Timer]:
    timer = Timer()
    started = time.perf_counter()
    try:
        yield timer
    finally:
        timer.seconds = time.perf_counter() - started
