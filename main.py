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
import whisper
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
        _whisper_model = whisper.load_model("base")
    return _whisper_model


class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.frames = []
        self._stream = None

    def start(self):
        self.frames = []
        self.recording = True

        def callback(indata, frame_count, time_info, status):
            if self.recording:
                self.frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self):
        self.recording = False
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
        result = model.transcribe(tmp_path, fp16=False)
        return result["text"].strip()
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
        self.geometry("900x700")
        self.configure(bg="#1e1e2e")
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
        self.geometry("600x480")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        self.recorder = AudioRecorder()
        self.is_recording = False
        self._notes_queue = queue.Queue()
        self._notes_window = None
        self._notes_buffer = []

        self._build_ui()
        self._poll_queue()

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
        subtitle_lbl.pack(pady=(0, 30))

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


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
