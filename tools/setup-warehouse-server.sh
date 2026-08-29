#!/usr/bin/env bash
#
# Prepare an existing PostgreSQL server to host the MVA warehouse.
#
# Run this ON THE SERVER. It assumes PostgreSQL is already installed and running —
# it never installs, upgrades or restarts it, and it pins no version.
#
# What it does, all of it idempotent:
#   1. finds a way to reach the superuser (packaged, containerised, or told)
#   2. creates a login role for the warehouse
#   3. creates the database, owned by that role
#   4. creates the schemas the pipeline writes into
#   5. optionally installs the DuckDB CLI for querying while logged into the box
#   6. prints the .env block to paste on the client
#
# Re-running it on a prepared server changes nothing and re-prints the .env block.
#
# Usage:
#   ./setup-warehouse-server.sh [--db mva] [--user mva] [--password SECRET]
#                               [--schema NAME] [--docker CONTAINER]
#                               [--superuser NAME] [--maint-db NAME]
#                               [--no-duckdb] [--print-env-only] [--diagnose]
#
# If --password is omitted a strong one is generated and shown once.

set -euo pipefail

DB_NAME=mva
DB_USER=mva
DB_PASSWORD=""
SCHEMAS=(warehouse results)
INSTALL_DUCKDB=1
PRINT_ONLY=0
DIAGNOSE=0
CONTAINER=""            # set by --docker, or discovered
RUNTIME=""              # "docker", "podman", or a sudo-prefixed form
PUBLISHED_PORT=""       # host-side port when Postgres is containerised
SUPERUSER_OVERRIDE=""   # --superuser
MAINTDB_OVERRIDE=""     # --maint-db
MAINT_DB="postgres"     # resolved by probing
PROBE_LOG=()            # every (user, db) pair tried, with the error it gave

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db)             DB_NAME="$2"; shift 2 ;;
    --user)           DB_USER="$2"; shift 2 ;;
    --password)       DB_PASSWORD="$2"; shift 2 ;;
    --schema)         SCHEMAS+=("$2"); shift 2 ;;
    --docker)         CONTAINER="$2"; shift 2 ;;
    --superuser)      SUPERUSER_OVERRIDE="$2"; shift 2 ;;
    --maint-db)       MAINTDB_OVERRIDE="$2"; shift 2 ;;
    --no-duckdb)      INSTALL_DUCKDB=0; shift ;;
    --print-env-only) PRINT_ONLY=1; shift ;;
    --diagnose)       DIAGNOSE=1; shift ;;
    -h|--help)        sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
note() { printf '    \033[33m·\033[0m %s\n' "$*"; }

# ── 0. Find a way in ─────────────────────────────────────────────────────────
#
# Three arrangements exist in the wild, and guessing wrong produces a confusing auth
# error rather than an obvious one, so each is tried in turn:
#
#   1. MVA_PSQL_SUPER — you told us exactly how to connect. Always wins.
#   2. Postgres in a container. The superuser lives *inside* it, so there is no local
#      `postgres` OS user to sudo to and the packaged guess cannot work.
#   3. A packaged Postgres owned by the `postgres` OS user — the Debian/Ubuntu default.
#
# Within an arrangement, *which* superuser and *which* maintenance database still have
# to be discovered. Both are routinely non-default: an image built with
# POSTGRES_USER=abdu has no `postgres` role, and — the failure this exists to prevent —
# `psql -U abdu` with no `-d` tries to open a database called `abdu`, which the image
# only creates when POSTGRES_DB is unset. So candidates are probed as pairs.

find_runtime() {
  local candidate
  for candidate in "docker" "podman" "sudo docker" "sudo podman"; do
    command -v "${candidate%% *}" >/dev/null 2>&1 || continue
    if $candidate ps >/dev/null 2>&1; then echo "$candidate"; return 0; fi
  done
  return 1
}

find_pg_containers() {
  $1 ps --format '{{.Names}}\t{{.Image}}' 2>/dev/null \
    | awk -F'\t' 'tolower($2) ~ /postgres|postgis|timescale|pgvector/ { print $1 }'
}

# Read a variable out of the container's environment, empty if absent.
container_env() {
  $RUNTIME exec "$CONTAINER" printenv "$1" 2>/dev/null | tr -d '\r' || true
}

