#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p "$PROJECT_DIR/logs"

if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

export SITES=avto
export SEEN_FILE="$PROJECT_DIR/seen-avto.json"
export PYTHONUNBUFFERED=1

PY="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "Missing $PY — run scripts/install_avto_mac.sh first" >&2
  exit 1
fi

exec /usr/bin/caffeinate -i "$PY" "$PROJECT_DIR/monitor.py"
