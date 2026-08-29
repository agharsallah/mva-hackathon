"""Turn a profile directory into typed tables, then into shared storage.

The exploration side reads the delivered tables straight off disk, which is the right
thing while the numbers are still being argued about on one laptop. This side is for
after that: one typed, columnar copy of the derived tables in a store the team shares.

:mod:`mva.warehouse.stage` normalises a profile directory into Parquet under
``build/warehouse/``; :mod:`mva.warehouse.postgres` loads that into a hosted PostgreSQL
and runs the derivations declared in :mod:`mva.warehouse.analysis`. Bulk immutable files
live in the MinIO object store (:mod:`mva.warehouse.objects`,
:mod:`mva.warehouse.source`) and are queried in place.

Nothing here is specific to this proband or this challenge. :mod:`mva.warehouse.catalog`
sniffs whatever directory it is pointed at, so a different N-of-1 case is a different
``--profile`` argument, not a fork.
"""

from .catalog import Dataset, discover
from .stage import Staged, stage

__all__ = ["Dataset", "Staged", "discover", "stage"]
