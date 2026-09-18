# Step 1 — dictionary terms, draft

**Standing:** drafted 2026-09-18 by the wave-1 *record* agent, against `fixtures/it4/` only.
Not merged: the one dictionary is [`docs/dictionary.md`](../../dictionary.md) and the wave-3
*docs* agent merges these entries in dependency order. Nothing here is a result.

Source for every entry: `docs/iteration4/plan.md` §5 (step 1), `src/mva/zoo/types.py`,
`src/mva/zoo/record.py`, `src/mva/zoo/record_hgvs.py`, `src/mva/zoo/record_write.py`.

Insert in the order below — each entry only uses words defined above it.

---

**allele id** — a short fingerprint of one genetic change, computed from the change itself, that
names it without saying *where* in the genome it is.
*Example:* `b50f371246f588f4` — the first 16 hex characters of SHA-256 over `1:100000:C:G`.
*Context:* `mva.zoo.types.allele_id`, pinned in iteration 4 wave 0. The same expression is
written in SQL in `mva.zoo.record.allele_id_sql`, and `tests/test_zoo_record.py` asserts the two
agree on every contig spelling. It exists because the repository's coordinate gate
(`tools/check_coordinates.py`) forbids a patient position in any tracked file: the position stays
in `build/it4/records.parquet`, the id is what appears in tables, reports and model inputs.
Related: [allele record](#), [catalogue field](#). *first seen 2026-09-18*

**allele record** — one normalized row per genetic change, carrying every spelling of that change
a model might read: which gene, which transcript, the cDNA and protein notation, the protein
accession, the frequency, the ClinVar class, and (later) the sequence windows.
*Example:* `AlleleRecord(allele_id="b50f3712…", gene="GENEA", consequence="stop_gained",
hgvs_c="ENST00000000002.3:c.22C>T", hgvs_p="ENSP00000000002.3:p.Gln8Ter", uniprot="Q00000")` —
the synthetic row of `tests/test_vep_response_hgvs.py`; a real example would name the child's
allele and is therefore never written here.
*Context:* `mva.zoo.types.AlleleRecord`, built by `mva.zoo.record.build_records` from
`results.coding_alleles` joined to `warehouse.coding_annotations` and
`warehouse.it2_insilico_annotations`, unioned with `warehouse.it2_read_annotations`. In
software terms it is the single DTO in front of a dozen consumers: a new model is a new reader,
never a new query against the warehouse. Lands in `results.it4_allele_records`.
Related: [allele id](#), [HGVS notation](#), [sequence window](#). *first seen 2026-09-18*

**HGVS notation** (`hgvs_c` / `hgvs_p`) — the standard text spelling of a genetic change, agreed by
the Human Genome Variation Society. `hgvs_c` spells it on the transcript's coding sequence,
`hgvs_p` on the protein the transcript makes.
*Example:* `ENST00000000002.3:c.22C>T` (cDNA) and `ENSP00000000002.3:p.Gln8Ter` (protein) — the
same synthetic change, written twice.
*Context:* Requested from Ensembl VEP REST with the `hgvs=1` option
(`mva.pipeline.annotate_vep.QUERY_PARAMS`), parsed in `mva.pipeline.vep_response.parse` and
filled onto the record by `mva.zoo.record_hgvs.hgvs_pass`. It is the join key of every
precomputed score table in the zoo, so nothing in step 2 can be looked up without it. Think of
it as a stable string id in an external system's format, as opposed to our own coordinate.
Claim `P4-1a` measures how many coding alleles get one.
Related: [allele record](#), [UniProt accession](#), [variant-effect predictor](#).
*first seen 2026-09-18*

**UniProt accession** — the stable id of a *protein* (as opposed to a transcript) in the UniProt
database. VEP reports the reviewed (SwissProt) accession per transcript; the isoform suffix is
dropped because score tables index the bare accession.
*Example:* `Q00000` — from VEP's `"swissprot": ["Q00000.4"]`.
*Context:* `mva.pipeline.vep_response._uniprot`, requested with the `uniprot=1` option added by
`mva.zoo.record_hgvs.HgvsAnnotator`. Needed because ESM1b's precomputed files are one per
protein, keyed on accession + `hgvs_p`, not on an Ensembl transcript id.
Related: [HGVS notation](#), [precomputed scores](#). *first seen 2026-09-18*

**catalogue field** — a field on the allele record whose value came out of a curated *catalogue*
of known answers (ClinVar), rather than out of a measurement or a model.
*Example:* `clin_sig = "benign"`; `--mask-catalogue` replaces it with `NULL`.
*Context:* `mva.zoo.types.CATALOGUE_FIELDS` and `AlleleRecord.masked()`, plan decision D4. A
model trained on ClinVar can "know" the answer; running the zoo a second time with the catalogue
fields nulled is what makes the catalogue-free / aware comparison honest. Distinct from
**catalogue-adjacent**, which describes a *model*, not a field.
Related: [allele record](#), [catalogue-adjacent](#). *first seen 2026-09-18*

**sequence window** — a fixed-length stretch of sequence centred on the change, given to a model
that reads sequence rather than a table: an amino-acid string for a protein language model, a
DNA string for a DNA language model. Written in both the reference and the altered form so the
model can score the difference.
*Example:* `protein_window_ref` / `protein_window_alt` (±n amino acids), `dna_window_ref` /
`dna_window_alt` (8,192 bp, plan §5).
*Context:* Columns already present in `mva.zoo.types.AlleleRecord` and in
`mva.zoo.record_write.PARQUET_COLUMNS`, and **null in the MVP** — plan §5 labels them opt-A and
opt-B, so filling them is a fill, not a schema migration. They are patient sequence, so they may
only ever live in `build/it4/records.parquet` (coordinate gate rule 4).
Related: [allele record](#), [protein language model](#), [DNA language model](#).
*first seen 2026-09-18*
