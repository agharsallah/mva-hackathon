# 056 — The protein-structure endpoint: an alpha-carbon trace from AlphaFold DB

**A step-0 platform entry, so it carries no hypothesis.** It records the live replies that
were read before any code was written, the mmCIF facts learned from the real file, the
resulting payload size, and the four upstream latencies measured.

## Question

The 1D exhibits — the exon track and the domain lollipop of entry
[040](040-locus-gene-track.md) — put amino acids on a line and answer *which domain* an
allele lands in. They cannot answer the two questions that decide a **compound
heterozygote** (two different broken copies of one gene, one from each parent):

1. are the two damaged residues **close in space**? Sequence distance is a poor proxy for
   3D distance: residues 350 and 900 can pack into one binding pocket.
2. does either residue sit on a **partner interface** — a surface where another protein
   binds? That is a mechanism claim, and a mechanism claim is what Track 2 needs.

So: can a folded model of one panel gene's protein be fetched server-side, trimmed to a
payload a browser can draw, and made to share the **same residue axis** the lollipop
already uses — without a new Python dependency, and without any patient data riding along?

## Inputs

| Input | Shape as read |
|---|---|
| `ressources/data-profile/mva_panel_grch38.bed` | 8 genes with their stable Ensembl gene id (reused via `genestructure.panel_gene`) |
| `https://rest.ensembl.org/lookup/id/{ENSG}?expand=1` | live; the same call entry 040 made, reused via `genestructure.pick_transcript` |
| `https://rest.ensembl.org/xrefs/id/{ENSP}?external_db=Uniprot/SWISSPROT` | live; **new to this entry** |
| `https://alphafold.ebi.ac.uk/api/prediction/{accession}` | live, keyless; **new to this entry** |
| `https://alphafold.ebi.ac.uk/files/AF-O60566-F1-model_v6.cif` | live, 999,519 B |
| Code | `src/mva/viz/proteinstructure.py`, `src/mva/viz/mmcif.py`, route in `src/mva/viz/routes_panel.py` |
| Contract | `app/src/api/types/protein.ts` (frozen before the build; implemented field for field) |
| Design | [three.js behind one wrapper](../notes/three-js-behind-one-wrapper.md) §2, §5 |

No warehouse table is read. That is the point of the perimeter section below.

## Probe 1 — does Ensembl hand over a UniProt accession for a translation?

AlphaFold DB is keyed by **UniProt accession** (the stable id of a protein sequence, e.g.
`O60566`), not by an Ensembl id. The design note observed that
`/overlap/translation/{ENSP}` *already returns* an AlphaFold reference
(`{"type": "alphafold", "id": "AF-O60566-F1", …}`), so the accession could be scraped out
of an id we already fetch. It was rejected: parsing an accession out of a model **name** is
a string-shape assumption, while `xrefs` is the endpoint whose job it is. Probed:

```bash
curl -s -H 'Accept: application/json' \
  'https://rest.ensembl.org/xrefs/id/ENSP00000287598?external_db=Uniprot/SWISSPROT'
```

Reply (one row, verbatim, description trimmed):

```json
[{"dbname":"Uniprot/SWISSPROT","info_text":"Generated via direct","score":5469,
  "primary_id":"O60566","version":"231","cigar_line":"1050M","ensembl_identity":100,
  "display_id":"O60566.231","ensembl_start":1,"xref_start":1,"ensembl_end":1050,
  "xref_end":1050,"xref_identity":100,"info_type":"DIRECT","synonyms":[]}]
```

Facts learned:

- `primary_id` is the bare accession; `display_id` carries a `.231` **sequence version**
  suffix and would 404 against AlphaFold. The code reads `primary_id`.
- the reply is a **list**, and rows carry `xref_identity`; the highest-identity row is
  taken so a partial-match xref cannot outrank the 100 % one.
- an unfiltered `/xrefs/id/{ENSP}` returns hundreds of rows across BioGRID, ChEMBL, EMBL,
  … — so the `external_db` filter is load-bearing, not a nicety.
