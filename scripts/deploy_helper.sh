#!/usr/bin/env bash
# Helper script - creates zip with directory structure
# Gets source from script location, outputs to temp folder

EXCLUDE=(
    '__pycache__' '.git' '.pytest_cache' 'venv' 'node_modules'
    '*.pyc' '*.log' 'instance' '.env' '*.db' 'tests' 'stress_tests'
    'deploy_to_pi.*' 'deploy_helper.ps1' 'deploy_helper.sh'
)

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ZIP="${TMPDIR:-/tmp}/ghosthub_deploy.zip"
TEMP_DIR="${TMPDIR:-/tmp}/ghosthub_staging_$$"

mkdir -p "$TEMP_DIR"

# Build rsync exclude args
RSYNC_ARGS=()
for ex in "${EXCLUDE[@]}"; do
    RSYNC_ARGS+=("--exclude=$ex")
done

rsync -a "${RSYNC_ARGS[@]}" "$SRC/" "$TEMP_DIR/"

rm -f "$OUT_ZIP"
(cd "$TEMP_DIR" && zip -r "$OUT_ZIP" .)
rm -rf "$TEMP_DIR"

echo "Created: $OUT_ZIP"
