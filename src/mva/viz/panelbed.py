"""The two panel columns that only exist in the committed BED file.

``ressources/data-profile/mva_panel_grch38.bed`` is a six-column BED: the standard
``chrom start end name`` plus an Ensembl gene id and a free-text note saying *why* the
gene is on the candidate list. Staging keeps only the four standard columns, because a
BED reader is entitled to assume four — so the annotation has to be read from the file.

That is fine here and only here: the BED is public gene coordinates, explicitly
whitelisted in ``.gitignore``, and it is the *source of truth* for the panel rather than
a copy of something in the database.
"""

from pathlib import Path

#: Relative to the repository root, which is where the API is started from.
DEFAULT_BED = Path("ressources/data-profile/mva_panel_grch38.bed")


def annotations(path: Path | None = None) -> dict[str, dict]:
    """Map gene symbol → ``{ensembl_id, note}``.

    A missing or short-columned file yields an empty mapping rather than an error: the
    panel's counts are the point, and the note is decoration the chart can render blank.
    """
    path = Path(path) if path else DEFAULT_BED
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    out: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith(("#", "track", "browser")):
            continue
        columns = line.rstrip("\n").split("\t")
        if len(columns) < 4:
            continue
        symbol = columns[3]
        out[symbol] = {
            "ensembl_id": columns[4] if len(columns) > 4 else None,
            "note": columns[5] if len(columns) > 5 else None,
        }
    return out
