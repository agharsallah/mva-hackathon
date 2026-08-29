#!/usr/bin/env bash
#
# Prepare an existing PostgreSQL server to host the MVA warehouse.
#
# Run this ON THE SERVER, as a user who can reach the `postgres` superuser role
# (typically via `sudo -u postgres`). It assumes Postgres is already installed and
# running — it never installs, upgrades or restarts it, and it pins no version.
#
# What it does, all of it idempotent:
#   1. creates a login role for the warehouse
#   2. creates the database, owned by that role
#   3. creates the schemas the pipeline writes into
#   4. optionally installs the DuckDB CLI for anyone wanting to query from the box
#   5. prints the .env block to paste on the client
#
# Re-running it on a prepared server changes nothing and re-prints the .env block.
#
# Usage:
#   ./setup-warehouse-server.sh [--db mva] [--user mva] [--password SECRET]
#                               [--schema warehouse] [--no-duckdb] [--print-env-only]
#
# If --password is omitted a strong one is generated and shown once.

set -euo pipefail

DB_NAME=mva
DB_USER=mva
DB_PASSWORD=""
SCHEMAS=(warehouse results)
INSTALL_DUCKDB=1
PRINT_ONLY=0
CONTAINER=""          # set by --docker, or discovered
RUNTIME=""            # "docker", "podman", or the sudo-prefixed form
PUBLISHED_PORT=""     # host-side port when Postgres is containerised

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)             DB_NAME="$2"; shift 2 ;;
    --user)           DB_USER="$2"; shift 2 ;;
    --password)       DB_PASSWORD="$2"; shift 2 ;;
    --schema)         SCHEMAS+=("$2"); shift 2 ;;
    --docker)         CONTAINER="$2"; shift 2 ;;
    --no-duckdb)      INSTALL_DUCKDB=0; shift ;;
    --print-env-only) PRINT_ONLY=1; shift ;;
    -h|--help)        sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()  { printf '    \033[32m✓\033[0m %s\n' "$*"; }

# ── 0. Find a way in ─────────────────────────────────────────────────────────
#
# There are three arrangements in the wild and the script tries each in turn, because
# guessing wrong is the difference between "it just worked" and a confusing auth error:
#
#   1. MVA_PSQL_SUPER — you told us exactly how to connect. Always wins.
#   2. A Postgres in a container. The superuser lives *inside* it, so there is no local
#      `postgres` OS user to sudo to and the stock guess cannot work.
#   3. A packaged Postgres owned by the `postgres` OS user — the Debian/Ubuntu default.

# Find a working container runtime, preferring one that needs no sudo.
find_runtime() {
  local candidate
  for candidate in "docker" "podman" "sudo docker" "sudo podman"; do
    command -v "${candidate%% *}" >/dev/null 2>&1 || continue
    if $candidate ps >/dev/null 2>&1; then echo "$candidate"; return 0; fi
  done
  return 1
}

# Names of running containers whose image looks like a Postgres.
find_pg_containers() {
  $1 ps --format '{{.Names}}\t{{.Image}}' 2>/dev/null \
    | awk -F'\t' 'tolower($2) ~ /postgres|postgis|timescale|pgvector/ { print $1 }'
}

# The image's superuser: POSTGRES_USER if the container was built with one, else postgres.
container_superuser() {
  local user
  user=$($RUNTIME exec "$1" printenv POSTGRES_USER 2>/dev/null | tr -d '\r') || true
  echo "${user:-postgres}"
}

say "Finding the database"

if [[ -n "${MVA_PSQL_SUPER:-}" ]]; then
  read -r -a PSQL_SUPER <<< "$MVA_PSQL_SUPER"
  ok "using MVA_PSQL_SUPER"
