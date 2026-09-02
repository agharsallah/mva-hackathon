#!/usr/bin/env python3
"""Convert the methods description workbook to markdown using the stdlib only.

Reads shared strings, every sheet's cell grid, and the cell comments (which carry
instructions that are invisible in a flat grid dump).
"""

import re
import sys
import zipfile
from pathlib import Path

# `<t ...>` only — the space/`>` guard stops this matching `<text>`, which wraps
# comment bodies and would otherwise swallow the run-property markup with it.
_T = re.compile(r"<t(?:\s[^>]*)?>(.*?)</t>", re.S)


def texts(fragment: str) -> str:
    return "".join(_T.findall(fragment))


def main(src: str, dst: str) -> None:
    z = zipfile.ZipFile(src)

    shared = [
        texts(si)
        for si in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode("utf8"), re.S)
    ]
    names = re.findall(r'<sheet name="([^"]+)"', z.read("xl/workbook.xml").decode("utf8"))

    lines = [
        "# Methods description form",
        "",
        (
            "Extracted from `methods_description_form.xlsx`. "
            "Column A is the question, column B is our answer slot."
        ),
        "",
    ]

    for i, name in enumerate(names, start=1):
        lines += [f"## Sheet {i}: {name}", ""]

        xml = z.read(f"xl/worksheets/sheet{i}.xml").decode("utf8")
        for row in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
            cells = []
            for attrs, body in re.findall(r"<c\b([^>]*)>(.*?)</c>", row, re.S):
                if 't="inlineStr"' in attrs:
                    cells.append(texts(body))
                    continue
                v = re.search(r"<v>(.*?)</v>", body, re.S)
                if not v:
                    continue
                cells.append(shared[int(v.group(1))] if 't="s"' in attrs else v.group(1))
            cells = [c.strip() for c in cells if c.strip()]
            if cells:
                lines.append("- " + " | ".join(cells))

        comments_file = f"xl/comments{i}.xml"
        if comments_file in z.namelist():
            notes = [
                texts(c).strip()
                for c in re.findall(
                    r"<comment\b.*?</comment>",
                    z.read(comments_file).decode("utf8"),
                    re.S,
                )
            ]
            notes = [n for n in notes if n]
            if notes:
                lines += ["", f"### Sheet {i} cell comments", ""]
                lines += [f"- {n}" for n in notes]

        lines.append("")

    with Path(dst).open("w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
