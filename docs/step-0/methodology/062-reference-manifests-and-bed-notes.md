# 062 — The last three reference tables get a manifest, and two panel notes get their citations

**Date:** 2026-09-03
**Question:** two follow-ups [061](061-reference-data-provenance.md) left open, and they
turn out to be the same follow-up. (1) `gnomad_constraint.tsv`, `clinvar_panel.tsv` and
`qc_norms.tsv` carried their provenance as *prose in a README* rather than as a manifest,
so `GET /api/provenance/reference` listed four rows and not seven — and the honest
question underneath: can a manifest be written for a file that is already committed, when
the upstream may have moved on, without either regenerating the file or inventing a
digest? (2) The panel BED still called SMC5 and CEP192 "candidate", which is what
[060](060-structure-gene-set.md) flagged and what 061's `literature` array inherited,
because it is extracted from those notes.

_(step-0 platform machinery: this entry records decisions and measurements, not a
hypothesis. Per [`docs/method.md`](../../method.md), step 0 takes no hypotheses.)_

## Inputs

| | |
|---|---|
| Code at build time | `cb066b8` (recorded by every tool as `code_version`) |
| gnomAD constraint | `https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/constraint/gnomad.v4.1.constraint_metrics.tsv` |
| ClinVar GRCh38 VCF | `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz` (+ `.tbi`) |
| Scratch downloads | `build/reference-scratch/`, gitignored, still holding the 2026-08-31 downloads |
| Panel BED, before | `ressources/data-profile/mva_panel_grch38.bed`, 786 B, sha256 `7e81f3ee…` |
| Panel BED, after | same file, **943 B**, sha256 `4873acfed8f4ebc0f027f47b3c5b0b6204c4cb06443d0add7d59f7c204aa2b68` |
| Citation sources | NCBI E-utilities (`efetch` PubMed, `esummary` MedGen and Gene) — OMIM's own site returned `403` |

## Commands run

```bash
# 1 — has either upstream moved on since the committed TSVs?
curl -sIL <gnomad-url> | grep -iE 'content-length|last-modified|etag'
curl -sIL <clinvar-url> | grep -iE 'content-length|last-modified'
curl -s <clinvar-url> | shasum -a 256          # the full 193 MB, streamed, never stored

# 2 — the digests of what is on disk
shasum -a 256 build/reference-scratch/{gnomad.v4.1.constraint_metrics.tsv,clinvar_GRCh38.vcf.gz}
shasum -a 256 ressources/reference/{gnomad_constraint,clinvar_panel,qc_norms}.tsv

# 3 — verify the two citations live
curl -s '.../efetch.fcgi?db=pubmed&id=37981762&rettype=abstract&retmode=text'
curl -s '.../esearch.fcgi?db=medgen&term=620185%5BOMIM%5D&retmode=json'
curl -s '.../esummary.fcgi?db=medgen&id=1824055&retmode=json'
curl -s -A 'Mozilla/5.0' -o /dev/null -w '%{http_code}\n' https://www.omim.org/entry/620185

# 4 — write the three manifests for the COMMITTED tables, regenerating nothing
uv run tools/build_reference_data.py manifests

# 5 — the BED notes, then everything that reads them
uv run python tools/build_gene_set.py --spec ressources/reference/structure_genes.spec.tsv \
  --alias CCDC84=CENATAC
uv run tools/build_reference_data.py manifests      # again: the BED digest changed
uv run python -c "from mva.viz import refprovenance; print(len(refprovenance.rows()))"
tools/check-python.sh --fix
```

## Observed output

### Neither upstream has moved on — and one is now provably the same bytes

The design question was what to do if the server had published a newer release than the
repository holds: write the manifest for the committed file, mark the unknown fields
`null`, and report the newer release as open. **That branch was not needed**, and the
measurement is why:

| Upstream | Measured 2026-09-03 | Verdict |
|---|---|---|
| gnomAD v4.1 | `content-length: 95546041`, `last-modified: Thu, 18 Apr 2024 00:04:32 GMT`, `etag "14df4b2a…"`; scratch copy hashes `68d8abdb7fc48f570869b02dfaa74b9fecaece7fcc5f301ddca40ec1ce12da00` | unchanged, and the digest **matches the one [030](030-population-reference-data.md) recorded** — the URL is versioned, so this is expected and now checked rather than assumed |
| ClinVar GRCh38 | `Content-Length: 193427450`; full streamed re-hash of the live file → `e72f5619f003c80cb3051afcb0c1f11c4409741054b48bbfd0ced03046ec91f9`, **identical** to the scratch copy; `##fileDate=2026-08-29` in both | unchanged. This URL is *not* versioned, so this had to be measured, not reasoned about |

