#!/usr/bin/env python3
"""
AI Lecture Note-Taker for Raspberry Pi
Records audio, transcribes with Whisper, generates notes with Claude.
"""

import threading
import queue
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
CLAUDE_MODEL = "claude-opus-4-8"

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
    def __init__(self):
        self.recording = False
        self.frames = []
        self._stream = None
        self.device_index, self.device_name = resolve_input_device()
        self.current_level = 0.0  # 0.0–1.0, live input loudness for the meter

    def _callback(self, indata, frame_count, time_info, status):
        # Track loudness always, so the meter shows the mic is live even
        # before recording. Only buffer frames while actually recording.
        self.current_level = float(np.sqrt(np.mean(indata ** 2)))
        if self.recording:
            self.frames.append(indata.copy())

    def open_monitor(self):
        """Open a persistent stream just for live level monitoring."""
        if self._stream is not None or self.device_index is None:
            return
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            device=self.device_index,
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
        max_tokens=4096,
        thinking={"type": "adaptive"},
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

        self._build_ui()
        self._poll_queue()

        # Start live mic monitoring so the level meter works immediately.
        try:
            self.recorder.open_monitor()
        except Exception as e:
            self._log(f"Could not open microphone: {e}")
        self._update_level()

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
            text="Record · Transcribe · Summarize",
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
            text="Press Start to begin recording",
            font=("Helvetica", 12),
            bg="#1e1e2e",
            fg="#6c7086",
        )
        self.status_lbl.pack(pady=(10, 30))

        btn_frame = tk.Frame(self, bg="#1e1e2e")
        btn_frame.pack()

        self.start_btn = tk.Button(
            btn_frame,
            text="▶  Start Recording",
            command=self._on_start,
            font=("Helvetica", 14, "bold"),
            bg="#a6e3a1",
            fg="#1e1e2e",
            relief=tk.FLAT,
            padx=28,
            pady=12,
            cursor="hand2",
        )
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = tk.Button(
            btn_frame,
            text="■  Stop & Generate",
            command=self._on_stop,
            font=("Helvetica", 14, "bold"),
            bg="#f38ba8",
            fg="#1e1e2e",
            relief=tk.FLAT,
            padx=28,
            pady=12,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT, padx=10)

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
        self.after(60, self._update_level)

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
