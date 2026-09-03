# 058 — Hardening the hand-rolled mmCIF reader: six silent-corruption paths closed

**A step-0 platform entry, so it carries no hypothesis.** It records six defects a review
of the uncommitted protein-structure work found in `src/mva/viz/mmcif.py` and
`src/mva/viz/proteinstructure.py`, the test that reproduces each one, the fix, and the
proof that the BUB1B payload entry [056](056-protein-structure-endpoint.md) measured is
unchanged by all six — the rebuilt JSON parses equal to the committed fixture, field for
field.

Supersedes nothing. Entry 056 stands: it recorded what the reader did on *one real
AlphaFold monomer*, and every number in it still reproduces. This entry is about the files
that reader would have read **wrong** — an NMR ensemble, a complex whose file opens with a
ligand, a chain with author-only numbering, a `_struct_conf` carrying a prose `details`
field, a tab-separated row, a fragment isoform model. None of those is BUB1B, which is
exactly why the tests below had to be written rather than the fixture re-run.

## Question

Entry 056 justified a hand-rolled reader on the grounds that "the subset here is a
tokeniser and a loop reader … and it fails loudly rather than guessing". Does it? For each
input the docstring claims to handle, does the reader produce the right rows, refuse, or
silently produce *plausible wrong* rows?

## Inputs

| Input | Shape as read |
|---|---|
| Review findings | `src/mva/**` lines of the protein-exhibit review (6 findings: 3 bug, 3 risk) |
| Code before | `src/mva/viz/mmcif.py` (294 lines), `src/mva/viz/proteinstructure.py` |
| Real file | `https://alphafold.ebi.ac.uk/files/AF-O60566-F1-model_v6.cif`, 999,519 B |
| Committed fixture | `tests/fixtures/mini_alphafold.cif` (6 residues, real coordinates) |
| Frozen contract | `app/src/api/types/protein.ts` — unchanged by this entry |
| Baseline payload | `app/src/fixtures/data/panel-protein-structure.json` (80,463 B, pretty-printed) |

## The six findings, and what each one does to a real file

| # | Finding | What the reader did | What that costs |
|---|---|---|---|
| 1 | `_tokens` split with `partition(" ")` | a tab-separated data row became **one token** | every later column of that row shifts — the exact silent corruption the docstring said quoting prevented |
| 2 | no `;`-delimited text field support | a multi-line value was tokenised as words, and an inner line starting `_` or `#` **ended the loop** | a `_struct_conf` with a prose `details` column loses every row after the first, so segments silently vanish |
| 3 | `_int(label_seq_id) or _int(auth_seq_id)` | residue number **0** read as absent → fell through to the other numbering axis; `_segment` had the same idiom | `label_seq_id` (sequence index) and `auth_seq_id` (depositor's numbering) are unrelated integers; a trace with some residues on each is a *wrong* picture, and `protein_pos` is only meaningful on the label axis |
| 4 | `_first_chain` took the first atom row's chain | a file opening with a ligand or nucleic chain yielded **no CA** | `MmcifError` instead of tracing the protein that is right there |
| 5 | no `pdbx_PDB_model_num` filter, `pdbx_PDB_ins_code` ignored | an NMR ensemble's models 2..N were dropped only as a side effect of de-duplication; `52A` collapsed onto `52` | residues silently swallowed with no count |
| 6 | isoform picked by `uniprotEnd == length` | only equal when `uniprotStart == 1` | a fragment model (`F2`) can never match, and a *different* isoform whose end happens to equal the length can |

## Method — a failing test per finding, first

Each fix was written against a test that fails on the pre-fix code. The pre-fix module was
restored beside the new tests to prove it (both source files are uncommitted, so the
"before" was reconstructed from the reviewed text, not `git checkout`):

```
uv run pytest tests/test_viz_mmcif.py tests/test_viz_proteinstructure.py -q
14 failed, 48 passed, 1 warning in 1.10s
```

The 14, each naming its finding:

| Finding | Test (in `tests/test_viz_mmcif.py` unless noted) |
|---|---|
| 1 | `test_a_tab_separated_row_is_split_into_its_values_not_left_as_one` |
| 2 | `test_a_multi_line_text_field_is_one_token_and_does_not_end_the_loop`, `test_a_text_field_does_not_shift_the_segments_read_out_of_the_loop`, `test_an_unterminated_text_field_is_a_loud_failure_not_a_short_row` |
| 3 | `test_residue_number_zero_is_a_number_not_an_absent_value`, `test_a_chain_with_no_label_numbering_falls_back_to_the_author_axis_as_a_whole`, `test_a_chain_that_would_mix_the_two_axes_is_refused_rather_than_half_right`, `test_a_segment_with_one_end_on_each_axis_is_no_segment_at_all` |
| 4 | `test_a_file_opening_with_a_ligand_chain_still_traces_the_protein`, `test_a_second_protein_chain_is_not_concatenated_onto_the_first` |
| 5 | `test_only_the_first_model_of_an_ensemble_is_traced`, `test_an_inserted_residue_is_dropped_and_counted_not_collapsed_onto_its_neighbour`, plus `test_the_real_model_reports_the_chain_model_and_axis_it_was_read_on` |
| 6 | `test_a_fragment_model_is_matched_by_its_span_not_by_where_it_ends` (in `tests/test_viz_proteinstructure.py`) |

One further test — `test_column_aligned_values_are_split_on_the_whole_run_of_spaces` —
**passed before the fix** and is kept as a guard, not claimed as a reproduction:
`partition(" ")` plus `lstrip()` already handled runs of spaces. Only the tab broke it.

## The fix

| Finding | Change |
|---|---|
| 1 | `mmcif_tokens.tokens` splits on any whitespace run (`str.split(None, 1)`) outside quotes |
| 2 | `mmcif_tokens._text_field`: a line whose first character is `;` opens a value, a line that is exactly `;` closes it, the lines between join with `\n` as **one token**. An unterminated field raises `MmcifError`. The loop-end test now never sees a line inside a text field |
| 3 | `_sequence_axis` picks **one axis for the whole chain** — `label` when every alpha carbon has `label_seq_id`, `auth` when none does, and `MmcifError` naming the chain and the counts when it is patchy. `_segment` prefers label for *both* ends and falls back to auth only when both label ends are absent |
| 4 | `_first_ca_chain` returns the first `label_asym_id` that has a CA atom in the selected model |
| 5 | `_first_model` keeps the first `pdbx_PDB_model_num` the table names and drops every other model's rows; a non-blank `pdbx_PDB_ins_code` is dropped and **counted** |
| 6 | `proteinstructure._span` = `uniprotEnd - uniprotStart + 1` (start defaulting to 1), compared against Ensembl's translation length; the canonical-`F1` preference now runs as its own loop, so it cannot pre-empt a span match |

Two structural consequences:

* **`src/mva/viz/mmcif_tokens.py` is new** (169 lines): the syntax layer — tokenising, the
  `loop_` header/body reader, the null and numeric coercions. `mmcif.py` (320 lines) keeps
  the structural biology. The 294-line original would have passed the 400-line cap with
  the fixes bolted on; the split is by concern, and it kept both files under the warning
  band.
* **`Trace` (a frozen dataclass) is what the parser now returns** from
  `mmcif.ca_trace_detail`: the residues plus `chain`, `model`, `seq_axis` and
  `dropped_insertion_codes`. `mmcif.ca_trace` is the residue list, unchanged, and is what
  the payload still carries. Those four facts are deliberately **not** in the HTTP payload:
  `app/src/api/types/protein.ts` is frozen and has no field for them, and inventing one
  would put the client and the contract out of step. A file that would *need* them to be
  understood — one mixing the two numbering axes — is refused instead of shipped.

Tests moved with the concern: the parser's tests are now `tests/test_viz_mmcif.py` (348
lines), and `tests/test_viz_proteinstructure.py` (419) keeps the endpoint's.

