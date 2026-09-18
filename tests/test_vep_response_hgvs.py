"""HGVS notation survives the VEP parse — and comes from the transcript the parser picked.

``hgvs_c`` / ``hgvs_p`` (the Human Genome Variation Society's text spelling of a change, at
cDNA and protein level) is what every precomputed score table in the zoo is keyed on, so
step 1 cannot start without them. VEP returns one entry per overlapping transcript and they
disagree; :func:`~mva.pipeline.vep_response.best_transcript` already decides which entry the
gene symbol, impact, AlphaMissense call and exon numbers are read from, and the point of
these tests is that the two new strings come from the **same** entry rather than from
whichever one happened to carry them.

Every position here is invented, on chromosome 1 below 1,000,000 — no patient coordinate.
"""

from __future__ import annotations

from mva.pipeline.variant import Variant
from mva.pipeline.vep_response import best_transcript, parse

SNV = Variant("chr1", 123_456, "C", "T")

#: Two transcripts of one synthetic gene. Only the second is canonical and only it carries
#: the most severe consequence, so the tie-breaks in ``best_transcript`` must land there.
TWO_TRANSCRIPTS = {
    "input": "1 123456 . C T . . .",
    "most_severe_consequence": "stop_gained",
    "transcript_consequences": [
        {
            "transcript_id": "ENST00000000001",
            "gene_symbol": "GENEA",
            "biotype": "protein_coding",
            "consequence_terms": ["missense_variant"],
            "impact": "MODERATE",
            "hgvsc": "ENST00000000001.1:c.11C>T",
            "hgvsp": "ENSP00000000001.1:p.Pro4Leu",
            "swissprot": ["Q11111.2"],
        },
        {
            "transcript_id": "ENST00000000002",
            "gene_symbol": "GENEA",
            "biotype": "protein_coding",
            "canonical": 1,
            "consequence_terms": ["stop_gained"],
            "impact": "HIGH",
            "hgvsc": "ENST00000000002.3:c.22C>T",
            "hgvsp": "ENSP00000000002.3:p.Gln8Ter",
            "swissprot": ["Q00000.4"],
            "trembl": ["A0A000"],
        },
    ],
}

#: An intronic call: VEP gives a cDNA spelling and no protein one.
INTRONIC = {
    "input": "1 123456 . C T . . .",
    "most_severe_consequence": "intron_variant",
    "transcript_consequences": [
        {
            "transcript_id": "ENST00000000003",
            "gene_symbol": "GENEB",
            "biotype": "protein_coding",
            "canonical": 1,
            "consequence_terms": ["intron_variant"],
            "impact": "MODIFIER",
            "hgvsc": "ENST00000000003.2:c.33+5C>T",
        }
    ],
}

#: Outside every transcript — an intergenic call has no transcript block at all.
INTERGENIC = {
    "input": "1 123456 . C T . . .",
    "most_severe_consequence": "intergenic_variant",
    "intergenic_consequences": [{"impact": "MODIFIER"}],
}


class TestHgvsFields:
    def test_reads_the_transcript_the_parser_picked(self):
        record = parse(TWO_TRANSCRIPTS, SNV)
        chosen = best_transcript(TWO_TRANSCRIPTS)

        assert chosen is not None
        assert record.transcript == chosen["transcript_id"] == "ENST00000000002"
        assert record.hgvsc == "ENST00000000002.3:c.22C>T"
        assert record.hgvsp == "ENSP00000000002.3:p.Gln8Ter"

    def test_the_other_transcripts_spelling_is_not_used(self):
        record = parse(TWO_TRANSCRIPTS, SNV)

        assert record.hgvsc != "ENST00000000001.1:c.11C>T"
        assert record.hgvsp != "ENSP00000000001.1:p.Pro4Leu"

    def test_the_uniprot_accession_loses_its_isoform_suffix(self):
        """``P04637.4`` → ``P04637``: the score tables are indexed by the bare accession."""
        record = parse(TWO_TRANSCRIPTS, SNV)

        assert record.uniprot == "Q00000"

    def test_no_swissprot_entry_is_none_rather_than_the_trembl_one(self):
        item = {
            **TWO_TRANSCRIPTS,
            "transcript_consequences": [
                {
                    **TWO_TRANSCRIPTS["transcript_consequences"][1],
                    "swissprot": [],
                    "trembl": ["A0A000"],
                }
            ],
        }

        assert parse(item, SNV).uniprot is None

    def test_a_protein_less_change_keeps_the_cdna_spelling_only(self):
        record = parse(INTRONIC, SNV)

        assert record.transcript == "ENST00000000003"
        assert record.hgvsc == "ENST00000000003.2:c.33+5C>T"
        assert record.hgvsp is None

    def test_no_transcript_means_no_spelling_and_no_crash(self):
        record = parse(INTERGENIC, SNV)

        assert (record.transcript, record.hgvsc, record.hgvsp) == (None, None, None)
        assert record.uniprot is None
        assert record.impact == "MODIFIER"

    def test_the_panel_gene_still_breaks_the_tie(self):
        """``genes`` outranks canonical — and the HGVS pair follows it, not the canonical one."""
        item = {
            **TWO_TRANSCRIPTS,
            "transcript_consequences": [
                {**TWO_TRANSCRIPTS["transcript_consequences"][0], "gene_symbol": "GENEZ"},
                {**TWO_TRANSCRIPTS["transcript_consequences"][1], "gene_symbol": "GENEY"},
            ],
        }

        record = parse(item, SNV, frozenset({"GENEZ"}))

        assert record.transcript == "ENST00000000001"
        assert record.hgvsc == "ENST00000000001.1:c.11C>T"

    def test_defaults_are_none_so_existing_callers_are_untouched(self):
        """The three fields are optional: a record built without them is still valid."""
        from mva.pipeline.vep_response import VepRecord

        assert VepRecord(variant=SNV).transcript is None
        assert VepRecord(variant=SNV).hgvsc is None
        assert VepRecord(variant=SNV).hgvsp is None
        assert VepRecord(variant=SNV).uniprot is None
