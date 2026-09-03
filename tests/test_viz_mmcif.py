"""The mmCIF reader: tokenising, ``loop_`` tables, and what one alpha-carbon trace is.

Split out of ``tests/test_viz_proteinstructure.py`` when the parser was hardened (see
``docs/step-0/methodology/058-mmcif-parser-hardening.md``): that module owns the endpoint —
model resolution, the envelope, the 502 — and this one owns the file format.

Two kinds of input here. ``tests/fixtures/mini_alphafold.cif`` is six residues trimmed out
of the real AlphaFold model for BUB1B, so the happy path is asserted against a real file.
Everything else is a hand-written table built by :func:`atom_site`, because the cases that
matter — a file opening with a ligand chain, an NMR ensemble, an insertion code, a chain
with no ``label_seq_id`` — cannot all be present in one real monomer model.

Every value is **public reference data**: an AlphaFold model is identical for every human.
"""

from pathlib import Path

import pytest

from mva.viz import mmcif
from mva.viz.mmcif import MmcifError

MINI_CIF = (Path(__file__).parent / "fixtures" / "mini_alphafold.cif").read_text(encoding="utf-8")

#: The ``_atom_site`` columns this reader looks at, in the order :func:`atom_site` writes.
ATOM_TAGS = (
    "group_PDB",
    "id",
    "label_atom_id",
    "label_alt_id",
    "label_comp_id",
    "label_asym_id",
    "label_seq_id",
    "pdbx_PDB_ins_code",
    "Cartn_x",
    "Cartn_y",
    "Cartn_z",
    "B_iso_or_equiv",
    "auth_seq_id",
    "pdbx_PDB_model_num",
)


def atom(**over: str) -> str:
    """One ``_atom_site`` row: an alpha carbon of chain A, model 1, with fields overridden."""
    row = {
        "group_PDB": "ATOM",
        "id": "1",
        "label_atom_id": "CA",
        "label_alt_id": ".",
        "label_comp_id": "ALA",
        "label_asym_id": "A",
        "label_seq_id": "1",
        "pdbx_PDB_ins_code": "?",
        "Cartn_x": "1.0",
        "Cartn_y": "2.0",
        "Cartn_z": "3.0",
        "B_iso_or_equiv": "90.0",
        "auth_seq_id": "1",
        "pdbx_PDB_model_num": "1",
    }
    row.update(over)
    return " ".join(row[tag] for tag in ATOM_TAGS)


def atom_site(*rows: str) -> str:
    """An ``_atom_site`` loop holding ``rows``."""
    header = "".join(f"_atom_site.{tag}\n" for tag in ATOM_TAGS)
    return "loop_\n" + header + "\n".join(rows) + "\n#\n"


# ── the loop reader ──────────────────────────────────────────────────────────────────


def test_a_loop_is_read_as_rows_keyed_by_its_tags():
    rows = mmcif.loop_rows(MINI_CIF, "atom_site")
    assert len(rows) == 9
    assert rows[0]["label_atom_id"] == "N"
    assert rows[1]["label_comp_id"] == "MET"
    assert rows[1]["B_iso_or_equiv"] == "42.81"


def test_an_absent_category_is_an_empty_list_not_an_error():
    assert mmcif.loop_rows(MINI_CIF, "struct_sheet_range") == []


def test_quoted_values_keep_their_spaces_instead_of_shifting_the_row():
    text = "loop_\n_demo.a\n_demo.b\n'two words' 7\n#\n"
    assert mmcif.loop_rows(text, "demo") == [{"a": "two words", "b": "7"}]


def test_a_row_wrapped_across_lines_is_still_one_row():
    text = "loop_\n_demo.a\n_demo.b\n_demo.c\n1 2\n3\n#\n"
    assert mmcif.loop_rows(text, "demo") == [{"a": "1", "b": "2", "c": "3"}]


def test_a_tab_separated_row_is_split_into_its_values_not_left_as_one():
    """mmCIF's separator is any whitespace; a tab used to yield one token per line."""
    text = "loop_\n_demo.a\n_demo.b\n_demo.c\n1\t2\t3\n#\n"
    assert mmcif.loop_rows(text, "demo") == [{"a": "1", "b": "2", "c": "3"}]


def test_column_aligned_values_are_split_on_the_whole_run_of_spaces():
    text = "loop_\n_demo.a\n_demo.b\n1     2\n#\n"
    assert mmcif.loop_rows(text, "demo") == [{"a": "1", "b": "2"}]


# ── multi-line ';' text fields ───────────────────────────────────────────────────────

