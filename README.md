# Jarvis — a local AI assistant for macOS

A JARVIS-inspired personal AI assistant that runs entirely on your Mac:
local LLMs through Ollama, voice conversations with wake words, macOS
automation, web research, long-term memory, specialized agents, and a plugin
system — behind a modern desktop UI with a strict permission model.


<img width="1800" height="1169" alt="Screenshot 2026-07-17 at 01 26 43" src="https://github.com/user-attachments/assets/632d61e8-9cb6-4b42-b79d-396e787a4962" />

---

## Requirements

Before anything else, make sure you have these installed:

| What | Check with | Install from |
|---|---|---|
| **macOS** | — | (built for macOS) |
| **Python 3.11+** | `python3 --version` | https://www.python.org/downloads/ |
| **Node.js 18+** | `node --version` | https://nodejs.org |
| **Ollama** | `ollama --version` | https://ollama.com/download |
| **Chrome** (or the desktop app) | — | only needed for the voice features |

You also need at least one model downloaded:

```bash
ollama pull llama3.1
```
   ![Uploading Screenshot 2026-07-17 at 01.26.43.png…]()

---

## ▶️ How to run it — step by step

### Option A: the easy way (one command)

1. Open **Terminal**.
2. Go to the project folder:
   ```bash
   cd path/to/jarvis
   ```
3. Make the start script executable (first time only):
   ```bash
   chmod +x start.sh
   ```
4. Run it:
   ```bash
   ./start.sh
   ```

That's it. On the first run it installs everything automatically (takes a
minute or two), then your browser opens at **http://localhost:5173**.

**To turn it off:** press **Ctrl+C** in that terminal, or from anywhere run:

```bash
./stop.sh          # stops the UI and backend
./stop.sh --all    # also stops Ollama
```

Nothing starts automatically when your Mac boots — if localhost shows
"can't connect", Jarvis is off; run `./start.sh` to turn it on.

### Option B: run it from Visual Studio Code

1. **Open the project**
   - Open VS Code → **File ▸ Open Folder…** → choose the `jarvis` folder.
   - If VS Code suggests recommended extensions (Python, Pylance), click
     **Install** — you want them.

2. **Install the dependencies** (first time only)
   - Press **⇧⌘P** to open the Command Palette.
   - Type **"Tasks: Run Task"** and press Enter.
   - Choose **"Install: everything"**.
   - Wait for both installs to finish in the terminal panel.

