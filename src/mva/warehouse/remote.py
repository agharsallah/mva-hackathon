"""Put the staged Parquet on a remote box and build the DuckDB file there.

DuckDB is an *embedded* database — a library linked into whatever process opens the file,
the same arrangement as SQLite. There is no daemon to start and no port to listen on, so
"the database on the server" means exactly one thing: a ``.duckdb`` file sitting on that
server's disk, opened by whoever is logged into it. Nothing in this module exposes a
network service, and that is the point — the only way in is the SSH access the box already
has, so there is no second surface to authenticate, firewall or keep patched.

Three verbs, in the order you need them:

``provision``
    Put a ``duckdb`` binary on the box. No package manager involved: the release is a
    single static executable, so it is fetched and dropped into ``~/.local/bin``.
``push``
    ``rsync`` the staged Parquet up. Restartable and delta-encoded, which matters the
    first time and is nearly free every time after.
``load``
    Run one SQL script over SSH that rebuilds every table from the Parquet it just
    received.

Every function here *builds* its command and hands it to :func:`run`, rather than shelling
out from inside the logic. That is what makes the module testable without a server, and
what lets ``--dry-run`` print exactly what would execute.
"""

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: DuckDB release fetched by :func:`provision`. Pinned: the file format is stable across
#: minor versions but the CLI's flags are not, and a warehouse built by one version should
#: be readable by the exact binary the team documented.
DUCKDB_VERSION = "1.5.5"
DUCKDB_ASSET = "duckdb_cli-linux-amd64.zip"


@dataclass(frozen=True)
class Remote:
    """Where the warehouse lives on the far side of an SSH connection.

    ``host`` is anything ``ssh`` accepts — a bare hostname, ``user@host``, or an alias out
    of ``~/.ssh/config``, which is the tidiest option since it keeps the port, key and user
    out of every command line. ``root`` is the directory the Parquet and the database file
    share; ``~`` is expanded by the remote shell, not this one.
    """

    host: str
    root: str = "~/warehouse"
    database: str = "profile.duckdb"
    binary: str = "~/.local/bin/duckdb"
    ssh: str = "ssh"

    @property
    def parquet_dir(self) -> str:
        """Where pushed Parquet lands on the remote box."""
        return f"{self.root}/parquet"

    @property
    def database_path(self) -> str:
        """The remote path of the DuckDB file itself."""
        return f"{self.root}/{self.database}"

    def ssh_command(self, script: str) -> list[str]:
        """An ``ssh`` invocation running ``script`` through the remote shell."""
        return [*shlex.split(self.ssh), self.host, script]

    def rsync_command(self, source: Path) -> list[str]:
        """An ``rsync`` invocation mirroring ``source`` into the remote Parquet directory.

        ``--delete`` keeps the remote a mirror rather than an accumulation: a table renamed
        or dropped locally must not linger upstream, or the next load rebuilds a stale one.
        """
        return [
            "rsync", "--archive", "--compress", "--partial", "--delete",
            "--human-readable", "--info=stats1",
            "-e", self.ssh,
            f"{str(source).rstrip('/')}/", f"{self.host}:{self.parquet_dir}/",
        ]


def run(command: list[str], dry_run: bool = False, check: bool = True) -> int:
    """Execute one command, or print it and do nothing when ``dry_run`` is set."""
    if dry_run:
        print("  " + " ".join(shlex.quote(part) for part in command))
        return 0
    result = subprocess.run(command)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}")
    return result.returncode


def provision_script(remote: Remote) -> str:
    """The shell script that installs DuckDB on the remote box.

    Idempotent by design — re-running it on a box that already has the right version is a
    no-op, so it is safe to make it the first step of every deployment rather than a
    one-time ritual someone has to remember whether they performed.
    """
    return f"""set -euo pipefail
mkdir -p "$(dirname {remote.binary})" {remote.parquet_dir}
if [ -x {remote.binary} ] && {remote.binary} --version | grep -q '{DUCKDB_VERSION}'; then
  echo "duckdb {DUCKDB_VERSION} already installed at {remote.binary}"
  exit 0
fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
url=https://github.com/duckdb/duckdb/releases/download/v{DUCKDB_VERSION}/{DUCKDB_ASSET}
echo "fetching $url"
curl -fsSL "$url" -o "$tmp/duckdb.zip"
unzip -oq "$tmp/duckdb.zip" -d "$tmp"
install -m 0755 "$tmp/duckdb" {remote.binary}
{remote.binary} --version
"""


def preflight_script(remote: Remote) -> str:
    """A read-only script reporting whether the box can host the warehouse at all.

    Run before anything is uploaded. It answers the three questions that actually stop a
    deployment — is there a fetch tool, is there an unzipper, is there disk — while
    changing nothing, so a failure here costs nothing to retry.
    """
    return f"""set -u
echo "host:    $(hostname)"
echo "os:      $(uname -sr)"
echo "arch:    $(uname -m)"
for tool in curl unzip rsync; do
  if command -v "$tool" >/dev/null 2>&1; then echo "tool:    $tool ok"
  else echo "tool:    $tool MISSING"; fi
done
if [ -x {remote.binary} ]; then echo "duckdb:  $({remote.binary} --version)"
else echo "duckdb:  not installed"; fi
echo "disk:"
df -h "$(dirname {remote.root} 2>/dev/null || echo .)" 2>/dev/null | tail -2
"""


def load_sql(tables: list[str], remote: Remote) -> str:
    """SQL that rebuilds every table in the database from the pushed Parquet.

    Paths here are *relative* to the warehouse root, and the caller is responsible for
    ``cd``-ing there first. That is not a stylistic choice: a ``~`` inside a SQL string
    literal is not expanded by anyone — the remote shell never sees it, and DuckDB treats
    it as a literal directory named ``~`` — so ``read_parquet('~/warehouse/x.parquet')``
    fails with a file-not-found on a box where the file plainly exists.

    ``CREATE OR REPLACE`` makes a load fully repeatable: the database is a *derived*
    artefact of the Parquet beside it, never a thing accumulating edits, so a bad run is
    fixed by fixing the Parquet and loading again rather than by unpicking state.
    """
    statements = [
        f"CREATE OR REPLACE TABLE {table} AS "
        f"SELECT * FROM read_parquet('parquet/{table}.parquet');"
        for table in sorted(tables)
    ]
    verify = (
        "SELECT table_name, estimated_size AS rows "
        "FROM duckdb_tables() ORDER BY table_name;"
    )
    return "\n".join(statements) + "\n" + verify + "\n"


def load_command(remote: Remote, sql: str) -> list[str]:
    """An ``ssh`` invocation feeding ``sql`` to the remote ``duckdb`` on stdin.

    The SQL is embedded in a quoted heredoc so the remote shell performs no expansion on
    it — a ``$`` or a backtick inside a table description must reach DuckDB untouched.
    """
    script = (
        f"set -euo pipefail\ncd {remote.root}\n"
        f"{remote.binary} -box {remote.database} <<'MVA_WAREHOUSE_SQL'\n"
        f"{sql}MVA_WAREHOUSE_SQL\n"
    )
    return remote.ssh_command(script)


def query_command(remote: Remote, sql: str) -> list[str]:
    """An ``ssh`` invocation running one ad-hoc query against the remote warehouse."""
    return remote.ssh_command(
        f"cd {remote.root} && {remote.binary} -box -readonly {remote.database} "
        f"{shlex.quote(sql)}"
    )
