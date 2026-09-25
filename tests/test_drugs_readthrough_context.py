"""The stop-codon facts: exon placement, the 50-55 nt rule, truncation, Ensembl parsing.

Every fixture here is synthetic sequence written in this file. No patient sequence, no
genomic position: :mod:`mva.drugs.readthrough_context` works in coding-sequence offsets.
"""

from __future__ import annotations

import pytest

from mva.drugs.readthrough_context import (
    Domain,
    TranscriptModel,
    nmd_call,
    stop_context,
    transcript_from_ensembl,
    truncation,
)

# 61 codons: codon 10 is TTA (Leu), so a T>G at its middle base (offset 29) makes TGA.
CDS = "ATG" + "GCT" * 8 + "TTA" + "GCT" * 50 + "TAA"


def _model(exon_ends: tuple[int, ...], **kwargs: object) -> TranscriptModel:
    return TranscriptModel(
        transcript_id="T1",
        cds=CDS,
        cds_exon_ends=exon_ends,
        exons_total=len(exon_ends),
        protein_length=len(CDS) // 3 - 1,
        **kwargs,  # type: ignore[arg-type]
    )


def test_substitution_makes_the_stop_and_reads_its_context() -> None:
    model = _model((len(CDS),))
    context = stop_context(model, 29, "G")  # codon 10, middle base
    assert context.codon_index == 10
    assert context.reference_codon == "TTA"
    assert context.stop_codon == "TGA"
    assert context.rna_stop == "UGA"
    assert context.plus4 == "G"
    assert context.tetranucleotide == "UGA G"
    assert context.minus1 == "T"


def test_a_substitution_that_makes_no_stop_is_refused() -> None:
    model = _model((len(CDS),))
    with pytest.raises(ValueError, match="not a stop codon"):
        stop_context(model, 29, "C")  # TTA -> TCA (Ser)


def test_fifty_five_nt_rule_both_ways() -> None:
    """Far from the last junction: NMD-competent. Inside the window or past it: escaping."""
    far = _model((30, 90, len(CDS)))  # stop's last base at 30, last junction at 90
    competent = nmd_call(far, 10)
    assert competent.competent
    assert competent.nt_to_last_junction == 60
    assert competent.exon_index == 1
    assert competent.junctions_downstream == 2

    near = _model((60, len(CDS)))  # junction at 60, the stop's last base 30 nt before it
    assert nmd_call(near, 10).competent is False
    assert "escapes NMD" in nmd_call(near, 10).reason

    last_exon = _model((60, len(CDS)))
    call = nmd_call(last_exon, 25)  # last base 75, downstream of the only junction
    assert call.competent is False
    assert call.nt_to_last_junction is not None and call.nt_to_last_junction < 0
    assert "last exon" in call.reason


def test_single_exon_transcript_has_no_junction_and_escapes() -> None:
    call = nmd_call(_model((len(CDS),)), 10)
    assert call.nt_to_last_junction is None
    assert call.competent is False
    assert "single-exon" in call.reason


def test_truncation_counts_residues_and_sorts_domains() -> None:
    model = _model(
        (len(CDS),),
        domains=(Domain("N-terminal", 1, 5), Domain("kinase", 20, 30), Domain("straddles", 8, 12)),
    )
    result = truncation(model, 10)
    assert result.residues_kept == 9
    assert result.protein_length == 60
    assert result.fraction_lost == pytest.approx(1 - 9 / 60)
    assert result.domains_lost == ("kinase",)
    assert result.domains_kept == ("N-terminal",)
    assert result.domains_truncated == ("straddles",)


def test_ensembl_reply_becomes_a_model_with_utr_trimmed() -> None:
    """Exon 1 is half UTR and exon 3 runs past the stop: only the coding part counts."""
    lookup = {
        "id": "T1",
        "strand": 1,
        "Translation": {"start": 11, "end": 10 + len(CDS)},
        "Exon": [
            {"start": 1, "end": 40},  # 30 coding bases after the 10-base UTR
            {"start": 41, "end": 100},  # 60 coding
            {"start": 101, "end": 400},  # the rest of the CDS, then UTR
        ],
    }
    model = transcript_from_ensembl(lookup, CDS.lower())
    assert model.cds == CDS
    assert model.cds_exon_ends == (30, 90, len(CDS))
    assert model.exons_total == 3
    assert model.protein_length == 60
    assert model.exon_of(91) == 3


def test_a_model_whose_exons_do_not_cover_the_cds_is_refused() -> None:
    with pytest.raises(ValueError, match="exon ends"):
        TranscriptModel("T1", CDS, (30,), 1, 60)


def test_hgvs_c_parser_accepts_a_substitution_and_refuses_the_rest() -> None:
    from mva.drugs.readthrough_context import parse_hgvs_c

    parsed = parse_hgvs_c("ENST00000000001.9:c.910G>T")
    assert (parsed.transcript, parsed.offset, parsed.ref, parsed.alt) == (
        "ENST00000000001.9",
        910,
        "G",
        "T",
    )
    assert parse_hgvs_c("c.12A>C").transcript == ""
    for bad in ("c.12delA", "c.12-3A>G", "c.*12A>G", "p.Arg550Ter", "n.12A>G"):
        with pytest.raises(ValueError, match="plain coding substitution"):
            parse_hgvs_c(bad)
