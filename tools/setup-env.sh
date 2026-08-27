#!/usr/bin/env bash
#
# Install the toolchain this repo needs, without root.
#
#   usage: tools/setup-env.sh && source tools/activate.sh
#
# micromamba rather than apt because the target machines (a WSL2 box here, Modal
# containers later) do not reliably have sudo, and bcftools/fastp are not in the
# default Ubuntu repositories at a useful version anyway.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PREFIX="$HOME/.local/micromamba/envs/bio"

if ! command -v micromamba >/dev/null && [ ! -x "$HOME/.local/bin/micromamba" ]; then
  echo "==> installing micromamba"
  mkdir -p "$HOME/.local/bin"
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest \
    | tar -xj -C "$HOME/.local" bin/micromamba
fi
MAMBA="$(command -v micromamba || echo "$HOME/.local/bin/micromamba")"

echo "==> creating bio environment at $ENV_PREFIX"
"$MAMBA" create -y -p "$ENV_PREFIX" -c conda-forge -c bioconda \
  bcftools samtools htslib seqkit fastp

echo "==> creating Python venv"
[ -d "$REPO/.venv" ] || python3 -m venv "$REPO/.venv"
"$REPO/.venv/bin/pip" install -q --upgrade pip
"$REPO/.venv/bin/pip" install -q pytest

cat > "$REPO/tools/activate.sh" <<EOF
# source this: adds the bio toolchain and the project venv to PATH
export PATH="$ENV_PREFIX/bin:$REPO/.venv/bin:\$PATH"
EOF

echo
echo "done. now run:  source tools/activate.sh && pytest"
