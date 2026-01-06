#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing AWS CLI v2 + AWS Copilot CLI"
echo "    User: $(whoami)"
echo "    OS:   $(uname -a)"

# ---- Helpers ----
need_cmd() { command -v "$1" >/dev/null 2>&1; }

install_unzip_if_possible() {
  if need_cmd unzip; then return 0; fi

  echo "==> 'unzip' not found."
  if [[ "$(id -u)" -eq 0 ]] && need_cmd apt-get; then
    echo "==> Installing unzip via apt-get (root detected)"
    apt-get update -y
    apt-get install -y --no-install-recommends unzip ca-certificates curl
    rm -rf /var/lib/apt/lists/*
  else
    echo "!! Can't auto-install unzip (not root or apt-get missing)."
    echo "   Please install unzip, or run this script as root."
    exit 1
  fi
}

choose_install_paths() {
  # Prefer system-wide install if writable
  if [[ -w /usr/local/bin ]]; then
    BIN_DIR="/usr/local/bin"
    AWS_INSTALL_DIR="/usr/local/aws-cli"
  else
    BIN_DIR="${HOME}/.local/bin"
    AWS_INSTALL_DIR="${HOME}/.local/aws-cli"
    mkdir -p "$BIN_DIR"
  fi
}

append_path_hint() {
  if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo
    echo "==> PATH update needed (current shell won't find installed binaries):"
    echo "    export PATH=\"$BIN_DIR:\$PATH\""
    echo
    echo "    To make it permanent, add to ~/.bashrc:"
    echo "    echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.bashrc"
  fi
}

# ---- Main ----
choose_install_paths

# Ensure basic tools
if ! need_cmd curl; then
  if [[ "$(id -u)" -eq 0 ]] && need_cmd apt-get; then
    apt-get update -y
    apt-get install -y --no-install-recommends curl ca-certificates
    rm -rf /var/lib/apt/lists/*
  else
    echo "!! curl not found and cannot auto-install (not root)."
    exit 1
  fi
fi

install_unzip_if_possible

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

# ---- Install AWS CLI v2 ----
echo "==> Installing AWS CLI v2..."
AWS_ZIP="$TMP_DIR/awscliv2.zip"

curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "$AWS_ZIP"
unzip -q "$AWS_ZIP" -d "$TMP_DIR"

# Remove old install if present (idempotent-ish)
if [[ -x "$BIN_DIR/aws" ]] || [[ -d "$AWS_INSTALL_DIR" ]]; then
  echo "    Detected existing AWS CLI install (will update/overwrite)."
fi

# Run installer
# --update handles existing install; if first install, it's fine too.
"$TMP_DIR/aws/install" --bin-dir "$BIN_DIR" --install-dir "$AWS_INSTALL_DIR" --update

echo "==> AWS CLI installed:"
"$BIN_DIR/aws" --version || true

# ---- Install AWS Copilot CLI ----
echo "==> Installing AWS Copilot CLI..."
COPILOT_BIN="$BIN_DIR/copilot"
curl -sSL "https://github.com/aws/copilot-cli/releases/latest/download/copilot-linux" -o "$COPILOT_BIN"
chmod +x "$COPILOT_BIN"

echo "==> Copilot installed:"
"$COPILOT_BIN" --version || true

append_path_hint

echo
echo "==> Done."
echo "    Verify:"
echo "      aws --version"
echo "      copilot --version"
