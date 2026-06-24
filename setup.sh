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

# Python packages
echo "[2/4] Installing Python packages..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

# Whisper model pre-download
echo "[3/4] Pre-downloading Whisper 'base' model..."
python3 -c "import whisper; whisper.load_model('base')"

echo "[4/4] Setup complete!"
echo ""
echo "Before running, set your Anthropic API key:"
echo "  export ANTHROPIC_API_KEY='your-key-here'"
echo ""
echo "Then launch the app:"
echo "  python3 main.py"
