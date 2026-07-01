#!/bin/bash
# Setup script for AI Lecture Note-Taker on Raspberry Pi

set -e

echo "=== AI Lecture Note-Taker Setup ==="

# System dependencies
echo "[1/4] Installing system dependencies..."
sudo apt-get update -q
sudo apt-get install -y -q \
    python3-pip \
    python3-tk \
    portaudio19-dev \
    libsndfile1 \
    ffmpeg \
    python3-numpy

# Python packages (--break-system-packages needed on Raspberry Pi OS Bookworm+)
echo "[2/4] Installing Python packages..."
pip3 install --break-system-packages --upgrade pip
pip3 install --break-system-packages -r requirements.txt

# Whisper model pre-download (faster-whisper: lightweight, no PyTorch)
echo "[3/4] Pre-downloading Whisper 'base' model..."
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

echo "[4/4] Setup complete!"
echo ""
echo "Before running, set your Anthropic API key:"
echo "  export ANTHROPIC_API_KEY='your-key-here'"
echo ""
echo "Then launch the app:"
echo "  python3 main.py"
