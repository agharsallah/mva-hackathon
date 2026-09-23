"""Boltz-2 on a Modal GPU: fold wild-type and variant proteins, return the confidences.

Not a callset scorer. Boltz-2 (github.com/jwohlwend/boltz, MIT) predicts a 3-D structure
from a sequence and, with it, a per-residue confidence — **pLDDT** (predicted local distance
difference test: 0–100, "how sure is the model this residue sits where it drew it"). The
lane folds the reference protein and a few one-residue variants of it and hands the
confidences back; the laptop computes the local change around the substituted residue.

**MSA, and what leaves the laptop.** An MSA (multiple sequence alignment: the protein's
relatives from other species, stacked) is what lets a structure model see which residues
evolution keeps. ``msa="server"`` asks the public ColabFold MMseqs2 server for it — for the
**reference** sequence only, which is a public protein. Every variant then reuses that
alignment with its own query row patched in, so no variant sequence ever reaches a
third-party server. ``msa="none"`` folds single-sequence.

    uv run --group zoo-ml python tools/modal_trace.py run boltz2 smoke      # ubiquitin
    uv run --group zoo-ml python tools/modal_trace.py deploy boltz2
    uv run --group zoo-ml python tools/modal_trace.py run boltz2 fold_case  # the case, build/
    uv run --group zoo-ml python tools/modal_trace.py stop boltz2
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path
from typing import Any

import modal

from ..modal_contract import app_name
from . import _common

KEY = "boltz2"
BOLTZ_VERSION = "2.2.1"
HF_REPO = "boltz-community/boltz-2"
HF_REVISION = "6fdef46d763fee7fbb83ca5501ccceff43b85607"
GPU = "H100"
WEIGHTS = Path("/weights")
OUT = Path("build/it4/boltz2")

#: Sampling. Boltz's defaults (3 recycling steps, 200 diffusion steps) — the published
#: setting — but 3 diffusion samples per input instead of 1, so the spread between samples
#: of one sequence is the noise floor a variant's change is read against.
SAMPLES = 3
RECYCLING = 3
SAMPLING_STEPS = 200
SEED = 0

#: Human ubiquitin (UniProt P0CG48, residues 1–76): public, small, famously well folded.
UBIQUITIN = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"

app = modal.App(app_name(KEY))

image = _common.with_mva(
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install(
        f"boltz[cuda]=={BOLTZ_VERSION}", "huggingface-hub==0.36.0", "fastapi[standard]==0.115.6"
    )
    .env({"HF_XET_HIGH_PERFORMANCE": "1"}),
    KEY,
)


def _yaml(sequence: str, msa: str | None) -> str:
    lines = [
        "version: 1",
        "sequences:",
        "  - protein:",
        "      id: A",
        f"      sequence: {sequence}",
    ]
    if msa is not None:
        lines.append(f"      msa: {msa}")
    return "\n".join(lines) + "\n"


def _boltz(inputs: Path, out: Path, *, samples: int, seed: int, server: bool) -> None:
    import subprocess

    command = [
        "boltz", "predict", str(inputs), "--out_dir", str(out), "--cache", str(WEIGHTS),
        "--diffusion_samples", str(samples), "--recycling_steps", str(RECYCLING),
        "--sampling_steps", str(SAMPLING_STEPS), "--seed", str(seed), "--write_full_pae",
    ]  # fmt: skip
    if server:
        command.append("--use_msa_server")
    subprocess.run(command, check=True)


def _patched_msa(csv: Path, sequence: str, target: Path) -> Path:
    """The reference alignment with its query row (row 1) replaced by ``sequence``."""
    rows = csv.read_text().splitlines()
    header, query = rows[0], rows[1].split(",", 1)
    if len(query[1]) != len(sequence):
        raise ValueError("a variant must keep the reference length to reuse its MSA")
    target.write_text("\n".join([header, f"{query[0]},{sequence}", *rows[2:]]) + "\n")
    return target


def _collect(out: Path) -> dict[str, Any]:
    """Per input: every sample's confidence JSON and pLDDT array (0–100)."""
    import numpy as np

    folds: dict[str, Any] = {}
    for pred in sorted(out.glob("boltz_results_*/predictions/*")):
        name, samples = pred.name, []
        for conf in sorted(pred.glob(f"confidence_{name}_model_*.json")):
            k = conf.stem.rsplit("_", 1)[-1]
            plddt = np.load(pred / f"plddt_{name}_model_{k}.npz")["plddt"]
            samples.append(
                {
                    "confidence": json.loads(conf.read_text()),
                    "plddt": [round(float(x) * 100, 2) for x in plddt],
                }
            )
        folds[name] = samples
    return folds


def _tarball(root: Path) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path in sorted(root.glob("boltz_results_*/predictions")):
            tar.add(path, arcname=path.parent.name)
        for path in sorted(root.glob("boltz_results_*/msa/*.csv")):
            tar.add(path, arcname=f"msa/{path.name}")
    return buffer.getvalue()


