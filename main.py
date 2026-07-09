#!/usr/bin/env python3
"""
AI Lecture Note-Taker for Raspberry Pi
Records audio, transcribes with Whisper, generates notes with Claude.
"""

import threading
import queue
import re
import glob
import smtplib
import datetime
from email.message import EmailMessage
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

# Where saved notes live (a "notes" folder next to this script).
NOTES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes")

_whisper_model = None


# --------------------------------------------------------------------------
# Saved-notes storage
# --------------------------------------------------------------------------

def _derive_title(text):
    """Use the first meaningful line of the notes as a short title."""
    for line in text.splitlines():
        clean = line.strip().strip("#=-•* ").strip()
        if clean:
            return clean[:60]
    return "Untitled Notes"


def save_note(text):
    """Save a note to a timestamped file. Returns the file path."""
    os.makedirs(NOTES_DIR, exist_ok=True)
    now = datetime.datetime.now()
    title = _derive_title(text)
    # Make a filesystem-safe slug from the title.
    slug = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")[:40] or "note"
    fname = now.strftime("%Y-%m-%d_%H%M%S_") + slug + ".txt"
    path = os.path.join(NOTES_DIR, fname)
    with open(path, "w") as f:
        f.write(text)
    return path


def list_notes():
    """Return saved notes as [(path, title, date_str)], newest first."""
    if not os.path.isdir(NOTES_DIR):
        return []
    out = []
    for path in sorted(glob.glob(os.path.join(NOTES_DIR, "*.txt")), reverse=True):
        try:
            with open(path) as f:
                text = f.read()
        except OSError:
            continue
        title = _derive_title(text)
        ts = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        out.append((path, title, ts.strftime("%b %d, %Y  %I:%M %p")))
    return out


def delete_note(path):
    if os.path.exists(path):
        os.remove(path)


# --------------------------------------------------------------------------
# Email sending (SMTP)
# --------------------------------------------------------------------------

def load_email_config():
    """Return (address, app_password, host, port) for sending mail.

    Reads EMAIL_ADDRESS / EMAIL_APP_PASSWORD from the environment, or from
    an email_config.txt file next to this script (line 1 = address,
    line 2 = app password). Defaults to Gmail's SMTP server.
    """
    addr = os.environ.get("EMAIL_ADDRESS", "").strip()
    pw = os.environ.get("EMAIL_APP_PASSWORD", "").strip()
    if not (addr and pw):
        cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_config.txt")
        if os.path.exists(cfg):
            with open(cfg) as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if len(lines) >= 2:
                addr, pw = lines[0], lines[1]
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    return addr, pw, host, port


def send_note_email(path, recipient):
    """Email a saved note (as body + attachment) to recipient."""
    addr, pw, host, port = load_email_config()
    if not (addr and pw):
        raise RuntimeError(
            "Email isn't set up. Create email_config.txt with your Gmail "
            "address on line 1 and an app password on line 2."
        )
    with open(path) as f:
        body = f.read()
    title = _derive_title(body)

    msg = EmailMessage()
    msg["Subject"] = f"Notes: {title}"
    msg["From"] = addr
    msg["To"] = recipient
    msg.set_content(body)
    msg.add_attachment(body.encode("utf-8"), maintype="text",
                       subtype="plain", filename=os.path.basename(path))

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(addr, pw)
        server.send_message(msg)


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        # faster-whisper: lightweight, no PyTorch, runs well on a Raspberry Pi.
        # Model size and thread count are tunable via env vars for speed:
        #   WHISPER_MODEL=tiny   -> ~3-4x faster than "base" (slightly less accurate)
        #   WHISPER_THREADS=4    -> use all 4 Pi cores (defaults to all available)
        # tiny.en = English-only tiny model: faster AND more accurate for
        # English than plain "tiny". Use WHISPER_MODEL=tiny for other languages.
        model_size = os.environ.get("WHISPER_MODEL", "tiny.en")
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
            language=os.environ.get("WHISPER_LANG", "en"),  # skip auto-detect
            beam_size=1,       # greedy decoding: faster than the default beam search
            vad_filter=True,   # skip silent gaps so there's less audio to process
            condition_on_previous_text=False,  # less work per segment
        )
        return " ".join(seg.text for seg in segments).strip()
    finally:
        os.unlink(tmp_path)


