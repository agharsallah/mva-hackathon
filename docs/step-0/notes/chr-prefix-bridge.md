# The `chr` prefix is added in exactly one function

**Standing:** firm. The owner is `src/mva/pipeline/variant.py` —
`Variant.from_vcf()` and the `to_submission_contig()` it calls. Verified 2026-08-29:
those are the only places in `src/` that build a chromosome string.

Two naming conventions collide, and nothing in the middle reconciles them:

| | Says | Because |
|---|---|---|
| The proband VCF | `15` | called against `GCA_000001405.15_GRCh38…_no_chr.fasta` |
| The challenge scorer | `chr15` | it builds `(chrom.strip(), int(pos), ref.upper(), alt.upper())` and compares **verbatim** — it `.strip()`s and does nothing else |

So `"15"`, `"chr15"` and `"CHR15"` are three different chromosomes to the scorer. Copying a
coordinate straight out of the VCF into a submission produces a well-formed CSV that
scores **zero** while looking perfectly correct. It is the single easiest silent total
miss available, which is why it gets a rule rather than a convention.

**The rule:** one function converts, and no other code — not a view, not a report, not a
warehouse query, not a shell script — may build a chromosome string with an f-string or a
concatenation.

Conversion goes both ways, and the direction matters:

- **In → out (VCF to submission):** `Variant.from_vcf()` adds the prefix. Everything
  downstream speaks `Variant` and is already correct by construction.
- **Out → in (panel to `bcftools`):** region queries need the *bare* contig, so the
  chr-prefixed panel BED is stripped on the way into a query. Same single owner.

`to_submission_contig()` also handles the mitochondrion, where the no-chr analysis set says
`M` and Ensembl-style references say `MT`; both become `chrM`.

## Consequences

`test_variant.py` is the enforcement point, and a chr-prefix test is mandatory before the
first submission — this is a known live failure mode, not a hypothetical one.

This note is the owner of the rule. Other documents state the result in one sentence and
link here; before this note existed the same rule was restated in five places with no
owner, which is how a rule quietly acquires an exception.
