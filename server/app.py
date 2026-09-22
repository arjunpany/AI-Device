#!/usr/bin/env python3
"""
StudyChat — tiny web app that hosts lecture notes at a short link and lets
anyone open them and ask an AI questions about the content.

Endpoints:
  POST /api/notes        {title, content}      -> {id, url}   (Pi uploads here)
  GET  /n/<id>                                  -> the chat page for that note
  GET  /api/notes/<id>                          -> {title, content}
  POST /api/chat         {id, messages}         -> {reply}

The Anthropic API key lives ONLY on the server (env var ANTHROPIC_API_KEY),
so students never need their own key — they just open the link.
"""
import os
import time
import json
import sqlite3
import secrets

from flask import Flask, request, jsonify, render_template_string, abort
import anthropic

app = Flask(__name__)

DB_PATH = os.environ.get("DB_PATH", "notes.db")
MODEL = os.environ.get("NOTES_MODEL", "claude-haiku-4-5")
_client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


# --------------------------------------------------------------------------
# Storage (SQLite)
# --------------------------------------------------------------------------
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notes ("
        "id TEXT PRIMARY KEY, title TEXT, content TEXT, created REAL)"
    )
    return conn


def save_note(title, content):
    note_id = secrets.token_urlsafe(5)[:7]
    with _db() as conn:
        conn.execute(
            "INSERT INTO notes (id, title, content, created) VALUES (?,?,?,?)",
            (note_id, title or "Lecture Notes", content or "", time.time()),
        )
    return note_id


