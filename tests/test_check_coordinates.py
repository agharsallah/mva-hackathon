"""The coordinate gate: what counts as a leak and what is allowed to stand."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPAN = ("15", 40_140_984, 40_241_137)


@pytest.fixture(scope="module")
def gate():
    spec = importlib.util.spec_from_file_location(
        "check_coordinates", ROOT / "tools" / "check_coordinates.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module  # ``@dataclass`` looks the module up by name
    spec.loader.exec_module(module)
    return module


def scan(gate, text: str, positions=(), allowed=()):
    return gate.scan_text(
        text, rel="doc.md", positions=set(positions), span=SPAN, allowed=set(allowed)
    )


def test_a_real_looking_submission_row_is_a_leak(gate):
    row = f'PROBAND01,chr15,{12_345_678},T,G,chr15,{23_456_789},T,G,0.99,primary,"x"\n'
    found = scan(gate, row)
    assert [f.rule for f in found] == ["submission row"]


def test_a_synthetic_submission_row_with_short_positions_passes(gate):
    assert scan(gate, "PROBAND01,chr15,12345,C,T,chr15,12399,G,A,0.99,primary,\n") == []
    assert scan(gate, "PROBAND01,chr1,100000,A,T,chr1,200000,G,C,0.90,primary,\n") == []


def test_a_spec_position_is_found_anywhere_in_a_line(gate):
    found = scan(gate, "see 7:117559590 in the panel\n", positions={"117559590"})
    assert [f.rule for f in found] == ["spec position"]


def test_a_spec_position_does_not_match_inside_a_longer_number(gate):
    assert scan(gate, "count 1175595901\n", positions={"117559590"}) == []


def test_a_position_inside_the_gene_span_is_a_leak(gate):
    inside = 40_200_000  # spelled with underscores so the source itself is not a match
    for line in (f"chr15:{inside} A>G", f"15 {inside} . C T", f"15,{inside},T,G", f"15_{inside}"):
        assert [f.rule for f in scan(gate, line)] == ["inside candidate-gene span"], line


def test_the_span_endpoints_and_outside_positions_pass(gate):
    assert scan(gate, f"bcftools view -r 15:{SPAN[1]}-{SPAN[2]}\n") == []
    assert scan(gate, f"chr15:{40_100_000}-{40_300_000} is a window\n") == []  # both outside
    assert scan(gate, f"chr2:{40_200_000}\n") == []  # right number, wrong chromosome


def test_an_allowlisted_position_passes(gate):
    assert scan(gate, f"15 {40_161_230} . G A\n", allowed={str(40_161_230)}) == []


def test_the_allowlist_ignores_comments(gate, tmp_path):
    path = tmp_path / "allow.txt"
    path.write_text(f"# header\n{40_161_230}  # synthetic\n\n{40_194_393}\n")
    assert gate.load_allowlist(path) == {str(40_161_230), str(40_194_393)}


def test_spec_positions_are_read_from_the_spec(gate, tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text('{"alleles": {"a": {"chrom": "1", "pos": 5, "ref": "A", "alt": "T"}}}')
    assert gate.spec_positions(spec) == {"5"}
    assert gate.spec_positions(tmp_path / "missing.json") == set()


def test_the_repository_itself_is_clean(gate):
    """The gate CI runs, run here too: the tree must hold no patient coordinate."""
    findings = gate.scan(
        ROOT, ROOT / "build/submission/spec.json", ROOT / "tools/coordinate_allowlist.txt", SPAN
    )
    assert findings == [], "\n".join(map(str, findings))
