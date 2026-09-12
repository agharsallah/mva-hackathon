"""The calling adapters: the parsers, the flags and the priors — not the tools themselves.

Running minimap2 or delly in a unit test would test homebrew. What is ours, and what can
silently go wrong, is the translation layer: a JSON key that moved, a BED column read as
the wrong field, a bait-edge window measured from the wrong end, a phase block stitched
from the wrong records. Every test here is over a committed fixture of real tool output
or a hand-checkable input.
"""

import gzip
import json
from pathlib import Path

import pytest

from mva.calling import coverage, phase, sv, tools

FLAGSTAT_JSON = json.dumps(
    {
        "QC-passed reads": {
            "total": 1000,
            "primary": 980,
            "mapped": 940,
            "properly paired": 900,
            "duplicates": 40,
            "singletons": 8,
        },
        "QC-failed reads": {"total": 0},
    }
)

MOSDEPTH_REGIONS = "1\t100\t200\tBUB1B_exon1\t41.20\n1\t300\t400\tBUB1B_exon2\t3.10\n"

PHASED_VCF = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tproband
1\t100\t.\tA\tG\t50\tPASS\t.\tGT:PS\t0|1:100
1\t250\t.\tC\tT\t50\tPASS\t.\tGT:PS\t1|0:100
1\t9000\t.\tG\tA\t50\tPASS\t.\tGT:PS\t0|1:9000
1\t9500\t.\tT\tC\t50\tPASS\t.\tGT\t0/1
"""


def test_require_names_every_missing_tool_at_once():
    with pytest.raises(tools.ToolMissingError) as raised:
        tools.require("definitely-not-a-tool", "also-not-a-tool", "sh")
    message = str(raised.value)
    assert "definitely-not-a-tool" in message and "also-not-a-tool" in message
    assert "sh" not in message.split(":")[1]


def test_run_records_argv_version_and_timing():
    invocation = tools.run(["sh", "-c", "exit 0"], tool="sh", version="test-1")
    assert invocation.argv == ("sh", "-c", "exit 0")
    assert invocation.version == "test-1"
    assert invocation.returncode == 0
    assert invocation.seconds >= 0


def test_run_raises_with_the_stderr_that_explains_it():
    with pytest.raises(RuntimeError, match="boom"):
        tools.run(["sh", "-c", "echo boom >&2; exit 3"], tool="sh", version="test-1")


def test_run_can_be_told_not_to_raise():
    invocation = tools.run(["sh", "-c", "exit 7"], tool="sh", version="x", check=False)
    assert invocation.returncode == 7


def test_run_redirects_stdout_to_a_file_rather_than_a_pipe(tmp_path):
    out = tmp_path / "deep" / "out.txt"
    tools.run(["sh", "-c", "echo hello"], tool="sh", version="x", stdout=out)
    assert out.read_text().strip() == "hello"


def test_pipe_connects_stages_and_records_each_one(tmp_path):
    out = tmp_path / "piped.txt"
    invocations = tools.pipe([["sh", "-c", "printf 'b\\na\\nc\\n'"], ["sort"]], stdout=out)
    assert out.read_text() == "a\nb\nc\n"
    assert [item.tool for item in invocations] == ["sh", "sort"]


def test_pipe_raises_naming_the_stage_that_failed(tmp_path):
    with pytest.raises(RuntimeError, match="exited"):
        tools.pipe([["sh", "-c", "echo hi"], ["sh", "-c", "exit 4"]], stdout=tmp_path / "x.txt")


def test_provenance_records_inputs_outputs_and_invocations(tmp_path):
    record = tools.started_now("align")
    record.inputs = {"bam": "a.bam"}
    record.invocations.append(tools.run(["sh", "-c", "true"], tool="sh", version="x"))
    written = json.loads(record.write(tmp_path / "p.json").read_text())
    assert written["stage"] == "align"
    assert written["inputs"] == {"bam": "a.bam"}
    assert written["invocations"][0]["tool"] == "sh"
    assert written["finished_at"] >= written["started_at"]


def test_sha256_of_a_truncated_read_says_it_was_truncated(tmp_path):
    target = tmp_path / "big.bin"
    target.write_bytes(b"x" * 100)
    assert tools.sha256(target, limit=10).endswith(":first10")
    assert ":" not in tools.sha256(target)


def test_flagstat_reads_the_json_keys_samtools_actually_emits(tmp_path, monkeypatch):
    monkeypatch.setattr("mva.calling.align.capture", lambda argv, **kw: FLAGSTAT_JSON)
    from mva.calling import align

    stats = align.flagstat(tmp_path / "x.bam")
    assert stats == {
        "total": 1000,
        "mapped": 940,
        "properly_paired": 900,
        "duplicates": 40,
        "singletons": 8,
    }


def test_write_bed_sorts_so_the_depth_walk_does_not_reseek(tmp_path):
    path = coverage.write_bed(
        [("2", 10, 20, "b"), ("1", 300, 400, "c"), ("1", 100, 200, "a")], tmp_path / "r.bed"
    )
    assert path.read_text().splitlines()[0].split("\t")[3] == "a"
    assert path.read_text().splitlines()[-1].split("\t")[0] == "2"


def test_regions_are_read_with_the_depth_in_the_fifth_column(tmp_path):
    path = tmp_path / "x.regions.bed.gz"
    path.write_bytes(gzip.compress(MOSDEPTH_REGIONS.encode()))
    regions = coverage.read_regions(path)
    assert [region.name for region in regions] == ["BUB1B_exon1", "BUB1B_exon2"]
    assert regions[0].mean_depth == 41.2
    assert regions[0].bases == 100


def test_coverage_summary_names_what_falls_under_the_floor(tmp_path):
    path = tmp_path / "x.regions.bed.gz"
    path.write_bytes(gzip.compress(MOSDEPTH_REGIONS.encode()))
    found = coverage.Coverage(
        regions=coverage.read_regions(path), manifest=Path("m"), prefix=Path("p")
    )
    summary = coverage.summarise(found, floor=10.0)
    assert summary["below_floor"] == 1
    assert summary["below_floor_names"] == ["BUB1B_exon2"]
    assert summary["min_depth"] == 3.1


def test_an_empty_coverage_summary_does_not_divide_by_zero():
    empty = coverage.Coverage(regions=(), manifest=Path("m"), prefix=Path("p"))
    assert coverage.summarise(empty)["regions"] == 0


def test_precision_prior_is_type_specific_and_zero_when_unmeasured():
    assert sv.precision_prior("DEL") > sv.precision_prior("DUP")
    assert sv.precision_prior("DUP") > sv.precision_prior("INV")
    assert sv.precision_prior("BND") == 0.0
    assert sv.precision_prior("tra") == 0.0


def test_the_two_sv_callers_are_different_method_classes():
    assert sv.METHOD_CLASS["delly"] != sv.METHOD_CLASS["dysgu"]
    assert len(set(sv.METHOD_CLASS.values())) == 2


def test_a_breakpoint_at_either_end_of_a_baited_interval_is_flagged():
    edges = {"1": [(1000, 5000)]}
    assert sv.near_bait_edge("1", 1000, edges)
    assert sv.near_bait_edge("1", 5000, edges)
    assert sv.near_bait_edge("1", 4200, edges, window=1000)
    assert not sv.near_bait_edge("1", 3000, edges)
    assert not sv.near_bait_edge("2", 1000, edges)


def test_phase_blocks_are_grouped_by_the_phase_set_field(tmp_path):
    path = tmp_path / "phased.vcf"
    path.write_text(PHASED_VCF)
    blocks = phase.read_blocks(path)
    assert len(blocks) == 2
    assert (blocks[0].start, blocks[0].end, blocks[0].variants) == (100, 250, 2)
    assert blocks[1].variants == 1


def test_a_record_without_a_phase_set_joins_no_block(tmp_path):
    path = tmp_path / "phased.vcf"
    path.write_text(PHASED_VCF)
    found = phase.Phasing(vcf=path, blocks=phase.read_blocks(path), manifest=Path("m"))
    assert found.block_containing("1", 9500) is None


def test_two_alleles_in_different_blocks_are_not_claimed_to_be_phased(tmp_path):
    path = tmp_path / "phased.vcf"
    path.write_text(PHASED_VCF)
    found = phase.Phasing(vcf=path, blocks=phase.read_blocks(path), manifest=Path("m"))
    assert found.same_block("1", 100, 250)
    assert not found.same_block("1", 100, 9000)


def test_a_workflow_stage_whose_tool_is_missing_is_skipped_not_fatal(tmp_path):
    """Five hours of alignment must not be thrown away because a phaser is absent."""
    from mva.calling import workflow as workflow_module

    flow = workflow_module.Workflow(out_dir=tmp_path)

    def absent():
        raise tools.ToolMissingError("not on PATH: nonesuch")

    assert workflow_module._timed(flow, "phase", absent) is None
    assert flow.stages[0].status == "skipped"
    assert "nonesuch" in flow.stages[0].note
    assert not flow.stages[0].ok


def test_a_workflow_stage_that_fails_records_the_first_line_of_why(tmp_path):
    from mva.calling import workflow as workflow_module

    flow = workflow_module.Workflow(out_dir=tmp_path)

    def broken():
        raise RuntimeError("delly exited 1\n  argv: delly call")

    assert workflow_module._timed(flow, "sv:delly", broken) is None
    assert flow.stages[0].status == "failed"
    assert flow.stages[0].note == "delly exited 1"


def test_a_workflow_stage_that_runs_records_its_detail(tmp_path):
    from mva.calling import workflow as workflow_module

    flow = workflow_module.Workflow(out_dir=tmp_path)
    result = workflow_module._timed(
        flow, "call:freebayes", lambda: 42, detail=lambda value: {"records": value}
    )
    assert result == 42
    assert flow.stages[0].ok and flow.stages[0].detail == {"records": 42}


def test_a_reused_stage_counts_as_having_its_output(tmp_path):
    """Alignment is the hour of the chain. Re-running to fix a caller must cost the caller,
    and a reused stage is not a skipped one — its output exists."""
    from mva.calling import workflow as workflow_module

    reused = workflow_module.Stage(name="align", status="reused", note="already built")
    skipped = workflow_module.Stage(name="align", status="skipped", note="no tool")
    assert reused.ok and not skipped.ok


def test_the_workflow_summary_is_json_and_names_every_stage(tmp_path):
    from mva.calling import workflow as workflow_module

    flow = workflow_module.Workflow(out_dir=tmp_path)
    flow.record(workflow_module.Stage(name="align", status="ran", seconds=1.25))
    flow.record(workflow_module.Stage(name="phase", status="skipped", note="absent"))
    written = json.loads(flow.write(tmp_path / "report.json").read_text())
    assert [stage["name"] for stage in written["stages"]] == ["align", "phase"]
    assert written["stages"][0]["seconds"] == 1.2
    assert written["alignment"] is None and written["callsets"] == {}


def test_fragment_support_reads_cis_trans_and_silence():
    assert phase.FragmentSupport(both_alt=8).verdict == "cis"
    assert phase.FragmentSupport(alt_ref=5, ref_alt=6).verdict == "trans"
    assert phase.FragmentSupport(both_alt=3, alt_ref=4).verdict == "conflicting"
    silent = phase.FragmentSupport()
    assert silent.verdict == "no spanning fragment"
    assert not silent.informative
