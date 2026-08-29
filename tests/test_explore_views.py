"""The views: a figure never travels without the words that make it readable."""
from pathlib import Path

import pytest

from mva.explore import CallsetProfile, build_sections
from mva.explore.views import SECTIONS, karyotype, locus, panel
from mva.pipeline import read_calls

PROFILE = Path(__file__).parent / "fixtures" / "profile"
MINI_VCF = Path(__file__).parent / "fixtures" / "mini.vcf"


def sections():
    return build_sections(CallsetProfile.load(PROFILE))


def every_exhibit():
    return [e for s in sections() for e in s.exhibits]


def test_the_synthetic_profile_exercises_every_registered_section():
    # If a section stops producing exhibits the fixture no longer covers it, and a
    # broken view would pass the suite by rendering nothing at all.
    assert [s.slug for s in sections()] == [spec.slug for spec in SECTIONS]


@pytest.mark.parametrize("attribute", ["caption", "legend", "title"])
def test_every_exhibit_explains_itself(attribute):
    for item in every_exhibit():
        assert getattr(item, attribute), f"{item.slug} has no {attribute}"


def test_every_legend_decodes_its_own_colours():
    # The repository rule is that a visual is followed by a line saying what its colours
    # mean. Generating that line from the palette objects is what keeps it truthful.
    for item in every_exhibit():
        assert item.legend.startswith("**Legend** — ")
        assert item.legend.endswith(".")


def test_an_exhibit_carries_either_a_figure_or_rendered_html_never_neither():
    for item in every_exhibit():
        assert (item.figure is not None) or item.html


def test_views_degrade_to_nothing_when_their_data_is_absent(tmp_path):
    empty = CallsetProfile.load(tmp_path)
    assert karyotype.exhibits(empty) == []
    assert panel.exhibits(empty) == []
    assert build_sections(empty) == []


def test_chromosomes_are_plotted_in_assembly_order_not_alphabetically():
    # Sorted as strings, chromosome 10 would precede chromosome 2 and X would land in the
    # middle. The plot has to read left to right the way a karyotype does.
    figure = karyotype.allele_balance(CallsetProfile.load(PROFILE)).figure
    assert list(figure.data[0].x) == ["chr1", "chr2", "chr20", "chrX", "chrY"]


def test_the_diploid_reference_lines_survive_onto_the_figure():
    # Plotly resolves a shape's row/col against the axes its traces created, and silently
    # drops one added to a still-empty subplot. The allele-balance chart is unreadable
    # without its 0.48 / 0.50 / 0.52 reference lines, and losing them raises no error.
    figure = karyotype.allele_balance(CallsetProfile.load(PROFILE)).figure
    on_the_balance_axis = [s.y0 for s in figure.layout.shapes if s.yref == "y"]
    assert sorted(on_the_balance_axis) == [0.48, 0.5, 0.52]


def test_sex_chromosomes_are_drawn_but_not_graded():
    # A male sample carries one X and one Y, so both sit far off the diploid expectation
    # by construction. Grading them would paint the most predictable fact in the dataset
    # as its most alarming finding.
    from mva.explore.theme import MUTED

    figure = karyotype.allele_balance(CallsetProfile.load(PROFILE)).figure
    colours = dict(zip(figure.data[0].x, figure.data[0].marker.color))
    assert colours["chrX"] == MUTED.fill
    assert colours["chrY"] == MUTED.fill
    assert colours["chr1"] != MUTED.fill


def test_the_pair_search_space_is_the_pair_count_not_the_variant_count():
    # The answer key is a pair, so the ranked unit is a pair and the search space grows
    # quadratically. 40 calls offer 780 pairs, which is the number worth showing.
    figure = panel.search_space(CallsetProfile.load(PROFILE)).figure
    assert max(figure.data[0].x) == 780


def test_locus_views_classify_pairs_from_real_calls():
    calls = read_calls(MINI_VCF)
    built = {e.slug.rsplit("-", 1)[0]: e for e in locus.exhibits(calls, "fixture")}
    matrix = next(e for slug, e in built.items() if "pair-matrix" in slug)
    # The fixture encodes one cis pair (rejected) and two trans pairs (the 1|0 / 0|1
    # neighbours plus the two ALT alleles of the multiallelic record).
    assert "1 rejected cis" in matrix.notes[0]
    assert "2 confirmed trans" in matrix.notes[0]


def test_locus_views_are_skipped_when_there_is_nothing_to_show():
    assert locus.exhibits([]) == []


def test_exhibit_slugs_are_filesystem_safe():
    for item in every_exhibit():
        assert item.slug == item.slug.lower()
        assert all(ch.isalnum() or ch == "-" for ch in item.slug)


def test_a_generated_caption_agrees_with_its_own_count():
    # Captions are assembled from live numbers, so "1 calls were flagged" is a real
    # output, not a hypothetical.
    calls = read_calls(MINI_VCF)
    caption = locus.variant_track(calls, "fixture").caption
    assert "1 was flagged" in caption
    assert "11 are heterozygous" in caption


def test_the_locus_page_does_not_claim_to_be_built_from_summaries():
    # The profile report reads aggregates; the locus report reads patient records. Saying
    # the wrong one on the page that carries real coordinates is the dangerous direction.
    from mva.explore.report import LOCUS_BLURB, render
    from mva.explore.figure import Section

    section = Section("locus", "Locus", "…", locus.exhibits(read_calls(MINI_VCF), "fixture"))
    page = render([section], title="t", subject="s", blurb=LOCUS_BLURB)
    assert "keep this page outside the repository" in page
    assert "committable summary statistics" not in page


def test_a_bcftools_overflow_bin_is_flagged_as_a_catch_all(tmp_path):
    # `bcftools stats` folds every indel longer than its limit into the outermost bin, so
    # the plot shows a spike at that exact length. A reader who does not know that reads
    # it as a real peak.
    from mva.explore.views import callset

    (tmp_path / "vcf_stats_summary.txt").write_text(
        "IDD\t0\t-60\t1929\t0\t.\n"
        "IDD\t0\t-59\t39\t0\t.\n"
        "IDD\t0\t-1\t500\t0\t.\n"
        "IDD\t0\t1\t500\t0\t.\n"
        "IDD\t0\t59\t60\t0\t.\n"
        "IDD\t0\t60\t1937\t0\t.\n"
    )
    notes = callset.indel_lengths(CallsetProfile.load(tmp_path)).notes
    assert any("not a real peak" in note for note in notes)


def test_a_smoothly_decaying_tail_is_not_flagged(tmp_path):
    from mva.explore.views import callset

    (tmp_path / "vcf_stats_summary.txt").write_text(
        "IDD\t0\t-3\t100\t0\t.\n"
        "IDD\t0\t-2\t200\t0\t.\n"
        "IDD\t0\t-1\t500\t0\t.\n"
        "IDD\t0\t1\t500\t0\t.\n"
        "IDD\t0\t2\t200\t0\t.\n"
        "IDD\t0\t3\t100\t0\t.\n"
    )
    notes = callset.indel_lengths(CallsetProfile.load(tmp_path)).notes
    assert not any("not a real peak" in note for note in notes)
