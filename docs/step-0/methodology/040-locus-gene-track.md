# 040 — The gene track and the protein-domain lollipop

**A step-0 platform entry, so it carries no hypothesis.** It records what was probed, what
was built, the latencies measured, and the one thing that turned out to be *not* derivable
from what the warehouse stores.

## Question

The locus explorer plots the proband's records inside a candidate gene against a bare
number line. A number line cannot answer the question a reviewer asks next: **is this
record in a part of the gene that reaches the protein, and if so, does it hit a part of
the protein that does something?**

Two things were missing and neither is in the warehouse:

1. **Gene structure** — exons (the stretches kept in the mature transcript), introns (the
   stretches spliced out), and the strand (the direction the gene is read).
2. **Protein domains** — the semi-independent functional units of the folded protein, and
   where each protein-altering allele lands relative to them.

Can Ensembl REST supply both from the server side, and can our own alleles be placed in
amino-acid space at all?

## Inputs

| Input | Shape as read |
|---|---|
| `ressources/data-profile/mva_panel_grch38.bed` | 8 genes, each with its stable Ensembl gene id in column 5 |
| `pg.warehouse.panel_annotations` | 13 columns: chrom, pos, ref, alt, rsid, gene, consequence, impact, gnomad_af, gnomad_af_grpmax, clin_sig, annotated_at, source |
| `pg.results.panel_candidates` | the above joined to the callset's genotype evidence |
| `https://rest.ensembl.org` | live, GRCh38 by default (established in entry 031) |
| Code | `src/mva/viz/genestructure.py`, route in `src/mva/viz/routes_warehouse.py` |

## The blocker, established first

`warehouse.panel_annotations` is the only place a VEP answer is stored, and its schema
(`src/mva/warehouse/annotate.py:ensure_table`) has **no protein-position column**. The
annotation run kept gene, consequence, impact, frequency and clinical significance —
nothing that says *which amino acid*. So a lollipop of our own alleles is **not derivable
from stored data**. Two ways out were available:

* re-derive the codon offset locally from the transcript's exon bounds and CDS start, or
* ask VEP once more, for the handful of protein-altering alleles in one gene.

The second was chosen. The first is a second, untested implementation of VEP's reading
frame — including the UTR boundary, the phase of a split codon, and indel shifting — and
a lollipop drawn one codon off is worse than none. The extra call is small and bounded:
the largest panel gene has 6 protein-altering alleles, one POST, behind the same disk
cache as everything else.

## Endpoints probed, live, before any code

```bash
curl -s 'https://rest.ensembl.org/lookup/symbol/homo_sapiens/BUB1B?expand=1;content-type=application/json'
curl -s 'https://rest.ensembl.org/lookup/id/ENSG00000156970?expand=1;content-type=application/json'
curl -s 'https://rest.ensembl.org/lookup/id/ENSG00000141510?expand=1;content-type=application/json'   # minus strand
curl -s 'https://rest.ensembl.org/overlap/translation/ENSP00000287598?content-type=application/json'
curl -s -X POST 'https://rest.ensembl.org/vep/homo_sapiens/region' \
     -H 'Content-Type: application/json' -H 'Accept: application/json' \
     -d '{"variants":["15 40161230 . G A . . .","15 40194393 . C T . . ."],"canonical":1}'
```

Four facts came back that the code depends on, none of them assumed:

| Probed | Observed |
|---|---|
| `lookup/id?expand=1` transcript pointer | `canonical_transcript` is **versioned** (`ENST…598.11`); the transcript objects' `id` is not — the match has to drop the suffix |
| exon order | returned in **transcript** order: descending coordinates on the minus strand (checked on TP53). The code re-sorts anyway, so the numbering survives a change |
| `overlap/translation` contents | **28 features for one protein, only 4 of them domains.** Type histogram: `sifts` 12, `Seg` 4, `Gene3D` 2, `MobiDBLite` 2, `PANTHER` 1, `Smart` 1, `ncoils` 1, `Pfam` 1, `SuperFamily` 1, `alphafold` 1, `CDD` 1, `Prosite_profiles` 1 |
| `vep/…/region` protein position | `transcript_consequences[].protein_start` **is present** for a coding SNV and **absent** for an intronic one — exactly the null the contract needs |

