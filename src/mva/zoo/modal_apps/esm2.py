"""ESM-2 650M on a Modal GPU — the iteration-6 model-generation check, masked marginals.

**What it is.** ESM-2 (Lin et al. 2022, *Science* 379:1123) is Meta's masked protein language
model; ``esm2_t33_650M_UR50D`` is the 650M-parameter checkpoint. It is ESM1b's successor and
was trained on no variant labels. Frozen protocol:
``ressources/track2/it6/esm2_check/protocol.md``.

**What it computes.** For each job ``(start, site)``: the 1,022-residue window of the public
reference sequence beginning at 0-based ``start``, the 1-based ``site`` masked, and the
model's log-probabilities over the 20 canonical residues there. One forward pass gives all 19
substitutions at the site (the official ``masked-marginals`` recipe of
``facebookresearch/esm/examples/variant-prediction/predict.py``). The laptop turns them into
``log P(alt) − log P(wt)`` (:mod:`mva.drugs.esm2_check`).

**What crosses the wire.** The public UniProt O60566 sequence and integer jobs. Nothing
patient-derived: the patient's substitution is placed on the laptop, under ``build/``.

**Licence.** MIT (``facebook/esm2_t33_650M_UR50D`` model card). Not gated.

Run only through ``tools/modal_trace.py`` (``run esm2 pilot`` / ``run esm2 full``).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import modal

from mva.zoo.modal_contract import app_name

from . import _common

KEY = "esm2"
HF_REPO = "facebook/esm2_t33_650M_UR50D"
#: Pinned to the commit the Hugging Face API returned on 2026-10-22.
HF_REVISION = "08e4846e537177426273712802403f7ba8261b6c"
TRANSFORMERS_VERSION = "4.46.3"
GPU = "L4"
VERSION = f"esm2_t33_650M_UR50D transformers=={TRANSFORMERS_VERSION} hf:{HF_REVISION[:12]}"
WEIGHTS = Path("/weights")
AMINO = "ACDEFGHIKLMNPQRSTVWY"
#: Masked copies of one window per forward pass.
FORWARD_BATCH = 8
#: Jobs per remote call: the unit of progress and of the ledger.
CHUNK = 256
FASTA = Path("build/it6/esm2/O60566.fasta")
OUT = Path("build/it6/esm2")

app = modal.App(app_name(KEY))

image = _common.with_mva(
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        f"transformers=={TRANSFORMERS_VERSION}",
        "torch==2.4.1",
        "huggingface-hub==0.26.2",
        "safetensors==0.4.5",
    )
    .env({"HF_HOME": str(WEIGHTS / "hf")}),
    KEY,
)


def groups(job_list: Sequence[tuple[int, int]], batch: int) -> list[list[tuple[int, int]]]:
    """Jobs grouped by window start, then cut into forward batches."""
    by_start: dict[int, list[tuple[int, int]]] = {}
    for start, site in job_list:
        by_start.setdefault(start, []).append((start, site))
    return [
        rows[i : i + batch]
        for _, rows in sorted(by_start.items())
        for i in range(0, len(rows), max(1, batch))
    ]


@app.cls(
    image=image,
    gpu=GPU,
    volumes={str(WEIGHTS): _common.weights_volume(KEY)},
    scaledown_window=_common.SCALEDOWN_SECONDS,
    timeout=30 * _common.MINUTES,
    max_containers=1,
)
class Scorer:
    @modal.enter()
    def load(self) -> None:
        import json

        import torch
        from huggingface_hub import snapshot_download
        from transformers import AutoTokenizer, EsmForMaskedLM

        torch.set_grad_enabled(False)
        torch.manual_seed(0)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        root = WEIGHTS / "snapshot"
        if not (root / "model.safetensors").exists():
            snapshot_download(HF_REPO, revision=HF_REVISION, local_dir=str(root),
                              allow_patterns=["*.json", "*.txt", "model.safetensors"])  # fmt: skip
            _common.weights_volume(KEY).commit()
        memo = root / "digest.json"
        if not memo.exists():
            memo.write_text(json.dumps({"sha256": _common.sha256_tree(root)}))
            _common.weights_volume(KEY).commit()
        self.digest = json.loads(memo.read_text())["sha256"]
        self.tokenizer = AutoTokenizer.from_pretrained(str(root))
        self.model = EsmForMaskedLM.from_pretrained(str(root), torch_dtype=torch.float32)
        self.model = self.model.eval().to("cuda")
        self.amino_ids = [self.tokenizer.convert_tokens_to_ids(a) for a in AMINO]

    @modal.method()
    def scan(
        self, sequence: str, job_list: list[tuple[int, int]], context: int, batch: int
    ) -> dict[str, Any]:
        """20 log-probabilities per ``(start, site)`` job, plus timing and provenance."""
        import time

        import torch

        began = time.time()
        rows: list[list[Any]] = []
        mask = self.tokenizer.mask_token_id
        with torch.inference_mode():
            for group in groups(job_list, batch):
                start = group[0][0]
                window = sequence[start : start + context]
                ids = self.tokenizer([window] * len(group), return_tensors="pt")["input_ids"]
                ids = ids.to("cuda")
                for n, (_, site) in enumerate(group):
                    spot = site - 1 - start
                    assert 0 <= spot < len(window), (start, site)
                    ids[n, spot + 1] = mask  # <cls> is token 0: residue i is token i+1
                logits = self.model(input_ids=ids).logits.float()
                log_probs = torch.log_softmax(logits, dim=-1)
                for n, (_, site) in enumerate(group):
                    at = log_probs[n, site - start][self.amino_ids]
                    rows.append([start, site, [float(v) for v in at.cpu()]])
            torch.cuda.synchronize()
        return {"rows": rows, "version": VERSION, "digest": self.digest, "gpu": GPU,
                "seconds": round(time.time() - began, 3), "context": context}  # fmt: skip


def _sequence() -> str:
    lines = FASTA.read_text().splitlines()
    return "".join(line.strip() for line in lines if not line.startswith(">"))


def _ledger(reply: dict[str, Any], note: str) -> None:
    from mva.zoo.modal_budget import Ledger

    Ledger().record(KEY, gpu=reply["gpu"], seconds=reply["seconds"], items=len(reply["rows"]),
                    scored=len(reply["rows"]), note=note)  # fmt: skip


@app.local_entrypoint()
def pilot() -> None:
    """16 public sites: timing, and batched (8) versus single-row agreement."""
    import json

    from mva.drugs.esm2_check import CONTEXT, jobs

    seq = _sequence()
    planned = jobs(len(seq), CONTEXT)
    sample = [planned[i] for i in range(0, len(planned), len(planned) // 16)][:16]
    scorer = Scorer()
    batched = scorer.scan.remote(seq, sample, CONTEXT, FORWARD_BATCH)
    single = scorer.scan.remote(seq, sample[:4], CONTEXT, 1)
    _ledger(batched, "pilot batched")
    _ledger(single, "pilot single")
    ref = {(r[0], r[1]): r[2] for r in batched["rows"]}
    worst = max(
        abs(a - b) for r in single["rows"] for a, b in zip(r[2], ref[(r[0], r[1])], strict=True)
    )
    per_job = batched["seconds"] / len(sample)
    summary = {"jobs": len(sample), "seconds": batched["seconds"], "per_job": per_job,
               "extrapolated_full_seconds": per_job * len(planned), "planned_jobs": len(planned),
               "batch_vs_single_max_abs": worst, "digest": batched["digest"],
               "version": batched["version"]}  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pilot.json").write_text(json.dumps({**summary, "rows": batched["rows"]}, indent=1))
    print(json.dumps(summary, indent=2))


@app.local_entrypoint()
def full() -> None:
    """Every planned job, in chunks; each chunk saved as it lands so a stop keeps progress."""
    import json

    from mva.drugs.esm2_check import CONTEXT, jobs

    seq = _sequence()
    planned = jobs(len(seq), CONTEXT)
    OUT.mkdir(parents=True, exist_ok=True)
    scorer = Scorer()
    total = 0.0
    for i in range(0, len(planned), CHUNK):
        part = OUT / f"chunk-{i // CHUNK:03d}.json"
        if part.exists():
            continue
        reply = scorer.scan.remote(seq, planned[i : i + CHUNK], CONTEXT, FORWARD_BATCH)
        _ledger(reply, f"full chunk {i // CHUNK}")
        part.write_text(json.dumps(reply))
        total += reply["seconds"]
        print(f"chunk {i // CHUNK}: {len(reply['rows'])} jobs in {reply['seconds']:.1f}s")
    print(f"done: {len(planned)} jobs, {total:.1f}s GPU this invocation")
