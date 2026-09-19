"""The zoo on a *second* case: a different TOML, the same code, no edit anywhere.

This is the reusability claim of `docs/iteration4/reusability.md` under test rather than in
prose. One temporary config declares another illness — another confirmed gene, another docs
folder — and the whole eight-stage workflow runs on the synthetic fixture set. What the test
asserts is exactly what a second case needs to be true:

* the flagged pair is the **new** gene's, not iteration 4's, and not the fixture file's own
  ``is_confirmed`` column;
* every output lands under the new case's folder (``docs/<iteration>/…``);
* an unsolved case (no ``confirmed_gene``) flags nothing and says so in words rather than
  guessing;
* the case's label and gene reach the rendered report, so a report never claims to be about
  an illness it is not about.

No database, no network: :meth:`mva.zoo.workflow_types.Deps.fixtures` reads ``fixtures/it4/``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mva.zoo import workflow
from mva.zoo.pairs import PAIR_RULES, pairs_from_alleles, pairs_from_fixture
from mva.zoo.workflow_types import Config, Deps

#: Absolute, because the workflow runs with the working directory moved to ``tmp_path``.
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "it4"

#: A second case. Every case-specific value is here and nowhere else — that is the point.
DEMO_TOML = """
[case]
label = "Demo illness — synthetic proband"
iteration = "demo"
table_prefix = "demo"
confirmed_gene = "GENEB"
confirmed_pair_rule = "lof+missense"
phenotype_term_set = "proband-only"
hpo_table = "hpo_gene_scores"

[run]
mode = "catalogue-free"
models = ["alphamissense", "esm1b", "spliceai", "revel"]
schema = "results"
warehouse_schema = "warehouse"

[merge]
method = "fusion"
rrf_k = 60

[llm]
mode = "none"
"""


@pytest.fixture
def demo_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A case TOML in an empty working directory, so derived paths are visible."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "demo.toml"
    path.write_text(DEMO_TOML, encoding="utf-8")
    return path


# ── the config alone ─────────────────────────────────────────────────────────────────────


def test_a_second_case_derives_its_paths_from_its_iteration(demo_case: Path):
    config = Config.load(demo_case)
    assert config.confirmed_gene == "GENEB"
    assert config.reports_dir == Path("docs/demo/reports")
    assert config.docs_runs_dir == Path("docs/demo/runs")
    assert config.merged_path == Path("docs/demo/report.md")
    assert config.out_dir == Path("build/demo")
    assert config.table("model_reports") == "demo_model_reports"
    assert config.run_id.startswith("demo-")


def test_the_iteration_override_moves_every_default_path(demo_case: Path):
    config = Config.load(demo_case, iteration="other")
    assert config.reports_dir == Path("docs/other/reports")
    assert config.merged_path == Path("docs/other/report.md")


def test_the_case_gene_override_replaces_the_files_gene(demo_case: Path):
    assert Config.load(demo_case, confirmed_gene="GENEC").confirmed_gene == "GENEC"


def test_a_case_with_no_confirmed_gene_flags_nothing_and_says_so(tmp_path: Path):
    path = tmp_path / "unsolved.toml"
    path.write_text(DEMO_TOML.replace('confirmed_gene = "GENEB"', 'confirmed_gene = ""'))
    config = Config.load(path)
    assert config.confirmed_gene == ""
    build = pairs_from_alleles(
        [
            {"gene": "GENEB", "chrom": "1", "pos": 101, "ref": "A", "alt": "T", "gt": "0/1"},
            {"gene": "GENEB", "chrom": "1", "pos": 202, "ref": "C", "alt": "G", "gt": "0/1"},
        ],
        confirmed_gene=config.confirmed_gene,
    )
    assert [p.is_confirmed for p in build.pairs] == [False]
    assert build.confirmed_note == "no confirmed pair declared: the case names no confirmed gene"


def test_the_all_rule_flags_every_pair_of_the_gene():
    rows = [
        {"gene": "GENEB", "chrom": "1", "pos": 101, "ref": "A", "alt": "T", "gt": "0/1"},
        {"gene": "GENEB", "chrom": "1", "pos": 202, "ref": "C", "alt": "G", "gt": "0/1"},
        {"gene": "GENEB", "chrom": "1", "pos": 303, "ref": "G", "alt": "A", "gt": "0/1"},
    ]
    build = pairs_from_alleles(rows, confirmed_gene="GENEB", rule="all")
    assert sum(1 for p in build.pairs if p.is_confirmed) == 3
    assert "the rule is `all`" in build.confirmed_note


def test_an_unknown_rule_is_refused_by_name():
    with pytest.raises(ValueError, match="unknown confirmed_pair_rule"):
        pairs_from_alleles([], confirmed_gene="GENEB", rule="vibes")
    assert PAIR_RULES == ("lof+missense", "all")


def test_the_fixture_flag_yields_to_the_case_gene():
    """The file says GENEG; the case says GENEB; the case wins."""
    from_file = pairs_from_fixture(FIXTURES / "pairs.tsv")
    from_case = pairs_from_fixture(FIXTURES / "pairs.tsv", confirmed_gene="GENEB")
    assert [p.gene for p in from_file if p.is_confirmed] == ["GENEG"]
    assert [p.gene for p in from_case if p.is_confirmed] == ["GENEB"]


# ── the whole workflow, on the second case ───────────────────────────────────────────────


def test_the_workflow_runs_end_to_end_on_a_second_case(demo_case: Path, tmp_path: Path):
    manifest = workflow.run(demo_case, deps=Deps.fixtures(FIXTURES))

    # Every output under the demo case's own folders, inside tmp_path.
    assert manifest.run_id.startswith("demo-")
    assert (tmp_path / "docs/demo/report.md").is_file()
    assert (tmp_path / "docs/demo/runs" / f"{manifest.run_id}.json").is_file()
    assert (tmp_path / "build/demo/merged.json").is_file()
    rendered = sorted(p.name for p in (tmp_path / "docs/demo/reports").glob("*.md"))
    assert rendered == ["alphamissense.md", "esm1b.md", "revel.md", "spliceai.md"]
    # Nothing was written into iteration 4's folders.
    assert not (tmp_path / "docs/iteration4").exists()

    # The report is about *this* case: its label, its gene, its table.
    text = (tmp_path / "docs/demo/reports/alphamissense.md").read_text(encoding="utf-8")
    assert "Demo illness — synthetic proband" in text
    assert "GENEB" in text
    assert "demo_model_reports" in text
    assert "BUB1B" not in text
    assert "proband-only" in text


def test_the_flagged_pair_is_the_second_cases_gene(demo_case: Path, tmp_path: Path):
    workflow.run(demo_case, deps=Deps.fixtures(FIXTURES))
    import json

    payload = json.loads((tmp_path / "build/demo/reports/spliceai.json").read_text())
    assert payload["case"]["confirmed_gene"] == "GENEB"
    assert payload["sections"]["confirmed_pair"]["gene"] in (None, "GENEB")
    assert payload["reports_table"] == "demo_model_reports"
