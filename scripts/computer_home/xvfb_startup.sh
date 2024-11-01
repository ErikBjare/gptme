#!/bin/bash
set -e

DPI=96
RES_AND_DEPTH=${WIDTH}x${HEIGHT}x24

echo "Starting Xvfb..."
Xvfb $DISPLAY -ac -screen 0 $RES_AND_DEPTH -retro -dpi $DPI -nolisten tcp -nolisten unix &
XVFB_PID=$!

# Wait for Xvfb to be ready
timeout=10
start_time=$(date +%s)
while ! xdpyinfo >/dev/null 2>&1; do
    if [ $(($(date +%s) - start_time)) -gt $timeout ]; then
        echo "Xvfb failed to start within $timeout seconds" >&2
        exit 1
    fi
    sleep 0.1
done

echo "Xvfb started successfully on display ${DISPLAY}"
echo "Xvfb PID: $XVFB_PID"
