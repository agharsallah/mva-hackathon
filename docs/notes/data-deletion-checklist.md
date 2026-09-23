# Data deletion checklist — everything to delete within 30 days of the close

**Standing:** opened 2026-09-24 (iteration 4, step 8, plan §12 O9). Holds until the deletion is
done and the confirmation email is sent. No other doc owned this list; the reason the data may
not stay is [`no-patient-data-in-the-repository.md`](no-patient-data-in-the-repository.md).

**Rule** (challenge terms, `ideation/hackathon-intel.md`): delete **all** data within 30 days of
the close — local, cloud, notebooks, private repos, derived datasets — then email
RarediseaserealkidMVAhackathon2026@synapse.org to confirm.

## Modal (workspace `abdu-devhub`, environment `main`)

Volumes hold **weights only**. They were checked on 2026-09-24 with `modal volume ls`: no input, window or score is on them. They are listed here so nothing gets forgotten.

| object | kind | holds | delete with |
|---|---|---|---|
| `mva-zoo-ntv2-weights` | volume | NT-v2 500M weights + digest | `modal volume delete mva-zoo-ntv2-weights` |
| `mva-zoo-evo2-weights` | volume | Evo 2 1B weights (HF cache) | `modal volume delete mva-zoo-evo2-weights` |
| `mva-zoo-esmc-weights` | volume | ESM-C 600M weights + digest | `modal volume delete mva-zoo-esmc-weights` |
| `mva-zoo-boltz2-weights` | volume | Boltz-2 checkpoints, CCD molecules | `modal volume delete mva-zoo-boltz2-weights` |
| `mva-zoo-{ntv2,evo2,esmc,boltz2,api}` | apps (stopped) | code only; logs keep container stdout | `modal app list` → nothing to delete beyond logs; Modal expires them |
| proxy token (created 2026-09-23) | workspace credential | auth for the HTTP endpoints | `modal workspace proxy-tokens delete <id>` |

Boltz-2 also sent the **reference** BubR1 sequence (no patient substitution) to the public
ColabFold MSA server (entry 147). The sequence is public, so nothing needs deleting there.

## Local (`build/`, gitignored)

| path | holds |
|---|---|
| `build/it4/dna-windows.parquet` (+ provenance) | patient DNA windows, 39,286 × 2 |
| `build/it4/records.parquet` | coordinates + protein windows |
| `build/it4/{ntv2,evo2,esmc,esm2}/` | per-lane score checkpoints |
| `build/it4/boltz2/` | folded structures, pLDDT, PAE |
| `build/it4/modal/` | ledger, trace, logs, proxy token (`proxy-token.json`) |
| `build/`, `ressources/` data, the warehouse | everything else from steps 0–7 |

## Done when

- [ ] every Modal volume above deleted; `modal volume list` shows no `mva-zoo-*`
- [ ] proxy token deleted
- [ ] local `build/` and the warehouse dropped
- [ ] confirmation email sent
