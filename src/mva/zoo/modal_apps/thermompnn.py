"""ThermoMPNN on a Modal GPU: a predicted stability change for every single-residue swap.

Not a callset scorer. ThermoMPNN (Dieckhaus et al. 2024, PNAS, PMID 38285937;
github.com/Kuhlman-Lab/ThermoMPNN, MIT) reads a protein **structure** and predicts, for each
residue and each of the 20 amino acids, **ΔΔG** (delta-delta-G: how much a substitution
changes the folding free energy, in kcal/mol). Its sign here is the repository's: **positive
= destabilising** (the mutant folds less readily), negative = stabilising. One forward pass
of ProteinMPNN's encoder embeds the whole structure; a small head then scores every swap —
so a site-saturation scan (every position × every residue) costs one structure, not 20,000.

**What crosses the wire.** A public structure (an AlphaFold DB model, CC BY 4.0) and a chain
id. No patient data: the atlas this feeds is protein-generic, and the laptop places a
patient's allele on it afterwards, in ``build/`` only.

**Weights.** Shipped inside the ThermoMPNN repository (``models/thermoMPNN_default.pt`` and
ProteinMPNN's ``vanilla_model_weights/v_48_020.pt``), cloned into the image at a pinned
commit — so this lane needs no weights volume. The digest covers both files.

    uv run --group zoo-ml python tools/modal_trace.py run thermompnn smoke   # p53 2OCJ
    uv run --group zoo-ml python tools/modal_trace.py run thermompnn atlas --uniprot O60566
    uv run --group zoo-ml python tools/modal_trace.py stop thermompnn
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import modal

from ..modal_contract import app_name
from . import _common

KEY = "thermompnn"
#: The ledger's model id for this lane (step 9, experiment E1).
LEDGER_KEY = "e1-thermompnn"
#: The E1 share of the Modal budget (step 9 plan, 2026-09-24). Checked beside the ledger guard.
SHARE_USD = 5.0
REPO_URL = "https://github.com/Kuhlman-Lab/ThermoMPNN.git"
#: ``main`` on 2026-09-24, read from the GitHub API.
COMMIT = "370f76ec62bd929f7425e311d8df04a0d094990f"
REPO = Path("/opt/ThermoMPNN")
GPU = "T4"
VERSION = f"ThermoMPNN@{COMMIT[:12]} thermoMPNN_default.pt + ProteinMPNN v_48_020"
OUT = Path("build/it4/track2-e1/thermompnn")
RAW = f"https://raw.githubusercontent.com/Kuhlman-Lab/ThermoMPNN/{COMMIT}"
ALPHABET = "ACDEFGHIKLMNPQRSTVWY"

app = modal.App(app_name(KEY))

image = _common.with_mva(
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git")
    .run_commands(f"git clone {REPO_URL} {REPO}", f"git -C {REPO} checkout {COMMIT}")
    .uv_pip_install(
        # The repository's own pyproject pins, plus the CUDA build of its torch.
        "torch==2.5.1",
        "torchmetrics==1.9.0",
        "pytorch-lightning==2.6.5",
        "biopython==1.88",
        "wandb==0.30.0",
        "tqdm==4.70.0",
        "pandas==2.3.3",
        "numpy==2.2.6",
        "omegaconf==2.3.1",
        "joblib==1.6.0",
        "fastapi[standard]==0.115.6",
    ),
    KEY,
)

#: The model config ``analysis/custom_inference.py`` builds, verbatim.
MODEL_CONFIG = {
    "training": {"num_workers": 8, "learn_rate": 0.001, "epochs": 100, "lr_schedule": True},
    "model": {
        "hidden_dims": [64, 32],
        "subtract_mut": True,
        "num_final_layers": 2,
        "freeze_weights": True,
        "load_pretrained": True,
        "lightattn": True,
        "lr_schedule": True,
    },
}


def rows_to_tsv(rows: list[tuple[int, str, str, float]]) -> str:
    """``position`` (1-based) · ``wt`` · ``alt`` · ``ddg`` as TSV text, self-swaps kept."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["position", "wt", "alt", "ddg"])
    writer.writerows((p, w, a, f"{d:.5f}") for p, w, a, d in rows)
    return buffer.getvalue()


