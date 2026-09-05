# 068 — Closing step 0: what the platform holds, and what it already answered

**A step-0 platform entry, the last one. It carries no hypothesis.** Written 2026-09-04.

## Question

Step 0 was meant to answer one thing — can the delivered bytes be trusted, stored without
loss, and queried in SQL? — and it did, by entry 016. It then kept absorbing work for eleven
days: an app, a read store, reference data, a phenotype ranking, a 3D exhibit. Some of that
work answered *research* questions before the research steps existed. Before opening the
solving phase, three things had to be settled:

1. What does the platform hold, counted rather than remembered?
2. Which research questions did step-0 exploration already answer, and where do those
   results belong now?
3. What was wrong in the record — numbering, budget, stale banners — and is it fixed?

## Inputs

- The repository at `f199670` (198 commits, 2026-08-26 → 2026-09-03), working tree clean.
- The live warehouse on the remote Postgres, reached through `mva-warehouse pg-check`.
- Three read-only inventories of `docs/`, `src/`, `app/` taken this session; their findings
  are folded into [`../../toolset.md`](../../toolset.md) and [`../../roadmap.md`](../../roadmap.md).

## Commands

```bash
uv run mva-warehouse pg-check
uv run mva-warehouse pg-query "select (select count(*) from information_schema.tables where table_schema='warehouse') w, \
  (select count(*) from information_schema.tables where table_schema='results') r, \
  (select count(*) from pg.warehouse.hypotheses) h, (select count(*) from pg.warehouse.evidence) e, \
  (select count(*) from pg.warehouse.probe_ledger) p, (select count(*) from pg.warehouse.data_lineage) l"
uv run mva-science check && uv run mva-science export && uv run mva-science report
ls docs/step-0/methodology/*.md | grep -v README | wc -l
ls tests/test_*.py | wc -l
find src/mva -name '*.py' | xargs cat | wc -l
find app/src -name '*.ts*' | wc -l ; find app/src -name '*.ts*' | xargs cat | wc -l
```

## Observed

| What | Count | How |
|---|---|---|
| Postgres | connected, 18.4, 1343 MB, schemas `public`, `results`, `warehouse` | `pg-check` |
| schema `warehouse` | 27 tables | live `information_schema` |
| schema `results` | 23 tables | live `information_schema` |
| `warehouse.hypotheses` / `warehouse.evidence` | 2 / 6 rows, all step-3, no verdict | live count |
| `warehouse.probe_ledger` | 0 rows of a budget of **6** | live count; budget from `probes.BUDGET` |
| `warehouse.data_lineage` | 39 edges | live count |
| step-0 methodology entries on disk | 66 files, 001–066, before this entry | `ls` |
| Python | 28,882 lines under `src/mva/`, 60 test files | `wc`, `ls` |
| App | 300 `.ts`/`.tsx` files, 39,474 lines | `find`, `wc` |
| Research-record mirror | `mva-science check` → `check passed: 2 hypotheses, 6 evidence rows, no coordinates`; `export` wrote 5 files; `report` wrote `figures/science-report.html` (43 KB) — 2 hypotheses, 0/6 probes spent | executed |

Two things the run itself surfaced:

- `mva-science report` first failed with `Binder Error: Column "hypothesis_ids" referenced …
  cannot be referenced before it is defined`. The `probe_ledger` widening designed in
  [017](017-the-research-record.md) had never been applied to the live table (11 columns).
  Applied `ALTER TABLE … ADD COLUMN IF NOT EXISTS hypothesis_ids VARCHAR` on the empty table
  through a writable `attached()` connection; the column list then read 12 and the report
  rendered. `pg-query` could not do it — it attaches read-only by design.
- The committed mirror `docs/science-register.json` was dated 2026-08-29 with zero
  hypotheses while the database held two. It is regenerated and agrees now.

## What step 0 answered that belongs to research steps

| Question | Entry | Result (numbers in [data-findings §6](../../../ideation/data-findings.md)) | Belongs to |
|---|---|---|---|
| Which panel alleles are rare and protein-altering? | [031](031-vep-rest-panel-annotation.md) | exactly two, both BUB1B, both het, both PASS: a ClinVar-pathogenic `stop_gained` and a gnomAD-absent `missense` | step 2 |
| Does the sample show whole-chromosome mosaic aneuploidy above the allele-balance floor? | [037](037-baf-karyogram.md) | no, all autosomes flat | step 5 |
| Do the panel's non-PASS calls hide a rare damaging allele? | [049](049-suppressed-calls.md) | no, 0 of 20 | step 4 |
| Is either candidate allele already in ClinVar? | [051](051-clinvar-presence.md) | one, the `stop_gained`, for MVA syndrome 1 | step 2 / 7 |
| Does a panel-blind phenotype ranking agree? | [step-3/067](../../iteration1/step-3/methodology/067-phenotype-ranking-without-java.md) | BUB1B 6th of 5,267 | step 3 (already filed) |

These enter the register as `retrospective:` claims under those steps — the rule added to
[`method.md`](../../method.md) today — never as pre-registered predictions. Phase of the pair
is **not** established; two `0/1` calls are consistent with *cis*.

## Corrections made to the record

| Defect | Fix |
|---|---|
| Entry `056` existed twice (this folder and step-3) | step-3's renumbered **067**; 13 references updated; both files say so |
| "Next entry" stated as 017, 018 in four docs | all say **069**, global |
| `043` missing from this folder's index | row added |
| Budget recorded as 18 everywhere (3 members × 6) | one member is registered: **6**. `probes.BUDGET = 6 × MVA_TEAM_MEMBERS`; docs, app fixtures, dictionary, two SVGs, intel §7/§9/§11 corrected |
| `steps.py` said steps 2 and 4 `planned`, no step for solution paths 5–6 or Track 2 | 2 and 4 `open`; **step-7** (knowledge and literature) and **step-8** (Track 2) added |
| `roadmap.md`, `current-state.md`, `decisions.md`, `docs/README.md`, root `README.md` dated 2026-08-29 and contradicting `data-findings.md` §6 | rewritten or refreshed; roadmap is now the 8-step plan |
| No page mapped question → tool | [`toolset.md`](../../toolset.md) added |
| 3D note said built, three indexes said not built | indexes now match the note |

## Conclusions

- Step 0 is **closed** at this entry. Its goal was met at 016; everything after was tooling
  the research steps will use, and it is catalogued in `toolset.md`.
- From here, a tool built for a research step is recorded under that step. Only a cross-step
  platform fix lands in this folder, naming the step that needed it. Numbering is global;
  the next entry is **069**.
- The case stands at one BUB1B pair with phase unknown and four converging checks, none of
  them a verdict. Steps 1 (normalize), 2 and 4 (file the retrospective claims, then go
  genome-wide), 3 (join the ranking to the callset) and 7 (literature) are the next tests.
  No upload before step 6's gate.
