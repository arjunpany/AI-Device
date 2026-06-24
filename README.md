# AI Lecture Note-Taker

A Raspberry Pi app that records audio, transcribes it with Whisper, then uses Claude AI to generate organized, visual notes.

## Features

- **One-click recording** — Start/Stop buttons with a live blinking indicator
- **Local transcription** — OpenAI Whisper runs on-device (no cloud needed for STT)
- **AI note generation** — Claude (`claude-opus-4-8`) condenses the transcript into structured notes
- **Streaming output** — Notes appear in real-time as Claude generates them
- **Visual formatting** — Color-coded headers, bullet points, quotes, and summaries

## Setup

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
bash setup.sh
```

## Run

```bash
python3 main.py
```

## How It Works

1. Press **Start Recording** — microphone captures audio at 16 kHz
2. Press **Stop & Generate** — Whisper transcribes the audio locally
3. Claude AI reads the transcript and generates organized notes with:
   - Title and topic overview
   - Key concepts with explanations
   - Important details and supporting points
   - Notable quotes
   - Summary bullet points
4. Notes display in a styled window with copy-to-clipboard support

## Kiosk Mode (auto-launch on boot)

To make the app the *only* thing that appears when the Pi powers on — fullscreen,
no desktop, auto-restart if it crashes:

```bash
bash kiosk/install-kiosk.sh
```

Then finish two settings:

1. **Boot to desktop with auto-login:**
   `sudo raspi-config` → System Options → Boot / Auto Login → **Desktop Autologin**
2. **Set your API key** — add to the end of `~/.bashrc`:
   `export ANTHROPIC_API_KEY="sk-ant-..."`

Reboot (`sudo reboot`) and the note-taker comes up fullscreen on its own.

- The app runs fullscreen with no window borders (`KIOSK=1`, the default).
- If it ever crashes, `run.sh` restarts it automatically.
- Screen blanking/power-saving is disabled so the display stays on.
- **Emergency exit:** press `Ctrl + Shift + Q` to quit to the desktop.
- To run in a normal window instead (for testing): `KIOSK=0 python3 main.py`

## Requirements

- Raspberry Pi 3B+ or newer (4 recommended for Whisper)
- USB or built-in microphone
- Internet connection (for Claude API only)
- `ANTHROPIC_API_KEY` environment variable set
