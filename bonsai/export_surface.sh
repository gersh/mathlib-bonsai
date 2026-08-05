#!/usr/bin/env bash
# Trusted Mathlib Bonsai surface exporter.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 REPOSITORY TRUSTED_SURFACE_LEAN OUTPUT" >&2
  exit 2
fi

repository=$(realpath "$1")
surface_script=$(realpath "$2")
output=$(realpath -m "$3")
cd "$repository"
GOLF_SURFACE_OUT="$output" lake env lean "$surface_script"