#: A ``_struct_conf`` loop whose ``details`` column is a multi-line ``;`` text field. The
#: block deliberately contains a line starting ``_`` and a line starting ``#``: read
#: line-by-line those look like a new category and a comment, and used to end the loop
#: early, losing the STRN row entirely.
STRUCT_CONF_WITH_TEXT = (
    "loop_\n"
    "_struct_conf.conf_type_id\n"
    "_struct_conf.beg_label_seq_id\n"
    "_struct_conf.end_label_seq_id\n"
    "_struct_conf.details\n"
    "HELX_RH_AL_P 4 6\n"
    ";A helix, described at length by the depositor\n"
    "_not_a_new_category 1\n"
    "# not a comment either\n"
    ";\n"
    "STRN 1 2 ?\n"
    "#\n"
)


def test_a_multi_line_text_field_is_one_token_and_does_not_end_the_loop():
    rows = mmcif.loop_rows(STRUCT_CONF_WITH_TEXT, "struct_conf")
    assert [row["conf_type_id"] for row in rows] == ["HELX_RH_AL_P", "STRN"]
    assert rows[0]["details"] == (
        "A helix, described at length by the depositor\n"
        "_not_a_new_category 1\n"
        "# not a comment either"
    )
    assert rows[1]["details"] == "?"


def test_a_text_field_does_not_shift_the_segments_read_out_of_the_loop():
    assert mmcif.secondary(STRUCT_CONF_WITH_TEXT) == [
        {"kind": "strand", "start": 1, "end": 2},
        {"kind": "helix", "start": 4, "end": 6},
    ]


def test_an_unterminated_text_field_is_a_loud_failure_not_a_short_row():
    text = "loop_\n_demo.a\n_demo.b\n1\n;never closed\nstill going\n"
    with pytest.raises(MmcifError, match="unterminated"):
        mmcif.loop_rows(text, "demo")


# ── the alpha-carbon trace ───────────────────────────────────────────────────────────


def test_only_alpha_carbons_survive_the_atom_table():
    residues = mmcif.ca_trace(MINI_CIF, confidence=True)
    assert [r["n"] for r in residues] == [1, 2, 3, 5, 6]
    # residue 1 has three atoms in the file and exactly one CA
    assert residues[0]["ca"] == [27.21, 69.68, 11.46]


def test_an_unknown_residue_name_becomes_x_rather_than_being_dropped():
    residues = mmcif.ca_trace(MINI_CIF, confidence=True)
    assert [r["aa"] for r in residues] == ["M", "A", "A", "X", "K"]


def test_a_second_alternate_location_does_not_overwrite_the_first():
    residue = mmcif.ca_trace(MINI_CIF, confidence=True)[-1]
    assert residue["n"] == 6
    assert residue["ca"] == [17.21, 62.42, 11.87]  # the A altloc, not the B decoy


def test_b_factor_is_reported_as_plddt_only_for_a_predicted_model():
    assert mmcif.ca_trace(MINI_CIF, confidence=True)[0]["plddt"] == 42.8
    assert mmcif.ca_trace(MINI_CIF, confidence=False)[0]["plddt"] is None


def test_coordinates_are_rounded_to_two_decimals_and_plddt_to_one():
    residue = mmcif.ca_trace(MINI_CIF, confidence=True)[1]
    assert residue["ca"] == [24.54, 68.73, 14.11]
    assert residue["plddt"] == 40.6


def test_a_file_with_no_atom_table_is_an_error_not_an_empty_trace():
    with pytest.raises(MmcifError):
        mmcif.ca_trace("data_nothing\n#\n", confidence=True)


def test_a_file_with_atoms_but_no_alpha_carbons_is_an_error():
    text = MINI_CIF.replace(" CA ", " CB ")
    with pytest.raises(MmcifError):
        mmcif.ca_trace(text, confidence=True)


def test_the_real_model_reports_the_chain_model_and_axis_it_was_read_on():
    parsed = mmcif.ca_trace_detail(MINI_CIF, confidence=True)
    assert (parsed.chain, parsed.model, parsed.seq_axis) == ("A", "1", "label")
    assert parsed.dropped_insertion_codes == 0


# ── which chain gets traced ──────────────────────────────────────────────────────────


def test_a_file_opening_with_a_ligand_chain_still_traces_the_protein():
    """The first atom row's chain is not necessarily a chain with a backbone at all."""
    text = atom_site(
        atom(
            group_PDB="HETATM",
            id="1",
            label_atom_id="ZN",
            label_comp_id="ZN",
            label_asym_id="B",
            label_seq_id=".",
        ),
        atom(id="2", label_comp_id="MET", label_seq_id="1", auth_seq_id="1"),
        atom(id="3", label_comp_id="LYS", label_seq_id="2", auth_seq_id="2"),
    )
    parsed = mmcif.ca_trace_detail(text, confidence=False)
    assert parsed.chain == "A"
    assert [r["n"] for r in parsed.residues] == [1, 2]


def test_a_second_protein_chain_is_not_concatenated_onto_the_first():
    text = atom_site(
        atom(id="1", label_seq_id="1", auth_seq_id="1"),
        atom(id="2", label_asym_id="B", label_seq_id="9", auth_seq_id="9"),
    )
    parsed = mmcif.ca_trace_detail(text, confidence=False)
    assert (parsed.chain, [r["n"] for r in parsed.residues]) == ("A", [1])


