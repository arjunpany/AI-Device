#!/usr/bin/env python3
"""
AI Lecture Note-Taker for Raspberry Pi
Records audio, transcribes with Whisper, generates notes with Claude.
"""

import threading
import queue
import time
import tkinter as tk
from tkinter import scrolledtext, ttk
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as wav_write
from faster_whisper import WhisperModel
import anthropic
import tempfile
import os


SAMPLE_RATE = 16000
CHANNELS = 1
# Fast model for quick note generation. Override with NOTES_MODEL, e.g.
# NOTES_MODEL=claude-opus-4-8 for higher quality (but slower).
CLAUDE_MODEL = os.environ.get("NOTES_MODEL", "claude-haiku-4-5")

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        # faster-whisper: lightweight, no PyTorch, runs well on a Raspberry Pi.
        # Model size and thread count are tunable via env vars for speed:
        #   WHISPER_MODEL=tiny   -> ~3-4x faster than "base" (slightly less accurate)
        #   WHISPER_THREADS=4    -> use all 4 Pi cores (defaults to all available)
        model_size = os.environ.get("WHISPER_MODEL", "tiny")
        threads = int(os.environ.get("WHISPER_THREADS", str(os.cpu_count() or 4)))
        _whisper_model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            cpu_threads=threads,
        )
    return _whisper_model


def list_input_devices():
    """Return [(index, name, channels)] for every device that can record."""
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append((idx, dev["name"], dev["max_input_channels"]))
    return devices


def resolve_input_device():
    """Pick which microphone to use.

    Priority:
      1. The AUDIO_DEVICE env var (an index number, or part of a device name)
      2. The system default input device
    Returns (index_or_None, human_readable_name).
    """
    inputs = list_input_devices()
    if not inputs:
        return None, "NO INPUT DEVICE FOUND"

    pref = os.environ.get("AUDIO_DEVICE", "").strip()
    if pref:
        if pref.isdigit():
            idx = int(pref)
            for i, name, _ in inputs:
                if i == idx:
                    return idx, name
        else:
            for i, name, _ in inputs:
                if pref.lower() in name.lower():
                    return i, name

    # Fall back to the system default input device.
    try:
        default_idx = sd.default.device[0]
        if default_idx is not None and default_idx >= 0:
            name = sd.query_devices(default_idx)["name"]
            return default_idx, name
    except Exception:
        pass

    # Last resort: the first available input.
    return inputs[0][0], inputs[0][1]