That closes a gap 030 and the reference README both stated: ClinVar "names a release but
does not identify the bytes". It does now. The manifest records
`digest_scope` saying exactly what the digest is a digest *of* — the scratch copy present
at manifest time, not a digest the extract run itself captured — because the honest
statement is weaker than "the extract's input hashed to this".

### The three manifests, as written

`uv run tools/build_reference_data.py manifests`, which regenerates no table:

```
panel   8 genes from ressources/data-profile/mva_panel_grch38.bed
manifest ressources/reference/gnomad_constraint.provenance.json  (describes gnomad_constraint.tsv sha256 7d64f3b4…)
manifest ressources/reference/clinvar_panel.provenance.json      (describes clinvar_panel.tsv sha256 ca7fe098…)
manifest ressources/reference/qc_norms.provenance.json           (describes qc_norms.tsv sha256 9f366524…)
```

| Manifest | Output, as measured | Inputs | Release, and where it came from |
|---|---|---|---|
| `gnomad_constraint` | 3,250,168 B, **18,314 rows**, sha256 `7d64f3b4c508d9eec233c9f490aabc34b4eb48ac20a45666acc44177dee90b5b` | the 95 MB object (digest + bytes), the panel BED | `4.1`, **the versioned path segment** — URL and release cannot disagree |
| `clinvar_panel` | 2,690,034 B, **17,832 rows**, sha256 `ca7fe098852f75517c0c3cf6ae106ba7b21246132e28e16e9867ee36ad9e6a73` | the 193 MB VCF, its `.tbi` (610,396 B), the panel BED | `2026-08-29`, **read from the VCF's own `##fileDate`** — the URL carries no version and the FTP `Last-Modified` describes the mirror |
| `qc_norms` | 13,819 B, **27 rows**, sha256 `9f36652400d808c9bd6d55228c64b30e2030bd99f8926c35092cadce760a3277` | **7 papers**, extracted from the table's own `source`/`url` columns | none — a paper has no release |

Both output byte counts and both row counts match what [030](030-population-reference-data.md)
recorded for the run that produced them, so the manifests describe the same files that
entry measured.

Three decisions inside `mva/viz/referencemanifest.py`, each because the alternative would
have been a fabrication:

1. **A fact is measured or it is `null`.** No digest is read out of a README. The two
   upstreams live in gitignored scratch, so when the copy is absent `sha256` and `bytes`
   are `null` and a `known_gap` field names the missing fact and how to record it. Both
   were present on this run, so both are real.
2. **`qc_norms`' inputs *are* its citations**, extracted from the file — the same rule
   `structure_genes`' `literature` array follows. A hand-kept list beside the table would
   drift, and a drifted citation is worse than none because it looks checked. Each input
   also carries the `metrics` it supplies, so a number can be checked against the right
   paper without opening the table.
3. **`bcftools 1.24 / htslib 1.24` is recorded as `tool`.** A region query is not a pure
   function of the VCF alone; a reader reproducing 17,832 rows needs the binary.

### The route needed no change, and now answers 7 rows

`mva.viz.refprovenance` matches any `*provenance.json` in the reference directory as a
suffix, so both new spellings were picked up with **no code change** — the one thing 061's
design bought that could only be checked by adding a file:

```
rows: 7
 - clinvar_panel      reference  ressources/reference/clinvar_panel.provenance.json       inputs 3  outputs 1
 - gnomad_constraint  reference  ressources/reference/gnomad_constraint.provenance.json   inputs 2  outputs 1
 - hpo                reference  ressources/reference/hpo_provenance.json                 inputs 2  outputs 2
 - qc_norms           reference  ressources/reference/qc_norms.provenance.json            inputs 7  outputs 1
 - structure_genes    reference  ressources/reference/structure_genes.provenance.json     inputs 3  outputs 1
 - protein-structure fixtures  fixture  app/src/fixtures/data/protein/_provenance.json         inputs 3  outputs 21
 - gene-structure fixtures     fixture  app/src/fixtures/data/gene-structure/_provenance.json  inputs 2  outputs 23
```