# ── one model, one numbering axis, no insertion codes ────────────────────────────────


def test_only_the_first_model_of_an_ensemble_is_traced():
    """An NMR ensemble's models 2..N are superposed copies, not extra residues."""
    text = atom_site(
        atom(id="1", label_seq_id="1", auth_seq_id="1"),
        atom(id="2", label_seq_id="2", auth_seq_id="2"),
        atom(id="3", label_seq_id="1", auth_seq_id="1", pdbx_PDB_model_num="2"),
        atom(id="4", label_seq_id="3", auth_seq_id="3", pdbx_PDB_model_num="2"),
    )
    parsed = mmcif.ca_trace_detail(text, confidence=False)
    assert parsed.model == "1"
    assert [r["n"] for r in parsed.residues] == [1, 2]


def test_an_inserted_residue_is_dropped_and_counted_not_collapsed_onto_its_neighbour():
    text = atom_site(
        atom(id="1", label_seq_id="52", auth_seq_id="52"),
        atom(id="2", label_seq_id="52", auth_seq_id="52", pdbx_PDB_ins_code="A"),
        atom(id="3", label_seq_id="53", auth_seq_id="53"),
    )
    parsed = mmcif.ca_trace_detail(text, confidence=False)
    assert [r["n"] for r in parsed.residues] == [52, 53]
    assert parsed.dropped_insertion_codes == 1


def test_residue_number_zero_is_a_number_not_an_absent_value():
    """``label or auth`` read 0 as absent and silently switched numbering axis."""
    text = atom_site(
        atom(id="1", label_seq_id="0", auth_seq_id="800"),
        atom(id="2", label_seq_id="1", auth_seq_id="801"),
    )
    parsed = mmcif.ca_trace_detail(text, confidence=False)
    assert parsed.seq_axis == "label"
    assert [r["n"] for r in parsed.residues] == [0, 1]


def test_a_chain_with_no_label_numbering_falls_back_to_the_author_axis_as_a_whole():
    text = atom_site(
        atom(id="1", label_seq_id=".", auth_seq_id="17"),
        atom(id="2", label_seq_id=".", auth_seq_id="18"),
    )
    parsed = mmcif.ca_trace_detail(text, confidence=False)
    assert parsed.seq_axis == "auth"
    assert [r["n"] for r in parsed.residues] == [17, 18]


def test_a_chain_that_would_mix_the_two_axes_is_refused_rather_than_half_right():
    text = atom_site(
        atom(id="1", label_seq_id="1", auth_seq_id="1"),
        atom(id="2", label_seq_id=".", auth_seq_id="900"),
    )
    with pytest.raises(MmcifError, match="axes would be mixed"):
        mmcif.ca_trace_detail(text, confidence=False)


# ── covered ranges ───────────────────────────────────────────────────────────────────


def test_covered_merges_consecutive_residues_into_inclusive_runs():
    assert mmcif.covered([1, 2, 3, 7, 8]) == [[1, 3], [7, 8]]


def test_covered_is_order_and_duplicate_insensitive():
    assert mmcif.covered([3, 1, 2, 2]) == [[1, 3]]


def test_covered_of_nothing_is_nothing():
    assert mmcif.covered([]) == []


def test_the_gap_in_the_mini_model_shows_up_as_two_runs():
    residues = mmcif.ca_trace(MINI_CIF, confidence=True)
    assert mmcif.covered([r["n"] for r in residues]) == [[1, 3], [5, 6]]


# ── secondary structure ──────────────────────────────────────────────────────────────


def test_helices_and_strands_are_read_and_turns_are_not():
    assert mmcif.secondary(MINI_CIF) == [
        {"kind": "strand", "start": 1, "end": 2},
        {"kind": "helix", "start": 4, "end": 6},
    ]


def test_a_sheet_range_table_is_read_too_for_an_experimental_entry():
    text = (
        "loop_\n"
        "_struct_sheet_range.sheet_id\n"
        "_struct_sheet_range.id\n"
        "_struct_sheet_range.beg_label_seq_id\n"
        "_struct_sheet_range.end_label_seq_id\n"
        "AA 1 12 18\n"
        "#\n"
    )
    assert mmcif.secondary(text) == [{"kind": "strand", "start": 12, "end": 18}]


def test_a_segment_with_one_end_on_each_axis_is_no_segment_at_all():
    text = (
        "loop_\n"
        "_struct_conf.conf_type_id\n"
        "_struct_conf.beg_label_seq_id\n"
        "_struct_conf.end_label_seq_id\n"
        "_struct_conf.end_auth_seq_id\n"
        "HELX_RH_AL_P 4 ? 600\n"
        "#\n"
    )
    assert mmcif.secondary(text) == []


def test_a_file_without_either_table_reports_no_annotation_rather_than_all_coil():
    assert mmcif.secondary("data_bare\n#\n") == []