# Unique, order-preserving.
dedupe() { awk 'NF && !seen[$0]++'; }

superuser_candidates() {
  {
    [[ -n "$SUPERUSER_OVERRIDE" ]] && echo "$SUPERUSER_OVERRIDE"
    [[ -n "$CONTAINER" ]] && container_env POSTGRES_USER
    echo postgres
  } | dedupe
}

maintdb_candidates() {
  {
    [[ -n "$MAINTDB_OVERRIDE" ]] && echo "$MAINTDB_OVERRIDE"
    echo postgres
    if [[ -n "$CONTAINER" ]]; then
      container_env POSTGRES_DB
      container_env POSTGRES_USER      # the image names the default db after the user
    fi
    echo template1                     # always present, even on a stripped cluster
  } | dedupe
}

# Try one (command, database) pair. Records the failure and returns non-zero.
probe() {
  local db="$1"; shift
  local -a cmd=("$@")
  local err
  if err=$("${cmd[@]}" -d "$db" -v ON_ERROR_STOP=1 -qtA -c 'SELECT 1' 2>&1); then
    return 0
  fi
  PROBE_LOG+=("${cmd[*]} -d $db
        → $(echo "$err" | head -2 | tr '\n' ' ')")
  return 1
}

say "Finding the database"

RESOLVED=0
declare -a PSQL_BASE=()

if [[ -n "${MVA_PSQL_SUPER:-}" ]]; then
  read -r -a PSQL_BASE <<< "$MVA_PSQL_SUPER"
  ok "using MVA_PSQL_SUPER"
  for db in $(maintdb_candidates); do
    if probe "$db" "${PSQL_BASE[@]}"; then MAINT_DB="$db"; RESOLVED=1; break; fi
  done
else
  # Prefer a container when one is named, or when the packaged path plainly is not there.
  if [[ -n "$CONTAINER" ]] || ! command -v psql >/dev/null 2>&1 \
     || ! sudo -n -u postgres psql -tAc 'SELECT 1' >/dev/null 2>&1; then
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
    for su in $(superuser_candidates); do
      for db in $(maintdb_candidates); do
        if probe "$db" $RUNTIME exec -i "$CONTAINER" psql -U "$su"; then
          read -r -a PSQL_BASE <<< "$RUNTIME exec -i $CONTAINER psql -U $su"
          MAINT_DB="$db"; RESOLVED=1
          ok "superuser '$su', maintenance database '$db'"
          break 2
        fi
      done
    done
    # The port inside the container is always 5432 regardless of what is mapped on the
    # host. `|| true` is load-bearing: `docker port` exits non-zero when nothing is
    # published, which would abort the script at the moment it must detect that.
    PUBLISHED_PORT=$($RUNTIME port "$CONTAINER" 5432/tcp 2>/dev/null \
                     | head -1 | sed 's/.*://' | tr -d '\r' || true)
  else
    for db in $(maintdb_candidates); do
      if probe "$db" sudo -u postgres psql; then
        read -r -a PSQL_BASE <<< "sudo -u postgres psql"
        MAINT_DB="$db"; RESOLVED=1
        ok "packaged Postgres, maintenance database '$db'"
        break
      fi
    done
  fi
fi

if [[ $RESOLVED -eq 0 ]]; then
  echo >&2
  echo "Could not reach a PostgreSQL superuser. Everything tried, with the real error:" >&2
  echo >&2
  printf '    %s\n\n' "${PROBE_LOG[@]}" >&2
  echo "Fix it by naming what is true for this server:" >&2
  echo >&2
  echo "    --docker <container>     which container Postgres runs in" >&2
  echo "                             list them: ${RUNTIME:-docker} ps" >&2
  echo "    --superuser <name>       the role with CREATEDB/CREATEROLE" >&2
  echo "    --maint-db <name>        an existing database to connect through" >&2
  echo >&2
  echo "Or give the whole connection yourself:" >&2
  echo "    MVA_PSQL_SUPER=\"${RUNTIME:-docker} exec -i <container> psql -U <role>\" \\" >&2
  echo "        ./setup-warehouse-server.sh" >&2
  echo >&2
  echo "To see what the container declares:" >&2
  echo "    ${RUNTIME:-docker} exec ${CONTAINER:-<container>} printenv | grep -i postgres" >&2
  exit 1
fi

# Every later call goes through these, so the resolved maintenance database is used
# consistently and no call site has to remember it.
psql_super() { "${PSQL_BASE[@]}" -d "$MAINT_DB" -v ON_ERROR_STOP=1 -qtA "$@"; }
psql_db()    { local db="$1"; shift; "${PSQL_BASE[@]}" -d "$db" -v ON_ERROR_STOP=1 -qtA "$@"; }

ok "postgres reachable — $(psql_super -c 'SHOW server_version')"

if [[ $DIAGNOSE -eq 1 ]]; then
  say "Diagnostics"
  note "connection: ${PSQL_BASE[*]} -d $MAINT_DB"
  note "current role: $(psql_super -c 'SELECT current_user')"
  note "is superuser: $(psql_super -c 'SELECT usesuper FROM pg_user WHERE usename = current_user')"
  note "databases: $(psql_super -c 'SELECT string_agg(datname, \", \") FROM pg_database WHERE NOT datistemplate')"
  [[ -n "$CONTAINER" ]] && note "published port: ${PUBLISHED_PORT:-none}"
  exit 0
fi

if [[ $PRINT_ONLY -eq 1 ]]; then
  DB_PASSWORD="${DB_PASSWORD:-<the password you set>}"
else

# ── 1. Role ──────────────────────────────────────────────────────────────────
say "Role '$DB_USER'"
ROLE_EXISTS=$(psql_super -c "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")
if [[ -z "$ROLE_EXISTS" ]]; then
  if [[ -z "$DB_PASSWORD" ]]; then
    DB_PASSWORD=$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 28)
    GENERATED=1
  fi
  psql_super -c "CREATE ROLE \"$DB_USER\" LOGIN PASSWORD '$DB_PASSWORD'"
  ok "created"