class AudioRecorder:
    # Tap onset detection tuning.
    TAP_ABS_MIN = float(os.environ.get("TAP_ABS_MIN", "0.12"))  # min peak to count
    TAP_RATIO = float(os.environ.get("TAP_RATIO", "4.0"))       # peak vs background
    # Crest factor = peak / RMS within the block. A finger tap is impulsive
    # (one sharp spike, so peak >> RMS -> high crest). Speech/vowels spread
    # energy out (peak ~ RMS -> low crest), so this rejects voices like "hello".
    TAP_CREST_MIN = float(os.environ.get("TAP_CREST_MIN", "6.0"))
    # High-frequency ratio: taps are broadband/clicky (lots of sample-to-sample
    # change); voiced speech is dominated by low frequencies. Rejects vowels.
    TAP_HF_MIN = float(os.environ.get("TAP_HF_MIN", "0.35"))
    TAP_REFRACTORY = 0.09  # seconds to ignore after a detected tap

    def __init__(self):
        self.recording = False
        self.frames = []
        self._stream = None
        self.device_index, self.device_name = resolve_input_device()
        self.current_level = 0.0  # 0.0–1.0, live input loudness for the meter

        # Tap (finger-on-screen) onset detection state.
        self._bg_level = 0.0        # slow-moving background loudness
        self._last_tap_t = 0.0
        self.taps = []              # monotonic timestamps of detected taps

    def _callback(self, indata, frame_count, time_info, status):
        # Track loudness always, so the meter shows the mic is live even
        # before recording. Only buffer frames while actually recording.
        self.current_level = float(np.sqrt(np.mean(indata ** 2)))
        if self.recording:
            self.frames.append(indata.copy())

        # --- Tap onset detection ---
        # A finger tap is a short, sharp, broadband spike. We reject anything
        # that isn't impulsive (crest factor) and clicky (high-frequency), so
        # voices, claps and hums don't trigger it.
        x = indata[:, 0] if indata.ndim > 1 else indata
        peak = float(np.max(np.abs(x)))
        rms = float(np.sqrt(np.mean(x ** 2))) + 1e-9
        crest = peak / rms
        # High-frequency content: average sample-to-sample change vs. amplitude.
        # Impulsive/clicky sounds are high; voiced speech (low pitch) is low.
        hf = float(np.mean(np.abs(np.diff(x)))) / (float(np.mean(np.abs(x))) + 1e-9)
        now = time.monotonic()
        is_onset = (
            peak > self.TAP_ABS_MIN
            and peak > self._bg_level * self.TAP_RATIO
            and crest > self.TAP_CREST_MIN
            and hf > self.TAP_HF_MIN
            and (now - self._last_tap_t) > self.TAP_REFRACTORY
        )
        if is_onset:
            self._last_tap_t = now
            self.taps.append(now)
        # Update background AFTER the test (slow attack so a tap doesn't inflate it).
        self._bg_level = 0.97 * self._bg_level + 0.03 * peak

    def consume_taps(self):
        """Return and clear the taps detected since the last call."""
        taps, self.taps = self.taps, []
        return taps

    def open_monitor(self):
        """Open a persistent stream just for live level monitoring."""
        if self._stream is not None or self.device_index is None:
            return
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            device=self.device_index,
            blocksize=512,  # ~32ms blocks: fine enough to time taps apart
            callback=self._callback,
        )
        self._stream.start()

    def start(self):
        self.frames = []
        self.open_monitor()  # reuse the monitor stream for capture
        self.recording = True

    def stop(self):
        self.recording = False

    def close(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_audio_array(self):
        if not self.frames:
            return None
        return np.concatenate(self.frames, axis=0)


def transcribe_audio(audio_array):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name

    try:
        audio_int16 = (audio_array * 32767).astype(np.int16)
        wav_write(tmp_path, SAMPLE_RATE, audio_int16)
        model = get_whisper_model()
        segments, _info = model.transcribe(
            tmp_path,
            beam_size=1,       # greedy decoding: faster than the default beam search
            vad_filter=True,   # skip silent gaps so there's less audio to process
        )
        return " ".join(seg.text for seg in segments).strip()
    finally:
        os.unlink(tmp_path)


def generate_notes(transcript, status_callback):
    client = anthropic.Anthropic()

    prompt = f"""You are an expert note-taker. Below is a transcript from a lecture or speech.
Create beautiful, organized notes from this content. Your notes should:

1. Start with a bold title/topic header
2. List the KEY CONCEPTS with clear explanations
3. Include IMPORTANT DETAILS and supporting points
4. Highlight any notable quotes (use quotation marks)
5. End with a SUMMARY section (3-5 bullet points of the most critical takeaways)

Use clear visual structure with headers (===), subheaders (---), bullet points (•), and
numbered lists where appropriate. Make it easy to scan and review.

TRANSCRIPT:
{transcript}

Generate comprehensive, well-structured notes:"""

    notes_text = []

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            notes_text.append(text)
            status_callback(text)

    return "".join(notes_text)


class NoteDisplayWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("AI Generated Notes")
        self.configure(bg="#1e1e2e")
        if getattr(parent, "kiosk", False):
            self.attributes("-fullscreen", True)
        else:
            self.geometry("900x700")
        self._build_ui()

    def _build_ui(self):
        header = tk.Label(
            self,
            text="AI Generated Notes",
            font=("Helvetica", 18, "bold"),
            bg="#1e1e2e",
            fg="#cdd6f4",
        )
        header.pack(pady=(16, 8))

        frame = tk.Frame(self, bg="#1e1e2e")
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        self.text_area = scrolledtext.ScrolledText(
            frame,
            wrap=tk.WORD,
            font=("Courier New", 12),
            bg="#181825",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            selectbackground="#45475a",
            relief=tk.FLAT,
            padx=16,
            pady=16,
        )
        self.text_area.pack(fill=tk.BOTH, expand=True)

        self._configure_tags()

        btn_frame = tk.Frame(self, bg="#1e1e2e")
        btn_frame.pack(pady=(0, 12))

        copy_btn = tk.Button(
            btn_frame,
            text="Copy Notes",
            command=self._copy_notes,
            bg="#89b4fa",
            fg="#1e1e2e",
            font=("Helvetica", 11, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
        )
        copy_btn.pack(side=tk.LEFT, padx=8)

        close_btn = tk.Button(
            btn_frame,
            text="Close",
            command=self.destroy,
            bg="#45475a",
            fg="#cdd6f4",
            font=("Helvetica", 11),
            relief=tk.FLAT,
            padx=20,
            pady=6,
            cursor="hand2",
        )
        close_btn.pack(side=tk.LEFT, padx=8)

    def _configure_tags(self):
        self.text_area.tag_configure("header", font=("Courier New", 14, "bold"), foreground="#89b4fa")
        self.text_area.tag_configure("subheader", font=("Courier New", 12, "bold"), foreground="#94e2d5")
        self.text_area.tag_configure("bullet", foreground="#a6e3a1")
        self.text_area.tag_configure("quote", foreground="#f9e2af", font=("Courier New", 12, "italic"))
        self.text_area.tag_configure("normal", foreground="#cdd6f4")

    def append_text(self, text):
        self.text_area.configure(state=tk.NORMAL)
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.configure(state=tk.DISABLED)

    def set_full_text(self, text):
        self.text_area.configure(state=tk.NORMAL)
        self.text_area.delete("1.0", tk.END)
        self._render_formatted(text)
        self.text_area.configure(state=tk.DISABLED)

    def _render_formatted(self, text):
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("===") or stripped.endswith("==="):
                self.text_area.insert(tk.END, line + "\n", "header")
            elif stripped.startswith("---") or stripped.endswith("---"):
                self.text_area.insert(tk.END, line + "\n", "subheader")
            elif stripped.startswith("•") or stripped.startswith("-") or stripped.startswith("*"):
                self.text_area.insert(tk.END, line + "\n", "bullet")
            elif '"' in stripped and stripped.count('"') >= 2:
                self.text_area.insert(tk.END, line + "\n", "quote")
            elif stripped.startswith("#"):
                self.text_area.insert(tk.END, line.lstrip("#").strip() + "\n", "header")
            else:
                self.text_area.insert(tk.END, line + "\n", "normal")

    def _copy_notes(self):
        content = self.text_area.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(content)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI Lecture Note-Taker")
        self.configure(bg="#1e1e2e")

        # Kiosk mode: fullscreen, no window decorations, no way to accidentally exit.
        # Enabled by default; set KIOSK=0 to run in a normal window (e.g. for testing).
        self.kiosk = os.environ.get("KIOSK", "1") != "0"
        if self.kiosk:
            self.attributes("-fullscreen", True)
            self.config(cursor="arrow")
            # Emergency exit so the device isn't permanently locked: Ctrl+Shift+Q
            self.bind("<Control-Shift-Q>", lambda e: self.destroy())
        else:
            self.geometry("600x480")
            self.resizable(False, False)

        self.recorder = AudioRecorder()
        self.is_recording = False
        self._notes_queue = queue.Queue()
        self._notes_window = None
        self._notes_buffer = []

        # Acoustic double-tap control: the mic listens for two finger taps on
        # the screen and toggles recording. On by default; TAP_LISTEN=0 disables.
        self._tap_listen = os.environ.get("TAP_LISTEN", "1") == "1"
        self._recent_taps = []           # timestamps of recent detected taps
        self._tap_min_gap = 0.10         # two taps must be at least this far apart
        self._tap_max_gap = 0.60         # ...and at most this far apart
        self._tap_lockout_until = 0.0    # ignore taps briefly after a toggle

        self._build_ui()
        self._poll_queue()

        # Double-tap (or double-click) anywhere on the screen to start/stop.
        # Works with both a touchscreen and a mouse.
        self.bind("<Double-Button-1>", self._on_double_tap)

        # Start live mic monitoring so the level meter works immediately.
        try:
            self.recorder.open_monitor()
        except Exception as e:
            self._log(f"Could not open microphone: {e}")
        self._update_level()

    def _on_double_tap(self, event=None):
        # Toggle recording: start if idle, stop if recording.
        if self.is_recording:
            if self.stop_btn["state"] != tk.DISABLED:
                self._on_stop()
        else:
            if self.start_btn["state"] != tk.DISABLED:
                self._on_start()

    def _build_ui(self):
        title_lbl = tk.Label(
            self,
            text="AI Lecture Note-Taker",
            font=("Helvetica", 22, "bold"),
            bg="#1e1e2e",
            fg="#cdd6f4",
        )
        title_lbl.pack(pady=(30, 4))

        subtitle_lbl = tk.Label(
            self,
            text="Double-tap the screen to start / stop",
            font=("Helvetica", 12),
            bg="#1e1e2e",
            fg="#6c7086",
        )
        subtitle_lbl.pack(pady=(0, 16))

        # Show which microphone the app is actually using.
        dev_name = self.recorder.device_name
        dev_ok = self.recorder.device_index is not None
        self.device_lbl = tk.Label(
            self,
            text=("🎤 Mic: " + dev_name) if dev_ok else "⚠ NO MICROPHONE DETECTED",
            font=("Helvetica", 11),
            bg="#1e1e2e",
            fg="#a6e3a1" if dev_ok else "#f38ba8",
        )
        self.device_lbl.pack(pady=(0, 8))

        # Live input-level meter so you can SEE the mic picking up sound.
        self.level_canvas = tk.Canvas(self, width=300, height=14, bg="#181825", highlightthickness=0)
        self.level_canvas.pack(pady=(0, 16))
        self._level_bar = self.level_canvas.create_rectangle(0, 0, 0, 14, fill="#a6e3a1", outline="")

        self.indicator = tk.Canvas(self, width=20, height=20, bg="#1e1e2e", highlightthickness=0)
        self.indicator.pack()
        self._dot = self.indicator.create_oval(2, 2, 18, 18, fill="#45475a", outline="")

        self.status_lbl = tk.Label(
            self,
            text="Double-tap the screen (or press Start) to begin",
            font=("Helvetica", 12),
            bg="#1e1e2e",
            fg="#6c7086",
        )
        self.status_lbl.pack(pady=(10, 30))

        btn_frame = tk.Frame(self, bg="#1e1e2e")
        btn_frame.pack()

        # Large tap targets so they're easy to press with a finger on a
        # Pi touchscreen. width/height are in text units; big padding gives
        # a generous touch area.
        self.start_btn = tk.Button(
            btn_frame,
            text="▶  Start",
            command=self._on_start,
            font=("Helvetica", 20, "bold"),
            bg="#a6e3a1",
            fg="#1e1e2e",
            activebackground="#94d68f",
            relief=tk.FLAT,
            width=10,
            padx=20,
            pady=28,
            cursor="hand2",
        )
        self.start_btn.pack(side=tk.LEFT, padx=14)

        self.stop_btn = tk.Button(
            btn_frame,
            text="■  Stop",
            command=self._on_stop,
            font=("Helvetica", 20, "bold"),
            bg="#f38ba8",
            fg="#1e1e2e",
            activebackground="#e07b98",
            relief=tk.FLAT,
            width=10,
            padx=20,
            pady=28,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=14)

        self.progress = ttk.Progressbar(self, mode="indeterminate", length=400)
        self.progress.pack(pady=(30, 0))

        self.log_area = scrolledtext.ScrolledText(
            self,
            height=6,
            font=("Courier New", 10),
            bg="#181825",
            fg="#6c7086",
            relief=tk.FLAT,
            state=tk.DISABLED,
            padx=10,
            pady=8,
        )
        self.log_area.pack(fill=tk.X, padx=20, pady=(12, 20))

    def _update_level(self):
        # Scale RMS (typically 0–0.3) up to a 0–1 range for the bar.
        level = min(1.0, self.recorder.current_level * 6)
        width = int(level * 300)
        self.level_canvas.coords(self._level_bar, 0, 0, width, 14)
        # Green when quiet, yellow/red as it gets loud.
        color = "#a6e3a1" if level < 0.6 else ("#f9e2af" if level < 0.85 else "#f38ba8")
        self.level_canvas.itemconfig(self._level_bar, fill=color)

        self._check_double_tap()
        self.after(30, self._update_level)

    def _check_double_tap(self):
        """Detect two quick finger taps via the mic and toggle recording."""
        if not self._tap_listen:
            return
        now = time.monotonic()
        new_taps = self.recorder.consume_taps()
        for t in new_taps:
            if t < self._tap_lockout_until:
                continue
            self._recent_taps.append(t)

        # Drop taps older than the double-tap window.
        self._recent_taps = [t for t in self._recent_taps if now - t < 1.0]

        if len(self._recent_taps) >= 2:
            gap = self._recent_taps[-1] - self._recent_taps[-2]
            if self._tap_min_gap <= gap <= self._tap_max_gap:
                self._recent_taps = []
                # Ignore further taps for a moment so the same knocks don't
                # immediately toggle back.
                self._tap_lockout_until = now + 1.0
                self._on_double_tap()

    def _log(self, msg):
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def _set_status(self, text, color="#6c7086"):
        self.status_lbl.configure(text=text, fg=color)

    def _on_start(self):
        self.is_recording = True
        self.recorder.start()
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.indicator.itemconfig(self._dot, fill="#f38ba8")
        self._set_status("Recording... speak now", "#f38ba8")
        self._log("Recording started.")
        self._blink()

    def _blink(self):
        if self.is_recording:
            current = self.indicator.itemcget(self._dot, "fill")
            next_color = "#1e1e2e" if current == "#f38ba8" else "#f38ba8"
            self.indicator.itemconfig(self._dot, fill=next_color)
            self.after(600, self._blink)

    def _on_stop(self):
        self.is_recording = False
        self.recorder.stop()
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
        self.indicator.itemconfig(self._dot, fill="#45475a")
        self._set_status("Processing...", "#89b4fa")
        self._log("Recording stopped. Starting transcription...")
        self.progress.start(10)

        threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        try:
            audio = self.recorder.get_audio_array()
            if audio is None or len(audio) == 0:
                self._notes_queue.put(("error", "No audio recorded."))
                return

            self._notes_queue.put(("status", "Transcribing audio with Whisper..."))
            transcript = transcribe_audio(audio)

            if not transcript:
                self._notes_queue.put(("error", "Could not transcribe audio. Try speaking louder."))
                return

            self._notes_queue.put(("status", f"Transcribed ({len(transcript.split())} words). Generating notes..."))
            self._notes_queue.put(("transcript", transcript))
            self._notes_queue.put(("open_notes_window", None))

            def stream_callback(chunk):
                self._notes_queue.put(("notes_chunk", chunk))

            notes = generate_notes(transcript, stream_callback)
            self._notes_queue.put(("notes_done", notes))

        except Exception as e:
            self._notes_queue.put(("error", f"Error: {e}"))

    def _poll_queue(self):
        try:
            while True:
                msg_type, payload = self._notes_queue.get_nowait()

                if msg_type == "status":
                    self._set_status(payload, "#89b4fa")
                    self._log(payload)

                elif msg_type == "error":
                    self.progress.stop()
                    self._set_status(payload, "#f38ba8")
                    self._log(f"ERROR: {payload}")
                    self.start_btn.configure(state=tk.NORMAL)

                elif msg_type == "transcript":
                    self._log(f"Transcript preview: {payload[:120]}...")

                elif msg_type == "open_notes_window":
                    self._notes_buffer = []
                    self._notes_window = NoteDisplayWindow(self)
                    self._notes_window.append_text("Generating notes, please wait...\n\n")

                elif msg_type == "notes_chunk":
                    if self._notes_window:
                        self._notes_buffer.append(payload)

                elif msg_type == "notes_done":
                    self.progress.stop()
                    self._set_status("Notes ready!", "#a6e3a1")
                    self._log("Notes generated successfully.")
                    if self._notes_window:
                        self._notes_window.set_full_text(payload)
                    self.start_btn.configure(state=tk.NORMAL)

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)


def check_audio():
    """Print detected input devices and which one the app will use."""
    print("=== Audio input devices the Pi can see ===\n")
    inputs = list_input_devices()
    if not inputs:
        print("  NONE FOUND. Is your microphone plugged in?")
        print("  Try:  arecord -l    (lists ALSA capture hardware)")
        return
    for idx, name, ch in inputs:
        print(f"  [{idx}] {name}  ({ch} channel(s))")

    chosen_idx, chosen_name = resolve_input_device()
    print(f"\n=> The app will record from: [{chosen_idx}] {chosen_name}")
    print("\nTo force a different one, set AUDIO_DEVICE to its number or part")
    print("of its name, e.g.:  AUDIO_DEVICE=2 python3 main.py")
    print('                or:  AUDIO_DEVICE="USB" python3 main.py')


def main():
    import sys
    if "--check-audio" in sys.argv or "--list-devices" in sys.argv:
        check_audio()
        return
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
