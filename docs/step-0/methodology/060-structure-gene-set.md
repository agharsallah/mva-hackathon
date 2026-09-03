# 060 — A curated gene set for the structure explorer, and one real fold per gene

**A step-0 platform entry, so it carries no hypothesis.** It records the live Ensembl
replies that were read before any code was written, the two assumptions those replies
**refuted**, which genes are protein-coding, the byte cost of every generated fixture, and
the gates.

## Question

Entries [040](040-locus-gene-track.md) and [056](056-protein-structure-endpoint.md) built
the exon track and the folded-protein exhibit against the eight-gene panel BED. Both routes
resolved a symbol through `genestructure.panel_gene`, which reads that BED and raises
`LookupError` for anything else. So the explorer could show exactly eight genes — and the
BED is the right authority for *"which genes was this callset annotated against"*, because
those intervals are literally what VEP ran over.

It is the wrong authority for a different question the exhibit now has to answer: **which
genes may I draw a fold for?** A reader who wants to know whether BUBR1's kinase domain
looks like BUB1's needs BUB1 on screen, and BUB1 carries no patient allele at all. Same for
the other MVA-numbered genes discovered since the panel was drawn.

Three sub-questions, each of which could have been guessed wrong:

1. Can a *case-agnostic* tool resolve an arbitrary symbol list against Ensembl and produce a
   committed table — including the fact that decides everything downstream, **does the
   canonical transcript translate**?
2. What happens to the two structure routes when the gene is off-panel (no annotation was
   ever run) or non-coding (there is no protein to fold)? Both must be *stated*, not faked
   and not turned into a 502 the reader will retry forever.
3. Can the offline fixtures stop lying? The committed fixture handed **every** gene BUB1B's
   backbone with its own name on it. Invisible with one gene on screen; a visible falsehood
   the moment two are compared.

## Inputs

| Input | Shape as read |
|---|---|
| `ressources/reference/structure_genes.spec.tsv` | new; 23 rows of `symbol / group / note`, hand-maintained |
| `ressources/data-profile/mva_panel_grch38.bed` | 8 genes with stable ids and notes; the assertion target, and the source of the panel notes |
| `https://rest.ensembl.org/lookup/symbol/homo_sapiens/{symbol}?expand=1` | live, keyless; **new to this entry** |
| `https://rest.ensembl.org/xrefs/symbol/homo_sapiens/{symbol}` | live, keyless; **new to this entry** |
| `https://rest.ensembl.org/lookup/id/{ENSG}?expand=1` | live; reused from 040 via `genestructure.anatomy` |
| `https://rest.ensembl.org/overlap/translation/{ENSP}` | live; reused from 040 |
| `https://alphafold.ebi.ac.uk/api/prediction/{accession}` + the model mmCIF | live; reused from 056 via `proteinstructure.structure` |
| Contract | `app/src/api/types/protein.ts` (`StructureGene`) and `app/src/api/types/panel.ts` (`GeneStructure.in_panel`) — both **frozen before the build** and implemented field for field |
| Code | `tools/build_gene_set.py`, `tools/build_protein_fixture.py`, `src/mva/viz/geneset.py`, edits to `genestructure.py` / `proteinstructure.py` / `routes_panel.py` |

The gene list is the eight annotated panel genes, plus five genes with a documented
MVA / spindle-assembly-checkpoint link, plus ten requested for comparison. The two group
boundaries were **not** taken from `ideation/hackathon-intel.md` §3, which lists only
MVA1–MVA3 plus CEP192 / SMC5 / CENPE as candidates; the rest were checked against OMIM and
PubMed before a note was written (see *Probe 3*).

## Probe 1 — does `/lookup/symbol` resolve a retired gene symbol?

**No.** This was the first version of the tool's assumption, and it is wrong:

```
$ curl -s -H 'Accept: application/json' \
    'https://rest.ensembl.org/lookup/symbol/homo_sapiens/CCDC84?expand=1'
{"error":"No valid lookup found for symbol CCDC84"}     # HTTP 400
```

`CCDC84` is HGNC's own **previous symbol** for `CENATAC` (HGNC:30460, renamed 2020-06-08).
`/lookup/symbol` searches display names only. The endpoint that searches cross-references
does resolve it, and answers with a **list**:

