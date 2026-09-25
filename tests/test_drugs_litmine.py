"""Route R3's two gates: the quote verifier and the direction check.

Both are the parts a language model cannot be trusted to do for itself. The verifier decides
whether an extracted row is evidence or fiction; the direction check decides whether a drug
acts the way the genetic experiment did. Everything here runs offline on literal strings —
no network, no cache, no corpus.
"""

from __future__ import annotations

from mva.drugs.litmine_corpus import CorpusSpec, build_queries, jats_text, strip_markup
from mva.drugs.litmine_screen import Lexicon, screen_corpus, sentences
from mva.drugs.litmine_translate import (
    RUBRIC,
    candidates,
    control_recall,
    direction_check,
    strength,
)
from mva.drugs.litmine_verify import (
    INTERVENTION_ENUMS,
    INTERVENTION_FIELDS,
    normalise,
    verify_rows,
)

SOURCE = (
    "Overexpression of SIRT2 or treatment of mice with the NAD⁺ precursor "
    "nicotinamide mononucleotide (NMN) increases BubR1 abundance in–vivo."
)
TEXTS = {"1": {"abstract": SOURCE}}


def row(**overrides: str) -> dict[str, str]:
    base = {
        "intervention": "NMN",
        "intervention_type": "drug",
        "mode": "gain",
        "target": "NAD+",
        "effect_on": "bubr1_level",
        "direction": "increase",
        "model_system": "mouse_in_vivo",
        "pmid": "1",
        "quote": "treatment of mice with the NAD+ precursor nicotinamide mononucleotide "
        "(NMN) increases BubR1 abundance in-vivo.",
    }
    return {**base, **overrides}


