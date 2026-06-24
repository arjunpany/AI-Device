#!/bin/bash
# Installs the AI Lecture Note-Taker as an autostart kiosk app.
# Run this ON the Raspberry Pi after cloning the repo.
set -e

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(whoami)"

echo "=== Installing kiosk autostart for user '$USER_NAME' ==="
echo "App directory: $APP_DIR"

# Make scripts executable.
chmod +x "$APP_DIR/run.sh"

# Optional helpers for a clean kiosk experience.
echo "[1/3] Installing helper packages (unclutter for cursor hiding)..."
sudo apt-get update -q
sudo apt-get install -y -q unclutter || true

# Create the per-user autostart entry. This works for the LXDE/labwc
# desktop sessions used by Raspberry Pi OS.
echo "[2/3] Creating autostart entry..."
AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/ai-notes.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AI Lecture Note-Taker
Comment=Auto-launch the note-taker in kiosk mode on boot
Exec=$APP_DIR/run.sh
X-GNOME-Autostart-enabled=true
Terminal=false
EOF

echo "[3/3] Done."
echo ""
echo "IMPORTANT — finish these two steps:"
echo ""
echo "  1. Make sure the Pi boots to the DESKTOP and logs in automatically:"
echo "       sudo raspi-config  ->  System Options  ->  Boot / Auto Login"
echo "       ->  'Desktop Autologin'"
echo ""
echo "  2. Set your Anthropic API key so the app can reach Claude. Add this"
echo "     line to the end of  ~/.bashrc  (or edit run.sh):"
echo "       export ANTHROPIC_API_KEY=\"sk-ant-...\""
echo ""
echo "Reboot to test:  sudo reboot"
echo "Emergency exit from the app:  Ctrl + Shift + Q"