def load_api_key():
    """Find the Anthropic API key from the environment or a local file.

    Checks, in order:
      1. ANTHROPIC_API_KEY environment variable
      2. api_key.txt sitting next to this script (easiest for non-terminal use)
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    return None


def generate_notes(transcript, status_callback):
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError(
            "No API key found. Create a file called api_key.txt in the "
            "AI-Device folder and paste your key into it."
        )
    client = anthropic.Anthropic(api_key=api_key)

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
        # Top bar with title and an X button to go back to the main screen.
        top_bar = tk.Frame(self, bg="#1e1e2e")
        top_bar.pack(fill=tk.X, pady=(10, 8), padx=12)

        header = tk.Label(
            top_bar,
            text="AI Generated Notes",
            font=("Helvetica", 18, "bold"),
            bg="#1e1e2e",
            fg="#cdd6f4",
        )
        header.pack(side=tk.LEFT, padx=(4, 0))

        x_btn = tk.Button(
            top_bar,
            text="✕",
            command=self.destroy,
            font=("Helvetica", 18, "bold"),
            bg="#f38ba8",
            fg="#1e1e2e",
            activebackground="#e07b98",
            relief=tk.FLAT,
            width=3,
            pady=4,
            cursor="hand2",
        )
        x_btn.pack(side=tk.RIGHT)

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

        # Touch drag-to-scroll, like a phone: press and drag up/down to scroll.
        self._drag_last_y = None
        self.text_area.bind("<ButtonPress-1>", self._on_drag_start)
        self.text_area.bind("<B1-Motion>", self._on_drag_move)
        # Mouse wheel / trackpad scrolling too.
        self.text_area.bind("<MouseWheel>", self._on_wheel)
        self.text_area.bind("<Button-4>", lambda e: self.text_area.yview_scroll(-3, "units"))
        self.text_area.bind("<Button-5>", lambda e: self.text_area.yview_scroll(3, "units"))

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

    def _on_drag_start(self, event):
        self._drag_last_y = event.y
        return "break"  # don't start a text selection on touch

    def _on_drag_move(self, event):
        if self._drag_last_y is None:
            self._drag_last_y = event.y
            return "break"
        # Scroll by how far the finger moved since the last event.
        dy = event.y - self._drag_last_y
        self._drag_last_y = event.y
        # Drag down -> content moves down (scroll up), like a phone.
        self.text_area.yview_scroll(int(-dy / 3) or (-1 if dy > 0 else 1), "units")
        return "break"

    def _on_wheel(self, event):
        self.text_area.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _copy_notes(self):
        content = self.text_area.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(content)


class OnScreenKeyboard(tk.Toplevel):
    """A finger-friendly keyboard for typing (e.g. an email address)."""

    ROWS = [
        list("1234567890"),
        list("qwertyuiop"),
        list("asdfghjkl"),
        list("zxcvbnm"),
    ]

    def __init__(self, parent, prompt, on_submit, initial=""):
        super().__init__(parent)
        self.on_submit = on_submit
        self.configure(bg="#1e1e2e")
        self.transient(parent)
        self.grab_set()
        if getattr(parent, "kiosk", False) or getattr(getattr(parent, "master", None), "kiosk", False):
            self.attributes("-fullscreen", True)
        else:
            self.geometry("820x520")

        tk.Label(self, text=prompt, font=("Helvetica", 16, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(pady=(16, 8))

        self.var = tk.StringVar(value=initial)
        entry = tk.Entry(self, textvariable=self.var, font=("Courier New", 20),
                         bg="#181825", fg="#cdd6f4", insertbackground="#cdd6f4",
                         relief=tk.FLAT, justify=tk.CENTER)
        entry.pack(fill=tk.X, padx=24, pady=(0, 12), ipady=8)

        keys = tk.Frame(self, bg="#1e1e2e")
        keys.pack(expand=True)
        for row in self.ROWS:
            rf = tk.Frame(keys, bg="#1e1e2e")
            rf.pack(pady=3)
            for ch in row:
                self._key(rf, ch, lambda c=ch: self._append(c))

        # Bottom row: special keys.
        special = tk.Frame(keys, bg="#1e1e2e")
        special.pack(pady=3)
        self._key(special, "@", lambda: self._append("@"))
        self._key(special, ".", lambda: self._append("."))
        self._key(special, "_", lambda: self._append("_"))
        self._key(special, "-", lambda: self._append("-"))
        self._key(special, "⌫", self._backspace, width=4, bg="#f9e2af")
        self._key(special, "@gmail.com", lambda: self._append("@gmail.com"),
                  width=11, bg="#89b4fa")

        # Action buttons.
        actions = tk.Frame(self, bg="#1e1e2e")
        actions.pack(pady=(10, 16))
        tk.Button(actions, text="Cancel", command=self.destroy,
                  font=("Helvetica", 15, "bold"), bg="#45475a", fg="#cdd6f4",
                  relief=tk.FLAT, width=10, pady=12, cursor="hand2").pack(side=tk.LEFT, padx=10)
        tk.Button(actions, text="Send ✉", command=self._submit,
                  font=("Helvetica", 15, "bold"), bg="#a6e3a1", fg="#1e1e2e",
                  relief=tk.FLAT, width=10, pady=12, cursor="hand2").pack(side=tk.LEFT, padx=10)

    def _key(self, parent, label, cmd, width=3, bg="#313244"):
        tk.Button(parent, text=label, command=cmd, font=("Helvetica", 15, "bold"),
                  bg=bg, fg="#cdd6f4" if bg in ("#313244",) else "#1e1e2e",
                  activebackground="#585b70", relief=tk.FLAT, width=width, pady=10,
                  cursor="hand2").pack(side=tk.LEFT, padx=3)

    def _append(self, ch):
        self.var.set(self.var.get() + ch)

    def _backspace(self):
        self.var.set(self.var.get()[:-1])

    def _submit(self):
        value = self.var.get().strip()
        if value:
            cb = self.on_submit
            self.destroy()
            cb(value)


class SavedNotesWindow(tk.Toplevel):
    """Browse saved notes: open, email, or delete each one."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Saved Notes")
        self.configure(bg="#1e1e2e")
        if getattr(parent, "kiosk", False):
            self.attributes("-fullscreen", True)
        else:
            self.geometry("900x700")

        # Top bar.
        top = tk.Frame(self, bg="#1e1e2e")
        top.pack(fill=tk.X, pady=(10, 8), padx=12)
        tk.Label(top, text="Saved Notes", font=("Helvetica", 18, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(side=tk.LEFT, padx=(4, 0))
        tk.Button(top, text="✕", command=self.destroy, font=("Helvetica", 18, "bold"),
                  bg="#f38ba8", fg="#1e1e2e", relief=tk.FLAT, width=3, pady=4,
                  cursor="hand2").pack(side=tk.RIGHT)

        self.status = tk.Label(self, text="", font=("Helvetica", 12),
                               bg="#1e1e2e", fg="#94e2d5")
        self.status.pack(pady=(0, 4))

        # Scrollable list area (Canvas + inner frame), with touch drag.
        container = tk.Frame(self, bg="#181825")
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self.canvas = tk.Canvas(container, bg="#181825", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.list_frame = tk.Frame(self.canvas, bg="#181825")
        self._win = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>",
                             lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                        lambda e: self.canvas.itemconfig(self._win, width=e.width))
        # Touch/mouse scrolling.
        self._drag_y = None
        for w in (self.canvas, self.list_frame):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
            w.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

        self.refresh()

    def _drag_start(self, e):
        self._drag_y = e.y_root

    def _drag_move(self, e):
        if self._drag_y is not None:
            dy = e.y_root - self._drag_y
            self._drag_y = e.y_root
            self.canvas.yview_scroll(int(-dy / 3) or (-1 if dy > 0 else 1), "units")

    def refresh(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        notes = list_notes()
        if not notes:
            tk.Label(self.list_frame, text="No saved notes yet.",
                     font=("Helvetica", 14), bg="#181825", fg="#6c7086").pack(pady=40)
            return
        for path, title, date_str in notes:
            self._add_row(path, title, date_str)

    def _add_row(self, path, title, date_str):
        row = tk.Frame(self.list_frame, bg="#1e1e2e")
        row.pack(fill=tk.X, padx=8, pady=6)

        # Title + date on top.
        tk.Label(row, text=title, font=("Helvetica", 14, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4", anchor="w").pack(fill=tk.X, padx=10, pady=(8, 0))
        tk.Label(row, text=date_str, font=("Helvetica", 10),
                 bg="#1e1e2e", fg="#6c7086", anchor="w").pack(fill=tk.X, padx=10)

        # Buttons in a row BELOW the title, so they always fit a narrow screen.
        btns = tk.Frame(row, bg="#1e1e2e")
        btns.pack(fill=tk.X, padx=10, pady=(6, 10))
        tk.Button(btns, text="Open", command=lambda p=path: self._open(p),
                  font=("Helvetica", 13, "bold"), bg="#89b4fa", fg="#1e1e2e",
                  relief=tk.FLAT, pady=10, cursor="hand2").pack(
                      side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        tk.Button(btns, text="Email", command=lambda p=path: self._email(p),
                  font=("Helvetica", 13, "bold"), bg="#a6e3a1", fg="#1e1e2e",
                  relief=tk.FLAT, pady=10, cursor="hand2").pack(
                      side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        tk.Button(btns, text="Delete", command=lambda p=path: self._delete(p),
                  font=("Helvetica", 13, "bold"), bg="#f38ba8", fg="#1e1e2e",
                  relief=tk.FLAT, pady=10, cursor="hand2").pack(
                      side=tk.LEFT, expand=True, fill=tk.X, padx=4)

    def _open(self, path):
        with open(path) as f:
            text = f.read()
        win = NoteDisplayWindow(self.app)
        win.set_full_text(text)

    def _email(self, path):
        default = os.environ.get("DEFAULT_EMAIL", "")
        OnScreenKeyboard(self, "Type the email address to send to:",
                         lambda addr: self._do_send(path, addr), initial=default)

    def _do_send(self, path, addr):
        self.status.configure(text=f"Sending to {addr}...", fg="#f9e2af")

        def worker():
            try:
                send_note_email(path, addr)
                self.after(0, lambda: self.status.configure(
                    text=f"✓ Sent to {addr}", fg="#a6e3a1"))
            except Exception as e:
                self.after(0, lambda: self.status.configure(
                    text=f"✗ {e}", fg="#f38ba8"))

        threading.Thread(target=worker, daemon=True).start()

    def _delete(self, path):
        # Simple tap-to-confirm dialog.
        dlg = tk.Toplevel(self)
        dlg.configure(bg="#1e1e2e")
        dlg.transient(self)
        dlg.grab_set()
        if getattr(self.app, "kiosk", False):
            dlg.attributes("-fullscreen", True)
        else:
            dlg.geometry("420x200")
        tk.Label(dlg, text="Delete this note?", font=("Helvetica", 18, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(pady=(50, 24))
        row = tk.Frame(dlg, bg="#1e1e2e")
        row.pack()
        tk.Button(row, text="Cancel", command=dlg.destroy,
                  font=("Helvetica", 14, "bold"), bg="#45475a", fg="#cdd6f4",
                  relief=tk.FLAT, width=9, pady=12, cursor="hand2").pack(side=tk.LEFT, padx=10)

        def do():
            delete_note(path)
            dlg.destroy()
            self.refresh()
            self.status.configure(text="Note deleted.", fg="#f38ba8")

        tk.Button(row, text="Delete", command=do,
                  font=("Helvetica", 14, "bold"), bg="#f38ba8", fg="#1e1e2e",
                  relief=tk.FLAT, width=9, pady=12, cursor="hand2").pack(side=tk.LEFT, padx=10)


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

        # Double-tap (or double-click) anywhere on the screen to start/stop.
        # Works with both a touchscreen and a mouse.
        self.bind("<Double-Button-1>", self._on_double_tap)
        # Spacebar also toggles (handy if a keyboard is attached).
        self.bind("<space>", lambda e: self._on_double_tap())

        # Physical GPIO push button: press to start/stop. Wire a button between
        # BUTTON_PIN and GND. Default GPIO17 (also the ReSpeaker 2-Mic HAT button).
        self._setup_gpio_button()

        # Start live mic monitoring so the level meter works immediately.
        try:
            self.recorder.open_monitor()
        except Exception as e:
            self._log(f"Could not open microphone: {e}")
        self._update_level()

    def _setup_gpio_button(self):
        """Wire a physical push button (GPIO) to start/stop, if available."""
        pin = int(os.environ.get("BUTTON_PIN", "17"))
        try:
            from gpiozero import Button
            # Button between the pin and GND; internal pull-up (default).
            self._gpio_button = Button(pin, pull_up=True, bounce_time=0.05)
            # gpiozero fires this on a background thread, so hand off to the
            # Tk thread safely via the queue instead of touching widgets here.
            self._gpio_button.when_pressed = lambda: self._notes_queue.put(("button", None))
            self._log(f"Physical button ready on GPIO{pin}.")
        except Exception as e:
            # No gpiozero, not on a Pi, or pin in use — just skip it.
            self._gpio_button = None
            self._log(f"No GPIO button (GPIO{pin}): {e}")

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
            text="Tap Start to record · Tap Stop for notes",
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
            text="Press the button (or Start) to begin",
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

        # Open the saved-notes library.
        self.notes_btn = tk.Button(
            self,
            text="📁  Saved Notes",
            command=self._open_saved_notes,
            font=("Helvetica", 14, "bold"),
            bg="#89b4fa",
            fg="#1e1e2e",
            activebackground="#74a0e0",
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor="hand2",
        )
        self.notes_btn.pack(pady=(20, 0))

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

    def _open_saved_notes(self):
        SavedNotesWindow(self)

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

                elif msg_type == "button":
                    self._on_double_tap()

                elif msg_type == "error":
                    self.progress.stop()
                    self._set_status(payload, "#f38ba8")
                    self._log(f"ERROR: {payload}")
                    self.start_btn.configure(state=tk.NORMAL)
                    # Show the error ON the notes window too, since it covers
                    # the main screen and the user can't see the log otherwise.
                    if self._notes_window:
                        self._notes_window.set_full_text(
                            "=== Something went wrong ===\n\n" + str(payload)
                        )

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
                    # Auto-save every note to the notes folder.
                    try:
                        path = save_note(payload)
                        self._log(f"Saved: {os.path.basename(path)}")
                    except Exception as e:
                        self._log(f"Could not save note: {e}")
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
