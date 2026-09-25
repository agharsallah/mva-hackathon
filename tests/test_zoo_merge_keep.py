"""A re-render of the merged report keeps every section a person wrote.

The renderer owns the preamble and ``## 1.`` … ``## 6.``. Iteration 4's ``report.md`` also
carries a hand-written headline above §1 and a Track 2 chapter and a limitations table after
§6; before this fix a re-render deleted both (``docs/iteration4/todo.md``, T2's open risk).
These tests pin the contract: a hand-written ``## `` section comes back **byte for byte**, in
the place it was, while the generated sections are refreshed from the new JSON.

Every report here is invented; no coordinate, no patient value.
"""

from __future__ import annotations

from pathlib import Path

from mva.zoo import workflow
from mva.zoo.merge_render import HandWritten, hand_written_sections, render_merged
from mva.zoo.workflow_types import Deps

CONFIG = "src/mva/zoo/zoo.example.toml"


def report(run_id: str) -> dict:
    """The smallest merged JSON the renderer accepts; ``run_id`` is what a re-render changes."""
    return {"run_id": run_id, "generated_at": "2099-01-01T00:00:00+00:00", "method": "fusion"}


#: The shapes a hand-written chapter really holds: a table, an HTML comment, a fence whose
#: ``## `` line is code rather than a heading, a figure, and a sub-heading.
TRACK2 = """## 7. Track 2 — mechanism to drug direction

<!-- hand-written 2099-01-01. Not produced by render_merged. -->

| link | state |
|---|---|
| mechanism | loss of function |

```text
## not a heading: it is inside a fence
```

### 7.1 a sub-section

![a figure](../../figures/demo.svg)"""

LIMITS = """## 8. Limitations

- one skipped lane, and the question it leaves open"""

HEADLINE = """## The headline

**One sentence**, a table and a figure, above everything generated.

| measured | result |
|---|---|
| consensus | rank 3 of 40 |"""


def test_a_re_render_keeps_sections_7_and_8_byte_identical(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    path.write_text(
        render_merged(report("run-old"), "A paragraph.") + "\n" + TRACK2 + "\n\n" + LIMITS + "\n",
        encoding="utf-8",
    )
    kept = hand_written_sections(path)
    assert [(h.after, h.text.splitlines()[0]) for h in kept] == [
        ("6", "## 7. Track 2 — mechanism to drug direction"),
        ("6", "## 8. Limitations"),
    ]

    again = render_merged(report("run-new"), "A paragraph.", hand_written=kept)

    assert again.endswith("\n\n" + TRACK2 + "\n\n" + LIMITS + "\n")  # verbatim, in order
    assert "run-new" in again and "run-old" not in again  # the generated part did refresh
    assert again.count("## not a heading") == 1  # the fenced line was not split on


def test_a_headline_above_section_1_stays_above_it_and_a_second_render_is_a_no_op(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report.md"
    first = render_merged(report("run-1"), "A paragraph.")
    path.write_text(first.replace("## 1. The lanes", HEADLINE + "\n\n## 1. The lanes"), "utf-8")
    before = path.read_text(encoding="utf-8")

    path.write_text(
        render_merged(report("run-1"), "A paragraph.", hand_written=hand_written_sections(path)),
        encoding="utf-8",
    )

    after = path.read_text(encoding="utf-8")
    assert after == before  # same JSON, same page: nothing moved, nothing lost
    assert after.index(HEADLINE) < after.index("## 1. The lanes")
    assert after.index("**Standing:**") < after.index(HEADLINE)  # the preamble stays generated


def test_a_section_whose_anchor_is_no_longer_written_is_kept_at_the_end() -> None:
    orphan = HandWritten(after="9", text="## 10. Written after a section that is gone")
    text = render_merged(report("run-1"), "A paragraph.", hand_written=[orphan])
    assert text.endswith("\n\n## 10. Written after a section that is gone\n")


def test_a_missing_file_has_no_hand_written_sections(tmp_path: Path) -> None:
    assert hand_written_sections(tmp_path / "absent.md") == []


def test_the_render_stage_keeps_them_across_a_forced_re_run(tmp_path: Path) -> None:
    """The stage that writes ``report.md`` in production, not only the pure renderer."""
    paths = {
        "out_dir": tmp_path / "build",
        "reports_dir": tmp_path / "reports",
        "docs_runs_dir": tmp_path / "runs",
        "merged_path": tmp_path / "report.md",
    }
    workflow.run(CONFIG, deps=Deps.fixtures("fixtures/it4"), **paths)
    merged = paths["merged_path"]
    merged.write_text(
        merged.read_text(encoding="utf-8").rstrip("\n") + "\n\n" + TRACK2 + "\n", "utf-8"
    )

    # `force=True`: a restored render leaves the file alone and would pass without running.
    workflow.run(CONFIG, force=True, deps=Deps.fixtures("fixtures/it4"), **paths)

    assert merged.read_text(encoding="utf-8").endswith("\n\n" + TRACK2 + "\n")
