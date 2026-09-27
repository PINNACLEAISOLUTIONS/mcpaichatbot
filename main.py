import asyncio
import logging
import uuid
import uvicorn  # type: ignore
import os
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Dict, Any, Optional, List
import time
from collections import defaultdict

from dotenv import load_dotenv  # type: ignore
from fastapi import FastAPI, HTTPException, Request, UploadFile, File  # type: ignore
from fastapi.staticfiles import StaticFiles  # type: ignore
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse, HTMLResponse  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.exceptions import RequestValidationError  # type: ignore
from pydantic import BaseModel  # type: ignore

# Local imports
import db_utils
import brand
from chatbot import PinnacleChatbot, LLM_ERRORS, _GROQ_MODELS
from gemini_image_client import GeminiImageClient
from voice_agent import VoiceAgent
import email_utils
import neon_sync
from neon_sync import process_chat_message_for_leads, insert_inbound_lead_async

# Load env
load_dotenv(override=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "1.4.4"

app = FastAPI(title="Pinnacle AI Expert Chatbot")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom middleware to allow iframe embedding
@app.middleware("http")
async def add_iframe_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    response.headers["Permissions-Policy"] = "microphone=*, autoplay=*"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Ensure validation errors return JSON."""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "message": "Invalid request format"},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global handler to ensure ALL errors return JSON, never raw HTML/text."""
    logger.error(f"Global error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "message": "An internal server error occurred.",
        },
    )


# Global state

gemini_image_client = None
voice_agent = None

# Cache of active chatbot instances in memory
active_chatbots: Dict[str, PinnacleChatbot] = {}

# Rate Limiting & Caching State
ip_request_counts: Dict[str, List[float]] = defaultdict(list)
session_request_counts: Dict[str, List[float]] = defaultdict(list)
session_total_counts: Dict[str, int] = defaultdict(int)  # Total messages per session
response_cache: Dict[tuple[str, str], Dict[str, Any]] = {}
CACHE_TTL = 600  # 10 minutes

# Anti-spam limits
RATE_LIMIT_IP_PER_MINUTE = 12  # Max requests per IP per 60s
RATE_LIMIT_IP_PER_10MIN = 40  # Max requests per IP per 10 min
RATE_LIMIT_SESSION_COOLDOWN = 3  # Seconds between messages per session
RATE_LIMIT_SESSION_TOTAL = 50  # Max total messages per session (resets on new session)


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    brand: Optional[str] = None
    stream: Optional[bool] = None


class LeadRequest(BaseModel):
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = "website_chat"
    brand: Optional[str] = "pinnacle"
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ToolCallRequest(BaseModel):
    server: str
    tool: str
    arguments: Dict[str, Any]


class ImageGenerateRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "1:1"
    size: Optional[str] = None
    user_id: Optional[str] = None


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    brand: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    global gemini_image_client, voice_agent

    project_root = Path(__file__).parent

    # 1. Initialize synchronous components
    db_utils.init_db()
    voice_agent = VoiceAgent()

    static_gen_dir = project_root / "static" / "generated"
    gemini_image_client = GeminiImageClient(static_dir=str(static_gen_dir))

    # 2. Asynchronous startup
    logger.info("Initializing services...")
    await gemini_image_client.start()

    logger.info(f"🎙️ Voice Agent: {voice_agent.get_status()}")
    logger.info("Backend initialized. Pinnacle AI Experts ready.")


@app.on_event("shutdown")
async def shutdown_event():
    if gemini_image_client:
        await gemini_image_client.stop()


def get_chatbot(session_id: str, brand_name: Optional[str] = None) -> PinnacleChatbot:
    """Get or create a chatbot for the given session and brand with strict isolation."""
    resolved_brand = brand.resolve_brand(brand_name)
    cache_key = f"{resolved_brand}_{session_id}"
    if cache_key in active_chatbots:
        return active_chatbots[cache_key]

    public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    bot = PinnacleChatbot(session_id=session_id, brand_name=resolved_brand)
    bot.gemini_image_client = gemini_image_client
    bot.public_base_url = public_base_url

    active_chatbots[cache_key] = bot
    logger.info(f"Created/Loaded chatbot for brand '{resolved_brand}', session '{session_id}'")
    return bot


