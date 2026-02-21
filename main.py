"""
Alita — FastAPI Backend Server
The web server that powers Alita's brain and serves the chat UI.
"""

import base64
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from alita.brain import Alita

# Try to import voice (graceful fallback if edge-tts has issues)
try:
    from alita.voice import text_to_speech, list_voices
    VOICE_AVAILABLE = True
    print("🔊 Voice system loaded")
except Exception as e:
    VOICE_AVAILABLE = False
    print(f"⚠️ Voice system unavailable: {e}")

    async def text_to_speech(*args, **kwargs):
        return b""

    async def list_voices(*args, **kwargs):
        return []


# ─── Global State ────────────────────────────────────────────────
alita_instance: Alita | None = None
USER_NAME = os.getenv("USER_NAME", "Kundan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Alita when the server starts."""
    global alita_instance
    print("\n" + "=" * 50)
    print("    💜 Starting Alita — Your Personal AI Partner")
    print("=" * 50)
    alita_instance = Alita(user_name=USER_NAME)
    yield
    print("\n💤 Alita is going to sleep. Memories saved.")


app = FastAPI(title="Alita — Personal AI Partner", lifespan=lifespan)

# Serve static files (CSS, JS, images)
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ─── API Models ──────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    voice_reply: bool = False


class ChatResponse(BaseModel):
    response: str
    memories_used: int
    audio_base64: Optional[str] = None


# ─── API Routes ──────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a message to Alita and get her response."""
    response = await alita_instance.chat(req.message)

    audio_b64 = None
    if req.voice_reply and VOICE_AVAILABLE:
        try:
            audio_bytes = await text_to_speech(response)
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            print(f"⚠️ TTS failed: {e}")

    return ChatResponse(
        response=response,
        memories_used=alita_instance.memory.memory_collection.count(),
        audio_base64=audio_b64,
    )


@app.post("/api/tts")
async def tts_endpoint(text: str):
    """Convert text to speech audio."""
    try:
        audio_bytes = await text_to_speech(text)
        if audio_bytes:
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            return JSONResponse(content={"audio_base64": audio_b64})
        return JSONResponse(content={"error": "No audio generated"}, status_code=500)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/voices")
async def get_voices(language: str = None):
    """List available TTS voices."""
    voices = await list_voices(language)
    return JSONResponse(content={"voices": voices})


@app.get("/api/stats")
async def get_stats():
    """Get Alita's current stats and memory info."""
    return JSONResponse(content=alita_instance.get_stats())


@app.get("/api/profile")
async def get_profile():
    """Get the user profile that Alita has built."""
    return JSONResponse(content=alita_instance.memory.get_profile())


@app.get("/api/memories")
async def get_memories(query: str = "", limit: int = 10):
    """Search Alita's memories."""
    if query:
        memories = alita_instance.memory.recall_memories(query, n_results=limit)
    else:
        recent = alita_instance.memory.get_recent_messages(limit=limit)
        memories = [f"[{m['timestamp']}] {m['role']}: {m['content']}" for m in recent]
    return JSONResponse(content={"memories": memories})


# ─── Serve the Chat UI ───────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the main chat interface."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Alita is running! But the UI files are missing.</h1>")


if __name__ == "__main__":
    import socket
    import uvicorn
    import os

    # Cloud platforms (Render, Railway) provide process.env.PORT
    port = int(os.environ.get("PORT", 8000))

    # Get local IP for phone access
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        local_ip = "YOUR_LAPTOP_IP"

    cert_file = Path("cert.pem")
    key_file  = Path("key.pem")
    use_ssl   = cert_file.exists() and key_file.exists()

    protocol = "https" if use_ssl else "http"
    print(f"\n{'='*50}")
    print(f"  Open on this PC   : {protocol}://localhost:{port}")
    if use_ssl:
        print(f"  Open on your phone: {protocol}://{local_ip}:{port}")
        print(f"  (Accept the security warning once — it's your own cert)")
    else:
        print(f"  Open on your phone: {protocol}://{local_ip}:{port}")
        print(f"  NOTE: Run 'python generate_cert.py' once for phone mic + PWA install (Local only)")
    print(f"{'='*50}\n")

    ssl_kwargs = {}
    if use_ssl:
        ssl_kwargs = {"ssl_certfile": str(cert_file), "ssl_keyfile": str(key_file)}

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, **ssl_kwargs)
