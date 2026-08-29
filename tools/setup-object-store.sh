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
#   ./setup-object-store.sh [--bucket mva] [--data-dir ~/mva-objects]
#                           [--port 9012] [--console-port 9013]
#                           [--user mva] [--password SECRET] [--name mva-minio]
#
# If --password is omitted a strong one is generated and shown once.

set -euo pipefail

BUCKET=mva
# Under rootless podman the container runs as *you*, so a path outside your home is a
# common cause of a container that starts and immediately dies on a write.
DATA_DIR="${HOME}/mva-objects"
# Host-side published ports for this project: 9012 API, 9013 console.
#
# Not MinIO's own 9000/9001, and not 9002/9003 — both were already taken on this server.
# Podman reports a port clash only at container *start*, so a collision leaves a container
# stuck in `Created` with an empty log and no error anywhere; the preflight below catches
# it instead. The ports INSIDE the container are always 9000 (API) and 9001 (console),
# whatever is published here.
PORT=9012
CONSOLE_PORT=9013
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

# A port that is already taken is the single most likely reason this fails, and podman
# reports it only at *start* time — leaving a container stuck in `Created` with an empty
# log, which looks like nothing happened at all. Check first and say so plainly.
port_owner() {
  if command -v ss >/dev/null 2>&1; then
    ss -lntp 2>/dev/null | awk -v p=":$1\$" '$4 ~ p {print $0; exit}'
  elif command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN 2>/dev/null | tail -1
  fi
}

say "Ports ${PORT} and ${CONSOLE_PORT}"
CLASH=0
for candidate in "$PORT" "$CONSOLE_PORT"; do
  owner=$(port_owner "$candidate")
  if [[ -n "$owner" ]]; then
    echo "    port ${candidate} is ALREADY IN USE:" >&2
    echo "      ${owner}" >&2
    CLASH=1
  else
    ok "${candidate} free"
  fi
done
if [[ $CLASH -eq 1 ]]; then
  echo >&2
  echo "  Pick ports nothing else holds and re-run, e.g.:" >&2
  suggest=$PORT
  while [[ -n "$(port_owner "$suggest")" ]]; do suggest=$((suggest + 10)); done
  suggest2=$((suggest + 1))
  while [[ -n "$(port_owner "$suggest2")" ]]; do suggest2=$((suggest2 + 1)); done
  echo "      $0 --port ${suggest} --console-port ${suggest2} --data-dir ${DATA_DIR}" >&2
  echo >&2
  echo "  (podman only reports this at container START, which is why a clash leaves a" >&2
  echo "   container stuck in 'Created' with an empty log.)" >&2
  exit 1
fi

say "Data directory"
mkdir -p "$DATA_DIR"
ok "$DATA_DIR ($(df -h "$DATA_DIR" | tail -1 | awk '{print $4}') free)"

say "MinIO container '$NAME'"
EXISTING=$($RUNTIME ps -a --format '{{.Names}} {{.Status}}' | grep "^${NAME} " || true)
if [[ -n "$EXISTING" ]]; then
  if $RUNTIME ps --format '{{.Names}}' | grep -qx "$NAME"; then
    ok "already running — leaving it alone"
    # A container keeps the ports it was CREATED with. Re-running with a different
    # --port does not change them, and printing a .env block for the requested port
    # would hand out a value that cannot connect.
    ACTUAL=$($RUNTIME port "$NAME" 2>/dev/null | awk -F: '/^9000\//{print $NF; exit}')
    if [[ -n "$ACTUAL" && "$ACTUAL" != "$PORT" ]]; then
      echo >&2
      echo "  WARNING: it publishes the API on ${ACTUAL}, not the ${PORT} you asked for." >&2
      echo "  Ports are fixed at creation. To change them:" >&2
      echo "      $RUNTIME rm -f $NAME && $0 --port $PORT --console-port $CONSOLE_PORT" >&2
      echo "  Using ${ACTUAL} in the .env block below." >&2
      PORT="$ACTUAL"
    fi
  else
    ok "exists but is NOT running: ${EXISTING#* }"
    echo
    echo "  Last lines of its log:" >&2
    $RUNTIME logs --tail 20 "$NAME" 2>&1 | sed 's/^/    /' >&2
    echo >&2
    echo "  Remove it and re-run this script once the cause is fixed:" >&2
    echo "      $RUNTIME rm -f $NAME" >&2
    exit 1
  fi
