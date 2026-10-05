"""``sepiq-zoo-api`` — one HTTP front door for every GPU lane (CPU only, proxy-auth).

Each lane app already serves its own endpoint; this gateway gives the zoo one URL and one
vocabulary, so a client never needs to know which lane is deployed where:

* ``GET  /models`` — every lane app the gateway can reach, with its health reply;
* ``POST /score/{key}`` — ``{"items": [Item, ...]}`` in, the lane's
  :class:`~sepiq.zoo.modal_contract.Reply` out, forwarded to ``sepiq-zoo-<key>``'s
  ``Scorer.score_batch``.

Proxy auth (``Modal-Key`` / ``Modal-Secret`` headers) because every call spends GPU money.
The gateway runs on a fraction of a CPU core and scales to zero; it keeps nothing.
"""

from __future__ import annotations

from typing import Any

import modal

from ..modal_contract import CLASS_NAME, METHOD, app_name
from ._common import SCALEDOWN_SECONDS, with_mva

LANES = ("ntv2", "evo2", "esmc", "boltz2")

image = with_mva(
    modal.Image.debian_slim(python_version="3.12").uv_pip_install("fastapi[standard]==0.118.0"),
    "api",
)
app = modal.App(app_name("api"), image=image)


@app.function(cpu=0.25, scaledown_window=SCALEDOWN_SECONDS, max_containers=2)
@modal.asgi_app(requires_proxy_auth=True)
def web() -> Any:
    from fastapi import FastAPI, HTTPException

    api = FastAPI(title="sepiq-zoo", description=__doc__)

    def lane(key: str) -> Any:
        if key not in LANES:
            raise HTTPException(404, f"unknown lane {key!r}; known: {', '.join(LANES)}")
        try:
            return modal.Cls.from_name(app_name(key), CLASS_NAME)()
        except modal.exception.NotFoundError as missing:
            raise HTTPException(503, f"lane {key} is not deployed") from missing

    @api.get("/models")
    def models() -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in LANES:
            try:
                modal.Cls.from_name(app_name(key), CLASS_NAME).hydrate()
                out[key] = {"app": app_name(key), "methods": [METHOD], "deployed": True}
            # A lane that is down is reported in the reply, not raised.
            except Exception as error:
                out[key] = {"app": app_name(key), "deployed": False, "error": str(error)[:200]}
        return out

    @api.post("/score/{key}")
    def score(key: str, body: dict[str, Any]) -> Any:
        items = body.get("items")
        if not isinstance(items, list) or not items:
            raise HTTPException(422, "body must be {'items': [Item, ...]}")
        if len(items) > 256:
            raise HTTPException(413, "at most 256 items per call")
        return getattr(lane(key), METHOD).remote(items)

    return api
