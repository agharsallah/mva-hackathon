# Methodology log — iteration 4, step 8

Append-only. Entries are numbered globally; each entry from a research step carries
`## Hypothesis and prediction`, `## What would refute it` (written before the run) and
`## Verdict` (after).

| entry | tests | result |
|---|---|---|
| [143](143-a-gpu-lane-that-sends-two-windows-and-a-bill.md) — the tier-3 contract and the DNA windows | H076 (`P4-1`, retrospective) | supported 0.77; 39,286 / 39,286 windows, 0 mismatches |
| [144](144-ntv2-reads-two-windows-on-an-l4.md) — NT-v2 on an L4 | H078 (`P4-13`) | both alleles scored; pair rank in 148 |
| [145](145-esmc-agrees-with-esm2-except-on-the-confirmed-allele.md) — ESM-C agrees with ESM2 except on the confirmed allele | H080 (`P4-15`) | supported 0.85; ρ 0.85 / 0.74 |
| [146](146-evo2-1b-scores-every-record-on-an-h100.md) — Evo 2 1B on an H100 | H079 (`P4-14`) | both alleles scored; pair rank in 148 |
| [147](147-boltz2-folds-bubr1-and-a-conservative-swap-drops-as-much.md) — Boltz-2 folds BubR1 | H081 (`P4-16`) | testing 0.31; a conservative swap drops as much |
| [148](148-the-gpu-lanes-and-the-consensus.md) — the GPU lanes and the consensus | H077 (`P4-4`), H078, H079, H082 (`P4-17`) | H077 supported 0.83; H078, H079 testing 0.40; H082 testing 0.20 — each GPU lane alone ranks the pair lower |