# API Endpoints
static_path = Path(__file__).parent.absolute() / "static"
static_generated_path = static_path / "generated"
static_path.mkdir(exist_ok=True)
static_generated_path.mkdir(exist_ok=True)


@app.api_route("/", methods=["GET", "HEAD"])
async def read_index(request: Request):
    brand_param = request.query_params.get("brand")
    resolved = brand.resolve_brand(brand_param)
    html = (static_path / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(
        brand.brand_page(html, resolved),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    """Health check endpoint for Render deployment."""
    print("⚡ UptimeRobot Ping Received! (Keeping bot awake)")
    logger.info("Health check ping received.")
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/lead")
async def create_lead_endpoint(lead_req: LeadRequest):
    """Direct lead submission endpoint syncing to Neon PostgreSQL leads table."""
    success = await insert_inbound_lead_async(
        company_name=lead_req.company_name,
        contact_name=lead_req.contact_name,
        email=lead_req.email,
        phone=lead_req.phone,
        status="inbound_chat",
        source=lead_req.source or "website_chat",
        brand=lead_req.brand or "pinnacle",
        notes=lead_req.notes,
        metadata=lead_req.metadata,
    )
    return {"status": "ok" if success else "error", "synced": success}


@app.post("/api/chat")
async def chat_endpoint(chat_msg: ChatMessage, request: Request):
    """
    Primary chat endpoint.
    Supports both real-time Server-Sent Events (SSE) streaming (stream=True or Accept: text/event-stream)
    and synchronous JSON responses.
    Automatically captures visitor leads (email/company/phone) to Neon PostgreSQL with status='inbound_chat'.
    """
    client_ip = request.client.host if request.client else "unknown"
    session_id = chat_msg.session_id or str(uuid.uuid4())
    user_message = chat_msg.message.strip()

    # Inbound Lead Auto-Capture: scan message for contact/company details and write to Neon
    asyncio.create_task(
        process_chat_message_for_leads(
            user_message=user_message,
            session_id=session_id,
            brand=chat_msg.brand,
            client_ip=client_ip,
        )
    )

    now = time.time()
    # Clean sliding windows
    ip_request_counts[client_ip] = [
        t for t in ip_request_counts[client_ip] if now - t < 600
    ]
    session_request_counts[session_id] = [
        t
        for t in session_request_counts[session_id]
        if now - t < RATE_LIMIT_SESSION_COOLDOWN
    ]

    # Anti-spam checks
    recent_1min = [t for t in ip_request_counts[client_ip] if now - t < 60]
    if len(recent_1min) >= RATE_LIMIT_IP_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="Slow down! Too many messages. Please wait a moment.",
        )

    if len(ip_request_counts[client_ip]) >= RATE_LIMIT_IP_PER_10MIN:
        raise HTTPException(
            status_code=429,
            detail="You've sent a lot of messages. Please take a short break and try again.",
        )

    if len(session_request_counts[session_id]) >= 1:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {RATE_LIMIT_SESSION_COOLDOWN} seconds between messages.",
        )

    if session_total_counts[session_id] >= RATE_LIMIT_SESSION_TOTAL:
        raise HTTPException(
            status_code=429,
            detail="You've reached the message limit for this session. Please start a new chat.",
        )

    is_stream = (
        chat_msg.stream is True
        or "text/event-stream" in request.headers.get("accept", "")
    )

    cache_key = (chat_msg.brand or "pinnacle", session_id, user_message)
    if not is_stream and cache_key in response_cache:
        cached_data = response_cache[cache_key]
        if (
            isinstance(cached_data, dict)
            and now - cached_data.get("timestamp", 0) < CACHE_TTL
        ):
            data = cached_data.get("data", {})
            return {**data, "session_id": session_id, "cached": True}

    ip_request_counts[client_ip].append(now)
    session_request_counts[session_id].append(now)
    session_total_counts[session_id] += 1

    chatbot_instance = get_chatbot(session_id, brand_name=chat_msg.brand)

    # STREAMING PATH (Server-Sent Events)
    if is_stream:
        async def event_generator():
            import json as _json

            try:
                async for chunk in chatbot_instance.send_message_stream(user_message):
                    yield chunk
                yield f"data: {_json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
            except Exception as e:
                logger.error(f"Stream error on /api/chat: {e}")
                yield f"data: {_json.dumps({'type': 'error', 'content': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # NON-STREAMING PATH (JSON)
    try:
        response = await chatbot_instance.send_message(user_message)
        if isinstance(response, dict) and "response" in response:
            response_cache[cache_key] = {"data": response, "timestamp": now}
            return {**response, "session_id": session_id}
        return {"response": response, "session_id": session_id}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/stream")