def get_note(note_id):
    with _db() as conn:
        row = conn.execute(
            "SELECT id, title, content FROM notes WHERE id=?", (note_id,)
        ).fetchone()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "content": row[2]}


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.post("/api/notes")
def api_create():
    data = request.get_json(force=True, silent=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    note_id = save_note(data.get("title"), content)
    url = request.url_root.rstrip("/") + "/n/" + note_id
    return jsonify({"id": note_id, "url": url})


@app.get("/api/notes/<note_id>")
def api_get(note_id):
    note = get_note(note_id)
    if not note:
        return jsonify({"error": "not found"}), 404
    return jsonify(note)


@app.post("/api/chat")
def api_chat():
    data = request.get_json(force=True, silent=True) or {}
    note = get_note(data.get("id", ""))
    if not note:
        return jsonify({"error": "note not found"}), 404
    messages = data.get("messages") or []
    # Keep only role/content and cap history length.
    clean = [{"role": m["role"], "content": str(m["content"])[:4000]}
             for m in messages if m.get("role") in ("user", "assistant")][-16:]
    if not clean or clean[-1]["role"] != "user":
        return jsonify({"error": "need a user message"}), 400
    system = (
        "You are a friendly study assistant. Answer the student's questions "
        "using ONLY the lecture notes below. If the notes don't cover something, "
        "say so briefly and point to what they do cover. Be clear and concise; "
        "quiz the student if they ask.\n\nLECTURE NOTES:\n" + note["content"]
    )
    try:
        resp = _client.messages.create(
            model=MODEL, max_tokens=1024, system=system, messages=clean,
        )
        reply = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    except Exception as e:
        return jsonify({"error": f"assistant error: {type(e).__name__}"}), 502
    return jsonify({"reply": reply})


# --------------------------------------------------------------------------
# The chat page
# --------------------------------------------------------------------------
@app.get("/n/<note_id>")
def page(note_id):
    if not get_note(note_id):
        abort(404)
    return render_template_string(PAGE, note_id=note_id)


@app.get("/")
def home():
    return "StudyChat is running. Notes open at /n/&lt;id&gt;.", 200


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ask Your Notes</title>
<style>
 :root{--bg:#f4f6fb;--panel:#fff;--ink:#1a1c25;--muted:#5c6273;--line:#d9deea;
  --accent:#3b6fd6;--ai:#fff;--note-bg:#f0f3fa;--blue:#2f6ad0;--red:#c6413f;
  --green:#2e9a5f;--yellow:#b6871a;--purple:#7b52c9;
  --sans:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,Menlo,Consolas,monospace;}
 @media(prefers-color-scheme:dark){:root{--bg:#0f121a;--panel:#171b26;--ink:#e6e9f2;
  --muted:#9aa1b4;--line:#282e3d;--accent:#5b8bf0;--ai:#0f121a;--note-bg:#12151f;
  --blue:#7aa8ef;--red:#f08a88;--green:#8fd6a8;--yellow:#e6c06a;--purple:#c3a6f0;}}
 *{box-sizing:border-box}html,body{height:100%}
 body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  height:100dvh;display:flex;flex-direction:column}
 header{padding:13px 18px;border-bottom:1px solid var(--line);background:var(--panel);
  display:flex;align-items:center;gap:12px;flex:none}
 .brand{width:32px;height:32px;border-radius:9px;background:var(--accent);color:#fff;
  display:grid;place-items:center;font-weight:800}
 header h1{font-size:16px;margin:0}header p{margin:1px 0 0;font-size:12.5px;color:var(--muted)}
 .wrap{flex:1;display:flex;min-height:0}@media(max-width:820px){.wrap{flex-direction:column}}
 .notes{width:42%;max-width:460px;border-right:1px solid var(--line);background:var(--note-bg);
  overflow-y:auto;padding:18px 20px}
 @media(max-width:820px){.notes{width:100%;max-width:none;max-height:34vh;border-right:none;
  border-bottom:1px solid var(--line)}}
 .nline{font-size:13.5px;line-height:1.5;margin:2px 0;white-space:pre-wrap}
 .n-title{font-weight:800;font-size:16px;color:var(--blue);margin:2px 0 8px}
 .n-head{font-weight:700;color:var(--blue);margin-top:12px}
 .n-imp{color:var(--red);font-family:var(--mono);font-size:12.5px}
 .n-ex{color:var(--green);font-style:italic}.n-def{color:var(--yellow)}.n-q{color:var(--purple)}
 .chat{flex:1;display:flex;flex-direction:column;min-width:0;min-height:0}
 .msgs{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
 .bubble{max-width:78%;padding:11px 14px;border-radius:14px;font-size:14.5px;line-height:1.5;
  white-space:pre-wrap;word-wrap:break-word}
 .u{align-self:flex-end;background:var(--accent);color:#fff;border-bottom-right-radius:4px}
 .a{align-self:flex-start;background:var(--panel);border:1px solid var(--line);border-bottom-left-radius:4px}
 .sys{align-self:center;color:var(--muted);font-size:13px;text-align:center;max-width:90%}
 .bar{display:flex;gap:10px;padding:14px 16px;border-top:1px solid var(--line);background:var(--panel)}
 .bar input{flex:1;border:1px solid var(--line);background:var(--bg);color:var(--ink);
  border-radius:12px;padding:12px 14px;font-size:15px;outline:none}
 .bar input:focus{border-color:var(--accent)}
 .bar button{border:none;background:var(--accent);color:#fff;border-radius:12px;padding:0 20px;
  font-size:15px;font-weight:700;cursor:pointer}.bar button:disabled{opacity:.5}
</style></head><body>
<header><div class="brand">✳</div><div><h1 id="t">Ask Your Notes</h1><p id="d"></p></div></header>
<div class="wrap"><aside class="notes" id="notes"></aside>
<section class="chat"><div class="msgs" id="msgs"></div>
<div class="bar"><input id="q" placeholder="Ask about this lecture…" autocomplete="off">
<button id="send">Ask</button></div></section></div>
<script>
const ID={{ note_id|tojson }};
let content="", history=[], busy=false;
const msgs=document.getElementById('msgs');
function bubble(cls,txt){const b=document.createElement('div');b.className='bubble '+cls;
 b.textContent=txt;msgs.appendChild(b);msgs.scrollTop=msgs.scrollHeight;return b;}
function renderNotes(text){const box=document.getElementById('notes');box.innerHTML='';
 text.split('\n').forEach(raw=>{const s=raw.trim();const d=document.createElement('div');d.className='nline';
  if(!s){d.innerHTML='&nbsp;';}
  else if(s.startsWith('# ')){d.className='n-title';d.textContent=s.slice(2);}
  else if(s.startsWith('## ')){d.className='nline n-head';d.textContent=s.slice(3);}
  else if(/^important:/i.test(s)){d.className='nline n-imp';d.textContent=s;}
  else if(/^example:/i.test(s)){d.className='nline n-ex';d.textContent=s;}
  else if(/^definition:/i.test(s)){d.className='nline n-def';d.textContent=s;}
  else if(/^q:/i.test(s)){d.className='nline n-q';d.textContent=s;}
  else d.textContent=s;box.appendChild(d);});}
fetch('/api/notes/'+ID).then(r=>r.json()).then(n=>{content=n.content||'';
 document.getElementById('t').textContent=n.title||'Lecture Notes';renderNotes(content);
 bubble('sys','Ask anything about this lecture — the assistant answers from these notes.');});
async function send(){const inp=document.getElementById('q');const q=inp.value.trim();
 if(!q||busy)return;inp.value='';busy=true;document.getElementById('send').disabled=true;
 bubble('u',q);history.push({role:'user',content:q});const bot=bubble('a','Thinking…');
 try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({id:ID,messages:history})});const j=await r.json();
  bot.textContent=j.reply||j.error||'Sorry, no answer.';
  if(j.reply)history.push({role:'assistant',content:j.reply});}
 catch(e){bot.textContent='Network error — try again.';}
 busy=false;document.getElementById('send').disabled=false;inp.focus();}
document.getElementById('send').onclick=send;
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script></body></html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
