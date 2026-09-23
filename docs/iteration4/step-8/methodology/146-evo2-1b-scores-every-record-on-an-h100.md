# 146 — Evo 2 1B scores every record on an H100, for $7.05

**Step:** iteration 4, [step 8](../README.md) — the GPU tier on Modal. **Date:** 2026-09-23/24.
**Claims:** H079 (`P4-14`). Contract: [entry 143](143-a-gpu-lane-that-sends-two-windows-and-a-bill.md).
**Sources:** genomic only (DNA windows from the records). The clinical terms play no part in a
zero-shot DNA likelihood; the pair-rank half, which crosses both, is the step-8 re-run's.

## Question

Can Evo 2 1B (`evo2_1b_base`, Arc Institute) — a DNA language model (an autoregressive model
that predicts each base from the bases before it) — be installed on Modal and give a zero-shot
score to all 39,286 records inside the lane's $18 share?

## Hypothesis and prediction

H079 / P4-14, as filed: *"Evo 2 1B ranks the confirmed pair in the top decile of its own pair
ranking."* Prediction: the evo2 lane scores both confirmed alleles and the confirmed pair's
percentile is ≤ 10.

## What would refute it

The lane abstains on either confirmed allele, or the pair sits above the median of the lane's
ranking.

## Inputs