@app.cls(
    image=image,
    gpu=GPU,
    volumes={str(WEIGHTS): _common.weights_volume(KEY)},
    scaledown_window=_common.SCALEDOWN_SECONDS,
    timeout=60 * _common.MINUTES,
    max_containers=1,
)
class Scorer:
    @modal.enter()
    def load(self) -> None:
        """Weights once into the lane volume, pinned to one Hugging Face revision."""
        stamp = WEIGHTS / "DIGEST"
        if not stamp.exists():
            from huggingface_hub import snapshot_download

            snapshot_download(repo_id=HF_REPO, revision=HF_REVISION, local_dir=WEIGHTS)
            with tarfile.open(WEIGHTS / "mols.tar") as tar:
                tar.extractall(WEIGHTS)
            stamp.write_text(_common.sha256_tree(WEIGHTS, (".ckpt",)))
            _common.weights_volume(KEY).commit()
        self.digest = stamp.read_text().strip()

    def _fold(self, request: dict[str, Any]) -> dict[str, Any]:
        """``{"reference": seq, "variants": {name: seq}, "msa": "server"|"none", ...}``."""
        import tempfile

        samples = int(request.get("samples", SAMPLES))
        seed = int(request.get("seed", SEED))
        server = request.get("msa", "server") == "server"
        variants: dict[str, str] = dict(request.get("variants", {}))
        with _common.timed() as timer, tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "ref").mkdir()
            (work / "ref" / "wt.yaml").write_text(
                _yaml(request["reference"], None if server else "empty")
            )
            _boltz(work / "ref", work / "out", samples=samples, seed=seed, server=server)
            csvs = sorted(work.glob("out/boltz_results_*/msa/*.csv"))
            msa_depth = len(csvs[0].read_text().splitlines()) - 1 if csvs else 0
            if variants:
                (work / "var").mkdir()
                (work / "msa").mkdir()  # outside the input dir: boltz parses every file there
                for name, sequence in variants.items():
                    msa = (
                        str(_patched_msa(csvs[0], sequence, work / "msa" / f"{name}.csv"))
                        if csvs
                        else "empty"
                    )
                    (work / "var" / f"{name}.yaml").write_text(_yaml(sequence, msa))
                _boltz(work / "var", work / "out", samples=samples, seed=seed, server=False)
            folds = _collect(work / "out")
            archive = _tarball(work / "out")
        return {
            "version": f"boltz=={BOLTZ_VERSION}",
            "weights": f"{HF_REPO}@{HF_REVISION}",
            "digest": self.digest,
            "gpu": GPU,
            "seconds": round(timer.seconds, 3),
            "msa": "colabfold-server(reference only)" if server else "single-sequence",
            "msa_depth": msa_depth,
            "params": {
                "samples": samples,
                "seed": seed,
                "recycling": RECYCLING,
                "sampling_steps": SAMPLING_STEPS,
            },
            "folds": folds,
            "archive": archive,
        }

    @modal.method()
    def fold(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._fold(request)

    @modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
    def fold_http(self, body: dict[str, Any]) -> dict[str, Any]:
        """The same fold over HTTP, minus the binary archive. Proxy auth: it spends GPU."""
        reply = self._fold(body)
        reply.pop("archive")
        return reply

    @modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
    def health(self) -> dict[str, str]:
        return {"model": KEY, "version": f"boltz=={BOLTZ_VERSION}", "digest": self.digest}


# ── the laptop side ──────────────────────────────────────────────────────────────────────

#: A conservative partner per residue (a BLOSUM62-positive swap): the "mild change at the
#: same site" control. Proline has no BLOSUM62-positive partner; it maps to alanine.
CONSERVATIVE = dict(zip("ARNDCQEGHILKMFPSTWYV", "SKDESEDAYVIRLYATSFFI", strict=True))


def _record(reply: dict[str, Any], items: int, note: str) -> dict[str, Any]:
    from mva.zoo.modal_budget import Ledger

    folded = len(reply["folds"])
    return Ledger().record(
        KEY, gpu=reply["gpu"], seconds=reply["seconds"], items=items, scored=folded, note=note
    )


def _local(plddt: list[float], site: int, radius: int = 5) -> float:
    """Mean pLDDT over residues ``site ± radius`` (``site`` 1-based)."""
    window = plddt[max(site - 1 - radius, 0) : site + radius]
    return sum(window) / len(window)


def summarise(reply: dict[str, Any], sites: dict[str, int], radius: int = 5) -> dict[str, Any]:
    """Global and local confidences per fold; local deltas of each variant versus wild type."""
    from statistics import mean

    rows: dict[str, Any] = {}
    for name, samples in reply["folds"].items():
        conf = [s["confidence"] for s in samples]
        rows[name] = {
            "samples": len(samples),
            "mean_plddt": [round(mean(s["plddt"]), 2) for s in samples],
            "ptm": [round(c.get("ptm", float("nan")), 4) for c in conf],
            "confidence_score": [round(c.get("confidence_score", float("nan")), 4) for c in conf],
        }
    wt = reply["folds"]["wt"]
    for name, site in sites.items():
        at_site = {
            n: [_local(s["plddt"], site, radius) for s in reply["folds"][n]] for n in ("wt", name)
        }
        rows[name]["site"] = site
        rows[name]["local_wt"] = [round(x, 2) for x in at_site["wt"]]
        rows[name]["local"] = [round(x, 2) for x in at_site[name]]
        rows[name]["local_delta"] = round(mean(at_site[name]) - mean(at_site["wt"]), 2)
    first = next(iter(sites.values()))
    wt_local = [_local(s["plddt"], first, radius) for s in wt]
    return {
        "radius": radius,
        "folds": rows,
        "noise_floor_wt_sample_range": round(max(wt_local) - min(wt_local), 2),
    }


def _save(reply: dict[str, Any], out: Path) -> dict[str, Any]:
    """Raw reply to ``out`` first, before any local arithmetic can fail and lose it."""
    out.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(reply["archive"]), mode="r:gz") as tar:
        tar.extractall(out, filter="data")
    meta = {k: v for k, v in reply.items() if k not in ("archive", "folds")}
    (out / "reply.json").write_text(json.dumps({**meta, "folds": reply["folds"]}) + "\n")
    return meta