def verify(*rows: dict[str, str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return verify_rows(rows, TEXTS, required=INTERVENTION_FIELDS, enums=INTERVENTION_ENUMS)


# ── the quote gate ───────────────────────────────────────────────────────────────────────


def test_quote_matches_through_unicode_and_whitespace_differences() -> None:
    """Superscript plus, non-breaking space and an en dash must not fail a true quote."""
    kept, rejected = verify(row())
    assert not rejected
    assert kept[0]["verified_in"] == "abstract"


def test_one_changed_word_is_rejected() -> None:
    """The mutation test: 'increases' → 'decreases' is a different claim, and must not pass."""
    bad = row(quote=row()["quote"].replace("increases", "decreases"))
    kept, rejected = verify(bad)
    assert not kept
    assert rejected[0]["reject_reason"] == "quote_not_in_source"


def test_short_quote_and_unknown_pmid_are_rejected() -> None:
    kept, rejected = verify(row(quote="BubR1 abundance"), row(pmid="99"))
    assert not kept
    assert [r["reject_reason"] for r in rejected] == ["quote_too_short", "no_cached_text"]


def test_field_vocabulary_is_enforced_before_the_quote() -> None:
    kept, rejected = verify(row(effect_on="bubr1_levels"), row(direction=""))
    assert not kept
    assert [r["reject_reason"] for r in rejected] == ["bad_value:effect_on", "empty:direction"]


def test_normalise_never_changes_words() -> None:
    assert normalise("a b—c “d”") == 'a b-c "d"'
    assert normalise(" two   words ").split() == ["two", "words"]


# ── the direction check ──────────────────────────────────────────────────────────────────


def test_direction_check_pairs_the_act_with_the_drug() -> None:
    assert direction_check("gain", "ACTIVATOR") == "match"
    assert direction_check("gain", "INHIBITOR") == "mismatch"
    assert direction_check("loss", "INHIBITOR") == "match"
    assert direction_check("loss", "AGONIST") == "mismatch"
    assert direction_check("loss", "MODULATOR") == "unknown"
    assert direction_check("exposure", "INHIBITOR") == "unknown"


def test_mismatched_drug_never_becomes_a_candidate() -> None:
    mapped = [
        {
            "intervention": "SIRT2 overexpression",
            "intervention_type": "genetic",
            "mode": "gain",
            "target": "SIRT2",
            "pmids": ["1"],
            "benefit_rows": [row(effect_on="bubr1_level", direction="increase")],
            "harm_rows": [],
            "drugs": [
                {
                    "drug_name": "a sirt2 inhibitor",
                    "mapping": "gene_analogue",
                    "max_phase": 4,
                    "direction_check": "mismatch",
                    "molecule_chembl_id": "CHEMBL1",
                },
                {
                    "drug_name": "a sirt2 activator",
                    "mapping": "gene_analogue",
                    "max_phase": 4,
                    "direction_check": "match",
                    "molecule_chembl_id": "CHEMBL2",
                },
            ],
        }
    ]
    out = candidates(
        mapped, branch_by_effect={"bubr1_level": "missense_unstable"}, control_passed=True
    )
    assert [c["drug_name"] for c in out] == ["a sirt2 activator"]
    assert out[0]["branch"] == "missense_unstable"
    assert out[0]["positive_control_passed"] == "true"


def test_a_row_moving_the_wrong_way_produces_no_candidate() -> None:
    mapped = [
        {
            "intervention": "x",
            "intervention_type": "drug",
            "mode": "loss",
            "target": "t",
            "pmids": ["1"],
            "benefit_rows": [],
            "harm_rows": [row()],
            "drugs": [
                {"drug_name": "x", "mapping": "direct", "max_phase": 4, "direction_check": "n/a"}
            ],
        }
    ]
    assert candidates(mapped, branch_by_effect={}, control_passed=True) == []


def test_strength_multiplies_the_four_rubric_axes() -> None:
    rows = [row(), row(pmid="2"), row(pmid="3")]
    expected = (
        RUBRIC["model"]["mouse_in_vivo"]
        * RUBRIC["directness"]["bubr1_level"]
        * RUBRIC["replication"]["3+"]
        * RUBRIC["translation"]["direct_approved"]
    )
    assert strength(rows, "direct_approved") == round(expected, 3)


def test_control_recall_needs_retrieval_and_the_right_finding() -> None:
    controls = {"1": [("bubr1_level", "increase")], "2": [("senescence", "decrease")]}
    result = control_recall([row()], controls, TEXTS)
    assert result == {
        "retrieval": "1/2",
        "extraction": "1/2",
        "passed": False,
        "per_pmid": {
            "1": {"retrieved": True, "extracted": True},
            "2": {"retrieved": False, "extracted": False},
        },
    }


# ── corpus and screen mechanics ──────────────────────────────────────────────────────────


def test_queries_are_built_from_the_card_only() -> None:
    spec = CorpusSpec(
        gene="GENEX",
        aliases=("ProtY",),
        topics={"level": ("protein level",)},
        disease_phrases=("some syndrome",),
    )
    terms = [q.term for q in build_queries(spec)]
    assert terms[0] == 'TITLE_ABS:(GENEX OR ProtY) AND TITLE_ABS:("protein level") AND SRC:MED'
    assert terms[1] == 'TITLE_ABS:"some syndrome" AND SRC:MED'
    assert not any(char.isdigit() for term in terms for char in term)


def test_jats_prose_drops_tables_and_references() -> None:
    xml = (
        "<article><front><abstract><p>BubR1 falls with age.</p></abstract></front>"
        "<body><p>Treatment raised it.</p><table-wrap><table><p>7.2</p></table></table-wrap>"
        "</body><back><ref-list><ref><article-title>Другая</article-title></ref></ref-list></back>"
        "</article>"
    )
    assert jats_text(xml) == "BubR1 falls with age. Treatment raised it."
    assert strip_markup("<i>a</i>&amp;  b") == "a & b"


def test_screen_keeps_only_sentences_with_all_three_word_kinds() -> None:
    text = (
        "BubR1 levels rose after treatment. BubR1 is a checkpoint protein. "
        "The drug raised nothing measurable here."
    )
    lexicon = Lexicon("t", subject=("bubr1",), effect=("level",), cue=("treat",))
    hits = screen_corpus({"1": {"abstract": text}}, lexicon)
    assert [h["sentence"] for h in hits] == ["BubR1 levels rose after treatment."]
    assert len(sentences(text)) == 3
