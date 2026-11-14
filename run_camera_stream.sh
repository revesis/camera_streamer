#!/bin/bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure writable adb config dir in case user's home is read-only
export ANDROID_USER_HOME="${ANDROID_USER_HOME:-/tmp/.android}"

echo "=================================================="
echo " Starting Realme Camera Web Streaming Service"
echo "=================================================="

# If first argument does not start with '-', treat it as --serial
ARGS=()
if [ $# -gt 0 ] && [[ "$1" != -* ]]; then
    ARGS+=("-s" "$1")
    shift
fi

# Append any remaining arguments
ARGS+=("$@")

# If ADB_SERIAL is set in environment and -s was not passed, pass it
if [ -n "$ADB_SERIAL" ]; then
    HAS_SERIAL=false
    for arg in "${ARGS[@]}"; do
        if [ "$arg" == "-s" ] || [ "$arg" == "--serial" ]; then
            HAS_SERIAL=true
            break
        fi
    done
    if [ "$HAS_SERIAL" = false ]; then
        ARGS+=("-s" "$ADB_SERIAL")
    fi
fi

# Launch server
exec python3 "$DIR/camera_streamer/server.py" "${ARGS[@]}"
