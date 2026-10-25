#!/bin/bash
# Start a private mpd instance (not the system service) and the Flask web UI.
# Stopping this script (Ctrl+C) stops mpd as well. The script exits with an error
# if mpd stops answering or the web UI dies, so a systemd service can restart it.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export MPD_HOST=localhost
export MPD_PORT=6601

mkdir -p ~/.mpd /dev/shm/ujagaga-radio/music

# Refuse to start a second copy: the leftover-mpd cleanup below would kill the running one
if (exec 3<>/dev/tcp/127.0.0.1/8888) 2>/dev/null; then
    echo "Radio is already running (port 8888 in use)" >&2
    exit 1
fi

# Kill an mpd left over from a previous run that did not shut down (e.g. it hung)
pkill -KILL -f "^mpd --no-daemon --stderr $SCRIPT_DIR/mpd_local.conf\$"

mpd --no-daemon --stderr "$SCRIPT_DIR/mpd_local.conf" &
MPD_PID=$!
stop_mpd() {
    kill $MPD_PID 2>/dev/null
    # A hung mpd ignores SIGTERM; force it after 5 seconds
    for i in $(seq 1 10); do
        kill -0 $MPD_PID 2>/dev/null || return
        sleep 0.5
    done
    kill -KILL $MPD_PID 2>/dev/null
}
trap 'kill $APP_PID 2>/dev/null; stop_mpd' EXIT
trap 'exit 130' INT TERM HUP

# Wait for mpd to accept connections
for i in $(seq 1 20); do
    mpc status >/dev/null 2>&1 && break
    sleep 0.5
done

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/radio.py" &
else
    python3 "$SCRIPT_DIR/radio.py" &
fi
APP_PID=$!

# Watchdog: mpd can hang without exiting, so check that it still answers
while kill -0 $APP_PID 2>/dev/null; do
    sleep 30 & wait $!
    if ! timeout 5 mpc status >/dev/null 2>&1; then
        echo "mpd is not responding, stopping radio" >&2
        exit 1
    fi
done
echo "Web UI stopped, stopping radio" >&2
exit 1
