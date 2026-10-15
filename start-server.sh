#!/usr/bin/env bash
# Start Personal AIssistent on the Pi.
# The supervisor runs the API, climate sampler, scale scanner, and news
# scheduler as separate processes and restarts whichever one exits.
#
# Boot (user crontab, after the venv and dependencies are installed):
#   @reboot /home/pi/Aissistant/start-server.sh >> /home/pi/Aissistant/data/server.log 2>&1
#
# The scale scan needs BlueZ running and this user in the bluetooth group.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="$(command -v python3 || command -v python)"
fi

# LAN Pi: phones and the PC web UI must reach this host. Override by exporting PA_HOST first.
export PA_HOST="${PA_HOST:-0.0.0.0}"
export PA_PORT="${PA_PORT:-8741}"

mkdir -p "$ROOT/data"
exec "$PYTHON" -m server.supervisor