else
  if [[ -n "$DB_PASSWORD" ]]; then
    psql_super -c "ALTER ROLE \"$DB_USER\" PASSWORD '$DB_PASSWORD'"
    ok "already existed — password reset to the one supplied"
  else
    ok "already exists — password left unchanged"
    DB_PASSWORD="<unchanged; use the existing password>"
  fi
fi

# ── 2. Database ──────────────────────────────────────────────────────────────
say "Database '$DB_NAME'"
DB_EXISTS=$(psql_super -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")
if [[ -z "$DB_EXISTS" ]]; then
  psql_super -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\""
  ok "created, owned by $DB_USER"
else
  ok "already exists"
fi

# ── 3. Schemas ───────────────────────────────────────────────────────────────
# `warehouse` holds the ingested source tables; `results` holds what the pipeline
# derives. Keeping them apart means a re-ingest can drop and rebuild one without
# touching the other.
say "Schemas: ${SCHEMAS[*]}"
for schema in "${SCHEMAS[@]}"; do
  psql_db "$DB_NAME" -c \
    "CREATE SCHEMA IF NOT EXISTS \"$schema\" AUTHORIZATION \"$DB_USER\"" >/dev/null
  ok "$schema"
done
psql_super -c "GRANT ALL ON DATABASE \"$DB_NAME\" TO \"$DB_USER\"" >/dev/null

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
  PORT=$(psql_super -c 'SHOW port' 2>/dev/null || echo 5432)
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

   a) Republish with  -p 5432:5432  (recreates the container; the data volume survives)
   b) Reach it over an SSH tunnel to this box
   c) Put it behind a reverse proxy

   Check what is published with:  ${RUNTIME:-docker} port $CONTAINER
UNPUBLISHED
fi

cat <<'NEXT'

Before ingesting from your laptop:

  1. Can anything outside the server reach Postgres?
       Packaged:    listen_addresses = '*' in postgresql.conf, plus a pg_hba.conf
                    line for your client (prefer hostssl + scram-sha-256), then
                    sudo systemctl reload postgresql
       Container:   those files live INSIDE the container; the host-side control is
                    the published port. Check with: docker port <container>

     Safest either way is not to expose it at all and tunnel instead:
       ssh -L 5432:localhost:PORT user@server      # then PGHOST=localhost in .env

  2. From your machine:
       uv run mva-warehouse pg-check
NEXT
