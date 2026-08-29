"""Ship a profile directory into a DuckDB warehouse on a remote box.

The toolkit's exploration side reads the delivered tables straight off disk, which is the
right thing while the numbers are still being argued about on one laptop. This side is for
after that: one typed, columnar copy of the derived tables, on a machine the team shares,
queryable in SQL.

The design decision worth restating, because it is the one people expect to be otherwise:
**DuckDB is embedded, not a service.** It is a library in your process and a file on disk,
the same arrangement as SQLite. There is no server process, no listening port and no
database user accounts. "The warehouse on the box" is a ``.duckdb`` file, and the access
control on it is the box's own SSH access — which is why no part of this module opens a
network service. See :mod:`mva.warehouse.remote`.

Nothing here is specific to this proband or this challenge. :mod:`mva.warehouse.catalog`
sniffs whatever directory it is pointed at, so a different N-of-1 case is a different
``--profile`` argument, not a fork.
"""

from .catalog import Dataset, discover
from .remote import Remote
from .stage import Staged, stage

__all__ = ["Dataset", "Remote", "Staged", "discover", "stage"]