```
$ curl -s -H 'Accept: application/json' \
    'https://rest.ensembl.org/xrefs/symbol/homo_sapiens/CCDC84'
[{"type":"gene","id":"ENSG00000186166"},{"type":"gene","id":"ENSG00000280975"}]
```

Two ids, so "exactly one match" would have been the wrong test and would have *refused* a
correct alias. Both are CENATAC — the second is the same gene on an alternate patch
scaffold:

```
$ curl -s .../lookup/id/ENSG00000280975
{"biotype":"protein_coding","seq_region_name":"HG2217_PATCH","display_name":"CENATAC",
 "description":"centrosomal AT-AC splicing factor [Source:HGNC Symbol;Acc:HGNC:30460]", …}
```

**Consequence in code.** `check_alias` tests *membership* of the primary symbol's id in the
xref list, and the tool run prints the verdict rather than the code asserting it silently:

```
alias CCDC84 → CENATAC: CONFIRMED — /xrefs/symbol/CCDC84 matches
['ENSG00000186166', 'ENSG00000280975']; /lookup/symbol/CENATAC is ENSG00000186166
```

`mva.viz.geneset.ALIASES` therefore has exactly one entry, and a test asserts that an
*unverified* alias (`p31comet` for MAD2L1BP, real in the literature, resolved by no
database) is **not** accepted. An alias nobody checked is a silent way to draw the wrong
protein.

## Probe 2 — is `coding` the same as `biotype == "protein_coding"`?

Not reliably, which is why the tool records both and derives `coding` from the transcript.
`/lookup/symbol/…?expand=1` returns every transcript; the canonical one is matched on the
unversioned id (the same rule `genestructure.pick_transcript` already applies, reused
deliberately so the flag cannot disagree with what the live route finds), and `coding` is
*"that transcript object carries a `Translation`"*.

The distinction is not hypothetical: BUB1B's own transcript list includes
`ENST00000560120` with biotype `protein_coding_CDS_not_defined` and no `Translation`. A gene
whose canonical transcript looked like that would be labelled protein-coding by biotype and
still have no protein to fold — and the exhibit would 502 rather than say *no protein*.

## Probe 3 — which of these genes actually has a documented MVA link?

Checked against OMIM entries and PubMed abstracts before any note was written, because
"MVA gene" is exactly the kind of claim an aggregator site will hand you for free:

| Gene | Verdict | Source |
|---|---|---|
| CENATAC | **MVA4**, OMIM #620153 (gene *620142); minor-spliceosome defect | PMID 34009673 |
| MAD1L1 | **MVA7**, OMIM #620189; SAC loss with inflammation and tumour predisposition | PMID 36322655 |
| SLF2 | **Atelis syndrome 1**, OMIM #620184 — OMIM files *"mosaic variegated aneuploidy syndrome 5"* as a synonym. Sister gene **SMC5** is ATELS2 / MVA6, OMIM #620185 | PMID 36333305 |
| MAD2L1BP | biallelic MVA + juvenile granulosa cell tumour, **literature only** — no OMIM phenotype number, no MedGen entry | PMID 37796616 |
| BUB1 | **not** an MVA-numbered entry. The only assigned phenotype is MCPH30 (primary microcephaly 30), OMIM #620183; patient cells are aneuploid, but neither the paper nor OMIM calls it MVA | PMID 35044816 |

The full OMIM MVA series as verified: MVA1 BUB1B #257300 · MVA2 CEP57 #614114 · MVA3 TRIP13
#617598 · MVA4 CENATAC #620153 · MVA5 SLF2 #620184 · MVA6 SMC5 #620185 · MVA7 MAD1L1
#620189. **This supersedes nothing in
[`ideation/hackathon-intel.md`](../../../ideation/hackathon-intel.md) §3 but does extend
it**: the brief's table stops at MVA3 and files CEP192 / SMC5 / CENPE as "candidate /
atypical". SMC5 in fact has an OMIM MVA number (#620185) and CEP192 has a published
MVA-with-tetraploidy report (PMID 37981762). The panel BED's notes for those two still read
"candidate, chromosome maintenance" and "candidate, centrosome"; they were left unedited
here because the BED is the single owner of that column and this entry is not the place to
change the annotated panel's provenance line. **Recorded as an open follow-up.**

