# Documentation index

**Standing:** 2026-10-05 — the one index. Every doc in this repository is reachable from
here; nothing links to a page this index does not list.

The repository was stripped of its previous case (MVA genomics) and repointed at the
**SEPIQ 2026 challenge** on this date. What survives is machinery. **No analysis has been
run and the dataset is not downloaded.**

## Start here

| Read | For |
|---|---|
| [`../README.md`](../README.md) | The front door: what this is, the data perimeter, the quickstart. |
| [`current-state.md`](current-state.md) | **What exists, what works, what to build next.** The honest inventory after the strip — every module with its state, what is declared but unproven, and the ordered next steps. |
| [`challenge.md`](challenge.md) | **The challenge statement.** Both tracks, their metrics, the AVIDa-hHER2 schema, what is organiser-stated fact versus inference, and the open questions. Read before any strategy decision. |
| [`toolset.md`](toolset.md) | What exists and what each piece is for. Read before writing a new script. |
| [`dictionary.md`](dictionary.md) | Every unclear word, explained for a software engineer with no biology background. Rendered at `/learn` in the app. |

## Reference

| Page | Owns |
|---|---|
| [`notes/python-quality-gates.md`](notes/python-quality-gates.md) | Why each gate is set where it is, and what to do when one fails. |
| [`../src/sepiq/README.md`](../src/sepiq/README.md) | The package index and the enforced layering. |
| [`../CONTEXT.md`](../CONTEXT.md) | The naming discipline: one chosen word per idea, plus the _Avoid_ list. |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Commit convention, hooks, how to run the gates. |

## The rules, in one place

- **One doc index** — this page. The root `README.md` is the front door and never
  duplicates it.
- **One owner per fact.** Every measured number has exactly one owning page; others link
  to it and never restate it.
- **One decision, one note** in `notes/`, each with a `**Standing:**` line saying whether
  it still holds. Other docs state the _result_ in a sentence and link the note; they
  never re-argue it.
- **`Standing:` or `Verified:` near the top of every page**, with the date it was last
  checked against reality. A page describing system state that has not been re-verified
  must say so.
- **`methodology/` is append-only.** Never edit an entry; append one that supersedes it
  and says so. Numbers are global and monotonic from **001**.
- **Check for an existing owner before writing a new page.** Extend the owner; do not
  start a parallel document.

## Not yet written

These are expected and deliberately absent — listed so their absence is visible rather
than looking like an oversight.

| Page | When it appears |
|---|---|
| `methodology/` | With the first executed run. |
| `data-profile.md` | Once the dataset is downloaded and profiled — it becomes the owner of every measured number about it. Step 3 of [`current-state.md`](current-state.md) §5. |
| `notes/` on split strategy, metric replicas, model choice | As each decision is actually made. |
