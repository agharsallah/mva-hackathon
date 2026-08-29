#!/usr/bin/env bash
#
# Stand up an S3-compatible object store (MinIO) on this server, so bulk files can be
# queried remotely over HTTP range requests instead of being copied to a laptop or
# reached by SSHing in.
#
# Run this ON THE SERVER. It uses whatever container runtime is present (podman or
# docker) and pins no version.
#
# Usage:
#   ./setup-object-store.sh [--bucket mva] [--data-dir /srv/mva-objects]
#                           [--port 9000] [--console-port 9001]
#                           [--user mva] [--password SECRET] [--name mva-minio]
#
# If --password is omitted a strong one is generated and shown once.

set -euo pipefail

BUCKET=mva
DATA_DIR=/srv/mva-objects
PORT=9000
CONSOLE_PORT=9001
ACCESS_USER=mva
ACCESS_PASSWORD=""
NAME=mva-minio

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket)       BUCKET="$2"; shift 2 ;;
    --data-dir)     DATA_DIR="$2"; shift 2 ;;
    --port)         PORT="$2"; shift 2 ;;
    --console-port) CONSOLE_PORT="$2"; shift 2 ;;
    --user)         ACCESS_USER="$2"; shift 2 ;;
    --password)     ACCESS_PASSWORD="$2"; shift 2 ;;
    --name)         NAME="$2"; shift 2 ;;
    -h|--help)      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()  { printf '    \033[32m✓\033[0m %s\n' "$*"; }

find_runtime() {
  local candidate
  for candidate in "podman" "docker" "sudo podman" "sudo docker"; do
    command -v "${candidate%% *}" >/dev/null 2>&1 || continue
    if $candidate ps >/dev/null 2>&1; then echo "$candidate"; return 0; fi
  done
  return 1
}

say "Container runtime"
RUNTIME=$(find_runtime) || { echo "no working podman or docker found" >&2; exit 1; }
ok "$RUNTIME"

if [[ -z "$ACCESS_PASSWORD" ]]; then
  ACCESS_PASSWORD=$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 28)
  GENERATED=1
fi

say "Data directory"
mkdir -p "$DATA_DIR"
ok "$DATA_DIR ($(df -h "$DATA_DIR" | tail -1 | awk '{print $4}') free)"

say "MinIO container '$NAME'"
if $RUNTIME ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  ok "already exists — leaving it alone (remove it first to recreate)"
else
  # MinIO stores objects as plain files under DATA_DIR, so the bytes remain readable
  # with ordinary tools and are not locked inside a database.
  $RUNTIME run -d --name "$NAME" --restart unless-stopped \
    -p "${PORT}:9000" -p "${CONSOLE_PORT}:9001" \
    -e "MINIO_ROOT_USER=${ACCESS_USER}" \
    -e "MINIO_ROOT_PASSWORD=${ACCESS_PASSWORD}" \
    -v "${DATA_DIR}:/data:z" \
    quay.io/minio/minio server /data --console-address ":9001" >/dev/null
  ok "started on :${PORT} (console :${CONSOLE_PORT})"
fi

say "Bucket '$BUCKET'"
for _ in $(seq 1 30); do
  if $RUNTIME exec "$NAME" mc alias set local http://127.0.0.1:9000 \
       "$ACCESS_USER" "$ACCESS_PASSWORD" >/dev/null 2>&1; then break; fi
  sleep 1
done
if $RUNTIME exec "$NAME" mc mb --ignore-existing "local/${BUCKET}" >/dev/null 2>&1; then
  ok "ready"
else
  ok "could not create it automatically — make it in the console at :${CONSOLE_PORT}"
fi

HOST_HINT=$(hostname -f 2>/dev/null || hostname)
cat <<ENVBLOCK

────────────────────────────────────────────────────────────────────────────
Append this to .env on YOUR MACHINE:
────────────────────────────────────────────────────────────────────────────
S3_ENDPOINT=${HOST_HINT}:${PORT}
S3_ACCESS_KEY=${ACCESS_USER}
S3_SECRET_KEY=${ACCESS_PASSWORD}
S3_BUCKET=${BUCKET}
S3_USE_SSL=false
────────────────────────────────────────────────────────────────────────────
ENVBLOCK

if [[ "${GENERATED:-0}" == "1" ]]; then
  echo "The password above was generated and is shown ONCE. Save it now."
fi

cat <<NEXT

⚠  S3_USE_SSL=false sends the access key over the wire in clear text. That is fine
   over an SSH tunnel and NOT fine over the open internet. Either:

     a) tunnel:   ssh -L ${PORT}:localhost:${PORT} <user>@${HOST_HINT}
                  then S3_ENDPOINT=localhost:${PORT}
     b) put MinIO behind a TLS reverse proxy, then S3_USE_SSL=true
     c) firewall port ${PORT} to your team's addresses

   This store will hold patient-derived data. Decide before uploading.

From your machine:
   uv run mva-warehouse s3-check
NEXT
