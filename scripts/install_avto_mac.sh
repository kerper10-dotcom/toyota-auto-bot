#!/bin/bash
# Avto.net cannot be scraped from GitHub Actions (Cloudflare).
# This installs a Mac launchd job every 2 hours using local Chrome.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$PROJECT_DIR/launchd/com.toyota.avto-monitor.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.toyota.avto-monitor.plist"
LABEL="com.toyota.avto-monitor"

mkdir -p "$PROJECT_DIR/logs" "$HOME/Library/LaunchAgents"

if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
  echo "Creating .venv..."
  python3 -m venv "$PROJECT_DIR/.venv"
  "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
fi

sed "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$PLIST_SRC" > "$PLIST_DEST"

UID_NUM="$(id -u)"
launchctl bootout "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "$PLIST_DEST"

echo "Instalirano: $PLIST_DEST"
echo "Raspored: svaka 2 sata + odmah sad (RunAtLoad)"
echo
echo "Ručno:   $PROJECT_DIR/scripts/run_avto.sh"
echo "Status:  launchctl print gui/${UID_NUM}/${LABEL} | head"
echo "Logovi:  $PROJECT_DIR/logs/"
echo "Stop:    launchctl bootout gui/${UID_NUM}/${LABEL}"