The overlap histogram is why an allowlist exists rather than a denylist: PDB
cross-references (`sifts`), an AlphaFold model, low-complexity (`Seg`), disorder
(`MobiDBLite`) and coiled-coil (`ncoils`) predictions are not domains. `PANTHER` is
excluded too — it is a whole-protein *family* assignment spanning 21–1036 of 1050 aa,
which as a bar would read "the entire protein is one domain".

## What was built

`GET /api/panel/gene-structure?gene=…&refresh=` — three Ensembl calls behind the existing
disk cache, because gene structure is static reference data:

```
/lookup/id/<ENSG>?expand=1      → gene bounds, strand, canonical transcript, exons, translation
/overlap/translation/<ENSP>     → domain features, filtered to the allowlist
POST /vep/homo_sapiens/region   → protein_start for the gene's protein-altering alleles
```

Gene validation is against the committed panel BED, not the warehouse copy: the BED is the
panel's source of truth *and* the only place the stable gene id survives staging. Unknown
gene → 404. Ensembl unreachable or refusing → **502 with the upstream detail**; there is no
fallback shape, because an invented gene structure is worse than a missing one.

Two contract decisions worth recording:

* **The payload carries no patient genomic coordinate.** Candidates are `{consequence,
  impact, rsid, rare, protein_pos, reason, label}`. Unlike `/api/panel/locus`, this cache
  entry holds nothing that could not be published.
* **`is_protein_altering`, not "rare *and* protein-altering".** Measured first:

  | gene | protein-altering | rare | both |
  |---|---|---|---|
  | BUB1B | 2 | 4 | **2** |
  | CENPE | 2 | 3 | 0 |
  | CEP192 | 6 | 2 | 0 |
  | CEP57 | 0 | 2 | 0 |
  | DICER1 | 0 | 1 | 0 |
  | SMC5 | 1 | 7 | 0 |
  | TP53 | 2 | 2 | 0 |
  | TRIP13 | 0 | 3 | 0 |

  The stricter filter would hand seven of eight genes an empty exhibit. Rarity is kept as
  a `rare` flag and drawn as a hollow lollipop head instead of deciding for the reader.

## Live check

Own instance on port 8944 (not the shared 8900), against the live warehouse and live
Ensembl, cache pointed at a scratch directory:

```bash
MVA_VIZ_CACHE=build/viz-cache-8944 uv run mva-viz-api --port 8944
curl -s -w '%{time_total} %{size_download}' \
  'http://127.0.0.1:8944/api/panel/gene-structure?gene=BUB1B&refresh=true'   # cold
curl -s -w '%{time_total}' 'http://127.0.0.1:8944/api/panel/gene-structure?gene=BUB1B'
# … same for TRIP13, plus gene=SONIC for the 404
```

| Request | Cold | Warm | Payload |
|---|---|---|---|
| `gene=BUB1B` | **9.53 s** | **0.0024 s** | 3,212 B |
| `gene=TRIP13` | **5.16 s** | **0.0021 s** | 2,485 B |
| `gene=SONIC` | 404 | — | — |

Cold cost is three sequential round trips to a public REST server, one of which is a VEP
region call; warm is a file read. That ratio is the whole argument for the cache.

### What actually resolved

| | BUB1B | TRIP13 |
|---|---|---|
| canonical transcript | `ENST00000287598` | `ENST00000166345` |
| translation | `ENSP00000287598`, 1,050 aa | `ENSP00000166345`, 432 aa |
| exons | **23** | **13** |
| domain rows after filtering | **7**, from Gene3D, Smart, Pfam, Prosite_profiles, CDD, SuperFamily | **10**, from Pfam, Gene3D, CDD, SuperFamily, Smart, PRINTS, Prosite_patterns |
| protein-altering alleles | **2** | **0** |
| placed in amino-acid space | **2 of 2** | n/a |