| input | value |
|---|---|
| windows | `build/it4/dna-windows.parquet` (entry 143): 39,286 ref/alt pairs, 8,192 bases, allele at offset 4,096, 0 clipped |
| weights | Hugging Face `arcinstitute/evo2_1b_base`, snapshot `2279e1df422c…`, file `evo2_1b_base.pt` |
| digest | `2cf1b34e95715d93fcb851cab971349e69d20acd82e532edd88fc8666a04a127` (`_common.sha256_tree`, measured in the container) |
| image | `nvcr.io/nvidia/pytorch:25.04-py3` (ships Transformer Engine + flash-attn; the Evo 2 Dockerfile's own base) + `evo2==0.6.0`, `vtx==1.1.0`, `fastapi[standard]==0.116.1` |
| GPU | H100 — the 1B checkpoint needs FP8 input projections (Transformer Engine) on a Hopper GPU (Evo 2 README) |
| window | 8,192 (the model's trained context, `configs/evo2-1b-8k.yml`; the BRCA1 notebook's window) |
| batch | 32 items per call, 8 sequences per forward pass, wave 16 calls, `max_containers = 4` |
| code | `src/mva/zoo/modal_apps/evo2.py`, card `src/mva/zoo/models.d/evo2.toml` |

**Score.** The Evo 2 BRCA1 notebook recipe (`notebooks/brca1/brca1_zero_shot_vep.ipynb`, read
2026-09-23): mean per-token log-likelihood (log-probability of each real base given the ones
before it, averaged) of the alt window minus the ref window. `score_sign = -1`, so the cached
score reads "higher = more damaging". `aux` keeps `delta_sum` (the summed delta), `delta_mean`,
`ll_ref_mean`, token counts and `recropped`. Normalisation: for an SNV mean and sum differ by
the constant `len − 1`; for an indel the mean is the length-normalised one — chosen because
the notebook uses it, and because on random bases the summed delta of a 6-base indel is ≈ ±8.5
nats from length alone (smoke, below). An insertion whose alt window exceeds 8,192 bases is
re-cropped centrally so the alt fits (`fit`, tested): 1,597 records. Right padding to a
multiple of 128 tokens never touches a causal model's real-base log-probabilities.

## Commands

```sh
uv run --group zoo-ml python tools/modal_trace.py deploy evo2           # image build 268 s (CPU)
uv run --group zoo-ml python tools/modal_trace.py run evo2 smoke        # 8 × 1,024 random bases
uv run --group zoo-ml python tools/modal_trace.py run evo2 smoke --n 32 --length 8192   # ×2: 8 vs 16 seqs/pass
curl -H "Modal-Key: …" -H "Modal-Secret: …" https://<workspace>--mva-zoo-evo2-scorer-health.modal.run
curl … -d '{"items":[…4 synthetic…]}' https://<workspace>--mva-zoo-evo2-scorer-score.modal.run
curl … -d '{"items":[…]}' https://<workspace>--mva-zoo-api-web.modal.run/score/evo2  # gateway
uv run --group zoo-ml mva-zoo score --model evo2 --dry-run
uv run --group zoo-ml mva-zoo score --model evo2       # card limit = 256: calibration
uv run --group zoo-ml mva-zoo score --model evo2       # limit removed: the rest
uv run --group zoo-ml python tools/modal_trace.py stop evo2
uv run --group zoo-ml modal app list
```

Logs: `build/it4/modal/evo2.log`, `evo2-full.out`, `trace.jsonl`, `ledger.jsonl`; checkpoints
`build/it4/evo2/batch-*.jsonl` (1,228 files).

## Observed output

**Install:** first try. No build from source: the NGC image already carries Transformer
Engine and flash-attn. One failed deploy was a syntax error in the lane file, not the stack.

**Smoke (random bases only).** Load ≈ 70 s cold (weights download to the volume on first start).
8 × 1,024 bases: 2.42 s cold pass, 0.18 s warm. The same items scored twice, in reversed order:
max |score difference| 1.2e-7 (1,024) and 3.6e-7 (8,192) — FP8 delayed scaling does not make
the score depend on batch order. 32 × 8,192: 5.39 s at 8 seqs/pass, 5.25 s at 16 — compute-bound,
so 8 kept.

**HTTP.** `GET …-scorer-health` → 200 with model, version, digest; the same URL without the
proxy headers → 401. `POST …-scorer-score` and the gateway's `POST /score/evo2` returned the
same four scores (identical in every printed digit).

**Calibration (256 real alleles):** 41.4 GPU-s, $0.0454 → $0.000177 per allele → 39,286 ×
that × 1.3 overhead ≈ $9.1 projected, under $18 at the full 8,192 window.

**Full run.**

| measure | value |
|---|---|
| records scored / total | **39,286 / 39,286** (every consequence class 100 %) |
| calls / skipped | 1,228 / 0; no error of any type |
| GPU seconds (ledger) | 6,426.4 |
| ledger $ | **$7.0497** (lane share $18) |
| $ per 1 M alleles | 179.4 |
| GPU-s per allele | 0.1636 (≈ 6.1 alleles/s per H100) |
| wall clock, remaining 39,030 | 1,983 s on ≤ 4 containers (≈ 19.7 alleles/s) |
| digest / version in every row | one each: `2cf1b34e9571…`, `evo2_1b_base@hf:2279e1df422c+evo2-0.6.0` |

**Sanity by consequence** (median damage score × 1e4, i.e. −Δmean-LL; fraction > 0):

| consequence | n | median | > 0 |
|---|---:|---:|---:|
| inframe_deletion | 277 | 5.29 | 0.84 |
| frameshift_variant | 564 | 2.32 | 0.70 |
| stop_gained | 289 | 2.27 | 0.68 |
| splice_donor_variant | 122 | 1.74 | 0.63 |
| missense_variant | 15,620 | 0.44 | 0.55 |
| intron_variant | 5,490 | 0.24 | 0.54 |
| synonymous_variant | 12,036 | 0.16 | 0.52 |
| inframe_insertion | 211 | −3.83 | 0.22 |

Among SNV classes the order is the expected one: stop_gained > splice donor > missense >
intron ≈ synonymous. Indels carry a length direction (below).

**Confirmed pair** (`[case]` rule: BUB1B's stop_gained and missense records, by allele id):

| allele_id | consequence | score (published Δmean) | `delta_sum` | allele percentile, higher = worse |
|---|---|---:|---:|---:|
| `addc19de8fa29228` | stop_gained | −9.571e-4 | −7.840 | top 5.6 % of 39,286 |
| `93e077ae83ac2642` | missense_variant | −1.918e-4 | −1.571 | top 32.1 % |

Spend outside the ledger: the three smokes and the HTTP calls (≈ 200 s wall in total, cold
starts included) are not priced by `mva-zoo score`; `modal billing report --start 2026-09-23`
returned `[]` (the day was not a complete interval) — reconciliation is pending.

## Verdict

- **Coverage half: holds.** Both confirmed alleles scored; the lane abstains on nothing.
- **Rank half: pending the step-8 re-run** by the main thread (the pair ranking combines the
  lane's allele scores; not computed here). The allele-level percentiles above are inputs to it,
  not the pair percentile H079 names.
- No confidence committed here.

## Limitations

- **Indel length direction.** Deletions skew "damaging" (inframe_deletion median highest of all)
  and insertions "benign" (inframe_insertion median negative). The mean-LL delta does not remove
  a length effect; indel scores are not comparable with SNV scores at face value.
- 1,597 insertions were re-cropped so the alt window fits 8,192 bases: their ref windows are
  shorter than the rest.
- One strand only. The notebook's optional reverse-complement averaging was not used.
- FP8 numerics: determinism checked to ~4e-7 on repeat; not checked against bf16 (the README says the
  1B model needs FP8 for numerical accuracy).
- Ledger GPU seconds exclude cold starts and idle scale-down; the Modal billing report settles it.
- Catalogue-free (trained on genomes, no variant labels); which human sequence its training set
  holds was not checked here.

## Conclusion

Evo 2 1B runs on Modal from the NGC PyTorch image with no source build, scores all 39,286
records at the paper's 8,192-base window for $7.05 of GPU (0.16 GPU-s per allele), and gives
both confirmed BUB1B alleles a score — the stop_gained in its top 6 %. Whether the pair lands in
the top decile is the step-8 re-run's to say.
