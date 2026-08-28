#!/usr/bin/env bash
#
# Install the toolchain this repo needs, without root.
#
#   usage: tools/setup-env.sh && source tools/activate.sh
#
# Two package managers, because they solve different problems:
#
#   uv          Python dependencies and the project environment (see CLAUDE.md).
#   micromamba  the bioinformatics binaries — bcftools, samtools, seqkit, fastp.
#               These are not Python packages. apt is unavailable (no passwordless
#               sudo on the target machines, including Modal containers later), and
#               conda-forge/bioconda carry current versions. See docs/notes/toolchain-choice.md.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PREFIX="$HOME/.local/micromamba/envs/bio"

if ! command -v uv >/dev/null; then
  echo "==> installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

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

echo "==> syncing Python environment"
( cd "$REPO" && uv sync )

echo
echo "done. now run:  source tools/activate.sh && uv run pytest"
