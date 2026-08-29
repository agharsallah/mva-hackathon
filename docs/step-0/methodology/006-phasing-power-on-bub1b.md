# 006 — How much of the compound-het search space can phasing resolve?

## Question

15.4% of records carry `PGT`/`PID` (entry 002). A compound heterozygote needs one variant
on each haplotype, so phasing could in principle collapse the search space. Does it?

Measured on BUB1B, the most likely candidate gene, using the pipeline's own reader and
pair finder — so this doubles as a check that the code works on real data rather than only
on the synthetic fixture.

## Inputs

- `~/ubuntu/work/proband.vcf.gz`
- BUB1B span `15:40140984-40241137` (Ensembl GRCh38 + 20 kb padding, from the panel BED)
- `src/mva/vcf.py`, `src/mva/compound_het.py`

## Commands

```bash
bcftools view -r 15:40140984-40241137 ~/ubuntu/work/proband.vcf.gz -Ov -o <scratch>/bub1b.vcf
```

```python
from mva.vcf import read_calls
from mva.compound_het import candidate_pairs, Phase

calls = read_calls('<scratch>/bub1b.vcf')
pairs = candidate_pairs(calls)
```

The extracted VCF was written to a scratch directory outside the repo and is not retained.

## Observed

```
BUB1B: 81 calls, 58 het, 23 hom-alt
       4 non-PASS
       contigs seen: ['chr15']

pairs: 1653 total -> unknown=1648, trans=3, cis=2
compound-het candidates surviving phase filter: 1651
```

The 81 calls come from 80 records — one multiallelic `1/2` site split into two calls, and
that site is classified TRANS by construction. Of the five phase-resolved pairs, the four
involving distinct positions were separated by 3, 42, 3 and 4 bp respectively.

## Conclusions

1. **Phasing resolves 5 of 1,653 pairs — 0.3%.** It is a confirmatory tool for
   neighbouring variants, not the discriminator. Any plan assuming phasing would collapse
   the search space was wrong.
2. **The reach is a few hundred bases**, consistent with the 266 bp insert size measured
   in entry 005. Two variants in different exons of the same gene will essentially never
   be phased by this data.
3. **UNKNOWN must never be treated as a rejection** — it is the verdict on 99.7% of pairs.
   The pipeline keeps them; only CIS is excluded.
4. **The candidate space is quadratic and must be narrowed by annotation.** 58 het calls in
   one gene give 1,653 pairs; phasing removes 2. This is the concrete reason annotation is
   the critical path.
5. **The reader and pair finder work on real data**, producing correctly `chr`-prefixed
   contigs and splitting the multiallelic site as designed.
