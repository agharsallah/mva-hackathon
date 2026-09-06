#!/usr/bin/env bash
#
# Install `mva-viz-api` as a systemd service on this server, so the hosted dashboard has
# a backend to talk to. Run this ON THE SERVER, from a checkout of the repository.
#
# What it does, in order:
#   1. refuses to continue without MVA_VIZ_TOKEN — the API serves real patient positions
#      on /api/panel/locus, and a public bind with no token publishes them;
#   2. `uv sync --all-groups` in the checkout, so the service has its dependencies;
#   3. writes a systemd unit that binds LOOPBACK on the server and starts it;
#   4. prints the reverse-proxy block (Caddy and nginx) that terminates TLS in front.
#
# The service binds 127.0.0.1 on purpose. TLS, the public hostname and the certificate
# belong to the reverse proxy, which is the only thing that should hold a public port.
#
# Usage:
#   ./tools/setup-viz-api-service.sh [--port 8900] [--user $USER] [--name mva-viz-api]
#                                    [--domain viz.example.org] [--no-start]
#
# --domain only changes the reverse-proxy block that is printed; nothing is installed
# for it. Uninstall with:  sudo systemctl disable --now mva-viz-api

set -euo pipefail

PORT=8900
SERVICE_USER="${USER}"
NAME=mva-viz-api
DOMAIN=""
START=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)     PORT="$2"; shift 2 ;;
    --user)     SERVICE_USER="$2"; shift 2 ;;
    --name)     NAME="$2"; shift 2 ;;
    --domain)   DOMAIN="$2"; shift 2 ;;
    --no-start) START=0; shift ;;
    -h|--help)  sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
fail() { printf '    \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

# --- 1. the token -----------------------------------------------------------------
# Read from the environment first, then from .env, matching mva.warehouse.settings.
say "checking MVA_VIZ_TOKEN"
TOKEN="${MVA_VIZ_TOKEN:-}"
if [[ -z "$TOKEN" && -f .env ]]; then
  TOKEN="$(sed -n 's/^[[:space:]]*\(export[[:space:]]\+\)\?MVA_VIZ_TOKEN=//p' .env | tail -1 | tr -d '"'"'"' ')"
fi
if [[ -z "$TOKEN" ]]; then
  cat >&2 <<EOF
    ✗ MVA_VIZ_TOKEN is empty in the environment and in $REPO/.env.

      /api/panel/locus serves REAL PATIENT POSITIONS. This service is only safe behind
      a token. Generate one and put it in .env:

        uv run python -c "import secrets; print(secrets.token_urlsafe(32))"

      Then set the SAME value as MVA_VIZ_API_TOKEN in the Vercel project, so the
      dashboard's proxy can reach this API. See docs/step-0/infrastructure.md.
EOF
  exit 1
fi
ok "token present (${#TOKEN} characters, not shown)"

# --- 2. dependencies --------------------------------------------------------------
command -v uv >/dev/null 2>&1 || fail "uv is not installed — https://docs.astral.sh/uv/"
say "uv sync --all-groups"
uv sync --all-groups
ok "environment ready at $REPO/.venv"

say "smoke-testing the API in-process"
uv run python -c "from mva.viz.app import create_app; create_app()" >/dev/null
ok "create_app() builds"

# --- 3. the unit ------------------------------------------------------------------
UNIT="/etc/systemd/system/${NAME}.service"
say "writing $UNIT"
sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=mva-viz-api — the warehouse and the read store as JSON, for the dashboard
Documentation=file://$REPO/docs/step-0/infrastructure.md
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
User=$SERVICE_USER
WorkingDirectory=$REPO
# .env holds PGPASSWORD, the object-store keys and MVA_VIZ_TOKEN. It is read by the
# settings loader from WorkingDirectory, so nothing is duplicated into this unit and
# no secret lands in /etc/systemd or in \`systemctl show\`.
ExecStart=$(command -v uv) run mva-viz-api --host 127.0.0.1 --port $PORT
Restart=on-failure
RestartSec=5
# The service reads the repository, the object store and Postgres. It writes only its
# JSON cache under build/ — which holds patient positions, hence the private tmp.
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=$REPO/build

[Install]
WantedBy=multi-user.target
EOF
ok "unit written"

sudo systemctl daemon-reload
sudo systemctl enable "$NAME" >/dev/null
ok "enabled at boot"

if [[ "$START" == "1" ]]; then
  say "starting $NAME"
  sudo systemctl restart "$NAME"
  sleep 2
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null; then
    ok "http://127.0.0.1:$PORT/health answers"
  else
    sudo systemctl status "$NAME" --no-pager --lines 20 || true
    fail "the service did not answer /health — see the status above"
  fi
fi

# --- 4. the reverse proxy ---------------------------------------------------------
HOSTNAME_SHOWN="${DOMAIN:-viz.example.org}"
cat <<EOF

$(say "next: terminate TLS in front of it")

The service is on loopback only. Publish it through a reverse proxy that holds the
certificate. Caddy (it obtains the certificate itself):

    $HOSTNAME_SHOWN {
        reverse_proxy 127.0.0.1:$PORT
    }

nginx, with a certificate from certbot:

    server {
        listen 443 ssl;
        server_name $HOSTNAME_SHOWN;
        # ssl_certificate / ssl_certificate_key from certbot
        location / {
            proxy_pass http://127.0.0.1:$PORT;
            proxy_set_header Host \$host;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            # /api/panel/locus streams; a figure PNG is a few hundred KB.
            proxy_read_timeout 120s;
        }
    }

Then, in the Vercel project (Settings -> Environment Variables):

    MVA_VIZ_API_URL    = https://$HOSTNAME_SHOWN
    MVA_VIZ_API_TOKEN  = (the MVA_VIZ_TOKEN value from .env — same secret)

Verify from your laptop, not from the server:

    curl -fsS https://$HOSTNAME_SHOWN/health
    curl -fsS -o /dev/null -w '%{http_code}\\n' https://$HOSTNAME_SHOWN/api/overview   # 401
    curl -fsS -H "X-API-Key: \$MVA_VIZ_TOKEN" https://$HOSTNAME_SHOWN/api/overview | head -c 200

Logs:  sudo journalctl -u $NAME -f
EOF
