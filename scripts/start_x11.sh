#!/bin/bash
set -e  # Exit on error

# Environment setup
DPI=96
RES_AND_DEPTH=${WIDTH}x${HEIGHT}x24
export DISPLAY=:${DISPLAY_NUM}

# Function to check if Xvfb is already running
check_xvfb_running() {
    if [ -e /tmp/.X${DISPLAY_NUM}-lock ]; then
        return 0  # Xvfb is already running
    else
        return 1  # Xvfb is not running
    fi
}

# Function to check if Xvfb is ready
wait_for_xvfb() {
    local timeout=10
    local start_time=$(date +%s)
    while ! xdpyinfo >/dev/null 2>&1; do
        if [ $(($(date +%s) - start_time)) -gt $timeout ]; then
            echo "Xvfb failed to start within $timeout seconds" >&2
            return 1
        fi
        sleep 0.1
    done
    return 0
}

# Start Xvfb if not already running
if ! check_xvfb_running; then
    echo "Starting Xvfb..."
    Xvfb $DISPLAY -ac -screen 0 $RES_AND_DEPTH -retro -dpi $DPI -nolisten tcp -nolisten unix &
    XVFB_PID=$!

    if ! wait_for_xvfb; then
        echo "Xvfb failed to start"
        kill $XVFB_PID
        exit 1
    fi
    echo "Xvfb started successfully on display ${DISPLAY}"
    echo "Xvfb PID: $XVFB_PID"
fi

# Start tint2
echo "Starting tint2..."
tint2 2>/tmp/tint2_stderr.log &
timeout=30
while [ $timeout -gt 0 ]; do
    if xdotool search --class "tint2" >/dev/null 2>&1; then
        break
    fi
    sleep 1
    ((timeout--))
done

if [ $timeout -eq 0 ]; then
    echo "tint2 stderr output:" >&2
    cat /tmp/tint2_stderr.log >&2
    exit 1
fi
rm /tmp/tint2_stderr.log

# Start window manager
echo "Starting mutter..."
XDG_SESSION_TYPE=x11 mutter --replace --sm-disable 2>/tmp/mutter_stderr.log &
timeout=30
while [ $timeout -gt 0 ]; do
    if xdotool search --class "mutter" >/dev/null 2>&1; then
        break
    fi
    sleep 1
    ((timeout--))
done

if [ $timeout -eq 0 ]; then
    echo "mutter stderr output:" >&2
    cat /tmp/mutter_stderr.log >&2
    exit 1
fi
rm /tmp/mutter_stderr.log

# Start VNC server
echo "Starting VNC server..."
x11vnc -display $DISPLAY -nopw -listen 0.0.0.0 -xkb -ncache 10 -ncache_cr -forever &
sleep 1

# Start noVNC
echo "Starting noVNC..."
/opt/noVNC/utils/novnc_proxy --vnc localhost:5900 --listen 0.0.0.0:6080 --web /opt/noVNC > /tmp/novnc.log 2>&1 &

# Wait for noVNC to start
timeout=10
while [ $timeout -gt 0 ]; do
    if netstat -tuln | grep -q ":6080 "; then
        break
    fi
    sleep 1
    ((timeout--))
done

if [ $timeout -eq 0 ]; then
    echo "noVNC failed to start"
    cat /tmp/novnc.log
    exit 1
fi

echo "noVNC started successfully"

# Start gptme server
echo "Starting gptme server..."
python3 -m gptme.server --host 0.0.0.0 --port 8081
