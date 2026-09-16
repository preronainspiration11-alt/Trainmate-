"""
TrainMate backend — Posimat MASTER-15
- Answers in Bengali / Hindi / English
- Serves CLEAN SVG machine diagrams (not scanned pages)
- Attaches the right diagram AUTOMATICALLY by matching the answer's topic
- /transcribe endpoint for voice-file upload (local Whisper, optional)

Run:
    pip install -r requirements.txt
    $env:ANTHROPIC_API_KEY = "sk-ant-..."
    $env:MODEL = "claude-sonnet-5"
    python -m uvicorn server:app --reload --port 8000
"""
import os, re, json, math, tempfile
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import anthropic

DATA = Path(__file__).parent / "data"
KB   = json.loads((DATA / "knowledge_base.json").read_text(encoding="utf-8"))
FIGS = json.loads((DATA / "figures_manifest.json").read_text(encoding="utf-8"))["figures"]
CHUNKS = KB["chunks"]

MODEL         = os.environ.get("MODEL", "claude-sonnet-5")
USE_RETRIEVAL = os.environ.get("USE_RETRIEVAL", "0") == "1"
TOP_K         = int(os.environ.get("TOP_K", "8"))

client = anthropic.Anthropic()

# ------------------------------------------------------------------ retriever
def _tok(s): return re.findall(r"[a-z0-9]{2,}", s.lower())
_df = Counter()
for c in CHUNKS:
    for w in set(_tok(c["text"])): _df[w] += 1
_N = len(CHUNKS)
_idf = {w: math.log(1 + _N / (1 + df)) for w, df in _df.items()}
def _vec(t):
    tf = Counter(t); v = {w: (1+math.log(n))*_idf[w] for w, n in tf.items() if w in _idf}
    nrm = math.sqrt(sum(x*x for x in v.values())) or 1.0
    return {w: x/nrm for w, x in v.items()}
_cv = [(_vec(_tok(c["text"])), c) for c in CHUNKS]
def retrieve(q, k=TOP_K):
    qv = _vec(_tok(q)); sc = []
    for cv, c in _cv:
        s = sum(qv[w]*cv.get(w, 0.0) for w in qv)
        if s > 0: sc.append((s, c))
    sc.sort(key=lambda x: -x[0]); return [c for _, c in sc[:k]]

def chunk_block(c):
    return f"[chunk {c['chunk_id']} | \u00a7{c['section']} {c['section_title']} | p.{c['page']}]\n{c['text']}"
FULL_MANUAL = "\n\n".join(chunk_block(c) for c in CHUNKS)

RULES = (
"You are TrainMate, a training assistant for the POSIMAT MASTER-15 bottle unscrambler "
"(document OC12737.3.01). Operators and technicians ask questions instead of reading the manual.\n\n"
"RULES\n"
"- Answer ONLY from the manual excerpts provided. If something isn't covered, say so plainly and point "
"to the nearest section — never invent specifications, alarm codes, torque values or part numbers.\n"
"- Be concise and practical, like an experienced technician. Lead with the direct answer, then detail. "
"Use short paragraphs or tight bullet lists ('- ').\n"
"- Cite the manual as you go, e.g. (\u00a73.1.1, p.30).\n"
"- Use `code style` for exact button names, screen names, timers (e.g. `T8`) and alarm text.\n"
"- SAFETY: for anything involving power, air, moving parts, guards or maintenance, put the key safety "
"step FIRST and prefix that line with \u26a0 (apply LOTO — lock out power and air).\n"
"- Do NOT write figure tags or mention diagrams; the app adds the right diagram automatically.\n"
"- Only discuss this machine. If asked something unrelated, briefly redirect."
)

def language_directive(language):
    lang = (language or "English").strip()
    if lang.lower() in ("english", "en", ""):
        return "Respond in clear English."
    return (
        f"Respond ENTIRELY in {lang}. This is critical: the operator reads {lang}.\n"
        "BUT keep the following EXACTLY as printed on the machine, in original English: button/selector/screen "
        "labels (Start, Stop, Reverse, Reset, AUTO/MAN, DOORS BLOCKAGE, INFORMATION, ALARMS), alarm/message "
        "text, timer codes (e.g. T8), photocell codes (e.g. FC1, FC10), machine/format names, and all \u00a7/page "
        f"citations. You may add a short {lang} gloss in parentheses the first time a label appears. Keep the "
        "\u26a0 prefix on safety lines. Numbers and units stay as-is."
    )

