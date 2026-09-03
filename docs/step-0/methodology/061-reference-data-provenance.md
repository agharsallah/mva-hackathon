# 061 — Every reference dataset names its own source, its release and its digest

**Date:** 2026-09-03
**Question:** the repository commits five kinds of data it did not compute — gnomAD
constraint, ClinVar, HPO, an Ensembl-resolved gene set, and 44 files of real Ensembl and
AlphaFold payload used as offline fixtures. For each one: *which upstream, at which
release, with which digest, built by which tool at which commit* — and can a reader get
that answer without reading the build script? Two of the five already had a manifest
(`hpo_provenance.json`) or a methodology entry; three had neither, and no endpoint listed
any of them.

_(step-0 platform machinery: this entry records decisions and measurements, not a
hypothesis. Per [`docs/method.md`](../../method.md), step 0 takes no hypotheses.)_

## Why a manifest and not a lineage edge

`warehouse.data_lineage` is an edge list of **derivations**: table X was computed from
object Y by transform Z, producing N rows
([`016`](016-lineage-backfill-and-probe-ledger.md)). Reference data has none of those
three things. An HPO release, an Ensembl gene record and an AlphaFold model are
**fetched**; there is no input table and no transformation, so an edge for them would
name a transform that never ran. Faking one would put a fabricated row in the one table
the project treats as evidence.

What they get instead is a **provenance manifest** committed beside the bytes — the
upstream URL and its release, a digest per input and per output, the tool, and the commit
it ran at — written by the tool on every run and never by hand. The distinction is now in
[`docs/dictionary.md`](../../dictionary.md) as **provenance manifest** and **provenance vs
lineage**.

## Inputs

| | |
|---|---|
| Code at build time | `cb066b8` (recorded by both tools as `code_version`) |
| Ensembl REST | `https://rest.ensembl.org`, release read live — see below |
| AlphaFold DB | `https://alphafold.ebi.ac.uk/api/prediction/{accession}` |
| Spec TSV | `ressources/reference/structure_genes.spec.tsv`, 2,311 B, sha256 `b6acc58133bdfa2eec78974053a68beb50830fc1ed048b8c50d4f9eeeadebddd` |
| Panel BED | `ressources/data-profile/mva_panel_grch38.bed`, 786 B, sha256 `7e81f3ee7978ed1a2b3d313f26fab2b53f341d352f2edb24724dabebb96040b7` |

## Commands run

```bash
# the Ensembl release, asked directly first
curl -s -H 'Accept: application/json' https://rest.ensembl.org/info/data
curl -sI -H 'Accept: application/json' https://rest.ensembl.org/lookup/id/ENSG00000156970

# 1 — the gene set, rebuilt so the TSV and its manifest come from one run
cp ressources/reference/structure_genes.tsv /tmp/before.tsv
uv run python tools/build_gene_set.py \
  --spec ressources/reference/structure_genes.spec.tsv --alias CCDC84=CENATAC
diff /tmp/before.tsv ressources/reference/structure_genes.tsv

# 2 — the fixtures, rebuilt from scratch so every per-gene manifest block is measured
cp -R app/src/fixtures/data/protein app/src/fixtures/data/gene-structure /tmp/fixtures-before/
uv run python tools/build_protein_fixture.py --force
diff -r /tmp/fixtures-before/protein app/src/fixtures/data/protein --exclude=_provenance.json
diff -r /tmp/fixtures-before/gene-structure app/src/fixtures/data/gene-structure --exclude=_provenance.json

# 3 — the endpoint, and the gates
uv run python -c "from mva.viz import refprovenance; print(refprovenance.rows())"
tools/check-python.sh
cd app && pnpm run typecheck
```

## Observed output

### The Ensembl release is only available at one endpoint

```
$ curl -s https://rest.ensembl.org/info/data
{"releases":[116]}

$ curl -sI https://rest.ensembl.org/lookup/id/ENSG00000156970
HTTP/2 200
vary: Origin
x-ratelimit-limit: 55000
x-runtime: 0.059288
```

**No reply header carries the release.** That is the measurement that decided the design:
a route cannot learn the release from the reply it already has, and asking `/info/data`
per request would add a round trip and a failure surface to the two routes whose whole
value is that their answer is already on disk. So the **build tools** ask live
(`mva.viz.ensembl.release`, memoised per process), and the **routes** report the release
the committed gene set was resolved at, under the key
`ensembl_release_at_gene_set_build` — named for what it is rather than implying it was
asked now.

Release **116** today. `structure_genes.tsv` was built at release 116 as well, so the two
agree; the point of the separate key is the day they stop agreeing.

### 1 — the gene set, and the assertion that mattered

