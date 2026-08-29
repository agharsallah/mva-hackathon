"""The report shell: one runtime, every exhibit reachable, nothing silently blank."""
from html.parser import HTMLParser
from pathlib import Path

from mva.explore import CallsetProfile, build_report, build_sections

PROFILE = Path(__file__).resolve().parents[1] / "ressources" / "data-profile"


class _Collector(HTMLParser):
    """Enough of an HTML parser to assert on structure without a dependency."""

    def __init__(self) -> None:
        super().__init__()
        self.exhibit_ids: list[str] = []
        self.nav_targets: list[str] = []
        self.plotly_srcs: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if tag == "figure" and "exhibit" in classes:
            self.exhibit_ids.append(attributes.get("id", ""))
        if tag == "a" and "exhibit-link" in classes:
            self.nav_targets.append(attributes.get("data-target", ""))
        if tag == "script" and "plotly" in (attributes.get("src") or "").lower():
            self.plotly_srcs.append(attributes["src"])


def parsed():
    profile = CallsetProfile.load(PROFILE)
    collector = _Collector()
    collector.feed(build_report(profile, "test report"))
    return profile, collector


def test_every_exhibit_is_rendered_and_reachable_from_the_sidebar():
    profile, page = parsed()
    expected = [e.slug for s in build_sections(profile) for e in s.exhibits]
    assert page.exhibit_ids == expected
    assert page.nav_targets == expected


def test_the_plotly_runtime_is_loaded_exactly_once():
    # The first exhibit of the report is a table, not a chart. Attaching the runtime by
    # position rather than by "first exhibit carrying a figure" leaves every chart on the
    # page blank with no error, which is why this is asserted rather than assumed.
    _, page = parsed()
    assert len(page.plotly_srcs) == 1


def test_exhibit_slugs_are_unique():
    profile, _ = parsed()
    slugs = [e.slug for s in build_sections(profile) for e in s.exhibits]
    assert len(slugs) == len(set(slugs))


def test_inline_markup_in_a_note_reaches_the_page_as_html_not_as_asterisks():
    from mva.explore.figure import inline

    assert inline("**TRIP13** trips `MQ40`") == "<strong>TRIP13</strong> trips <code>MQ40</code>"


def test_an_unpaired_delimiter_is_left_as_the_literal_character():
    from mva.explore.figure import inline

    assert inline("a lone * and a lone `") == "a lone * and a lone `"


def test_exhibit_text_is_escaped_before_markup_is_applied():
    # A gene symbol or filter name is untrusted-ish text from a data file; it must not be
    # able to introduce markup into the page.
    from mva.explore.figure import inline

    assert inline("<script>x</script> & co") == "&lt;script&gt;x&lt;/script&gt; &amp; co"
