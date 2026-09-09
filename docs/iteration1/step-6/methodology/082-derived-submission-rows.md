# 082 — Can every non-coordinate field of the submission CSV be derived from the warehouse and the register instead of typed?

**Step:** step-6   **Hypotheses tested:** none — this entry records **tooling step 6 needed**
(CLAUDE.md: a tool a research step needs is recorded in that step's methodology). H009 is
unchanged; what changes is how the file that tests it is built.
**Written:** 2026-09-09. **Nothing uploaded** — 0 of 6 spent.

## Question

The organisers' submission page (`track1_submission_template.csv`, "last updated 28 Aug
2026") asks for twelve columns: `proband_id`, the two alleles, `epcr`, `finding_type`,
`notes`. Entry [074](074-submission-v1-design.md) built those columns from a spec in which
three things were **typed by hand**:

1. the `epcr` of every row (0.95, 0.30, 0.29, 0.20, 0.19, 0.05, 0.04, 0.03);
2. the `notes` the organisers receive, including numbers (AlphaMissense 0.92, CADD 24.5,
   "44x", gnomAD 1.4e-6) copied from earlier entries by a person;
3. the hypothesis priors the decode table weighs replies with ("stated, not fitted").

Only the coordinates were derived from data (selectors, [076](076-iteration-tooling.md)).
Can the rest be derived too, and can the tool refuse a typed value?

## Method

| Piece | Where | Tested by |
|---|---|---|
| **Facts.** The selector's own `WHERE` clause is re-run against its table for the fact columns it has (`gene, consequence, impact, gt/zygosity, filter, dp, vaf, gnomad_af, clin_sig, rsid, is_clinvar_plp`); exactly one row must come back. A note can quote only these. | `src/mva/warehouse/submission_facts.py` | `tests/test_warehouse_submission_rows.py` |
| **Score.** One allele = rarity × severity, the ranker's existing term (`mva.pipeline.ranking.allele_score`, made public); a pair = the sum. VEP's first (most severe) consequence term is scored. | `src/mva/pipeline/ranking.py` | same |
| **epcr ladder.** The rank-1 row names the hypothesis it tests; its epcr is the register's suggested confidence for that claim (`mva.science.evidence.weigh`, read from the committed `docs/science-register.json`). Other primary rows: `(1 − anchor) × score / Σ scores`. Secondary rows: `lowest primary × 0.5 × score / max secondary score`. Four significant digits; a tie after rounding is an error. | `src/mva/warehouse/submission_rows.py` | same |
| **Notes.** `H:<id> \| <type> \| <allele facts> [+ <partner facts>] \| <rationale> \| <how the epcr was derived>`. A `rationale` may contain no number (a digit that does not continue an identifier such as `BUB1B` or `rs6025`). | same | same |
| **Priors.** In-callset hypothesis = `(1 − Σ declared unseen priors) × row epcr / Σ primary epcr`; only a hypothesis naming an `_unknown` allele may declare a prior. | same | same |
| **Refusals.** A row with `epcr` or `notes`; a rationale with a number; an in-callset hypothesis with a `prior`; an unseen hypothesis without one; an anchor row the ranker would not itself put first; a tie. | same | same (9 tests) |
| **Tool.** `resolve_submission_spec.py` runs the derivation when the selectors carry a `derivation` block, writes `derivation.json` + `derivation.md` (coordinate-free) beside them, and fills the gitignored spec's rows and priors. | `tools/resolve_submission_spec.py` | run below |
| **Gate.** `check_iteration.py` on a derived spec: no `epcr`/`notes` in rows, no in-callset prior, `derivation.json` present and newer than the selectors, its ladder strictly descending in (0, 1]. | `tools/check_iteration.py` | run below |
| **Dashboard.** `/api/submissions` carries `selectors.derivation`; `/submissions` shows the facts table and the arithmetic (`DerivationExhibit`), and epcr values are printed with significant digits. | `src/mva/viz/submissions_reader.py`, `app/src/pages/submissions/DerivationExhibit.tsx` | app tests |
| **CSV rendering.** epcr written as a plain decimal (`0.000006219`), never `6.219e-06` — the scorer parses either, a reader only one. | `src/mva/pipeline/submission.py` | `tests/test_submission.py` |

`submissions/track1/iteration-1/spec.selectors.json` was rewritten: same seven selectors,
same eight rows and eight hypotheses, but rows carry `finding_type`, `label`, a digit-free
`rationale` and (rank 1 only) `hypothesis: H009`; the three "unseen" hypotheses keep their
declared priors (0.12, 0.05, 0.05); everything else is gone.

## Commands

```bash
uv run pytest tests/test_warehouse_submission_rows.py tests/test_submission.py tests/test_probe_design.py -q
uv run python tools/resolve_submission_spec.py --selectors submissions/track1/iteration-1/spec.selectors.json \
    --out build/submission/spec.json --check build/submission/spec.pre-derivation.json
uv run python tools/design_submission.py --spec build/submission/spec.json \
    --out submissions/track1/iteration-1/agharsallah_bub1b-comphet-derived.csv --decode-md submissions/track1/iteration-1/decode-table.md
uv run python tools/check_iteration.py submissions/track1/iteration-1
shasum -a 256 submissions/track1/iteration-1/agharsallah_bub1b-comphet-derived.csv
```

## Observed

**Tests:** 46 passed (9 new).

**Two refusals fired before the run succeeded**, both on the real spec, both correct:

- `row 1: rationale contains a digit` — the first rule refused `BUB1B`. Rule narrowed to a
  digit that starts a number; identifiers with digits are words.
- `stop+intronB and stop+intronA both derive epcr 0.0014; the rank would be decided by file
  order` — rounding to four *decimal places* collapsed two shares of a 0.0037 residual.
  Rounding changed to four *significant* digits.

**Derivation (positions withheld by the tool; every line printed by the run):**

```
anchor: row 'stop+missense' tests H009 — register suggested confidence 0.9963
stop+missense: pair score 1.3000      stop+intronA: 1.0500      missense+intronA: 0.3500
stop+intronB: pair score 1.0050       missense+intronB: 0.3050
stop+intronA:     (1 - 0.9963) x 1.0500 / 2.7100 = 0.001427
stop+intronB:     (1 - 0.9963) x 1.0050 / 2.7100 = 0.001366
missense+intronA: (1 - 0.9963) x 0.3500 / 2.7100 = 0.0004758
missense+intronB: (1 - 0.9963) x 0.3050 / 2.7100 = 0.0004146
LZTR1 stop_gained (secondary): lowest primary 0.0004146 x 0.5 x 1.0000 / 1.0000 = 0.0002073
FLG stop_gained (secondary):   lowest primary 0.0004146 x 0.5 x 0.0500 / 1.0000 = 1.036e-05
F5 Leiden (secondary):         lowest primary 0.0004146 x 0.5 x 0.0300 / 1.0000 = 6.219e-06
prior stop+missense: (1 - 0.22) x 0.9963 / 1.0000 = 0.7771
check against build/submission/spec.pre-derivation.json: identical
wrote build/submission/spec.json  (7 alleles, 8 rows)
```

Two rank changes against 074: **stop+intronB (rank 3) now sits above missense+intronA
(rank 4)** because a stop_gained scores 1.0 and a gnomAD-absent missense 0.3; and **FLG
(rank 7) above F5 (rank 8)** because FLG's stop_gained at gnomAD 0.003 outscores Factor V
Leiden's missense at 0.017. Both orderings were hand-set the other way in 074 with no
stated reason.

**Rehearsal and cross-check:** 8 of 8 answer keys `agree` between the replica and the
organisers' `evaluation.py`. If the pair is right: `rank_points 100, f_max 1.0,
full_match_rank 1`. Decode table: 7 distinguishable replies over 8 keys; **prior entropy
1.111 bits, expected posterior 0.149 bits, expected information gain 0.963 bits**, largest
ambiguity 2 (the two "unseen partner" keys, as before). Down from 1.455 bits in 074: the
derived priors put 0.78 on the anchor pair where 074 stated 0.70, so there is less left to
learn — the earlier figure was a property of the hand-set priors, not of the file.

**CSV:** 8 rows, 3,122 bytes, LF; sha256
`54854a6ef7a2cb6ae67e54ccbf092c5c7d1459993379626c4e59f601f4ad8227` (was `fbc9e750…`).
Same seven coordinates (`--check … identical`); only `epcr` and `notes` changed.

**Folder gate** after the README was updated: `submissions/track1/iteration-1: ready — ok`
(before the README update it correctly failed on the stale sha256, and on the old rule
"row N epcr must be in (0, 1]" against rows that no longer carry an epcr — hence the
derivation-aware branch).

## Conclusion

Every column the template asks for is now produced by code from a documented source:
coordinates from selectors (076), facts and notes from the selected table row, epcr from the
register's weighing plus the ranker's heuristic, priors from the rows, `proband_id` from the
scorer's contract (`PROBAND01`, [data-findings §2.2](../../../../ideation/data-findings.md)).
The one number a human still sets is the prior mass on hypotheses the data cannot see
(0.22 across three "unseen" keys), and the file says so (`prior_source: declared`).

**Assumptions and limitations, stated next to the result:**

- The register's suggested confidence is a transparent triage heuristic, not a calibrated
  posterior (`docs/method.md`); the rank-1 epcr inherits that. The scorer ranks; it does not
  read the magnitude.
- The residual split is proportional to the ranker's additive score — defensible and
  inspectable, not fitted. Its constants (rarity 1.0 / 0.5 / 0.05, severity 1.0 / 0.6 / 0.1)
  are the ones the methods form already defends.
- A tiny epcr (`0.000006219`) is honest about belief but reads oddly; the alternative —
  inflating alternatives to look like probabilities a human would type — is what this entry
  removes.
- `derivation.json` is coordinate-free by construction (no field ever held a position) and
  the coordinate gate runs over it like every tracked file.