```
$ uv run python tools/build_gene_set.py --spec … --alias CCDC84=CENATAC
ensembl release 116 (GET https://rest.ensembl.org/info/data)
  CEP57        ENSG00000166037  protein_coding   canonical=ENST00000322347 …
  …
    retry 1/3 after GET …/lookup/symbol/homo_sapiens/BUB1?expand=1: ReadTimeout
  BUB1         ENSG00000169679  protein_coding   canonical=ENST00000302759 …
  alias CCDC84 → CENATAC: CONFIRMED — /xrefs/symbol/CCDC84 matches
      ['ENSG00000186166', 'ENSG00000280975']; /lookup/symbol/CENATAC is ENSG00000186166

21 of 23 genes have a translating canonical transcript
non-coding: ['DICER1-AS1', 'MAMDC2-AS1']
ressources/reference/structure_genes.tsv — 2,569 bytes, 23 rows
ressources/reference/structure_genes.provenance.json — sha256 1124e6c0…, 7 genes with a
    cited OMIM/PMID

$ diff /tmp/before.tsv ressources/reference/structure_genes.tsv
$ echo $?
0
```

**The TSV is byte-identical** to what [`060`](060-structure-gene-set.md) committed — same
2,569 bytes, same 23 rows, sha256
`1124e6c04a5c3f588dbaf26c469cec2eee7c3dc33a3bf3a7f195d62ae94d33cf`. That is the point of
rerunning rather than hand-writing the manifest: the digest in the manifest describes the
file that is actually on disk beside it, produced by the same process invocation.

`literature` came out as **7 genes** with a citation, extracted from the notes by regex
rather than retyped: CENATAC (OMIM 620153, PMID 34009673), MAD1L1 (620189, 36322655),
SLF2 (620184, 36333305), MAD2L1BP (PMID 37796616 only — no OMIM phenotype), BUB1 (620183,
35044816), MTMR2 (601382), WRAP53 (613988). The 16 genes whose notes cite nothing are
**omitted rather than listed empty**: their notes already say "no documented MVA link
found" in words, and an empty array beside that adds no fact.

### 2 — the fixtures, rebuilt

```
CEP57        panel     gene-structure    2.0 kB (11 exons, 3 domains, 3 synthetic candidates)
                                       | protein 28.9 kB (ENSP00000317902 / Q86XR8 alphafold v6,
                                         500 of 500 residues, covered [[1, 500]])
…
    BRD9: retry 1/5 after GET …/xrefs/id/ENSP00000419765?external_db=Uniprot/SWISSPROT
          -> 503: No server is available to handle this
BRD9         extended  gene-structure    2.4 kB (16 exons, 10 domains, 0 synthetic candidates)
                                       | protein 34.4 kB (…)
DICER1-AS1   extended  gene-structure    0.4 kB (2 exons, 0 domains, 0 synthetic candidates)
                                       | protein: none — lncRNA, no translation
app/src/fixtures/data/panel-structure-genes.json — 23 genes
app/src/fixtures/data/gene-structure/_provenance.json — 23 genes
app/src/fixtures/data/protein/_provenance.json — 21 genes

23 genes — 1,089,060 bytes total (1063.5 kB)
```

**1,089,060 bytes — the same total 060 measured**, and:

```
$ diff -r /tmp/fixtures-before/protein app/src/fixtures/data/protein --exclude=_provenance.json
PROTEIN IDENTICAL
$ diff -r /tmp/fixtures-before/gene-structure app/src/fixtures/data/gene-structure --exclude=_provenance.json
GENE-STRUCTURE IDENTICAL
$ diff /tmp/fixtures-before/panel-structure-genes.json app/src/fixtures/data/panel-structure-genes.json
INDEX IDENTICAL
```

All **44 per-gene files plus the index are byte-identical** across a full rebuild against
the live upstreams. Nothing had to be made deterministic: the exon list is already
re-sorted and renumbered by `mva.viz.genestructure`, the domain list is sorted by
`(start_aa, end_aa, source)`, and `write_json` fixes the separators and the key order. The
one AlphaFold model version in play is **v6** for all 21 proteins, and every
`modelCreatedDate` the API returned is `2025-08-01T00:00:00Z`.

One transient failure, recorded because it is the reason the build tools retry and the
routes do not: `GET /xrefs/id/ENSP00000419765` (BRD9) answered **503** once and 200 on the
next attempt. Ensembl REST also timed out once on `/lookup/symbol/BUB1` during run 1.

A per-gene block, verbatim:

```json
"ATP1B2": {
  "symbol": "ATP1B2",
  "ensembl_id": "ENSG00000129244",
  "ensembl_release": "116",
  "protein": "ENSP00000250111",
  "uniprot": "P14415",
  "model_url": "https://alphafold.ebi.ac.uk/files/AF-P14415-F1-model_v6.cif",
  "latest_version": "6",
  "alphafold_entry_id": "AF-P14415-F1",
  "model_created_date": "2025-08-01T00:00:00Z",
  "retrieved_at": "2026-09-03T12:15:08+00:00",
  "path": "app/src/fixtures/data/protein/ATP1B2.json",
  "sha256": "3fa9f8210191981f298519089b511278a6e796a61b4485d33d1f69eebbb4b31e",
  "bytes": 18010,
  "counts": { "residues": 290, "protein_length": 290, "secondary": 36 },
  "fields": { "…": "REAL/SYNTHETIC per top-level field" }
}
```