else
  # A container was named, or one can be discovered.
  if [[ -n "$CONTAINER" ]] || ! sudo -n -u postgres psql -tAc 'SELECT 1' >/dev/null 2>&1; then
    if RUNTIME=$(find_runtime); then
      if [[ -z "$CONTAINER" ]]; then
        mapfile -t FOUND < <(find_pg_containers "$RUNTIME")
        if [[ ${#FOUND[@]} -eq 1 ]]; then
          CONTAINER="${FOUND[0]}"
          ok "discovered Postgres container '$CONTAINER' via $RUNTIME"
        elif [[ ${#FOUND[@]} -gt 1 ]]; then
          echo "several Postgres containers are running:" >&2
          printf '    %s\n' "${FOUND[@]}" >&2
          echo "Pick one with --docker <name>." >&2
          exit 1
        fi
      else
        ok "using container '$CONTAINER' via $RUNTIME"
      fi
    fi
  fi

  if [[ -n "$CONTAINER" ]]; then
    SUPERUSER=$(container_superuser "$CONTAINER")
    read -r -a PSQL_SUPER <<< "$RUNTIME exec -i $CONTAINER psql -U $SUPERUSER"
    # The port inside the container is almost always 5432; what the client needs is the
    # port published on the host, which is a different question and a common way to get
    # a .env that cannot connect.
    # `|| true` is load-bearing: with `set -o pipefail`, `docker port` exits non-zero
    # when nothing is published, which would abort the script at exactly the moment we
    # are trying to detect and explain that situation.
    PUBLISHED_PORT=$($RUNTIME port "$CONTAINER" 5432/tcp 2>/dev/null \
                     | head -1 | sed 's/.*://' | tr -d '\r' || true)
  else
    PSQL_SUPER=(sudo -u postgres psql)
  fi
fi

PSQL_SUPER+=(-v ON_ERROR_STOP=1 -qtA)
# Same connection, but against the warehouse database rather than the maintenance one.
psql_db() { "${PSQL_SUPER[@]}" -d "$1" "${@:2}"; }

command -v "${PSQL_SUPER[0]}" >/dev/null || {
  echo "'${PSQL_SUPER[0]}' not found — is PostgreSQL (or your container runtime) installed?" >&2
  exit 1; }

if ! "${PSQL_SUPER[@]}" -c 'SELECT 1' >/dev/null 2>&1; then
  echo "cannot reach the postgres superuser role using:" >&2
  echo "    ${PSQL_SUPER[*]}" >&2
  echo >&2
  echo "If PostgreSQL runs in a container, name it:" >&2
  echo "    ./setup-warehouse-server.sh --docker <container-name>" >&2
  echo "List them with:  docker ps" >&2
  echo >&2
  echo "Or set MVA_PSQL_SUPER to a command that connects as a superuser:" >&2
  echo "    MVA_PSQL_SUPER=\"docker exec -i pg psql -U postgres\" ./setup-warehouse-server.sh" >&2
  exit 1
fi
ok "postgres reachable — $("${PSQL_SUPER[@]}" -c 'SHOW server_version')"

if [[ $PRINT_ONLY -eq 1 ]]; then
  DB_PASSWORD="${DB_PASSWORD:-<the password you set>}"
else

# ── 1. Role ──────────────────────────────────────────────────────────────────
say "Role '$DB_USER'"
ROLE_EXISTS=$("${PSQL_SUPER[@]}" -c "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")
if [[ -z "$ROLE_EXISTS" ]]; then
  if [[ -z "$DB_PASSWORD" ]]; then
    DB_PASSWORD=$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 28)
    GENERATED=1
  fi
  "${PSQL_SUPER[@]}" -c "CREATE ROLE \"$DB_USER\" LOGIN PASSWORD '$DB_PASSWORD'"
  ok "created"
else
  if [[ -n "$DB_PASSWORD" ]]; then
    "${PSQL_SUPER[@]}" -c "ALTER ROLE \"$DB_USER\" PASSWORD '$DB_PASSWORD'"
    ok "already existed — password reset to the one supplied"
  else
    ok "already exists — password left unchanged"
    DB_PASSWORD="<unchanged; use the existing password>"
  fi
fi

# ── 2. Database ──────────────────────────────────────────────────────────────
say "Database '$DB_NAME'"
DB_EXISTS=$("${PSQL_SUPER[@]}" -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")
if [[ -z "$DB_EXISTS" ]]; then
  "${PSQL_SUPER[@]}" -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\""
  ok "created, owned by $DB_USER"
else
  ok "already exists"
fi

# ── 3. Schemas ───────────────────────────────────────────────────────────────
# `warehouse` holds the ingested source tables; `results` holds what the pipeline
# derives. Keeping them apart means a re-ingest can safely drop and rebuild one
# without touching the other.
say "Schemas: ${SCHEMAS[*]}"
for schema in "${SCHEMAS[@]}"; do
  psql_db "$DB_NAME" -c \
    "CREATE SCHEMA IF NOT EXISTS \"$schema\" AUTHORIZATION \"$DB_USER\"" >/dev/null
  ok "$schema"
done
psql_db "$DB_NAME" -c "GRANT ALL ON DATABASE \"$DB_NAME\" TO \"$DB_USER\"" >/dev/null

# ── 4. DuckDB CLI on the box (optional) ──────────────────────────────────────
if [[ $INSTALL_DUCKDB -eq 1 ]]; then
  say "DuckDB CLI"
  if command -v duckdb >/dev/null 2>&1 || [[ -x "$HOME/.local/bin/duckdb" ]]; then
    ok "already installed"
  elif command -v curl >/dev/null && command -v unzip >/dev/null; then
    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    arch=$(uname -m); case "$arch" in
      x86_64) asset=duckdb_cli-linux-amd64.zip ;;
      aarch64|arm64) asset=duckdb_cli-linux-arm64.zip ;;
      *) asset="" ;;
    esac
    if [[ -n "$asset" ]] && curl -fsSL \
        "https://github.com/duckdb/duckdb/releases/latest/download/$asset" -o "$tmp/d.zip"; then
      unzip -oq "$tmp/d.zip" -d "$tmp"
      mkdir -p "$HOME/.local/bin"
      install -m 0755 "$tmp/duckdb" "$HOME/.local/bin/duckdb"
      ok "installed $("$HOME/.local/bin/duckdb" --version) to ~/.local/bin/duckdb"
    else
      ok "skipped (no release for $arch, or download failed) — not required"
    fi
  else
    ok "skipped (needs curl and unzip) — not required"
  fi
fi

fi  # PRINT_ONLY

# ── 5. The .env block ────────────────────────────────────────────────────────
HOST_HINT=$(hostname -f 2>/dev/null || hostname)

# Which port the *client* needs. For a containerised Postgres this is emphatically not
# `SHOW port`, which reports 5432 from inside the container regardless of what is
# published on the host — a .env built from it looks right and cannot connect.
if [[ -n "$CONTAINER" ]]; then
  if [[ -n "$PUBLISHED_PORT" ]]; then
    PORT="$PUBLISHED_PORT"
  else
    PORT="5432"
    NOT_PUBLISHED=1
  fi
else
  PORT=$("${PSQL_SUPER[@]}" -c 'SHOW port' 2>/dev/null || echo 5432)
fi

cat <<ENVBLOCK

────────────────────────────────────────────────────────────────────────────
Setup complete. Put this in .env at the repository root ON YOUR MACHINE:
────────────────────────────────────────────────────────────────────────────
PGHOST=$HOST_HINT
PGPORT=$PORT
PGDATABASE=$DB_NAME
PGUSER=$DB_USER
PGPASSWORD=$DB_PASSWORD
PGSCHEMA=${SCHEMAS[0]}
PGRESULTSCHEMA=${SCHEMAS[1]:-results}
────────────────────────────────────────────────────────────────────────────
ENVBLOCK

if [[ "${GENERATED:-0}" == "1" ]]; then
  echo "The password above was generated and is shown ONCE. Save it now."
fi

if [[ "${NOT_PUBLISHED:-0}" == "1" ]]; then
  cat <<UNPUBLISHED

⚠  Container '$CONTAINER' does not publish port 5432 to the host, so nothing outside
   it can connect yet — not even this server. Pick one:

   a) Republish the container with  -p 5432:5432  (recreates it; the data volume survives)
   b) Connect through the container network from this box only
   c) Reverse-proxy or tunnel it

   Check what is published with:  ${RUNTIME:-docker} port $CONTAINER
UNPUBLISHED
fi

cat <<'NEXT'

Two things to check before ingesting from your laptop:

  1. Is the server accepting remote connections at all?
       listen_addresses = '*'      in postgresql.conf
       a host line for your client in pg_hba.conf   (prefer hostssl + scram-sha-256)
     Then: sudo systemctl reload postgresql
     If Postgres runs in a container, those files are INSIDE it — the host-side
     control is the published port instead. Check with: docker port <container>

     If you only ever connect through an SSH tunnel, leave all of that alone — that
     is the safer default, and the client supports it:
       ssh -L 5432:localhost:PORT user@server     # then PGHOST=localhost in .env

  2. From your machine:
       uv run mva-warehouse pg-check
NEXT
