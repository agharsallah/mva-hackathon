# 007 — Can the whole data profile be read, graded and rendered from code?

## Question

Entries 001–006 each answered one question by reading one profile artifact by eye and
writing the conclusion down by hand. That does not survive the dataset changing, it does
not transfer to another case, and it leaves the reasoning behind each judgement — *why*
ts/tv near 2.0 is acceptable — in a person's head rather than in the repository.

Can the same profile directory be loaded, graded against stated expectations, and rendered
as an interactive report entirely from code, with the conclusions of 001–006 reproduced
rather than restated?

## Inputs

- `ressources/data-profile/` — 13 artifacts, the committed output of
  `tools/profile-genomic-data.sh` (no patient records)
- `tests/fixtures/profile/` — a synthetic profile directory, invented values
- `tests/fixtures/mini.vcf` — the synthetic locus fixture
- New code: `src/mva/explore/` (readers, profile, checks, theme, figure, views, report, cli)
- plotly 7.0.0, added as the project's first runtime dependency

## Commands

```bash
uv add plotly
uv run pytest tests/ -q
uv run mva-explore checks ressources/data-profile
uv run mva-explore report ressources/data-profile -o figures/explore-report.html \
  -t "MVA proband — callset exploration"
uv run mva-explore export ressources/data-profile -o figures/exhibits
uv run mva-explore locus tests/fixtures/mini.vcf -o figures/locus-fixture.html \
  -l "BUB1B (synthetic fixture)"
```

## Observed

`pytest`:

```
127 passed in 1.23s
```

69 pre-existing pipeline tests plus 58 new ones covering the toolkit, all against
synthetic fixtures with no dataset present.

`mva-explore checks ressources/data-profile`:

```
  PASS   Transition/transversion ratio                                     1.94
  PASS   Indel / SNP ratio                                                0.228
  FAIL   Multiallelic sites                                              66,860
  PASS   Heterozygous / homozygous-alt ratio                               1.61
  PASS   PASS fraction                                                    94.6%
  INFO   Records carrying physical phasing                                15.4%
  PASS   Q30 rate                                                         92.2%
  PASS   GC content                                                       41.1%
  PASS   Duplication rate                                                  9.3%
  PASS   Insert size peak                                                266 bp
  PASS   Estimated raw coverage                                             52×
  WARN   Largest autosomal allele-balance deviation (chr20)  0.4720 (Δ -0.0280)
  INFO   Genetic sex from sex-chromosome evidence            male (XY) — chrX 4,858 het @ 41×, chrY 4,301 het @ 36×

Worth acting on:
  - Multiallelic sites: Every one of these is a variant the scorer cannot be shown until
    the callset is normalized.
  - Largest autosomal allele-balance deviation (chr20): This is the direct blood-derived
    test for mosaic aneuploidy. A flat profile is a real negative result and belongs in
    the write-up as one.
```

`mva-explore report`, `export` and `locus`:

```
Wrote figures/explore-report.html — 20 exhibits across 6 sections (94 KB).
Wrote 20 files under figures/exhibits.
Wrote figures/locus-fixture.html — 12 calls, 3 exhibits.
```

The report was rendered in headless Chrome and inspected: sidebar navigation, tiles,
graded table and Plotly charts all draw, and the interactive filter and scroll-spy work
from a `file://` URL with no server.

## Conclusion

**Every conclusion from entries 002, 004 and 005 is now reproduced by code from the
committed profile, not restated.** The ts/tv of 1.94, the het:hom of 1.61, the 94.6% PASS
fraction, the 52× coverage, the male sex call and the flat autosomal allele balance all
fall out of `run_checks()` with the expected band attached to each.

Two findings the earlier entries had to be read for are now surfaced automatically:

- **chr20 is the largest autosomal deviation** at mean balance 0.4720 (Δ −0.0280), and the
  lowest share of heterozygous sites inside the diploid band at 68.9% against an autosomal
  median of 77.5%. It is graded `WARN`, which is a prompt to look and not a finding: the
  deviation is small, the depth on chr20 is unremarkable, and entry 004's conclusion — no
  mosaic aneuploidy visible in this blood sample — stands. It is now visible as the largest
  thing in an otherwise flat profile rather than as one number in a table of twenty-five.
- **TRIP13 carries the highest suppressed share** of the panel at 6 of 12 calls (50%),
  named in the exhibit's own note rather than found by scanning the counts table.

Two bugs were caught by writing the tests rather than by reading the output:

1. The Plotly runtime was attached to the first exhibit rather than the first exhibit
   *carrying a figure*. Since the report opens with a table, every chart on the page
   rendered blank with no error in the console. Now asserted.
2. An empty profile rendered an empty tile row and a headerless check table, which reads
   as "nothing is wrong" where it means "nothing was measured". Sections now contribute
   nothing when they have nothing to say.

One naming collision was resolved: `Panel` in `CONTEXT.md` is the candidate gene set, so
the report's figure-plus-caption unit is an **Exhibit**.

### What this does not establish

The check bands are community conventions, not measurements. They are cited in each
check's `basis` and live in one file so they can be argued with; a `PASS` means "inside
the range a healthy germline whole genome usually falls in", not "verified correct".

The coverage figure remains an estimate from compressed file size and read length, carried
over from entry 005, and the read-quality figures remain a 500k read-pair sample from lane
L001 only. Both are labelled as such in the report.

Nothing here touched the raw reads or the full VCF. The toolkit reads the ~600 KB profile;
the `locus` verb reads a real VCF and was exercised only against the synthetic fixture.