None of the ten `extended` genes has a documented MVA link, and two of them carry an
aggregator tag that would poison an automated gene–disease table:

* **PAK6** — GeneCards/MalaCards lists "Mosaic Variegated Aneuploidy Syndrome 1". It is
  positional: PAK6 is `chr15:40,217,428-40,277,489` and BUB1B is
  `chr15:40,160,984-40,221,137` — they **overlap**. No PAK6 variant report exists.
* **FAM76B** — MalaCards lists "Mosaic Variegated Aneuploidy Syndrome" with no primary
  source. FAM76B is at chr11:95.77 Mb, adjacent to MTMR2, and nowhere near CENATAC at
  chr11:119.0 Mb.

Both notes in the TSV say so explicitly. Three genes have a *different* Mendelian disease
(MTMR2 → CMT4B1 #601382; WRAP53 → DKCB3 #613988) or only a functional mitotic role
(SEH1L, in the Nup107-160 kinetochore complex); the rest carry
`user-requested; no documented MVA link found`.

## Command 1 — build the table

```
$ uv run python tools/build_gene_set.py \
    --spec ressources/reference/structure_genes.spec.tsv --alias CCDC84=CENATAC
```

Live reply facts, one line per gene, verbatim from the run (trimmed to the fields the tool
records):

```
resolving 23 symbols against https://rest.ensembl.org
  CEP57        ENSG00000166037  protein_coding   canonical=ENST00000325542 protein=ENSP00000317902  chr11:95789965-95837070   strand=1
  DICER1       ENSG00000100697  protein_coding   canonical=ENST00000343455 protein=ENSP00000343745  chr14:95086228-95158010   strand=-1
  BUB1B        ENSG00000156970  protein_coding   canonical=ENST00000287598 protein=ENSP00000287598  chr15:40160984-40221137   strand=1
  TP53         ENSG00000141510  protein_coding   canonical=ENST00000269305 protein=ENSP00000269305  chr17:7661779-7687546     strand=-1
  CEP192       ENSG00000101639  protein_coding   canonical=ENST00000506447 protein=ENSP00000427550  chr18:12991283-13125053   strand=1
  CENPE        ENSG00000138778  protein_coding   canonical=ENST00000265148 protein=ENSP00000265148  chr4:103105349-103198463  strand=-1
  TRIP13       ENSG00000071539  protein_coding   canonical=ENST00000166345 protein=ENSP00000166345  chr5:892849-919357        strand=1
  SMC5         ENSG00000198887  protein_coding   canonical=ENST00000361138 protein=ENSP00000354957  chr9:70258270-70354874    strand=1
  CENATAC      ENSG00000186166  protein_coding   canonical=ENST00000334418 protein=ENSP00000334767  chr11:118998051-119015811 strand=1
  MAD1L1       ENSG00000002822  protein_coding   canonical=ENST00000265854 protein=ENSP00000265854  chr7:1815787-2233243      strand=-1
  SLF2         ENSG00000119906  protein_coding   canonical=ENST00000238961 protein=ENSP00000238961  chr10:100912963-100965134 strand=1
  MAD2L1BP     ENSG00000124688  protein_coding   canonical=ENST00000372171 protein=ENSP00000361244  chr6:43629494-43640960    strand=1
  BUB1         ENSG00000169679  protein_coding   canonical=ENST00000302759 protein=ENSP00000302530  chr2:110635468-110678098  strand=-1
  PAK6         ENSG00000137843  protein_coding   canonical=ENST00000560346 protein=ENSP00000453858  chr15:40217428-40277489   strand=1
  MTMR2        ENSG00000087053  protein_coding   canonical=ENST00000346299 protein=ENSP00000345752  chr11:95821766-95925315   strand=-1
  WRAP53       ENSG00000141499  protein_coding   canonical=ENST00000396463 protein=ENSP00000379727  chr17:7686071-7703505     strand=1
  SEH1L        ENSG00000085415  protein_coding   canonical=ENST00000399892 protein=ENSP00000382779  chr18:12947133-12987713   strand=1
  BRD9         ENSG00000028310  protein_coding   canonical=ENST00000467963 protein=ENSP00000419765  chr5:850291-892838        strand=-1
  ATP1B2       ENSG00000129244  protein_coding   canonical=ENST00000250111 protein=ENSP00000250111  chr17:7646627-7657771     strand=1
  BDH2         ENSG00000164039  protein_coding   canonical=ENST00000296424 protein=ENSP00000296424  chr4:103077592-103099885  strand=-1
  FAM76B       ENSG00000077458  protein_coding   canonical=ENST00000358780 protein=ENSP00000351631  chr11:95768953-95790409   strand=-1
  DICER1-AS1   ENSG00000235706  lncRNA           canonical=ENST00000671073 protein=—               chr14:95157645-95181475   strand=1
  MAMDC2-AS1   ENSG00000204706  lncRNA           canonical=ENST00000715771 protein=—               chr9:70010139-70258924    strand=-1
  alias CCDC84 → CENATAC: CONFIRMED — /xrefs/symbol/CCDC84 matches ['ENSG00000186166', 'ENSG00000280975']; /lookup/symbol/CENATAC is ENSG00000186166

21 of 23 genes have a translating canonical transcript
non-coding: ['DICER1-AS1', 'MAMDC2-AS1']
ressources/reference/structure_genes.tsv — 2,569 bytes, 23 rows
```

**The panel assertion held.** All eight `panel` rows' resolved ids equal the BED's; the tool
exits 1 and writes nothing if any differ, because the BED's id is the one the callset was
annotated against and a moved id would place the proband's alleles on a record they were
never called against. (Note the BED's *coordinates* differ from Ensembl's by design — the
BED carries 20,000 bp of padding — so only the id is compared.)

**Genuinely two non-coding genes**, both `lncRNA`, both confirmed by the absence of a
`Translation` on the canonical transcript rather than by their names.

**One live fact about Ensembl's availability, recorded because it changed the code.**
Ensembl REST answered `503 Service Unavailable` and `500` intermittently throughout this
session — `/lookup/symbol/…/BRD9`, `/overlap/translation/ENSP00000317902` and
`/xrefs/id/ENSP00000317902` each failed once and succeeded moments later. The *routes* still
never retry (`genestructure._call` explains why: a request-scoped fetch behind a disk cache
recovers more cheaply by the reader pressing refresh). Both **build tools** now retry with a
bounded backoff, and `build_protein_fixture.py` skips a gene whose files already exist, so a
23-gene / ~70-call batch is not thrown away by one transient 503. That asymmetry is
deliberate and commented at both sites.

## Command 2 — build one real fixture per gene

```
$ uv run python tools/build_protein_fixture.py
```

Two files per gene under `app/src/fixtures/data/`, plus the index. **Every column below
except `cand.` is measured**: `exons` and `domains` are Ensembl's own, `ENSP / UniProt` and
`residues modelled` come from the live AlphaFold model that was parsed. `cand.` is the
synthetic allele count — three for a panel gene, zero for everything else.

| Gene | Ensembl gene | Group | biotype | coding | `gene-structure/` | exons | domains | cand. | `protein/` | ENSP / UniProt | residues modelled |
|---|---|---|---|:--:|---:|---:|---:|---:|---:|---|---|
| CEP57 | `ENSG00000166037` | `panel` | `protein_coding` | true | 2,031 B | 11 | 3 | 3 | 29,586 B | ENSP00000317902 / Q86XR8 | 500 of 500 |
| DICER1 | `ENSG00000100697` | `panel` | `protein_coding` | true | 8,312 B | 27 | 42 | 3 | 108,471 B | ENSP00000343745 / Q9UPY3 | 1922 of 1922 |
| BUB1B | `ENSG00000156970` | `panel` | `protein_coding` | true | 3,312 B | 23 | 7 | 3 | 57,959 B | ENSP00000287598 / O60566 | 1050 of 1050 |
| TP53 | `ENSG00000141510` | `panel` | `protein_coding` | true | 3,945 B | 11 | 17 | 3 | 23,625 B | ENSP00000269305 / P04637 | 393 of 393 |
| CEP192 | `ENSG00000101639` | `panel` | `protein_coding` | true | 5,600 B | 45 | 14 | 3 | 141,962 B | ENSP00000427550 / Q8TEP8 | 2537 of 2537 |
| CENPE | `ENSG00000138778` | `panel` | `protein_coding` | true | 5,699 B | 49 | 12 | 3 | 142,056 B | ENSP00000265148 / Q02224 | 2580 of 2701 |
| TRIP13 | `ENSG00000071539` | `panel` | `protein_coding` | true | 2,975 B | 13 | 10 | 3 | 26,221 B | ENSP00000166345 / Q15645 | 432 of 432 |
| SMC5 | `ENSG00000198887` | `panel` | `protein_coding` | true | 3,140 B | 25 | 4 | 3 | 61,291 B | ENSP00000354957 / Q8IY18 | 1101 of 1101 |
| CENATAC | `ENSG00000186166` | `mva-sac` | `protein_coding` | true | 1,097 B | 11 | 1 | 0 | 19,929 B | ENSP00000334767 / Q86UT8 | 332 of 332 |
| MAD1L1 | `ENSG00000002822` | `mva-sac` | `protein_coding` | true | 2,046 B | 19 | 5 | 0 | 42,486 B | ENSP00000265854 / Q9Y6D9 | 718 of 718 |
| SLF2 | `ENSG00000119906` | `mva-sac` | `protein_coding` | true | 1,733 B | 20 | 1 | 0 | 64,145 B | ENSP00000238961 / Q8IX21 | 1173 of 1173 |
| MAD2L1BP | `ENSG00000124688` | `mva-sac` | `protein_coding` | true | 740 B | 3 | 2 | 0 | 16,430 B | ENSP00000361244 / Q15013 | 274 of 274 |
| BUB1 | `ENSG00000169679` | `mva-sac` | `protein_coding` | true | 3,602 B | 25 | 13 | 0 | 59,653 B | ENSP00000302530 / O43683 | 1085 of 1085 |
| PAK6 | `ENSG00000137843` | `extended` | `protein_coding` | true | 2,536 B | 11 | 12 | 0 | 40,837 B | ENSP00000453858 / Q9NQU5 | 681 of 681 |
| MTMR2 | `ENSG00000087053` | `extended` | `protein_coding` | true | 2,672 B | 15 | 11 | 0 | 38,758 B | ENSP00000345752 / Q13614 | 643 of 643 |
| WRAP53 | `ENSG00000141499` | `extended` | `protein_coding` | true | 2,507 B | 11 | 13 | 0 | 33,568 B | ENSP00000379727 / Q9BUR4 | 548 of 548 |
| SEH1L | `ENSG00000085415` | `extended` | `protein_coding` | true | 3,019 B | 9 | 18 | 0 | 25,545 B | ENSP00000382779 / Q96EE3 | 421 of 421 |
| BRD9 | `ENSG00000028310` | `extended` | `protein_coding` | true | 2,419 B | 16 | 10 | 0 | 35,254 B | ENSP00000419765 / Q9H8M2 | 597 of 597 |
| ATP1B2 | `ENSG00000129244` | `extended` | `protein_coding` | true | 1,436 B | 7 | 5 | 0 | 18,010 B | ENSP00000250111 / P14415 | 290 of 290 |
| BDH2 | `ENSG00000164039` | `extended` | `protein_coding` | true | 2,848 B | 10 | 14 | 0 | 14,840 B | ENSP00000296424 / Q9BUT1 | 245 of 245 |
| FAM76B | `ENSG00000077458` | `extended` | `protein_coding` | true | 1,011 B | 10 | 1 | 0 | 20,266 B | ENSP00000351631 / Q5HYJ3 | 339 of 339 |
| DICER1-AS1 | `ENSG00000235706` | `extended` | `lncRNA` | false | 378 B | 2 | 0 | 0 | — | — | **no protein** |
| MAMDC2-AS1 | `ENSG00000204706` | `extended` | `lncRNA` | false | 630 B | 6 | 0 | 0 | — | — | **no protein** |
| **23 genes** | | | **21** `protein_coding`, **2** `lncRNA` | **21** | **63,688 B** | 379 | 215 | 24 | **1,020,892 B** | | |

`gene-structure/` **63,688 B** · `protein/` **1,020,892 B** · `panel-structure-genes.json`
**4,480 B** · **total 1,089,060 B (1063.5 kB)**, across 379 real exons, 215 real domains and
24 synthetic alleles.

**Size discipline.** Files over ~60 kB are re-rounded to 0.1 Å coordinates and whole-number
pLDDT (`compact()`), both far below the prediction's own uncertainty; that is a
*fixture-only* transformation, the live route keeps the parser's two decimals. It buys ~8 %,
measured (CENPE 150.6 → 138.7 kB), which is small because the parser already rounds to two
decimals — the honest saving is the per-gene split, not the rounding. **Three genes exceed
100 kB** (CEP192, CENPE, DICER1: 2,537 / 2,580 / 1,922 residues). They are kept at full
per-residue fidelity rather than decimated, because a trace with residues *removed* would
draw a fold that is subtly not the protein — and each is a **separate lazy chunk**, so a
reader who never opens CENPE never downloads it.

**Prettier does not format them.** `app/.prettierignore` now excludes the two directories
and the index, with the reason recorded there: Prettier writes one key per line, which
inflated the set from 1,089,060 B to **1,282,421 B (+17.8 %, measured)** and turns every
regeneration into a several-thousand-line diff. The generating tool owns the formatting,
the same way pnpm owns its lockfile.

**One non-coding gene is proof the branch is real**: `DICER1-AS1.json` is **378 B** — two
real exons, `protein: null`, `domains: []`, `candidates: []` — and there is no
`protein/DICER1-AS1.json` at all.

The old single-file fixtures `panel-gene-structure.json` (BUB1B-*shaped* synthetic
coordinates) and `panel-protein-structure.json` (BUB1B's real trace, handed to every gene
with a new name on it) are **deleted**. Nothing reads them.

## What the routes do now

| Case | `/panel/gene-structure` | `/panel/protein-structure` |
|---|---|---|
| panel gene | 200, `in_panel: true`, the proband's protein-altering alleles | 200, the fold |
| off-panel coding gene | 200, `in_panel: false`, `candidates: []` — **and the warehouse is not read at all**: no `panel_candidates` query, no VEP POST, so no patient coordinate leaves the process | 200, the fold |
| non-coding gene | 200, real exons, `protein: null`, `domains: []` | **422** `"<GENE> has no protein-coding canonical transcript"` |
| symbol in neither source | **404** naming both sources | **404** |

The 422 is the load-bearing choice. `NoProteinError` is deliberately **not** a
`ProteinModelError`: that class means *an upstream failed* and maps to 502, "come back
later". A lncRNA having no translation is not a failure and will never resolve, so 422
("this request cannot be answered for this gene") is the only status that tells the client
to stop asking. A test asserts `NoProteinError` is not in `UPSTREAM_ERRORS`, because the
route's `except` order is the only thing keeping the 422 from being swallowed by the 502.

`in_panel` is **derived from the BED at read time**, not stored as a seventh TSV column. Two
files that both claim to say what is in the panel can disagree; one cannot — and `in_panel`
is the flag that decides whether the proband's alleles exist for a gene.

`genestructure.structure` was split: `anatomy()` is the half that reads nothing but public
reference APIs (two GETs, no warehouse, no VEP), and `structure()` adds candidates on top.
That split is what lets an off-panel gene reach the exhibit *and* what lets the fixture
builder run on a bare checkout with no database.

## Perimeter

Everything generated here is **public reference data**. The gene set is symbols, stable ids
and biotypes. `gene-structure/<SYMBOL>.json` is Ensembl's own exon boundaries and Pfam /
SMART / PROSITE / Gene3D / SUPERFAMILY / CDD calls. `protein/<SYMBOL>.json` is an AlphaFold
model, identical for every human.

The one synthetic part is `candidates`, three invented alleles per **panel** gene, scaled to
that protein's length, every `rsid` written `rs00000000n` — not a real dbSNP accession. They
exist precisely *because* the proband's alleles are never committed. The shape module
docstring, the registry `source` line and the app's `fixture:` badge all say so.

`in_panel` is the only field that touches the proband, and it is a boolean about *which
genes were annotated*, never an allele. No genomic position of the proband appears in any
file this entry produced.

## Gates

```
$ tools/check-python.sh
==> ruff format --check
==> ruff check            All checks passed!
==> module size
==> import layering       3 contracts kept, 0 broken
==> mypy                  Success: no issues found in 163 source files
==> pytest                1501 passed, 1 warning in 29.65s
python gate: green
```

`==> module size` was **not** green at first: `genestructure.py` reached **406 lines**
against the project's 400 limit once `anatomy` was split out. Resolved by splitting rather
than by raising the limit, per CLAUDE.md — the Ensembl call layer moved to a new
`src/mva/viz/ensembl.py` (a bounded concern: *how this service talks to Ensembl, and what
it does when Ensembl says no*, shared by three callers), leaving `genestructure.py` at
**375**. `ENSEMBL_BASE` / `EnsemblError` are re-exported from their old home so 20 existing
call sites and tests did not churn.

Three existing tests changed behaviour deliberately, and each says why inline:

* `test_the_payload_carries_the_contract_s_fields` — `in_panel` joined the contract.
* `test_a_transcript_without_a_translation_is_a_stated_failure` — now expects
  `NoProteinError`, not `ProteinModelError`. That *is* the 502→422 change.
* `test_every_reference_file_is_declared` — gained a named `NOT_STAGED` exclusion for the
  two new TSVs, which `mva.viz.geneset` reads directly rather than staging into the
  warehouse. Named, not pattern-matched, so a genuinely undeclared reference table still
  fails the guard.

`tests/test_viz_geneset.py` adds **24 tests** over a four-row stand-in TSV in `tmp_path`
(never the committed one, so a later edit to the gene set cannot silently change what they
assert). The load-bearing ones: the warehouse must not be read for an off-panel gene
(asserted by making `queries.access.fetch` raise), the domain endpoint must not be called
for a gene with no translation, and `NoProteinError` must not be in `UPSTREAM_ERRORS`.

App side: `pnpm run typecheck` clean, `pnpm run lint` clean for this WP's files,
`pnpm run test` **329 tests, 20 files, all passing** — including
`src/test/fixtures.test.ts`'s 73 hash assertions over the regenerated payloads:

```
"/api/panel/structure-genes":            "7b439c53fa74a448"
"/api/panel/gene-structure":             "3e2e34d89de6d66d"
"/api/panel/gene-structure?gene=TP53":   "7db06a06b9b693ce"
"/api/panel/gene-structure?gene=CEP57":  "f7135ad7422d809a"
"/api/panel/gene-structure?gene=DICER1": "94edf6a64935700e"
"/api/panel/protein-structure":            "a827768cd79d8878"
"/api/panel/protein-structure?gene=TP53":  "f2ee41c03a9f703f"
"/api/panel/protein-structure?gene=CEP57": "60ee9d14f9bec173"
"/api/panel/protein-structure?gene=DICER1":"c329db369a75bd88"
```

## Conclusion

- **Yes to all three.** A case-agnostic symbol resolver produces a committed 23-row table
  whose every id, biotype and `coding` flag came from a live reply; the panel eight are
  asserted identical to the BED's.
- **Two assumptions were refuted by the replies rather than by review**: `/lookup/symbol`
  does not resolve a retired symbol at all, and `/xrefs/symbol` answers with a list whose
  length is not 1 even for an unambiguous alias. Either one, guessed, would have produced a
  confidently wrong gene.
- **The off-panel and non-coding branches are stated, not faked.** An off-panel gene reads
  no warehouse table (asserted by a test that makes `queries.access.fetch` raise), and a
  non-coding gene gets a 422 that says *never*, not a 502 that says *later*.
- **The fixtures stopped lying.** Every coding gene now carries its own measured AlphaFold
  trace and its own measured exon/domain track, so two genes side by side are two different
  shapes. The old single-file fixture's "same backbone, new name" compromise is gone.
- **Open follow-up, not fixed here:** the panel BED's notes for SMC5 and CEP192 read
  "candidate", but SMC5 has an OMIM MVA number (#620185) and CEP192 has a published
  MVA-with-tetraploidy report (PMID 37981762). The BED owns that column; updating it is a
  separate change to the annotated panel's provenance.
