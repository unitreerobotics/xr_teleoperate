#!/usr/bin/env bash

set -euo pipefail

##################################################################################################################
# This script sets up the conda environment and installs the necessary dependencies for the XR Teleop project.
# It assumes you have setup the base HIVE environment described in https://github.com/Hive-Robots/core-environment
##################################################################################################################

UNITREE_REPO_DIR="$HOME/repos/unitree_sdk2_python"
ENV_NAME="xr_tele"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR"
ENV_FILE="$SCRIPT_DIR/xr_tele.environment.yml"

prompt_yes_no() {
  local prompt="$1"
  local default="${2:-N}"
  local answer

  if [[ "$default" == "Y" ]]; then
    read -r -p "$prompt [Y/n]: " answer
    answer="${answer:-Y}"
  else
    read -r -p "$prompt [y/N]: " answer
    answer="${answer:-N}"
  fi

  [[ "$answer" =~ ^[Yy]$ ]]
}

if ! command -v git >/dev/null 2>&1; then
  echo "git is required but not found in PATH."
  exit 1
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is required but not found in PATH."
  exit 1
fi

if [[ ! -f "$REPO_DIR/requirements.txt" ]]; then
  echo "Expected repository files were not found in $REPO_DIR"
  exit 1
fi

if [[ ! -d "$UNITREE_REPO_DIR/.git" ]]; then
  echo "Unitree SDK repository didn't exist at $UNITREE_REPO_DIR; Please run the base setup first."
  exit 1  
fi

if [[ -d "$REPO_DIR/.git" ]]; then
  echo "Syncing submodules"
  git -C "$REPO_DIR" submodule sync --recursive
  git -C "$REPO_DIR" submodule update --init --depth 1
else
  echo "Skipping submodule sync because $REPO_DIR is not a git checkout"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Conda environment file not found: $ENV_FILE"
  exit 1
fi

if conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  if prompt_yes_no "Conda environment '$ENV_NAME' already exists. Update it?" "N"; then
    echo "Updating conda environment '$ENV_NAME'"
    conda env update --name "$ENV_NAME" --file "$ENV_FILE" --prune
  else
    echo "Skipping environment update for '$ENV_NAME'"
  fi
else
  echo "Creating conda environment '$ENV_NAME'"
  conda env create --name "$ENV_NAME" --file "$ENV_FILE"
fi

echo "Installing repository requirements"
conda run -n "$ENV_NAME" pip install -r "$REPO_DIR/requirements.txt"

echo "Installing unitree_sdk2_python as editable package"
conda run -n "$ENV_NAME" pip install -e "$UNITREE_REPO_DIR"

echo "Installing editable submodule packages"
conda run -n "$ENV_NAME" pip install -e "$REPO_DIR/teleop/televuer"
conda run -n "$ENV_NAME" pip install -e "$REPO_DIR/teleop/robot_control/dex-retargeting"

echo "Create televuer key and certificates"
cd "$REPO_DIR/teleop/televuer"
if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout key.pem -out cert.pem \
        -subj "/C=DK/ST=CPH/L=CPH/O=hive/CN=localhost"
fi

echo "Setup complete"