- `Uniprot/SPTREMBL` is tried second: Swiss-Prot is the manually reviewed half of UniProt
  and covers BUB1B, but a gene nobody curated only has a TrEMBL xref.

**`O60566` is never hardcoded in code.** It appears only in committed fixtures.

## Probe 2 — what does the AlphaFold prediction API actually return?

```bash
curl -s 'https://alphafold.ebi.ac.uk/api/prediction/O60566'
```

`http 200`, 10,860 B. The reply is a **list of three entries** — one per isoform model:

| `entryId` | `uniprotEnd` | `latestVersion` | `globalMetricValue` |
|---|---|---|---|
| `AF-O60566-F1` | 1050 | 6 | 63.59 |
| `AF-O60566-3-F1` | 1064 | 6 | 64.38 |
| `AF-O60566-2-F1` | 933 | 6 | 62.59 |

Fields read (trimmed from the first entry):

```
modelEntityId    = AF-O60566-F1        latestVersion  = 6
modelCreatedDate = 2025-08-01T00:00:00Z allVersions   = [1, 2, 3, 4, 5, 6]
uniprotAccession = O60566              uniprotStart/End = 1 / 1050
globalMetricValue = 63.59              fractionPlddtVeryLow = 0.373
cifUrl  = https://alphafold.ebi.ac.uk/files/AF-O60566-F1-model_v6.cif
bcifUrl = …-model_v6.bcif   pdbUrl = …-model_v6.pdb
plddtDocUrl = …-confidence_v6.json     isComplex = False   chainId = A
```

Facts learned, each of which changed the code:

- **the reply is a list, so "the first entry" is a coin flip on which isoform is drawn.**
  The entry is chosen by matching Ensembl's translation length (1050) against
  `uniprotEnd`; the canonical `AF-<acc>-F1` id is the fallback. Getting this wrong would
  paint residue *n* of the lollipop onto residue *n* of a **different** isoform — silently
  wrong, not absent.
- `latestVersion` is **6**, not the `model_v4` a 2023-era snippet would hardcode. The
  design note named that specific mistake; the version and the whole `cifUrl` are read
  from the reply.
- `globalMetricValue` 63.59 and `fractionPlddtVeryLow` 0.373 say this model is
  **low-confidence over more than a third of its length**. That is a finding for the
  exhibit, not a defect: it is why per-residue pLDDT has to be visible.

## Probe 3 — the mmCIF file itself

```bash
curl -s 'https://alphafold.ebi.ac.uk/files/AF-O60566-F1-model_v6.cif' -o af.cif
# http 200, 999,519 B
grep -n '^_struct_conf\.\|^_struct_sheet_range\|^_atom_site\.' af.cif
```

**`_atom_site` header** (the atom table), verbatim, plus the first two rows:

```
_atom_site.group_PDB _atom_site.id _atom_site.type_symbol _atom_site.label_atom_id
_atom_site.label_alt_id _atom_site.label_comp_id _atom_site.label_asym_id
_atom_site.label_entity_id _atom_site.label_seq_id _atom_site.pdbx_PDB_ins_code
_atom_site.Cartn_x _atom_site.Cartn_y _atom_site.Cartn_z _atom_site.occupancy
_atom_site.B_iso_or_equiv _atom_site.pdbx_formal_charge _atom_site.auth_seq_id …

ATOM 1 N N  . MET A 1 1 ? 26.584 70.797 10.710 1.00 42.81 ? 1 MET A N  1 O60566 UNP 1 M
ATOM 2 C CA . MET A 1 1 ? 27.212 69.682 11.463 1.00 42.81 ? 1 MET A CA 1 O60566 UNP 1 M
```

**mmCIF facts learned, and where each landed in the code:**

