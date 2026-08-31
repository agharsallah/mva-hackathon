"""The viz API — the warehouse and the read store as JSON for a browser.

One HTTP origin in front of three very different back ends, so the React app never has
to know which is which:

* **PostgreSQL** (via DuckDB, as everywhere else in this repo) for the callset tables.
* **The object store** for read-level aggregates, read with column-pruned Parquet scans.
* **`mva-reads-api`** for anything that needs a pass over 1.07 billion reads, proxied
  rather than reimplemented.

Every ``/api/*`` response is the same envelope — ``{data, cached_at, source}`` — so a
chart component can render provenance without a per-endpoint special case. ``source``
names where the numbers came from; ``cached_at`` is non-null exactly when the payload
was served from the disk cache.
"""