One thing did have to be fixed: paths. The first run wrote
`/Users/…/checkout/ressources/reference/gnomad_constraint.tsv` into `outputs`, which names
one laptop, and the reader addresses manifests through repository-relative paths.
`repo_relative()` now relativises every recorded path against the working directory and
leaves a path outside the tree alone, since a relative form of that would be a lie about
where the bytes were.

### The two citations, verified live

**OMIM itself could not be read**: `https://www.omim.org/entry/620185` answered **403**
with `<title>Just a moment...</title>` — a Cloudflare interstitial, not a missing entry.
Verification therefore went through NCBI, which mirrors OMIM's names with the OMIM id as
the source key. Both claims check out, and one needs a correction of emphasis:

**SMC5 — confirmed, with a nuance.** MedGen concept `1824055` (`esearch db=medgen
term=620185[OMIM]` returns exactly this one uid), whose `Names` block carries, verbatim:

```xml
<Name SDUI="620185" CODE="620185" SAB="OMIM" TTY="ACR" type="syn">MVA6</Name>
<Name SDUI="620185" CODE="620185" SAB="OMIM" TTY="PT"  type="syn">ATELIS SYNDROME 2</Name>
<Name SDUI="620185" CODE="620185" SAB="OMIM" TTY="ETAL" type="syn">MOSAIC VARIEGATED ANEUPLOIDY SYNDROME 6</Name>
...
<AssociatedGenes><Gene gene_id="23137" chromosome="9" cytogen_loc="9q21.12">SMC5</Gene></AssociatedGenes>
```

So OMIM **620185 is SMC5**, and `MVA6` is real — but as a *synonym*. The **preferred
title is Atelis syndrome 2 (ATELS2)**, and the definition's own words are *"mosaic
variegated **hyperploidy**"*, not aneuploidy:

> "Atelis syndrome-2 (ATELS2) is an autosomal recessive disorder characterized by poor
> overall growth with microcephaly and short stature, dysmorphic facial features, and
> congenital cardiac defects. … Patient cells exhibit a unique chromosomal instability
> phenotype consisting of segmented and dicentric chromosomes with mosaic variegated
> hyperploidy (Grange et al., 2022). … For a discussion of genetic heterogeneity of MVA,
> see MVA1 (257300)."

The paper is **PMID 36333305**, *Nat Commun.* 2022 Nov 4;13(1):6664 — "Pathogenic
variants in SLF2 and SMC5 cause segmented chromosomes and mosaic variegated
hyperploidy", Grange LJ, Reynolds JJ, Ullah F, … Stewart GS. Note that this is the **same
paper** the repository already cites for SLF2 = Atelis syndrome 1 (OMIM 620184): one
paper, two genes, two OMIM entries. So the note says "MVA6 / Atelis syndrome 2" and
"hyperploidy" rather than promoting the synonym to the title.

**CEP192 — confirmed.** `efetch db=pubmed id=37981762` returns, verbatim from the record:

> `HGG Adv. 2024 Jan 11;5(1):100256. doi: 10.1016/j.xhgg.2023.100256. Epub 2023 Nov 19.`
> **"Mosaic variegated aneuploidy syndrome with tetraploid, and predisposition to male
> infertility triggered by mutant CEP192."** Guo J, He WB, Dai L, … Yang Y.

Abstract, quoted: *"the CEP192 biallelic variants (c.1912C>T, p.His638Tyr and c.5750A>G,
p.Asn1917Ser) segregated with microcephaly, short stature, limb-extremity dysplasia, and
reduced testicular size, while CEP192 monoallelic variants segregated with infertility
and/or reduced testicular size"*, with mouse and patient-cell work behind it. **No OMIM
phenotype entry exists**: `esearch db=medgen term=CEP192` returns `count: 0` — zero
disease concepts — so the note says "no OMIM phenotype yet" rather than inventing a
number. Map location from `esummary db=gene`: CEP192 `18p11.21`, SMC5 `9q21.12`,
CENPE `4q24`.

### The BED edit, and everything downstream of it

The note column only. Asserted, not assumed:

```
$ diff bed.before ressources/data-profile/mva_panel_grch38.bed        # 2 lines, both note-only
$ cut -f1-5 bed.before > c.b; cut -f1-5 <after> > c.a; cmp c.b c.a
COLUMNS 1-5 BYTE-IDENTICAL                     # contig, start, end, symbol, ensembl_id
$ diff sg.before ressources/reference/structure_genes.tsv             # 2 lines, both note-only
TSV COLUMNS 1-5 BYTE-IDENTICAL
```

