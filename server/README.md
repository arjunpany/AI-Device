# StudyChat server

A tiny web app that hosts each lecture's notes at a short link and lets anyone
open it and ask an AI questions about the content. The Pi uploads notes here
and puts the short link in the email.

## Deploy to Render (free) — one time, ~5 minutes

1. Push this repo to GitHub (it already is).
2. Go to **https://render.com** → sign up (free) → **New → Blueprint**.
3. Connect this GitHub repo. Render reads `render.yaml` and sets up the service.
4. When prompted, paste your **`ANTHROPIC_API_KEY`** (the same `sk-ant-…` key).
   This key lives only on the server — students never need one.
5. Click **Apply / Deploy**. Wait a few minutes for the first build.
6. Render gives you a URL like **`https://studychat.onrender.com`**. Copy it.

## Point the Pi at it

On the Pi, add this line to `run.sh` (and/or `~/.bashrc`):

```bash
export NOTES_SERVER_URL="https://studychat.onrender.com"
```

Now when you email notes, the Pi uploads them and the email contains a short
link like `https://studychat.onrender.com/n/ab12cd` — open it and chat.

## Run locally (to test)

```bash
cd server
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
python app.py        # http://localhost:8000
```

## Free-tier notes
- Render's free service **sleeps after ~15 min idle** — the first open after
  that takes ~30–60 s to wake, then it's fast.
- Notes are stored in a local SQLite file, which **resets on redeploy**. Fine
  for use right after class; for permanent storage, add a Render Postgres
  database later (ask and I'll wire it in).
