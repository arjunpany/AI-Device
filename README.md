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

## Requirements

- Raspberry Pi 3B+ or newer (4 recommended for Whisper)
- USB or built-in microphone
- Internet connection (for Claude API only)
- `ANTHROPIC_API_KEY` environment variable set
