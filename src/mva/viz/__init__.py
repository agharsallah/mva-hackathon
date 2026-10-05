"""The HTTP API — the derived tables as JSON for a browser.

One HTTP origin in front of whatever the data layer holds, so the React app never has to
know which store answered. Today that is Parquet read in-process with DuckDB/Polars; a
route may also forward a long-running, job-shaped verb to an upstream service
(:mod:`mva.viz.proxy`) rather than reimplementing it.

Every ``/api/*`` response is the same envelope — ``{data, cached_at, source}`` — so a
chart component can render provenance without a per-endpoint special case. ``source``
names where the numbers came from; ``cached_at`` is non-null exactly when the payload was
served from the disk cache.

:mod:`mva.viz.app` is the assembly point and currently wires no routers: this is the
shell, and a route joins the list as its module lands.
"""
