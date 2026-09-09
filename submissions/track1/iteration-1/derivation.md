# How every non-coordinate field of the submission was derived

**Anchor:** row `stop+missense` tests H009; the register's suggested confidence is 0.9963 (a transparent triage heuristic, not a calibrated posterior). Written by `tools/resolve_submission_spec.py`; source `derivation.json` beside this file.

## Alleles — what the result table says

| allele | table | gene | consequence | call | gnomAD | ClinVar | score |
|---|---|---|---|---|---|---|---|
| stop | `results.coding_candidates` | BUB1B | stop_gained | het PASS DP 46 | 3.29e-05 | pathogenic;likely_pathogenic | 1.000 |
| missense | `results.coding_candidates` | BUB1B | missense_variant | het PASS DP 28 | absent | not listed | 0.300 |
| intronA | `results.panel_candidates` | BUB1B | intron_variant | het PASS DP 46 | absent | not listed | 0.050 |
| intronB | `results.panel_candidates` | BUB1B | intron_variant | het PASS DP 40 | 0.00213 | uncertain_significance | 0.005 |
| lztr1_stop | `results.coding_candidates` | LZTR1 | stop_gained | het PASS DP 48 | 1.37e-06 | pathogenic;likely_pathogenic | 1.000 |
| f5_leiden | `results.coding_candidates` | F5 | missense_variant | het PASS DP 54 | 0.0173 | pathogenic/pathogenic,_low_penetrance;drug_response;uncertain_significance;risk_factor;pathogenic | 0.030 |
| flg_stop | `results.coding_candidates` | FLG | stop_gained | het PASS DP 38 | 0.00302 | pathogenic;pathogenic/likely_pathogenic | 0.050 |

## Rows — the epcr ladder

| rank | row | type | pair score | epcr | hypothesis |
|---|---|---|---|---|---|
| 1 | stop+missense | primary | 1.300 | 0.9963 | H009 |
| 2 | stop+intronA | primary | 1.050 | 0.001427 | — |
| 3 | stop+intronB | primary | 1.005 | 0.001366 | — |
| 4 | missense+intronA | primary | 0.350 | 0.0004758 | — |
| 5 | missense+intronB | primary | 0.305 | 0.0004146 | — |
| 6 | LZTR1 stop_gained (secondary) | secondary | 1.000 | 0.0002073 | — |
| 7 | FLG stop_gained (secondary) | secondary | 0.050 | 1.036e-05 | — |
| 8 | F5 Leiden (secondary) | secondary | 0.030 | 6.219e-06 | — |

## Hypothesis priors

| hypothesis | prior | source |
|---|---|---|
| stop+missense | 0.7771 | row stop+missense |
| stop+intronA | 0.001113 | row stop+intronA |
| stop+intronB | 0.001065 | row stop+intronB |
| missense+intronA | 0.0003711 | row missense+intronA |
| missense+intronB | 0.0003234 | row missense+intronB |
| stop+unseen | 0.12 | declared |
| missense+unseen | 0.05 | declared |
| neither (other gene) | 0.05 | declared |

## Arithmetic

```
anchor: row 'stop+missense' tests H009 — register suggested confidence 0.9963
stop+missense: pair score 1.3000
stop+intronA: pair score 1.0500
missense+intronA: pair score 0.3500
stop+intronB: pair score 1.0050
missense+intronB: pair score 0.3050
stop+intronA: (1 - 0.9963) x 1.0500 / 2.7100 = 0.001427
missense+intronA: (1 - 0.9963) x 0.3500 / 2.7100 = 0.0004758
stop+intronB: (1 - 0.9963) x 1.0050 / 2.7100 = 0.001366
missense+intronB: (1 - 0.9963) x 0.3050 / 2.7100 = 0.0004146
LZTR1 stop_gained (secondary): lowest primary 0.0004146 x 0.5 x 1.0000 / 1.0000 = 0.0002073
F5 Leiden (secondary): lowest primary 0.0004146 x 0.5 x 0.0300 / 1.0000 = 6.219e-06
FLG stop_gained (secondary): lowest primary 0.0004146 x 0.5 x 0.0500 / 1.0000 = 1.036e-05
prior stop+missense: (1 - 0.22) x 0.9963 / 1.0000 = 0.7771
prior stop+intronA: (1 - 0.22) x 0.001427 / 1.0000 = 0.001113
prior stop+intronB: (1 - 0.22) x 0.001366 / 1.0000 = 0.001065
prior missense+intronA: (1 - 0.22) x 0.0004758 / 1.0000 = 0.0003711
prior missense+intronB: (1 - 0.22) x 0.0004146 / 1.0000 = 0.0003234
```
