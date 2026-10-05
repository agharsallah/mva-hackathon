# `modal_apps/` — the container side of a tier-3 lane

**Standing:** 2026-10-05 — written when the repository was stripped of its previous case.
**No model app ships here yet**: the roster is empty, so there is nothing to deploy.

Two halves, one contract. `mva.zoo.modal_contract` is the shared definition, imported by
both and depending on neither — it holds no `modal` and no `torch`, so the laptop can
import it without installing either.

| Half | Where | What it does |
|---|---|---|
| laptop | an adapter in `mva.zoo` | batches records, submits, polls, prices the call into the ledger |
| container | a module here | loads weights once, scores a batch, reports its own GPU seconds and weights digest |

## Modules

| Module | Holds |
|---|---|
| `_common.py` | The shared image base, the weights-volume digest helper, and the timer every lane reports through. |
| `api.py` | A CPU gateway app in front of every lane, so a caller has one address rather than one per model. |

## The wire shape

One call carries a batch of items; each item is a content-addressed id plus its named
chains. **Nothing else crosses the wire** — no labels, no cluster assignments, nothing the
container has no use for. The reply carries one score per item it could score, the weights
digest the container measured, and the GPU seconds it spent.

That last part is the point: the laptop prices every call from what the container
*reports*, not from what a billing dashboard says later.

## Adding a lane

One module here, one adapter on the laptop side, one registry fragment. The shared files
are not edited.

Deploy and run through [`tools/modal_trace.py`](../../../../tools/modal_trace.py) rather
than bare `modal`, so the command, its exit code, its duration and its output tail land in
`build/modal/trace.jsonl`.