BUB1B's domains came back as the two known halves of BUBR1: the N-terminal Mad3/Bub1
homology region (the TPR-containing part, called by four databases independently) and the
C-terminal kinase domain (called by CDD, Gene3D and SUPERFAMILY over near-identical
bounds). Both of the proband's protein-altering alleles resolved to an amino-acid offset:
one **stop-gained** landing just upstream of the kinase domain — a truncation that would
remove it entirely — and one **missense** inside it. Positions are deliberately not
written here; they are the proband's data and live only in the cache under gitignored
`build/`.

TRIP13 is the honest counter-case: full structure and ten domain rows, and **nothing to
place**, because the callset has no protein-altering allele in it. The exhibit says so
rather than rendering an empty axis without explanation.

## Frontend

* `app/src/pages/panel/LocusExplorer.tsx` — a third track under QUAL and VAF, sharing the
  x axis: exon boxes (blue = neutral machinery), introns as a thin line, a TSS arrow
  pointing the way the gene is read, hover naming `exon n/total` and its bp span.
* `app/src/pages/panel/DomainLollipop.tsx` — a separate exhibit in **amino-acid** space:
  the protein chain as a grey bar, domain bars laned one row per source database, and a
  lollipop per protein-altering allele coloured by impact (red HIGH, yellow MODERATE, blue
  LOW/MODIFIER), hollow-headed when the allele is not rare.
* `app/src/pages/panel/locus/geneTrack.ts` — the trace builder, split out so the page
  component stays about layout.
* `app/src/fixtures/gene-structure.ts` — a BUB1B-**shaped** offline fixture: 23 exons and
  a 1,050 aa protein on the same synthetic 1000, 2000, 3000 ladder the locus fixture uses,
  with real domain *names* at invented offsets. Marked as shape-not-measurement in the
  module docstring, and badged `fixture` in the UI.

An allele VEP could not place is **listed beside the plot with its reason**, never
dropped. There are two distinct reasons and the contract keeps them apart: VEP reported no
amino-acid position for that consequence on the canonical transcript (a splice-region or
UTR change has none), or the VEP call itself failed — in which case the gene track and the
domains still render and every lollipop is absent *with the failure quoted*.

## Tests

`tests/test_viz_genestructure.py`, **33 tests**, hermetic: `httpx.MockTransport` in the
style of `tests/test_annotate_vep.py` for Ensembl, `queries.fetch` replaced in the style of
`tests/test_viz_api.py` for the warehouse. Covered: the BED gate and its `LookupError`, the
versioned canonical pointer, the `is_canonical` and translating-transcript fallbacks,
plus- and minus-strand exon numbering, numbering surviving an out-of-order reply, the
domain allowlist and each excluded source by name, the description→accession fallback, the
sort, `protein_start` read only off the matching transcript, no VEP call when there are no
alleles, a VEP outage reported rather than raised, the contract's field set, the
protein-altering filter, both null reasons, **the absence of any patient genomic
coordinate in the payload**, a lookup outage raising, a non-JSON reply, a transport
failure, and the five HTTP behaviours (envelope, cache + `?refresh=`, 404, 422 on a key
that would escape the cache directory, 502 with the upstream detail).

## Conclusions

1. **Ensembl REST supplies the whole gene track from one call.** `lookup/id?expand=1`
   carries bounds, strand, every transcript's exons and the translation id, so the exon
   track and the protein axis come from a single fetch.
2. **The protein feature endpoint is mostly not domains.** 4 of 28 features on BUB1B's
   translation are domain calls. An allowlist is not tidiness here; without it the figure
   would show a PDB entry and a disorder prediction as if they were functional units.
3. **Protein positions were not derivable from what we store, and the honest fix was one
   more API call.** `panel_annotations` never kept a protein offset. Rather than
   re-deriving codon numbers from exon bounds — a second implementation of VEP's reading
   frame, untested against it — the endpoint asks VEP for the gene's protein-altering
   alleles and caches the answer. Both of BUB1B's resolved; the endpoint's contract still
   carries a null and a reason, because a splice-region allele legitimately has no
   amino-acid position.
4. **What remains impossible and is stated as such**: an allele whose consequence sits
   outside the coding sequence has no protein position and never will — it is listed, not
   plotted. And the domain track is only as good as the databases: an unannotated region
   of a protein is *unannotated*, not *unimportant*, and the exhibit must not be read as
   "outside a blue bar means harmless".