@app.cls(
    image=image,
    gpu=GPU,
    scaledown_window=_common.SCALEDOWN_SECONDS,
    timeout=30 * _common.MINUTES,
    max_containers=1,
)
class Scorer:
    @modal.enter()
    def load(self) -> None:
        import os
        import sys

        import torch

        sys.path[:0] = [str(REPO), str(REPO / "analysis")]
        os.chdir(REPO)
        from omegaconf import OmegaConf
        from thermompnn_benchmarking import get_trained_model

        cfg = OmegaConf.merge(OmegaConf.load(REPO / "local.yaml"), OmegaConf.create(MODEL_CONFIG))
        cfg.platform.thermompnn_dir = str(REPO)
        model = get_trained_model(
            model_name=str(REPO / "models" / "thermoMPNN_default.pt"),
            config=cfg,
            override_custom=True,
        )
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.eval().to(self.device)
        self.digest = (
            _common.sha256_tree(REPO / "models", (".pt",))
            + ":"
            + (_common.sha256_tree(REPO / "vanilla_model_weights", (".pt",)))
        )

    def _ssm(self, request: dict[str, Any]) -> dict[str, Any]:
        """``{"pdb": text | None, "example": "2OCJ" | None, "chain": "A"}`` → every swap."""
        import tempfile

        import torch
        from datasets import Mutation
        from protein_mpnn_utils import alt_parse_PDB

        chain = str(request.get("chain", "A"))
        with tempfile.TemporaryDirectory() as tmp, _common.timed() as timer:
            if request.get("pdb"):
                path = Path(tmp) / "input.pdb"
                path.write_text(str(request["pdb"]))
            else:
                path = REPO / "examples" / f"{request.get('example', '2OCJ')}.pdb"
            parsed = alt_parse_PDB(str(path), chain)
            seq = parsed[0]["seq"]
            mutations = [
                Mutation(position=i, wildtype=wt, mutation=alt, ddG=None, pdb=parsed[0]["name"])
                for i, wt in enumerate(seq)
                if wt in ALPHABET
                for alt in ALPHABET
            ]
            with torch.no_grad():
                pred, _ = self.model(parsed, mutations)
            rows = [
                (m.position + 1, m.wildtype, m.mutation, float(out["ddG"].cpu().item()))
                for m, out in zip(mutations, pred, strict=True)
            ]
            if self.device.type == "cuda":
                torch.cuda.synchronize()
        return {
            "version": VERSION,
            "digest": self.digest,
            "gpu": GPU,
            "seconds": round(timer.seconds, 3),
            "chain": chain,
            "length": len(seq),
            "gaps": seq.count("-"),
            "items": len(mutations),
            "tsv": rows_to_tsv(rows),
        }

    @modal.method()
    def ssm(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._ssm(request)

    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def ssm_http(self, body: dict[str, Any]) -> dict[str, Any]:
        """The same scan over HTTP. Proxy auth: it spends GPU."""
        return self._ssm(body)

    @modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
    def health(self) -> dict[str, str]:
        return {"model": KEY, "version": VERSION, "digest": self.digest, "gpu": GPU}


# ── the laptop side ──────────────────────────────────────────────────────────────────────


def _guard(estimate_usd: float) -> None:
    from mva.zoo.modal_budget import BudgetExceededError, Ledger
    from mva.zoo.modal_contract import OVERHEAD_FACTOR

    ledger = Ledger()
    ledger.guard(LEDGER_KEY, estimate_usd)
    if ledger.spent(LEDGER_KEY) + estimate_usd * OVERHEAD_FACTOR > SHARE_USD:
        raise BudgetExceededError(f"{LEDGER_KEY}: next wave would pass the E1 share")


def _record(reply: dict[str, Any], note: str) -> dict[str, Any]:
    from mva.zoo.modal_budget import Ledger

    return Ledger().record(
        LEDGER_KEY,
        gpu=reply["gpu"],
        seconds=reply["seconds"],
        items=reply["items"],
        scored=reply["items"],
        note=note,
    )


def _save(reply: dict[str, Any], out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.tsv").write_text(reply["tsv"])
    meta = {k: v for k, v in reply.items() if k != "tsv"}
    (out / f"{name}.reply.json").write_text(json.dumps(meta, indent=2) + "\n")
    return out / f"{name}.tsv"


@app.local_entrypoint()
def smoke() -> None:
    """p53 core domain (PDB 2OCJ, chain A): the repository's own example, and its output."""
    import urllib.request

    from mva.zoo.modal_contract import price

    _guard(price(GPU, 300))
    reply = Scorer().ssm.remote({"example": "2OCJ", "chain": "A"})
    print(json.dumps(_record(reply, "smoke: 2OCJ chain A (the repository example)")))
    ours = _save(reply, OUT / "smoke", "2OCJ")
    with urllib.request.urlopen(f"{RAW}/examples/ThermoMPNN_inference_2OCJ.csv") as handle:
        theirs = list(csv.DictReader(io.StringIO(handle.read().decode())))
    expected = {(int(r["position"]) + 1, r["mutation"]): float(r["ddG_pred"]) for r in theirs}
    got = {
        (int(r["position"]), r["alt"]): float(r["ddg"])
        for r in csv.DictReader(ours.open(), delimiter="\t")
    }
    shared = expected.keys() & got.keys()
    worst = max(abs(expected[k] - got[k]) for k in shared)
    print(
        json.dumps(
            {"seconds": reply["seconds"], "items": reply["items"], "shared": len(shared),
             "expected": len(expected), "max_abs_diff_vs_published": round(worst, 6)}
        )
    )  # fmt: skip


@app.local_entrypoint()
def atlas(uniprot: str = "O60566", seconds_estimate: float = 600.0) -> None:
    """Every swap of one UniProt protein's AlphaFold model; TSV to ``build/``."""
    from mva.drugs.variant_atlas_sources import alphafold_pdb
    from mva.zoo.modal_contract import price

    pdb = alphafold_pdb(uniprot, Path("build/variant_atlas") / uniprot)
    _guard(price(GPU, seconds_estimate))
    reply = Scorer().ssm.remote({"pdb": pdb.read_text(), "chain": "A"})
    print(json.dumps(_record(reply, f"atlas: {uniprot} AlphaFold model, every swap")))
    path = _save(reply, OUT, uniprot)
    print(json.dumps({k: v for k, v in reply.items() if k != "tsv"}))
    print(f"wrote {path}")
