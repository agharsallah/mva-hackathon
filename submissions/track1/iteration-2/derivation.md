# How every non-coordinate field of the submission was derived

**Anchor:** row `stop+missense` tests H009; the register's suggested confidence is 0.9993 (a transparent triage heuristic, not a calibrated posterior). Written by `tools/resolve_submission_spec.py`; source `derivation.json` beside this file.

## Alleles — what the result table says

| allele | table | gene | consequence | call | gnomAD | ClinVar | score |
|---|---|---|---|---|---|---|---|
| stop | `results.coding_candidates` | BUB1B | stop_gained | het PASS DP 46 | 3.29e-05 | pathogenic;likely_pathogenic | 1.000 |
| missense | `results.coding_candidates` | BUB1B | missense_variant | het PASS DP 28 | absent | not listed | 0.300 |
| lztr1_stop | `results.coding_candidates` | LZTR1 | stop_gained | het PASS DP 48 | 1.37e-06 | pathogenic;likely_pathogenic | 1.000 |
| f5_leiden | `results.coding_candidates` | F5 | missense_variant | het PASS DP 54 | 0.0173 | pathogenic/pathogenic,_low_penetrance;drug_response;uncertain_significance;risk_factor;pathogenic | 0.030 |
| flg_stop | `results.coding_candidates` | FLG | stop_gained | het PASS DP 38 | 0.00302 | pathogenic;pathogenic/likely_pathogenic | 0.050 |

## Rows — the epcr ladder

| rank | row | type | pair score | epcr | hypothesis |
|---|---|---|---|---|---|
| 1 | stop+missense | primary | 1.300 | 0.9993 | H009 |
| 2 | LZTR1 stop_gained (secondary) | secondary | 1.000 | 0.4996 | — |
| 3 | FLG stop_gained (secondary) | secondary | 0.050 | 0.02498 | — |
| 4 | F5 Leiden (secondary) | secondary | 0.030 | 0.01499 | — |

## Hypothesis priors

| hypothesis | prior | source |
|---|---|---|
| stop+missense | 1.0 | row stop+missense |

## Arithmetic

```
anchor: row 'stop+missense' tests H009 — register suggested confidence 0.9993
stop+missense: pair score 1.3000
LZTR1 stop_gained (secondary): lowest primary 0.9993 x 0.5 x 1.0000 / 1.0000 = 0.4996
F5 Leiden (secondary): lowest primary 0.9993 x 0.5 x 0.0300 / 1.0000 = 0.01499
FLG stop_gained (secondary): lowest primary 0.9993 x 0.5 x 0.0500 / 1.0000 = 0.02498
prior stop+missense: (1 - 0.00) x 0.9993 / 0.9993 = 1.0
```