| | before | after |
|---|---|---|
| CEP192 note | `candidate, centrosome` | `biallelic MVA with tetraploidy, male-infertility predisposition; PMID 37981762, no OMIM phenotype yet` |
| SMC5 note | `candidate, chromosome maintenance` | `MVA6 / Atelis syndrome 2 (OMIM 620185), segmented chromosomes and mosaic variegated hyperploidy; PMID 36333305` |

`tools/mva_panel_bed.py` owns those strings in its `PANEL` list, so the generator was
edited too and the BED it would rebuild now matches the committed one string for string
(asserted for all 8 genes). Then everything that reads the BED was re-run, because the
BED's digest is recorded in three manifests:

- **`structure_genes.tsv` rebuilt** against live Ensembl (release **116** again, two
  transient `503`s retried) — 2,569 B → **2,726 B**, sha256 `1124e6c0…` →
  `7461a74cf8a6ce06457bbc50a7f342301ab2e14753b81f0e34089053658605b7`, 23 rows both times,
  every id and biotype unchanged. Its `literature` array went from **7 genes to 9**: SMC5
  and CEP192 now carry their OMIM number and PMID, which is exactly the gap 061 recorded
  as inherited. It closed by fixing the BED, as predicted, with no second citation list
  anywhere.
- **The three reference manifests rewritten**, so the BED input reads 943 B /
  `4873acfe…` in all of them rather than the stale 786 B / `7e81f3ee…`.

## Gates

```
$ tools/check-python.sh
==> ruff format --check
238 files already formatted
==> ruff check
All checks passed!
==> module size
ok: every module within its limit (src: 400, tests: 600, tools: 400); 9 in the warning band.
==> import layering
Analyzed 160 files, 460 dependencies.
Contracts: 3 kept, 0 broken.
==> mypy
Success: no issues found in 167 source files
==> pytest
1562 passed, 1 warning in 24.81s
python gate: green
```

`tests/test_viz_referencemanifest.py` adds **25 tests**, and two of them are gates rather
than unit tests:

- `test_every_committed_reference_table_has_a_manifest` — a new reference table cannot be
  added without declaring where it came from.
- `test_the_committed_manifests_still_describe_the_committed_files` and
  `test_every_input_a_committed_manifest_names_inside_the_tree_still_hashes_the_same` —
  re-digest every output and every `file://` input a committed manifest claims. This is
  the only failure mode a build-time manifest has, and it is what would have caught the
  panel BED going stale in three manifests at once.

## Conclusion

1. **A manifest can be written for an already-committed file without lying**, and the
   mechanism is a subcommand that regenerates nothing (`build_reference_data.py
   manifests`) plus the rule that a fact is measured or `null`. The fallback path —
   `null` fields and a `known_gap` because the upstream moved on — is implemented and
   tested but was **not** needed: both upstreams still serve the bytes the repository
   holds, measured, not assumed.
2. **ClinVar's release now names bytes.** A full re-hash of the live 193 MB stream equals
   the scratch copy, `e72f5619…`. The gap 030 stated is closed *in the manifest*.
3. **`GET /api/provenance/reference` answers 7 rows and needed no code change** —
   the suffix match in `refprovenance` was the right seam.
4. **Both panel notes verified against primary records, and one was sharpened.** SMC5's
   OMIM 620185 is titled *Atelis syndrome 2*, with `MVA6` as an OMIM synonym and the
   phenotype worded *hyperploidy*; writing plain "MVA6" would have been true but would
   have hidden that. CEP192 has one published biallelic family and **no** OMIM phenotype
   entry, so the note says so. OMIM's own site is unreadable from a script (403), which
   is why the verification path is NCBI and is recorded as such.
5. **Still open, deliberately.**
   - The *warehouse lineage row* for `clinvar_panel` still has an empty `source_sha256`.
     The digest now exists in the manifest; copying it into `warehouse/reference.py` is a
     warehouse change this entry did not make.
   - `app/src/fixtures/data/provenance-reference.json` is stale: it was transcribed from
     a 4-row reply and the route now returns **7**. `panel-structure-genes.json` is stale
     too, by the two note strings. Both are app-owned files.
   - `figures/explore-report.html` still renders the old "candidate, centrosome" /
     "candidate, chromosome maintenance" hover text. It is a generated artifact of a
     warehouse run, and regenerating it needs the patient callset, not this change.
   - `qc_norms.tsv` remains hand-curated with no generator. Its manifest states that as a
     `known_gap` rather than implying a build.