The `fields` map is the part that cannot be checked by reading the payload: an AlphaFold
coordinate and an invented amino-acid position are both just numbers. It marks `residues`,
`covered`, `secondary`, `model_url` and `version` REAL; `partners` **EMPTY** (phase 2 — an
unfetched thing, not an invented one); and in the gene-structure manifest `candidates`
**SYNTHETIC** for the eight panel genes and **EMPTY** for the other 15, because outside the
panel no annotation was ever run.

### 3 — the endpoint

`GET /api/provenance/reference` reads the manifests off disk and needs **no database**. It
answers **4 rows** today — `hpo`, `structure_genes`, and one per fixture directory — normalised
onto the row shape `ReferenceProvenanceRow`
(`app/src/api/types/provenance.ts`). The two manifest families disagree structurally and
neither was rewritten: `hpo_provenance.json` maps output filename → row count and records
no output digest, so one is computed off disk at read time; this repository's newer tools
write a list carrying the digest measured at build time. The reader states which it got,
because "this is what the file hashes to today" is a weaker claim than "this is what the
build wrote".

A missing directory contributes **no rows rather than a 500** — a checkout whose reference
tables were never built has nothing to declare, and that is a true statement about it, not
a failure. A corrupt manifest is skipped for the same reason: a file that cannot be parsed
vouches for nothing.

### The envelope now names the reply, not just the route

Before, `/api/panel/protein-structure` reported the module's constant — the list of
endpoints it *may* call. Two screenshots of that route built from two AlphaFold model
versions were indistinguishable. Now:

```
source: ensembl rest /lookup/id + /xrefs/id, alphafold db /api/prediction + the model
mmCIF, ressources/data-profile/mva_panel_grch38.bed,
ressources/reference/structure_genes.tsv;
ensembl_release_at_gene_set_build=116, uniprot=P04637,
alphafold_model=https://alphafold.ebi.ac.uk/files/AF-P04637-F1-model_v6.cif,
alphafold_version=6, cache_key=protein-structure-TP53
```

The facts are stored **beside** the payload in the cache entry
(`mva.viz.cache.Built` → a third key in the entry JSON), not inside it, because the client
contract `app/src/api/types/protein.ts` is frozen and its `provenance` field is the string
`"alphafold"`, not a manifest. Storing them beside the payload is what makes a cache
**hit** report the provenance of the reply it is serving — and the hit is the reply a
reader actually screenshots. An entry written before this existed reads back with
`provenance` absent, so no cache directory had to be cleared.

## Gates

```
$ tools/check-python.sh
==> ruff format --check   236 files already formatted
==> ruff check            All checks passed!
==> module size           ok: every module within its limit
==> import layering       Contracts: 3 kept, 0 broken.
==> mypy                  Success: no issues found in 166 source files
==> pytest                1536 passed
python gate: green

$ cd app && pnpm run typecheck
$ tsc -b            # clean
```

Two modules had to be split to stay under the 400-line rule, both by concern rather than
by count: `tools/build_gene_set.py` grew past it, so the manifest's shape moved to
`src/mva/viz/genesetmanifest.py` (the writer) beside `mva.viz.geneset.provenance` (the
reader); `tools/build_protein_fixture.py` likewise, to
`src/mva/viz/fixturemanifest.py`. `src/mva/viz/refprovenance.py` is the third and owns the
*reading* side plus the two primitives both writers need — the file digest and the
current commit — so a digest recorded at build time and one computed later cannot differ
because two call sites chose different chunking.

## Conclusion

1. **The Ensembl release cannot be learnt from a reply.** Only `/info/data` publishes it,
   and no header carries it. Any claim that a route "reports the Ensembl release of this
   reply" is therefore either an extra round trip or a lie; this repository takes the
   third option and reports the release its committed gene set was resolved at, under a
   key that says so.
2. **Both rebuilds were byte-identical** — the TSV (2,569 B) and all 44 fixture files plus
   the index (1,089,060 B). No determinism fix was needed, and every digest in every
   manifest describes a file produced by the same invocation that recorded it.
3. **AlphaFold is at v6 for all 21 proteins**, every model created `2025-08-01`. That is
   one fact the fixtures could not previously state, and the one most likely to change
   underneath them.
4. **Reference data gets a manifest, never a lineage edge.** Four rows exist today and
   `GET /api/provenance/reference` lists them with no database, so the Provenance page can
   show the reference half of the data flow offline.
5. **Still open, deliberately.** `gnomad_constraint.tsv` and `clinvar_panel.tsv` carry
   their provenance as prose in `ressources/reference/README.md` (versioned URLs, literal
   digests) rather than as a manifest, so they do **not** appear in the endpoint's rows.
   They are the honest next candidate: `tools/build_reference_data.py` would have to write
   one, and that is a change to a tool this work did not touch.
6. **Follow-up 060 left open is still open.** The panel BED's notes for SMC5 and CEP192
   are out of date (SMC5 is MVA6, OMIM #620185; CEP192 has PMID 37981762). The manifest's
   `literature` array is extracted from the notes, so it inherits that gap — fixing the
   BED fixes both, and nothing here papers over it.
