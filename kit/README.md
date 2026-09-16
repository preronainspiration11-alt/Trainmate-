# TrainMate — clean install (Posimat MASTER-15)

Answers questions from the manual in **English / বাংলা / हिन्दी**, shows **clean machine
diagrams**, and supports **voice input**. Self-contained.

```
kit/
├─ server.py            backend (Claude + auto diagram picker + language + voice)
├─ client.html          the interface you type into
├─ run.ps1              one-command launcher (Windows)
├─ requirements.txt
└─ data/
   ├─ knowledge_base.json      whole manual (138 chunks)
   ├─ figures_manifest.json    diagram list
   └─ figures/                 7 clean SVG diagrams
```

## 0. Delete the old kit first
Remove any previous TrainMate folder so there's no old `server.py` lying around. Unzip this
fresh, e.g. to `C:\TrainMate` (you'll get `C:\TrainMate\kit`).

## 1. Prerequisites
- **Python** from python.org, tick **"Add Python to PATH"**. Check: `python --version`.
  (3.12 is safest; 3.14 usually works — if a package won't install, use 3.12.)
- **Anthropic API key** (console.anthropic.com → API Keys), starts with `sk-ant-`, plus a few
  dollars of credit (Plans & Billing).

## 2. Run (one command)
Open PowerShell in the `kit` folder (File Explorer address bar → type `powershell` → Enter), then:
```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```
Paste your key when asked. First run installs dependencies. When you see
**"Uvicorn running on http://localhost:8000"**, LEAVE THE WINDOW OPEN.

Then double-click **client.html** and ask a question.

### Manual alternative
```powershell
cd C:\TrainMate\kit
python -m pip install -r requirements.txt
$env:ANTHROPIC_API_KEY = "sk-ant-...your key..."
$env:MODEL = "claude-sonnet-5"
python -m uvicorn server:app --port 8000
```

## 3. Set the key once (optional, so you never retype it)
```powershell
setx ANTHROPIC_API_KEY "sk-ant-...your key..."
```
Close and reopen PowerShell afterwards.

## Features
- **Language** selector (top-right): English / বাংলা / हिन्दी. Machine labels (Start,
  DOORS BLOCKAGE, T8, FC1…) and §/page citations stay in English (that's how they're printed
  on the machine), with a short gloss in your language.
- **Mic 🎤** — press and speak (Chrome/Edge, needs internet). Works immediately.
- **Upload ⬆** — transcribe an audio file. Optional: `python -m pip install faster-whisper`
  then restart (offline, good at Bengali/Hindi). Without it, the mic still works.
- **Diagrams** — the backend auto-attaches the clean SVG that matches the answer
  (Giramat question → Giramat diagram). No scanned pages.

## Health check
http://localhost:8000/health → `{"ok":true,"figure_type":"svg",...}`

## Troubleshooting
- **"Could not reach the backend"** → server window not running. Start it, keep it open.
- **"API key is invalid"** → re-copy the key from the Console.
- **"Connection error."** → key not set in the server's window, or no internet / firewall
  blocking api.anthropic.com.
- Golden rule: set the key and start the server **in the same window**; keep that window open.