| Fact | Consequence |
|---|---|
| `B_iso_or_equiv` in an AlphaFold file **is pLDDT** (all atoms of residue 1 carry 42.81, a per-*residue* value), not a crystallographic B-factor | `mmcif.ca_trace(confidence=…)` — the caller states which kind of file it handed over, so an experimental entry reports `plddt: null` instead of mislabelling a B-factor as confidence |
| the file carries **`_struct_conf` but no `_struct_sheet_range`** (`grep -c _struct_sheet_range` → **0**) | strands must be read out of `_struct_conf`; `_struct_sheet_range` is still parsed, for an experimental PDB entry that uses it |
| `_struct_conf_type.id` values are DSSP-derived: `HELX_RH_AL_P`, `HELX_RH_3T_P`, `HELX_LH_PP_P`, `STRN`, `TURN_TY1_P`, `BEND` | helix = `conf_type_id` starting `HELX`; strand = `STRN`; `TURN`/`BEND` are dropped rather than painted, because they are neither |
| segment rows carry both `beg_label_seq_id` and `beg_auth_seq_id` | label numbering is preferred — it is the same axis as `_atom_site.label_seq_id`; author numbering is the fallback only |
| `_atom_site` has a `label_alt_id` column and a single chain `A` (`isComplex: False`) | alternate locations past the first are dropped, and only the first `label_asym_id` is traced, so a multi-chain experimental file cannot draw a tube between two molecules |
| rows are one-per-line here, but mmCIF permits wrapping and quoted values | the reader tokenises with quote handling and accumulates until a row is full — a quoted value containing a space would otherwise shift every later column of that row |

**No new dependency.** A full mmCIF library (gemmi, biotite, Biopython) brings a compiled
wheel and a structural-biology object model to read two tables. Following the repo's
[hand-rolled VCF reader](../../notes/hand-rolled-vcf-reader.md) precedent,
`src/mva/viz/mmcif.py` is ~290 lines including its docstrings, tested against a six-residue
trim of this real file (`tests/fixtures/mini_alphafold.cif`).

## What was built

| File | Role |
|---|---|
| `src/mva/viz/mmcif.py` | the loop tokeniser, `ca_trace`, `secondary`, `covered` |
| `src/mva/viz/proteinstructure.py` | resolution (gene → ENSG → ENSP → accession → model) and payload assembly |
| `src/mva/viz/routes_panel.py` | `GET /api/panel/protein-structure?gene=…&refresh=false`, moved with `gene-structure` into a new `_reference_structure_routes` group — the two routes that read no warehouse table |
| `tools/build_protein_fixture.py` | runs the same parser against the live API to produce the committed app fixture |
| `tests/test_viz_proteinstructure.py` | 47 tests, all offline via `httpx.MockTransport` |

Reuse, not reimplementation: `genestructure.panel_gene` gates the panel and
`genestructure.pick_transcript` chooses the transcript, so the trace and the lollipop
**cannot** end up on two different transcripts. `pick_transcript` raises
`EnsemblError`, so the route catches `(ProteinModelError, EnsemblError)` and 502s on either.

## Observed output

```
$ uv run python tools/build_protein_fixture.py
BUB1B: ENSP00000287598 / O60566 alphafold v6 — 1050 of 1050 residues,
  62 secondary segments, covered [[1, 1050]]
app/src/fixtures/data/panel-protein-structure.json — 62,867 bytes (61.4 kB)
model_url: https://alphafold.ebi.ac.uk/files/AF-O60566-F1-model_v6.cif
```