def _write_summary(meta: dict[str, Any], summary: dict[str, Any], out: Path) -> None:
    (out / "summary.json").write_text(json.dumps({**meta, **summary}, indent=2) + "\n")


@app.local_entrypoint()
def smoke() -> None:
    """Ubiquitin and one surface variant of it: proves image, weights, MSA and parsing."""
    from mva.zoo.modal_budget import Ledger
    from mva.zoo.modal_contract import price

    Ledger().guard(KEY, price(GPU, 600))
    variant = UBIQUITIN[:43] + "A" + UBIQUITIN[44:]  # I44A, the textbook hydrophobic patch
    reply = Scorer().fold.remote({"reference": UBIQUITIN, "variants": {"i44a": variant}})
    print(json.dumps(_record(reply, 2, "smoke: ubiquitin wt + I44A")))
    meta = _save(reply, OUT / "smoke")
    summary = summarise(reply, {"i44a": 44})
    _write_summary(meta, summary, OUT / "smoke")
    print(json.dumps(summary, indent=2))


def case_request(
    records: Path, sequences: Path, gene: str
) -> tuple[dict[str, Any], dict[str, int]]:
    """The confirmed gene's missense allele → wild type, mutant and two controls."""
    import pandas as pd

    from mva.zoo.record_window import parse_protein_change

    frame = pd.read_parquet(records, columns=["gene", "consequence", "hgvs_p"])
    hits = frame[(frame.gene == gene) & frame.consequence.str.contains("missense_variant")]
    change = parse_protein_change(str(hits.hgvs_p.iloc[0]))
    if change is None:
        raise SystemExit(f"{gene}: no parseable missense hgvs_p")
    wt = json.loads((sequences / f"{change.accession}.json").read_text())["seq"]
    site = change.position
    if wt[site - 1] != change.ref_aa:
        raise SystemExit("reference residue mismatch: record and sequence disagree")

    def swap(pos: int, aa: str) -> str:
        return wt[: pos - 1] + aa + wt[pos:]

    distal = min(
        (i + 1 for i, aa in enumerate(wt) if aa == change.ref_aa and abs(i + 1 - site) >= 100),
        key=lambda p: abs(p - site),
    )
    variants = {
        "mut": swap(site, change.alt_aa),
        "ctrl_conservative": swap(site, CONSERVATIVE[change.ref_aa]),
        "ctrl_distal": swap(distal, change.alt_aa),
    }
    sites = {"mut": site, "ctrl_conservative": site, "ctrl_distal": distal}
    return {"reference": wt, "variants": variants, "msa": "server"}, sites


@app.local_entrypoint()
def fold_case(msa: str = "server", seed: int = SEED, identity: bool = False) -> None:
    """The case: full-length reference protein, the patient's substitution, two controls.

    ``identity`` adds the wild-type sequence once more through the variants' path (patched
    MSA, second ``boltz predict``): its local "delta" is the pipeline's own offset.
    """
    import tomllib

    from mva.zoo.modal_budget import Ledger
    from mva.zoo.modal_contract import price

    case = tomllib.loads(Path("src/mva/zoo/zoo.example.toml").read_text())["case"]
    request, sites = case_request(
        Path("build/it4/records.parquet"), Path("build/it4/protein-seq"), case["confirmed_gene"]
    )
    if identity:
        request["variants"]["wt_identity"] = request["reference"]
        sites["wt_identity"] = sites["mut"]
    request |= {"msa": msa, "seed": seed}
    Ledger().guard(KEY, price(GPU, 2400))
    reply = Scorer().fold.remote(request)
    items = 1 + len(request["variants"])
    print(json.dumps(_record(reply, items, f"fold_case: seed={seed} identity={identity}")))
    out = OUT / ("case" if seed == SEED and not identity else f"case-seed{seed}")
    meta = _save(reply, out)
    summary = summarise(reply, sites)
    _write_summary(meta, summary, out)
    print(f"wrote {out} (summary.json holds the site; build/ only)")