## Observation 1 — what the fixed reader says about the real BUB1B file

```
uv run python -c '<fetch the cif, then mmcif.ca_trace_detail>'
999519 bytes; chain A model 1 axis label dropped_ins 0 residues 1050
atom rows 8403 models ['1'] chains ['A']
```

The axis actually used is **`label`**, the model **1**, the chain **A**, insertion codes
dropped **0** — which is why none of the six defects showed on this file, and why the
payload cannot have changed. This is the number the endpoint's docstring points at rather
than shipping a `seq_axis` field.

## Observation 2 — the payload is unchanged

```
uv run python tools/build_protein_fixture.py --out <scratch>/bub1b.new.json
BUB1B: ENSP00000287598 / O60566 alphafold v6 — 1050 of 1050 residues, 62 secondary segments, covered [[1, 1050]]
<scratch>/bub1b.new.json — 62,867 bytes (61.4 kB)
```

Compared against the committed fixture as parsed JSON (the committed file is
prettier-formatted, so a byte compare is meaningless):

```
python3 -c 'json.load(committed) == json.load(rebuilt)'  ->  equal: True
```

**`app/src/fixtures/data/panel-protein-structure.json` was therefore not regenerated and
is unchanged**, so `app/src/test/fixtureHashes.json` needs no update. Every figure in
entry 056 and entry 057 still holds: 1,050 residues, 62 secondary segments,
`covered [[1, 1050]]`, 61.4 kB.

## Observation 3 — the gates

```
./tools/check-python.sh --fix          # exit 0
==> ruff format         228 files left unchanged
==> ruff check --fix    All checks passed!
==> ruff format --check 228 files already formatted
==> ruff check          All checks passed!
==> module size         ok: every module within its limit (src: 400, tests: 600, tools: 400); 6 in the warning band.
==> import layering     Contracts: 3 kept, 0 broken.
==> mypy                Success: no issues found in 160 source files
==> pytest              1475 passed, 1 warning in 24.06s
python gate: green
```

`mmcif.py` (320) and `mmcif_tokens.py` (169) are both outside the 90 % warning band; the
six files the size gate names as "near" are all pre-existing and untouched here.

## Conclusion

* Five of the six defects were **silent** — they produced a plausible trace of the wrong
  thing rather than an error. That is the failure mode a hand-rolled reader has to be held
  to, and "it fails loudly rather than guessing" was true of the *file-shape* checks only.
  It is now true of the value-level ones: a mixed numbering axis and an unterminated text
  field both raise, naming the chain or the field.
* The reader's supported subset is now **stated in the module docstrings, exactly**: three
  value forms, one model, one chain, one numbering axis, no insertion codes, one altloc —
  with what is *not* supported (`save_` frames, `global_` blocks, an unclosed quote) named
  too.
* None of it moved a number in the shipped payload, which is the honest reading of a
  hardening pass against one monomer: the value is in the files this repo has not fetched
  yet — an experimental PDB complex for the interface work entry 056 lists as phase 2.
