"""Shared plumbing for every ``source-*`` handler: the two external seams, the resolved
defaults, and the in-place progress line.

Both things a handler reaches outside this process — the PostgreSQL connection and the
object-store (S3-compatible bucket) settings — are bound here under one name apiece,
``attached`` and ``object_store``. A handler module calls ``context.attached(...)``
rather than importing ``attached`` for itself, so a test replaces one name
(``context.attached``) instead of patching every handler module that happens to use it.
"""

import sys
import time
from pathlib import Path

from .. import source
from ..postgres import ALIAS, attached, safe_identifier
from ..settings import Postgres, object_store, setting

__all__ = [
    "ALIAS",
    "DEFAULT_REPO",
    "DEFAULT_SOURCE",
    "DEFAULT_STAGING",
    "Postgres",
    "attached",
    "clear",
    "interactive",
    "object_store",
    "progress",
    "safe_identifier",
    "source",
]

#: Delivery directory, staging scratch directory, and the (gated) dataset the delivery
#: came from. All three resolve as real environment > ``.env`` > ``settings.DEFAULTS``.
DEFAULT_SOURCE = Path(setting("MVA_SOURCE_DIR"))
DEFAULT_STAGING = Path(setting("MVA_STAGING_DIR"))
DEFAULT_REPO = setting("MVA_HF_REPO")


#: Width used to blank the progress line. Anything shorter leaves fragments of a longer
#: previous line on screen, which is how a tidy status display turns into noise.
LINE = 96


def interactive() -> bool:
    """In-place progress needs a terminal.

    Piped to a log — which is how an hours-long transfer should actually be run —
    carriage returns and blanking spaces become noise that buries the real output, so the
    whole progress line is simply suppressed.
    """
    return sys.stdout.isatty()


def clear() -> None:
    """Blank the in-place progress line and return the cursor to its start."""
    if not interactive():
        return
    sys.stdout.write("\r" + " " * LINE + "\r")
    sys.stdout.flush()


def progress(label: str, total: int):
    """A callback printing one rewritten line, so a long upload visibly moves.

    Rate is computed over the whole transfer rather than the last chunk: an instantaneous
    figure on a multipart upload swings wildly enough to be useless for deciding whether
    to wait or cancel.
    """
    state = {"done": 0, "last": 0.0, "start": time.time()}
    if not interactive():
        return lambda chunk: None

    def report(chunk: int) -> None:
        state["done"] += chunk
        now = time.time()
        if now - state["last"] < 0.5 and state["done"] < total:
            return
        state["last"] = now
        pct = 100.0 * state["done"] / total if total else 100.0
        rate = state["done"] / max(now - state["start"], 0.001) / 1e6
        eta = (total - state["done"]) / (rate * 1e6) if rate > 0 else 0
        clear()
        sys.stdout.write(
            f"    {label:<30} {pct:5.1f}%  {state['done'] / 1e9:5.2f}/{total / 1e9:.2f} GB"
            f"  {rate:5.1f} MB/s  eta {eta / 60:4.1f}m"
        )
        sys.stdout.flush()

    return report