else
  # MinIO stores objects as plain files under DATA_DIR, so the bytes remain readable
  # with ordinary tools and are not locked inside a database.
  #
  # Output is deliberately NOT discarded. An earlier version sent it to /dev/null, so a
  # failed start printed a .env block for a container that was not running — the worst
  # kind of success message.
  if ! $RUNTIME run -d --name "$NAME" \
      -p "${PORT}:9000" -p "${CONSOLE_PORT}:9001" \
      -e "MINIO_ROOT_USER=${ACCESS_USER}" \
      -e "MINIO_ROOT_PASSWORD=${ACCESS_PASSWORD}" \
      -v "${DATA_DIR}:/data:z" \
      quay.io/minio/minio server /data --console-address ":9001"; then
    echo >&2
    echo "Failed to start the container. Common causes:" >&2
    echo "  * port ${PORT} or ${CONSOLE_PORT} already in use — check: ss -lntp | grep -E '${PORT}|${CONSOLE_PORT}'" >&2
    echo "  * ${DATA_DIR} not writable by this user (rootless podman runs as you)" >&2
    echo "  * image could not be pulled — check: $RUNTIME pull quay.io/minio/minio" >&2
    exit 1
  fi
  ok "container created"
fi

# A container that starts and immediately dies is the failure this catches. Without the
# check, the script would happily print connection details for something already dead.
say "Waiting for MinIO to answer"
HEALTHY=0
for _ in $(seq 1 30); do
  if ! $RUNTIME ps --format '{{.Names}}' | grep -qx "$NAME"; then
    echo "  the container exited. Its log:" >&2
    $RUNTIME logs --tail 30 "$NAME" 2>&1 | sed 's/^/    /' >&2
    echo >&2
    echo "  If this says 'permission denied', ${DATA_DIR} is not writable by you." >&2
    echo "  Rootless podman runs as your user, so try a path in your home:" >&2
    echo "      $RUNTIME rm -f $NAME" >&2
    echo "      $0 --data-dir \$HOME/mva-objects --port ${PORT} --console-port ${CONSOLE_PORT}" >&2
    exit 1
  fi
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/minio/health/live" >/dev/null 2>&1; then
    HEALTHY=1; break
  fi
  sleep 1
done
if [[ $HEALTHY -eq 1 ]]; then
  ok "healthy on :${PORT} (console :${CONSOLE_PORT})"
else
  ok "running, but /minio/health/live did not answer on :${PORT} within 30s"
  echo "     check: $RUNTIME logs $NAME" >&2
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

say "Published ports"
$RUNTIME port "$NAME" 2>&1 | sed 's/^/    /' || echo "    (none — nothing outside the container can reach it)"
echo
echo
echo "    ┌─ Dashboard ────────────────────────────────────────────────────────"
echo "    │  URL       http://${HOST_HINT}:${CONSOLE_PORT}"
echo "    │  Username  ${ACCESS_USER}"
echo "    │  Password  ${ACCESS_PASSWORD}"
echo "    └────────────────────────────────────────────────────────────────────"
echo "    The same pair is the S3 access key and secret below — MinIO's root"
echo "    credentials serve both the API and the console."

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
  cat <<GENNOTE
The password above was generated and is shown ONCE. Save it now.

Lost it later? It is stored in the container's environment — read it back with:
    ${RUNTIME} inspect ${NAME} --format '{{range .Config.Env}}{{println .}}{{end}}' \
      | grep MINIO_ROOT

Or choose your own and recreate the container. Objects live in ${DATA_DIR} on the
host, so they survive:
    ${RUNTIME} rm -f ${NAME}
    $0 --password 'your-password' --port ${PORT} --console-port ${CONSOLE_PORT}
GENNOTE
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
