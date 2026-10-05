"""The mmCIF *syntax* layer: tokenising a line, and reading one ``loop_`` table.

Split out of :mod:`sepiq.viz.mmcif` so the file format and the structural biology are two
bounded concerns: this module knows nothing about atoms, residues or chains — it turns
text into rows of strings. :mod:`sepiq.viz.mmcif` gives those rows meaning.

**What the format is.** An mmCIF file is a bundle of named tables in one text file. A
table with many rows is written as a ``loop_`` header listing the column names
(``_atom_site.label_atom_id``, one per line) followed by data rows. Values are separated
by *any* whitespace — spaces, runs of spaces, or tabs — and a value containing a space is
quoted (``'two words'``). In software terms: a CSV whose delimiter is `\\s+` and whose
header rows are named.

**What is supported here, exactly.** Three value forms, which is every form the two
tables this repo reads actually use:

* a bare value, ended by any whitespace;
* a single- or double-quoted value on one line;
* a **multi-line text field**: a line whose *first character* is ``;`` opens it, and a
  line that is exactly ``;`` closes it. The lines between are joined with ``\\n`` and
  become one token, so a ``_struct_conf.details`` paragraph cannot shift the row's later
  columns — and a line inside it beginning ``_`` or ``#`` cannot end the loop early.

Not supported, and stated so rather than half-handled: ``save_`` frames, ``global_``
blocks, and a quoted value whose closing quote is missing (the rest of the line becomes
the value). An unterminated ``;`` field is a loud :class:`MmcifError`, never a silent
short row.
"""

#: The value mmCIF writes for "not applicable" and "unknown". Read as absent.
NULLS = frozenset({".", "?"})


class MmcifError(ValueError):
    """The file is not mmCIF, or lacks the atom table a trace needs."""


def loop_rows(text: str, category: str) -> list[dict[str, str]]:
    """Every row of the ``loop_`` table for ``category``, as tag → value dicts.

    ``category`` is the name without its leading underscore (``"atom_site"``). Returns an
    empty list when the file has no such loop — an absent secondary-structure table is a
    normal state, not an error, so this reports absence rather than raising.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != "loop_":
            continue
        tags, first_row = _loop_header(lines, index + 1, category)
        if tags:
            return _loop_body(lines, first_row, tags)
    return []


def tokens(line: str) -> list[str]:
    """One line's values, split on any whitespace *outside* quotes.

    Two rules, both load-bearing:

    * splitting on **any** whitespace run, not on a single space — mmCIF permits tabs and
      aligned columns, and ``partition(" ")`` on a tab-separated row returns one token
      holding several values, shifting every later column of that row. Silent corruption,
      which is worse than a failure;
    * a quote only opens a value at a token boundary, so an apostrophe *inside* a value
      (the ``O5'`` atom name) is data, not a delimiter.
    """
    out: list[str] = []
    rest = line.strip()
    while rest:
        if rest[0] in "'\"":
            quote = rest[0]
            end = rest.find(quote, 1)
            if end == -1:
                out.append(rest[1:])
                break
            out.append(rest[1:end])
            rest = rest[end + 1 :].lstrip()
            continue
        head, rest = _split_one(rest)
        out.append(head)
    return out


def value(raw: str | None, *, keep_null: bool = False) -> str | None:
    """``raw`` with mmCIF's two null spellings read as absent."""
    if raw is None:
        return None
    if raw in NULLS and not keep_null:
        return None
    return raw


def as_int(raw: str | None) -> int | None:
    """``raw`` as an integer, or ``None``. Never raises — absence is a normal state."""
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def as_float(raw: str | None) -> float | None:
    """``raw`` as a float, or ``None``. Never raises."""
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


# ── internals ────────────────────────────────────────────────────────────────────────


def _split_one(rest: str) -> tuple[str, str]:
    """``rest`` cut at its first whitespace run: the token, and what follows it."""
    parts = rest.split(None, 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _loop_header(lines: list[str], start: int, category: str) -> tuple[list[str], int]:
    """The tag list of the loop starting at ``start``, if it belongs to ``category``."""
    prefix = f"_{category}."
    tags: list[str] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("_"):
        tags.append(lines[index].strip())
        index += 1
    if not tags or not tags[0].startswith(prefix):
        return [], index
    return [tag.removeprefix(prefix) for tag in tags], index


def _loop_body(lines: list[str], start: int, tags: list[str]) -> list[dict[str, str]]:
    """Data rows of a loop, tokenised.

    A row may wrap across lines (mmCIF allows it), so tokens accumulate until a full row's
    worth is available rather than being read a line at a time. A ``;`` text field is read
    whole first, which is why the "does this line end the loop?" test below can never see
    a line that only *looks* like a new category.
    """
    rows: list[dict[str, str]] = []
    pending: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line.startswith(";"):
            field, index = _text_field(lines, index)
            pending.append(field)
        else:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "_")) or stripped == "loop_":
                break
            pending.extend(tokens(line))
            index += 1
        while len(pending) >= len(tags):
            rows.append(dict(zip(tags, pending[: len(tags)], strict=True)))
            pending = pending[len(tags) :]
    return rows


def _text_field(lines: list[str], index: int) -> tuple[str, int]:
    """One multi-line ``;``-delimited value, and the index of the line after it."""
    opener = lines[index][1:]
    parts: list[str] = [opener] if opener.strip() else []
    index += 1
    while index < len(lines):
        if lines[index].rstrip() == ";":
            return "\n".join(parts).strip(), index + 1
        parts.append(lines[index])
        index += 1
    raise MmcifError("unterminated ';' text field — the loop_ body ends mid-value")