# ---- deterministic figure picker: choose the ONE diagram that best fits the answer ----
def pick_figure(question, answer):
    text = (question + " " + answer).lower()
    cites = set(re.findall(r"\u00a7\s*([0-9]+(?:\.[0-9]+)*)", answer))  # e.g. 2.4, 3.1
    best, best_score = None, 0
    for f in FIGS:
        score = sum(1 for kw in f["triggers"] if kw in text)
        sec = f["section"]
        if any(c == sec or c.startswith(sec + ".") or sec.startswith(c + ".") or c == sec for c in cites):
            score += 3                      # strong boost if the answer cites this figure's section
        if score > best_score:
            best_score, best = score, f
    if best and best_score >= 3:            # conservative: only attach when clearly relevant
        return {"figure_id": best["figure_id"], "caption": best["caption"],
                "url": "/figures/" + Path(best["image_key"]).name, "section": best["section"]}
    return None

class AskReq(BaseModel):
    question: str
    history: list = []
    language: str = "English"

app = FastAPI(title="TrainMate API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/figures", StaticFiles(directory=str(DATA / "figures")), name="figures")

@app.get("/health")
def health():
    return {"ok": True, "model": MODEL, "chunks": len(CHUNKS), "figures": len(FIGS),
            "figure_type": "svg", "retrieval": USE_RETRIEVAL, "transcription": _asr_status()}

@app.post("/ask")
def ask(req: AskReq):
    context = "\n\n".join(chunk_block(c) for c in retrieve(req.question)) if USE_RETRIEVAL else FULL_MANUAL
    system = [
        {"type": "text", "text": RULES + "\n\nLANGUAGE:\n" + language_directive(req.language)},
        {"type": "text", "text": "MANUAL EXCERPTS:\n" + context, "cache_control": {"type": "ephemeral"}},
    ]
    messages = (req.history or []) + [{"role": "user", "content": req.question}]
    try:
        resp = client.messages.create(model=MODEL, max_tokens=2048, system=system, messages=messages)
    except Exception as e:
        return {"answer": "", "figures": [], "error": str(e)}

    answer = "".join(b.text for b in resp.content if b.type == "text")
    answer = re.sub(r"\[FIGURE:[^\]]*\]?", "", answer).strip()   # safety: strip any stray tag
    fig = pick_figure(req.question, answer)
    return {"answer": answer, "figures": ([fig] if fig else [])}

# ------------------------------------------------------------------ voice transcription (optional)
_WHISPER = None
def _asr_status():
    try:
        import faster_whisper  # noqa
        return "local-whisper"
    except Exception:
        return "openai-whisper" if os.environ.get("OPENAI_API_KEY") else "not-configured"
def _lang_code(language):
    return {"bengali": "bn", "hindi": "hi", "english": "en"}.get((language or "").strip().lower())

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form("")):
    audio = await file.read(); code = _lang_code(language)
    try:
        import faster_whisper
        global _WHISPER
        if _WHISPER is None:
            _WHISPER = faster_whisper.WhisperModel(os.environ.get("WHISPER_MODEL", "small"),
                                                   device="cpu", compute_type="int8")
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
            tmp.write(audio); path = tmp.name
        segs, _ = _WHISPER.transcribe(path, language=code)
        txt = "".join(s.text for s in segs).strip()
        try: os.remove(path)
        except OSError: pass
        return {"text": txt}
    except ImportError:
        pass
    except Exception as e:
        return {"text": "", "error": f"Local transcription failed: {e}"}
    if os.environ.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            with tempfile.NamedTemporaryFile(suffix="_" + (file.filename or "audio.webm"), delete=False) as tmp:
                tmp.write(audio); path = tmp.name
            with open(path, "rb") as fh:
                kw = {"model": "whisper-1", "file": fh}
                if code: kw["language"] = code
                r = OpenAI().audio.transcriptions.create(**kw)
            try: os.remove(path)
            except OSError: pass
            return {"text": (r.text or "").strip()}
        except Exception as e:
            return {"text": "", "error": f"OpenAI transcription failed: {e}"}
    return {"text": "", "error": "Transcription engine not installed. Use the mic button, or run "
                                  "'pip install faster-whisper' and restart."}
