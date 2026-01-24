import logging
import uuid
import uvicorn
import os
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
from collections import defaultdict
import db_utils

# Load env immediately before local project imports that might depend on env vars
load_dotenv(override=True)

from mcp_client_manager import MCPClientManager  # noqa: E402
from chatbot import MCPChatbot  # noqa: E402
from hf_mcp_client import HuggingFaceMCPClient  # noqa: E402
from gemini_image_client import GeminiImageClient  # noqa: E402
from voice_agent import VoiceAgent  # noqa: E402
import email_utils  # noqa: E402

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "1.3.0"

app = FastAPI(title="Miami Loves Green Chatbot")

# CORS Configuration - Allow frontend to call API
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
    # Allow embedding in iframes from any origin
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors *"
    return response


# Global state
mcp_manager = None
hf_client = None
gemini_image_client = None
voice_agent = None

# Cache of active chatbot instances in memory
active_chatbots: Dict[str, MCPChatbot] = {}

# Rate Limiting & Caching State
# IP -> list of timestamps
ip_request_counts: Dict[str, List[float]] = defaultdict(list)
# SessionID -> list of timestamps
session_request_counts: Dict[str, List[float]] = defaultdict(list)
# (session_id, message) -> {"data": dict, "timestamp": float}
response_cache: Dict[tuple[str, str], Dict[str, Any]] = {}
CACHE_TTL = 600  # 10 minutes


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
    voice: str = "josh"


@app.on_event("startup")
async def startup_event():
    global mcp_manager, hf_client, gemini_image_client, voice_agent

    # Get project root
    project_root = Path(__file__).parent
    config_path = project_root / "mcp_config.json"

    # Initialize MCP Manager
    mcp_manager = MCPClientManager(config_path=str(config_path))
    await mcp_manager.load_config()
    await mcp_manager.connect_to_servers()

    # Initialize HF MCP Client (for HF tools, not image gen)
    hf_client = HuggingFaceMCPClient()
    await hf_client.start()

    # Initialize Gemini Image Client (FREE tier only)
    static_gen_dir = project_root / "static" / "generated"
    gemini_image_client = GeminiImageClient(static_dir=str(static_gen_dir))
    await gemini_image_client.start()

    # Initialize Database
    db_utils.init_db()

    # Initialize Voice Agent (ElevenLabs TTS with Google fallback)
    voice_agent = VoiceAgent()
    logger.info(f"🎙️ Voice Agent: {voice_agent.get_status()}")

    # Startup Diagnostics
    gemini_key = os.getenv("GEMINI_API_KEY")
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    public_url = os.getenv("PUBLIC_BASE_URL", "NOT SET")
    logger.info("--- STARTUP DIAGNOSTICS ---")
    logger.info(f"🔑 GEMINI_API_KEY present: {bool(gemini_key)}")
    logger.info(f"🎙️ ELEVENLABS_API_KEY present: {bool(elevenlabs_key)}")
    logger.info(f"🌐 PUBLIC_BASE_URL: {public_url}")

    # Startup Diagnostics
    logger.info("--- CHATBOT STARTUP DIAGNOSTICS ---")
    logger.info(f"PUBLIC_BASE_URL: {os.getenv('PUBLIC_BASE_URL', 'Not Set')}")

    static_path = Path("static/generated")
    logger.info(
        f"Static Mount Ready: {static_path.exists()} (Path: {static_path.absolute()})"
    )

    logger.info(f"GEMINI_IMAGE_MODEL: {GeminiImageClient.PRIMARY_MODEL}")

    # Nanobanana Health Check
    if "nanobanana" in mcp_manager.clients:
        logger.info("🍌 Nanobanana READY (Connected)")
    else:
        logger.warning(
            "⚠️ Nanobanana NOT connected. Image generation will fallback to Gemini/Pollinations."
        )

    logger.info("---------------------------")

    logger.info("Backend initialized. Business assistant and email systems ready.")


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

    # Get public base URL for absolute image paths
    public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    # Create new instance
    # Type cast for mcp_manager to avoid Mypy Any | None error
    import typing

    m = typing.cast(typing.Any, mcp_manager)
    bot = MCPChatbot(m, session_id=session_id)
    bot.hf_client = hf_client
    bot.gemini_image_client = gemini_image_client  # Inject Gemini image client
    bot.public_base_url = public_base_url  # Pass public base URL

    active_chatbots[session_id] = bot
    logger.info(
        f"Created/Loaded chatbot for session {session_id} with base URL: {public_base_url}"
    )
    return bot


