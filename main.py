import logging
import uuid
import uvicorn  # type: ignore
import os
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Dict, Any, Optional, List
import time
import asyncio
from collections import defaultdict

from dotenv import load_dotenv  # type: ignore
from fastapi import FastAPI, HTTPException, Request, UploadFile, File  # type: ignore
from fastapi.staticfiles import StaticFiles  # type: ignore
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.exceptions import RequestValidationError  # type: ignore
from pydantic import BaseModel  # type: ignore

# Local imports
import db_utils
from mcp_client_manager import MCPClientManager
from chatbot import MCPChatbot
from hf_mcp_client import HuggingFaceMCPClient
from gemini_image_client import GeminiImageClient
from voice_agent import VoiceAgent
from hf_inference_client import HFInferenceClient
from replicate_client import ReplicateImageClient
from pollinations_client import PollinationsClient

# Load env
load_dotenv(override=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "1.3.1"

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
mcp_manager = None
hf_client = None
gemini_image_client = None
voice_agent = None
hf_inference = None
replicate_client = None
pollinations_client = None

# Cache of active chatbot instances in memory
active_chatbots: Dict[str, MCPChatbot] = {}

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


@app.on_event("startup")
async def startup_event():
    global \
        mcp_manager, \
        hf_client, \
        gemini_image_client, \
        voice_agent, \
        hf_inference, \
        replicate_client, \
        pollinations_client

    project_root = Path(__file__).parent
    config_path = project_root / "mcp_config.json"

    # 1. Initialize synchronous components first
    db_utils.init_db()
    voice_agent = VoiceAgent()
    mcp_manager = MCPClientManager(config_path=str(config_path))
    hf_client = HuggingFaceMCPClient()

    static_gen_dir = project_root / "static" / "generated"
    gemini_image_client = GeminiImageClient(static_dir=str(static_gen_dir))

    hf_inference = HFInferenceClient()
    replicate_client = ReplicateImageClient()
    pollinations_client = PollinationsClient()

    # 2. Parallelize all asynchronous startup tasks
    logger.info("Initializing services in parallel...")
    startup_tasks = [
        mcp_manager.load_config(),
        mcp_manager.connect_to_servers(),
        hf_client.start(),
        gemini_image_client.start(),
        hf_inference.start(),
        replicate_client.start(),
        pollinations_client.start(),
    ]

    # Use return_exceptions=True to ensure one failure doesn't block the whole app
    results = await asyncio.gather(*startup_tasks, return_exceptions=True)

    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"Service initialization task {i} failed: {res}")

    logger.info(f"🎙️ Voice Agent: {voice_agent.get_status()}")
    logger.info("Backend initialized. Pinnacle AI Expert and premium systems ready.")


@app.on_event("shutdown")
async def shutdown_event():
    if mcp_manager:
        await mcp_manager.disconnect_all()
    if hf_client:
        await hf_client.stop()
    if gemini_image_client:
        await gemini_image_client.stop()


def get_chatbot(session_id: str) -> MCPChatbot:
    """Get or create a chatbot for the given session."""
    if session_id in active_chatbots:
        return active_chatbots[session_id]

    public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    import typing

    m = typing.cast(typing.Any, mcp_manager)
    bot = MCPChatbot(m, session_id=session_id)
    bot.hf_client = hf_client
    bot.gemini_image_client = gemini_image_client
    bot.public_base_url = public_base_url
    bot.hf_inference = hf_inference
    bot.replicate_client = replicate_client
    bot.pollinations_client = pollinations_client

    active_chatbots[session_id] = bot
    logger.info(f"Created/Loaded chatbot for session {session_id}")
    return bot


# API Endpoints
static_path = Path(__file__).parent.absolute() / "static"
static_generated_path = static_path / "generated"
static_path.mkdir(exist_ok=True)
static_generated_path.mkdir(exist_ok=True)


@app.get("/")
async def read_index():
    return FileResponse(str(static_path / "index.html"))


@app.get("/health")
async def health_check():
    """Health check endpoint for Render deployment."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/chat")
async def chat_endpoint(chat_msg: ChatMessage, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    session_id = chat_msg.session_id or str(uuid.uuid4())
    user_message = chat_msg.message.strip()

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

    cache_key = (session_id, user_message)
    if cache_key in response_cache:
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

    chatbot_instance = get_chatbot(session_id)
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
    """SSE streaming endpoint — tokens arrive in real-time."""
    client_ip = request.client.host if request.client else "unknown"
    session_id = chat_msg.session_id or str(uuid.uuid4())
    user_message = chat_msg.message.strip()

    now = time.time()
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

    ip_request_counts[client_ip].append(now)
    session_request_counts[session_id].append(now)
    session_total_counts[session_id] += 1

    chatbot_instance = get_chatbot(session_id)

    async def event_generator():
        import json as _json

        try:
            async for chunk in chatbot_instance.send_message_stream(user_message):
                yield chunk
            # Send session_id as final metadata
            yield f"data: {_json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {_json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
    if mcp_manager:
        all_tools.extend(mcp_manager.get_all_tools())
    if hf_client:
        try:
            hf_res = await hf_client.list_tools()
            for tool in hf_res.get("tools", []):
                all_tools.append(
                    {
                        "server": "hf",
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                    }
                )
        except Exception as e:
            logger.error(f"Error listing HF tools: {e}")
    if gemini_image_client and gemini_image_client.enabled:
        all_tools.extend(gemini_image_client.get_tools())
    return {"tools": all_tools}


@app.get("/api/status")
async def status_endpoint():
    return {
        "status": "online",
        "version": APP_VERSION,
        "mcp_servers": list(mcp_manager.clients.keys()) if mcp_manager else [],
        "voice_agent": voice_agent.get_status() if voice_agent else None,
        "database": db_utils.check_db_connection(),
    }


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Voice agent TTS with fallback (v1.3 logic)"""
    if not voice_agent:
        raise HTTPException(status_code=503, detail="Voice agent offline")
    try:
        result = await voice_agent.text_to_speech(
            text=request.text, voice=request.voice, return_base64=True
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
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"),
            text=text,
            model_id="eleven_multilingual_v2",
        )
        return StreamingResponse(io.BytesIO(b"".join(audio)), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
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
