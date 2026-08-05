#!/usr/bin/env bash
# Trusted Mathlib Bonsai surface exporter.
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "usage: $0 REPOSITORY TRUSTED_SURFACE_LEAN OUTPUT CHANGED_SOURCE..." >&2
  exit 2
fi

repository=$(realpath "$1")
surface_script=$(realpath "$2")
output=$(realpath -m "$3")
shift 3
changed_modules=
for path in "$@"; do
  module=${path%.lean}
  module=${module//\//.}
  changed_modules+="${module};"
done
cd "$repository"
BONSAI_CHANGED_MODULES="$changed_modules" GOLF_SURFACE_OUT="$output" \
  lake env lean "$surface_script"