# API Endpoints

# --- Static File Serving (Crucial for Images) ---
static_path = Path(__file__).parent.absolute() / "static"
static_generated_path = static_path / "generated"

# Ensure directories exist
static_path.mkdir(exist_ok=True)
static_generated_path.mkdir(exist_ok=True)

# Shared public base URL for logging
global_public_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

logger.info(f"📁 Static files mounted at: {static_path}")
if not global_public_base_url:
    logger.warning(
        "⚠️ PUBLIC_BASE_URL is NOT set. Images will use relative URLs and may appear broken in some environments."
    )
else:
    logger.info(f"🌐 PUBLIC_BASE_URL is set to: {global_public_base_url}")

# Mount the static root
app.mount("/static", StaticFiles(directory=str(static_path), html=True), name="static")


@app.get("/api/sessions")
async def list_sessions():
    """List all available chat sessions from SQLite."""
    try:
        sessions = db_utils.get_all_sessions()
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return {"sessions": []}


@app.post("/api/sessions")
async def create_session():
    """Create a new session."""
    session_id = str(uuid.uuid4())
    get_chatbot(session_id)
    return {"id": session_id}


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Consolidated Health check with warmup status."""
    is_ready = mcp_manager is not None and len(mcp_manager.clients) > 0
    image_status = (
        gemini_image_client.get_health_status()
        if gemini_image_client
        else {
            "image_generation_enabled": False,
            "model": None,
        }
    )
    return {
        "status": "ready" if is_ready else "warming_up",
        "timestamp": datetime.utcnow().isoformat(),
        "version": APP_VERSION,
        "image_generation": image_status,
        "mcp_clients": len(mcp_manager.clients) if mcp_manager else 0,
        "hf_client": hf_client is not None,
        "business_assistant": {
            "knowledge_pack_loaded": bool(get_chatbot("default").knowledge_base),
            "database_connected": db_utils.check_db_connection(),
            "email_configured": email_utils.check_email_config(),
        },
    }


@app.post("/api/chat")
async def chat_endpoint(chat_msg: ChatMessage, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    session_id = chat_msg.session_id or str(uuid.uuid4())
    user_message = chat_msg.message.strip()

    # 1. Server-Side Rate Limiting
    now = time.time()

    # Cleanup old timestamps
    ip_request_counts[client_ip] = [
        t for t in ip_request_counts[client_ip] if now - t < 60
    ]
    session_request_counts[session_id] = [
        t for t in session_request_counts[session_id] if now - t < 5
    ]

    # IP limit: 10 per minute
    if len(ip_request_counts[client_ip]) >= 10:
        raise HTTPException(
            status_code=429,
            detail="Too many requests from this IP. Please wait a minute.",
        )

    # Session limit: 1 every 5 seconds
    if len(session_request_counts[session_id]) >= 1:
        raise HTTPException(
            status_code=429,
            detail="Rate limited: 1 message every 5 seconds per session.",
        )

    # 2. Caching Logic
    cache_key = (session_id, user_message)
    if cache_key in response_cache:
        cached_data = response_cache[cache_key]
        if now - cached_data["timestamp"] < CACHE_TTL:
            logger.info(f"Cache hit for session {session_id}")
            return {**cached_data["data"], "session_id": session_id, "cached": True}
        else:
            del response_cache[cache_key]

    # Record request
    ip_request_counts[client_ip].append(now)
    session_request_counts[session_id].append(now)

    chatbot_instance = get_chatbot(session_id)

    try:
        response = await chatbot_instance.send_message(user_message)

        # 3. Cache the successful result
        if isinstance(response, dict) and "response" in response:
            response_cache[cache_key] = {"data": response, "timestamp": now}
            return {**response, "session_id": session_id}

        return {"response": response, "session_id": session_id}
    except HTTPException as he:
        # Pass through specific HTTP errors (like 429) from the chatbot
        raise he
    except Exception as e:
        error_str = str(e)
        logger.error(f"Chat error: {error_str}")

        # Handle 429 from models specifically if not already an HTTPException
        if "429" in error_str or "quota" in error_str.lower():
            # If the error string contains the parsed delay, extract it for the detail
            return JSONResponse(
                status_code=429,
                content={"detail": error_str},
            )

        raise HTTPException(status_code=500, detail=error_str)


@app.get("/api/chat/{session_id}")
async def get_history(session_id: str):
    """Get history for a specific session."""
    chatbot_instance = get_chatbot(session_id)
    return {"history": chatbot_instance.conversation_history}


@app.get("/api/tools")
async def get_tools_endpoint():
    all_tools = []

    # Get Local MCP Tools
    if mcp_manager:
        all_tools.extend(mcp_manager.get_all_tools())

    # Get Hugging Face Tools
    if hf_client:
        try:
            hf_response = await hf_client.list_tools()
            hf_tools_list = hf_response.get("tools", [])
            for tool in hf_tools_list:
                all_tools.append(
                    {
                        "server": "hf",
                        "name": tool.get("name"),
                        "description": tool.get("description", "Hugging Face Tool"),
                        "arguments": tool.get("parameters", {}),
                    }
                )
        except Exception as e:
            logger.error(f"Error fetching HF tools: {e}")

    # Add Gemini image generation tool
    if gemini_image_client and gemini_image_client.enabled:
        all_tools.extend(gemini_image_client.get_tools())

    return {"tools": all_tools}


@app.get("/api/status")
async def status_endpoint():
    status = {
        "status": "online",
        "version": APP_VERSION,
        "active_sessions_in_mem": len(active_chatbots),
        "mcp_servers": list(mcp_manager.clients.keys()) if mcp_manager else [],
        "hf_mcp_enabled": hf_client is not None,
        "image_generation": gemini_image_client.get_health_status()
        if gemini_image_client
        else None,
        "voice_agent": voice_agent.get_status() if voice_agent else None,
        "database_connected": db_utils.check_db_connection(),
    }
    return status


# Direct Image Generation Endpoint
@app.post("/api/generate-image")
async def generate_image_endpoint(request: ImageGenerateRequest):
    """Direct endpoint to generate an image using Gemini 2.0 Flash."""
    if not gemini_image_client or not gemini_image_client.enabled:
        raise HTTPException(status_code=503, detail="Image generation not available")

    result = await gemini_image_client.generate_image(
        prompt=request.prompt,
        aspect_ratio=request.aspect_ratio,
        size=request.size,
        user_id=request.user_id or "anonymous",
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=500, detail=result.get("error", "Unknown error")
        )

    return result


# Hugging Face MCP Endpoints
@app.get("/hf/tools")
async def get_hf_tools():
    if not hf_client:
        raise HTTPException(status_code=500, detail="HF Client not initialized")
    return await hf_client.list_tools()


@app.post("/hf/call")
async def call_hf_tool(request: ToolCallRequest):
    if not hf_client:
        raise HTTPException(status_code=500, detail="HF Client not initialized")
    return await hf_client.call_tool(request.tool, request.arguments)


# ============ VOICE TRANSCRIPTION ENDPOINT ============


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribe audio using Groq Whisper API (HD voice input mode)."""
    try:
        # Save uploaded audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Use Groq Whisper for transcription
        from groq import Groq

        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            os.unlink(tmp_path)
            return {"success": False, "error": "Groq API key not configured"}

        client = Groq(api_key=groq_key.strip())
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="text",
            )

        # Cleanup temp file
        os.unlink(tmp_path)

        # Transcription is already a string when response_format="text"
        logger.info(f"🎤 Transcribed audio: {str(transcription)[:50]}...")
        return {"success": True, "text": str(transcription)}

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        # Cleanup temp file if it exists
        try:
            if "tmp_path" in locals():
                os.unlink(tmp_path)
        except Exception:
            pass
        return {"success": False, "error": str(e)}


