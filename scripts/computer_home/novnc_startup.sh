#!/bin/bash
echo "starting noVNC"

# Start noVNC with optimized settings
/opt/noVNC/utils/novnc_proxy \
    --vnc localhost:5900 \
    --listen 6080 \
    --web /opt/noVNC \
    --heartbeat 15 \
    --idle-timeout 0 \
    > /tmp/novnc.log 2>&1 &

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
    echo "noVNC failed to start, log output:" >&2
    cat /tmp/novnc.log >&2
    exit 1
fi

echo "noVNC started successfully"