3. **Make sure Ollama is running**
   - Open the built-in terminal (**⌃`**) and run:
     ```bash
     ollama serve
     ```
   - If it says the address is already in use, Ollama is already running —
     that's fine, continue.

4. **Start Jarvis**
   - Open the **Run and Debug** panel (**⇧⌘D**, the ▷ icon with a bug).
   - In the dropdown at the top, select **"Jarvis: Run All (backend + frontend)"**.
   - Press **F5** (or click the green ▷).
   - Two things start: the Python backend (port 8765) and the web UI
     (port 5173).

5. **Open the app**
   - Go to **http://localhost:5173** in your browser (Chrome recommended
     for voice).
   - The dot at the bottom-left of the sidebar should be **green** with your
     model name. You're ready — say hi.

6. **Stop it** with the red ■ stop button in VS Code (stops both).

### Option C: run each part manually

```bash
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — backend
cd jarvis/backend
python3 -m venv .venv                      # first time only
.venv/bin/pip install -r requirements.txt  # first time only
.venv/bin/python run.py                    # → http://127.0.0.1:8765

# Terminal 3 — frontend
cd jarvis/frontend
npm install                                # first time only
npm run dev                                # → http://localhost:5173
```

---

## First-run checklist (recommended)

Open **⚙️ Settings** in the app and:

1. **AI model** — pick your model. Any Ollama model works; you can pull new
   ones right from this page with a progress bar.
2. **Embedding model** — set to `nomic-embed-text` (pull it first) to make
   memory recall semantic instead of keyword-based.
3. **Vision model** — set to `llava` (pull it first) to enable
   "what's on my screen?" and camera questions.
4. **Voice** — enable, pick a voice, set your wake words (default:
   "jarvis", "computer", "assistant").

```bash
ollama pull nomic-embed-text
ollama pull llava
brew install imagesnap        # optional, for webcam capture
```

---

## Using Jarvis

- **◉ Core** — the JARVIS command center and main screen: an animated AI core
  that reacts while Jarvis thinks, listens, or speaks, live system meters
  (CPU, memory, loaded model), a tool-activity feed, and a context panel
  showing your current app, browser tabs and music. Type commands right into
  the bar under the core.
- **Type** in the chat box, or press **🎤** and speak, or press **👂** and it
  waits until you say *"Jarvis…"* followed by your request.
- Ask it to *search the web*, *open apps*, *play music or YouTube*, *organize
  files*, *create notes and reminders*, *check your calendar*, *draft
  emails/messages*, *look at your screen*, *remember things about you*,
  *run code* — it picks the right agent and tools automatically.
- **Context-aware automation**: it sees your open tabs and running apps, and
  continues in them — "play Drake" reuses the open YouTube tab; it never opens
  a duplicate window unless you say "new window".
- When a tool touches your system, an **Allow / Deny** dialog appears first.
  Dangerous ones (shell, AppleScript, browser JS, Trash) always ask. Messages
  and emails are only ever **drafted** — you press send yourself.
- **📋 Capabilities** — the Missing Capabilities Registry. Every request
  Jarvis couldn't fulfill is logged automatically with the reason, what was
  missing, a suggested fix and difficulty. Asking again raises its priority
  (1–3× low · 4–10× medium · 10+× high · 20+× critical). Generate a **Weekly
  Capability Report** there to get a prioritized improvement roadmap built
  from your real usage.
- **🧠 Memory** — view, edit or delete everything it remembers.
- **🛠 Developer** — live audit log of every tool call, plus tool/agent/plugin
  inspectors.
- **Custom voices** — Settings → Voice → Speech engine. Built-in browser
  voices work out of the box; install Piper (`brew install piper-tts` plus a
  voice `.onnx`) for local neural TTS with real audio-reactive core
  animations. New engines (XTTS-v2, Kokoro, OpenVoice, voice clones) plug
  into `backend/app/speech/engines.py` without touching anything else.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Red dot / "Ollama offline" in the sidebar | Run `ollama serve` in a terminal |
| "Cannot reach Ollama" error in chat | Same as above, or check Settings → host is `http://localhost:11434` |
| Model errors / empty replies | `ollama pull llama3.1`, and pick it in Settings |
| Port 8765 or 5173 already in use | Something else is running there — stop it, or change the port in `backend/run.py` / `frontend/vite.config.ts` |
| Voice buttons do nothing | Use Chrome (Safari doesn't support the speech API); allow microphone access when prompted |
| `screen_look` fails | Give your terminal/browser Screen Recording permission in System Settings → Privacy & Security |
| Context panel shows "permission missing" | Grant your terminal access under System Settings → Privacy & Security → **Automation** (System Events, Safari, Music) — macOS prompts the first time |
| Browser clicks/JS tools fail | One-time browser setting — Safari: Develop menu → "Allow JavaScript from Apple Events"; Chrome: View → Developer → same option |
| First reply is slow | Normal — Ollama loads the model into memory on the first message |

---

## Desktop app (optional)

A native macOS shell with a menu-bar icon and a ⌘⇧J floating window:

```bash
cd desktop
npm install     # downloads Electron (~100 MB)
npm start
```

It auto-starts the backend if needed. To package a `.app`: run
`npm run build` in `frontend/`, then `npm run package` in `desktop/`.

---

## Project layout

```
jarvis/
├── start.sh          ← one-command launcher
├── .vscode/          ← VS Code run/debug configs (F5)
├── backend/          ← FastAPI server (Python)
│   └── app/          llm/ chat/ tools/ agents/ memory/ plugins/ security/ api/
├── frontend/         ← React + TypeScript UI (Vite)
├── desktop/          ← Electron shell (tray, floating window)
├── plugins/          ← drop-in plugins (example included)
└── docs/             ← architecture & extension guide
```

Your data lives in `~/.jarvis/` (settings.json, jarvis.db, audit.log,
plugins/). Delete that folder for a factory reset.

To extend Jarvis — new tools, agents, or plugins — see
[docs/architecture.md](docs/architecture.md).