# ============ TEXT-TO-SPEECH (TTS) ENDPOINT ============


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """Convert text to speech using ElevenLabs (primary) or Google TTS (fallback)."""
    logger.info(f"TTS request: voice={request.voice}, text_len={len(request.text)}")

    if not voice_agent:
        logger.error("TTS failed: voice_agent is None")
        raise HTTPException(status_code=503, detail="Voice agent not initialized")

    # Skip availability check - try to call ElevenLabs directly
    # If key is missing, the API will return the actual error
    try:
        result = await voice_agent.text_to_speech(
            text=request.text, voice=request.voice, return_base64=True
        )

        logger.info(
            f"TTS result: success={result.get('success')}, provider={result.get('provider')}"
        )

        if not result.get("success"):
            logger.error(f"TTS failed: {result.get('error')}")
            raise HTTPException(
                status_code=500, detail=result.get("error", "TTS failed")
            )

        return result
    except Exception as e:
        logger.error(f"TTS exception: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/voice/status")
async def voice_status():
    """Get voice agent status (TTS availability)."""
    if not voice_agent:
        return {"available": False, "error": "Voice agent not initialized"}
    return voice_agent.get_status()


# Health check endpoint with image generation status.


@app.get("/")
async def read_index():
    return FileResponse(str(static_path / "index.html"))