async def chat_stream_endpoint(chat_msg: ChatMessage, request: Request):
    """SSE streaming alias for /api/chat with stream=True."""
    chat_msg.stream = True
    return await chat_endpoint(chat_msg, request)


@app.get("/api/sessions")
async def list_sessions():
    try:
        sessions = db_utils.get_all_sessions()
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return {"sessions": []}


@app.get("/api/tools")
async def get_tools_endpoint():
    all_tools = []
    if gemini_image_client and gemini_image_client.enabled:
        all_tools.extend(gemini_image_client.get_tools())
    return {"tools": all_tools}


@app.get("/api/status")
async def status_endpoint():
    return {
        "status": "online",
        "version": APP_VERSION,
        "voice_agent": voice_agent.get_status() if voice_agent else None,
        "database": db_utils.check_db_connection(),
        "email": {
            "configured": email_utils.check_email_config(),
            "smtp": bool(os.getenv("SMTP_PASS") or os.getenv("GMAIL_APP_PASSWORD")),
            "sendgrid": bool(os.getenv("SENDGRID_API_KEY")),
            "resend": bool(os.getenv("RESEND_API_KEY")),
        },
        "llm": {
            "groq_key": bool(os.getenv("GROQ_API_KEY")),
            "gemini_key": bool(os.getenv("GEMINI_API_KEY")),
            "groq_models": _GROQ_MODELS["ids"],
            "last_errors": LLM_ERRORS,
        },
    }


_llm_probe = {"checked": 0.0, "ok": False, "text": ""}


@app.api_route("/health/llm", methods=["GET", "HEAD"])
async def llm_health_check():
    """Deep health check for UptimeRobot: proves the AI actually answers.
    Keyword-monitor this for LLM_OK. Cached 4 min so pings don't burn quota."""
    if time.time() - _llm_probe["checked"] > 240:
        bot = get_chatbot("uptime-llm-probe")
        text = ""
        async for chunk in bot._get_completion_stream(
            messages=[{"role": "user", "content": "Reply with the single word: ready"}]
        ):
            text += chunk
        _llm_probe.update(
            checked=time.time(),
            ok=bool(text.strip()) and "high demand" not in text,
            text=text.strip()[:80],
        )
    body = "LLM_OK" if _llm_probe["ok"] else "LLM_DOWN"
    return JSONResponse(
        {"status": body, "reply": _llm_probe["text"], "last_errors": LLM_ERRORS},
        status_code=200 if _llm_probe["ok"] else 503,
    )


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Voice agent TTS with fallback (v1.3 logic)"""
    if not voice_agent:
        raise HTTPException(status_code=503, detail="Voice agent offline")
    try:
        result = await voice_agent.text_to_speech(
            text=request.text, voice=request.voice, brand_name=request.brand, return_base64=True
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tts/premium")
async def elevenlabs_tts_premium(request: Dict[str, str]):
    """Direct ElevenLabs Proxy (v1.3 legacy/direct access)"""
    from elevenlabs import ElevenLabs  # type: ignore
    import io

    text = request.get("text")
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Not configured")
    try:
        client = ElevenLabs(api_key=api_key)
        audio = client.text_to_speech.convert(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "nPczCjzI2devNBz1zQrb"),
            text=text,
            model_id="eleven_multilingual_v2",
        )
        return StreamingResponse(io.BytesIO(b"".join(audio)), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        suffix = Path(audio.filename or "").suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        from groq import Groq  # type: ignore

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        with open(tmp_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3", file=f, response_format="text"
            )
        os.unlink(tmp_path)
        return {"success": True, "text": str(transcription)}
    except Exception as e:
        return {"success": False, "error": str(e)}


app.mount("/static", StaticFiles(directory=str(static_path), html=True), name="static")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
