#!/bin/bash
# Launcher for the AI Lecture Note-Taker in kiosk mode.
# Used by the autostart entry, and runnable by hand.

# Resolve the directory this script lives in, so it works from anywhere.
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# --- Configuration -----------------------------------------------------------
# Put your API key here, or set it in the environment / ~/.bashrc instead.
# export ANTHROPIC_API_KEY="sk-ant-..."

export KIOSK=1   # fullscreen, no window chrome

# Use the USB microphone (matched by name). Change "USB" to a device number
# or a different name substring if your mic reports differently. Run
# `python3 main.py --check-audio` to see the exact names.
export AUDIO_DEVICE="USB"

# Disable screen blanking / power saving so the display stays on (X11 only).
if command -v xset >/dev/null 2>&1; then
    xset s off          # no screensaver
    xset -dpms          # no display power management
    xset s noblank      # don't blank the video device
fi

# Hide the mouse cursor when idle, if unclutter is installed.
if command -v unclutter >/dev/null 2>&1; then
    unclutter -idle 0.5 -root &
fi

# Wait for an audio input device to appear (USB mics enumerate slowly on boot).
for i in $(seq 1 10); do
    if arecord -l 2>/dev/null | grep -q card; then
        break
    fi
    sleep 1
done

# Launch the app. If it crashes, restart it after a short pause so the
# device never drops to a bare desktop.
while true; do
    python3 main.py
    echo "App exited (code $?). Restarting in 3s..." >&2
    sleep 3
done