# ============ HEALTH CHECK ENDPOINTS ============


# Health check consolidated above


@app.get("/api/debug/config")
async def debug_config(key: Optional[str] = None):
    """
    Debug endpoint to check environment variables and service connection status.
    WARNING: This exposes configuration status. Secured by simplistic key check or obscurity in this dev phase.
    """
    # Simple security check - requires a specific query param if you want to be strict,
    # but for now we'll just mask sensitive values.

    import shutil

    # 1. Check Env Vars (Masked)
    vars_to_check = [
        "GEMINI_API_KEY",
        "ELEVENLABS_API_KEY",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASS",
        "GROQ_API_KEY",
        "LEAD_TO_EMAIL",
    ]

    env_status = {}
    for var in vars_to_check:
        val = os.getenv(var)
        if val:
            # Show first 4 chars if long enough, else just "SET"
            visible = val[:4] + "..." if len(val) > 4 else "***"
            env_status[var] = f"✅ Set ({visible})"
        else:
            env_status[var] = "❌ MISSING"

    # 2. Check Dependencies/Commands
    node_path = shutil.which("node")
    npx_path = shutil.which("npx")
    python_path = shutil.which("python")

    system_status = {
        "node_installed": bool(node_path),
        "npx_installed": bool(npx_path),
        "python_path": python_path or "unknown",
        "working_dir": str(Path.cwd()),
    }

    # 3. Check Image Gen Client
    img_status = "Disabled"
    if gemini_image_client:
        img_status = f"Initialized (Enabled: {gemini_image_client.enabled})"

    return {
        "environment": env_status,
        "system": system_status,
        "image_client": img_status,
        "note": "If keys are 'MISSING', add them to Render Environment Variables.",
    }


@app.get("/api/debug/image")
async def debug_image_gen(
    prompt: str = "a cute neon robot by a waterfall", session_id: str = "debug-session"
):
    """Test full image generation flow (Nanobanana -> Gemini -> Pollinations)."""
    try:
        bot = get_chatbot(session_id)
        result = await bot._execute_mcp_tool("generate_image", {"prompt": prompt})

        # Log request details for verification (Acceptance Test 4)
        provider = result.get("provider", "unknown")
        url_type = "none"
        if result.get("image_base64"):
            url_type = "base64"
        elif result.get("image_url"):
            url_type = (
                "local" if "onrender.com" in result.get("image_url") else "external"
            )

        logger.info(f"📸 DEBUG IMAGE: provider={provider}, url_type={url_type}")

        return {
            "success": "image_url" in result or "image_base64" in result,
            "provider": provider,
            "url_type": url_type,
            "result": result,
            "public_base_url": bot.public_base_url,
        }
    except Exception as e:
        logger.error(f"Image gen debug endpoint failed: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/ping")
async def ping():
    """Simple ping endpoint for uptime monitoring."""
    return {"pong": True, "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