- **Payload: 61.4 kB of JSON from a 999,519 B coordinate file — a 15.9× reduction**, with
  coordinates rounded to 2 decimals (far below the model's own resolution) and pLDDT to 1.
  Well inside the ~150 kB fixture budget.
- **62 secondary segments**, which reconciles exactly with the file:
  25 `HELX_RH_AL_P` + 10 `HELX_RH_3T_P` + 9 `HELX_LH_PP_P` + 18 `STRN` = 62. The 41
  `TURN_TY1_P` and 51 `BEND` rows were correctly dropped.
- **`covered` is `[[1, 1050]]`** — AlphaFold models the whole sequence, so for this protein
  there is no unmodelled gap. The gap case is still exercised, by the mini fixture.
- **First residues agree with the API's own `sequence` field**: the parsed one-letter
  string starts `MAAVKKEGGALSEAMSLEGDEWELSKENVQPLRQGRIMSTLQGALAQESACNNTLQQQKR`, identical to
  the prediction reply's `sequence` prefix — an independent check that the residue axis is
  not off by one.
- `protein` is `ENSP00000287598`, which is what `/api/panel/gene-structure` reports for
  BUB1B, so the client's pre-paint assertion holds.

**Latency, measured (cold, one sample each):**

| Call | Time | Bytes |
|---|---|---|
| `rest.ensembl.org/lookup/id/ENSG00000156970?expand=1` | 3.44 s | 116,004 |
| `rest.ensembl.org/xrefs/id/ENSP00000287598?external_db=…` | 4.51 s | 444 |
| `alphafold.ebi.ac.uk/api/prediction/O60566` | 0.08 s | 10,860 |
| `alphafold.ebi.ac.uk/files/AF-O60566-F1-model_v6.cif` | 0.49 s | 999,519 |
| end-to-end `proteinstructure.structure('BUB1B')` incl. parse | **3.46 s** | — |

Ensembl dominates and is erratic (3–5 s per call); AlphaFold is fast even for the 1 MB
file. That is exactly the profile the disk cache exists for, so the route caches under
`safe_key("protein-structure", gene)` like `gene-structure` does.

## Perimeter

This payload contains **no patient data of any kind** — it is not merely de-identified. The
endpoint reads no warehouse table, makes no VEP call, and its only axis is an amino-acid
index. An AlphaFold model is public reference data and is identical for every human. Two
consequences:

1. `app/src/fixtures/data/panel-protein-structure.json` is the **real** trace, committed.
   It is the one fixture in that directory that is not a synthetic shape, and both its
   module docstring and the registry comment say so loudly, precisely because every
   neighbouring fixture *is* synthetic and must never be quoted.
2. A screenshot of this exhibit can go straight into the public report and the Track 2
   video. The locus and pileup views cannot.

A test asserts the negative structurally rather than by spot check: no `chrom`, `pos`,
`ref`, `alt`, `gt` or `candidates` key exists anywhere in the payload shape.

## Gates

`tools/check-python.sh --fix`, all six green: ruff format (1 file reformatted), ruff lint,
module size, import layering, mypy, pytest **1459 passed**. Two lint findings were fixed
rather than suppressed: `PIE810` (merged `startswith` calls) and `PLR0915` on
`_one_gene_routes`, which was over 50 statements once a fourth cached route joined it —
resolved by splitting the two reference-data routes into their own registrar, which is a
better grouping anyway (they are the only panel routes whose failure mode is an upstream
outage rather than a missing table).

App side: `pnpm run typecheck` clean, `pnpm run test` **149 passed** after blessing two new
`fixtureHashes.json` entries for the two new `fixtureMatrix.ts` rows.

## Conclusion

- **Yes.** A folded model of a panel gene's protein is fetchable server-side from two
  keyless public APIs, and trims to 61.4 kB — 6 % of the coordinate file — while keeping
  per-residue confidence, secondary structure and the coverage gaps.
- The residue axis is shared with the lollipop **by construction**, because the transcript
  choice is the same function call, not a second implementation of the same rule.
- Three things had to be read from live replies rather than assumed, and each would have
  been silently wrong if guessed: the prediction endpoint returns a **list of isoforms**;
  the current model version is **6**, not 4; and AlphaFold files carry **no
  `_struct_sheet_range`**, so strands live in `_struct_conf` as `STRN`.
- `partners` is `[]` and stays that way until the phase-2 experimental-complex path lands;
  the field is in the payload so the client need not change shape when it does.
- Honesty the exhibit still owes, unbuilt here: `globalMetricValue` 63.59 with 37.3 % of
  residues at very-low pLDDT means large stretches of BUBR1 support **no** spatial claim.
  The renderer must paint those as unmeasured rather than as a colour that reads as
  structure.
