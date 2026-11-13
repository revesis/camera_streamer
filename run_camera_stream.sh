#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERIAL="${ADB_SERIAL:-172.17.131.136:38163}"
PORT="${PORT:-8080}"

echo "=================================================="
echo " Starting Realme Camera Web Streaming Service"
echo " Target Device : $SERIAL"
echo " Web Port      : $PORT"
echo "=================================================="

# Check ADB connectivity
adb connect "$SERIAL" || true

# Launch server
exec python3 "$DIR/camera_streamer/server.py"
