"""
Voice Agent Module for Pinnacle AI Expert
TTS: ElevenLabs (primary) with Google TTS fallback
Designed for Render deployment with environment variables
"""

import os
import logging
import base64
from typing import Dict, Any, Optional
import httpx  # type: ignore

# Import Edge TTS (High-quality free fallback)
try:
    import edge_tts  # type: ignore
except ImportError:
    edge_tts = None

# Import ElevenLabs SDK
try:
    from elevenlabs.client import AsyncElevenLabs  # type: ignore
except ImportError:
    AsyncElevenLabs = None

logger = logging.getLogger(__name__)


class VoiceAgent:
    """Text-to-Speech agent with ElevenLabs primary, Edge TTS secondary, and Google fallback."""

    # ElevenLabs voice IDs (free tier compatible)
    VOICES = {
        "miami": "s3TPKV1kjDlVtZbl4Ksh",  # Custom Pinnacle AI Expert voice
        "rachel": "21m00Tcm4TlvDq8ikWAM",  # Warm, professional female
        "josh": "TxGEqnHWrfWFTfGW9XjX",  # Friendly male
        "bella": "EXAVITQu4vr4xnSDxMaL",  # Young female
        "adam": "pNInz6obpgDQGcFmaJgB",  # Deep male
        "antoni": "ErXwobaYiN019PkySvjV",  # Antoni (Deep, well rounded)
    }
    DEFAULT_VOICE = "miami"

    # Edge TTS Voice Map
    EDGE_VOICES = {
        "miami": "en-US-ChristopherNeural",  # Business professional
        "josh": "en-US-GuyNeural",  # Friendly male (OpenAI Cove equivalent)
        "rachel": "en-US-AriaNeural",  # Professional female
        "bella": "en-US-MichelleNeural",  # Young female
        "adam": "en-US-EricNeural",  # Deep male
        "antoni": "en-US-ChristopherNeural",  # Deep business
    }

    def __init__(self):
        """Initialize voice agent with API keys from environment."""
        # Load API keys from Render environment
        raw_key = os.getenv("ELEVENLABS_API_KEY")
        self.elevenlabs_api_key = raw_key.strip() if raw_key else None
        self.custom_voice_id = os.getenv("ELEVENLABS_VOICE_ID")

        # Reuse existing Google key if specific TTS key isn't provided
        self.google_tts_api_key = os.getenv("GOOGLE_TTS_API_KEY") or os.getenv(
            "GEMINI_API_KEY"
        )

        # Log initialization status
        if self.elevenlabs_api_key:
            if AsyncElevenLabs:
                self.client = AsyncElevenLabs(api_key=self.elevenlabs_api_key)
                logger.info("✅ ElevenLabs SDK client initialized")
                if self.custom_voice_id:
                    logger.info(
                        f"🎤 Custom ElevenLabs Voice ID detected: {self.custom_voice_id}"
                    )
                    # Allow 'custom' as a voice name
                    self.VOICES["custom"] = self.custom_voice_id
                    # Also override the requested voice if it's the default
                    self.VOICES["josh"] = self.custom_voice_id
            else:
                self.client = None
                logger.warning("⚠️ ElevenLabs API key found but SDK not installed!")
        else:
            self.client = None
            logger.warning("⚠️ ElevenLabs API key NOT found. Using fallback only.")

        if edge_tts:
            logger.info("✅ Edge TTS initialized (High-quality free fallback ready)")
        else:
            logger.warning("⚠️ Edge TTS not found. Fallback quality will be lower.")

        if self.google_tts_api_key:
            logger.info("✅ Google TTS/Gemini key loaded (tertiary fallback)")
        else:
            logger.warning("⚠️ No Google/ElevenLabs keys found for server-side TTS")

    @property
    def is_available(self) -> bool:
        """Check if any TTS service is available."""
        return bool(self.elevenlabs_api_key or edge_tts or self.google_tts_api_key)

    def get_status(self) -> Dict[str, Any]:
        """Return TTS service status."""
        return {
            "elevenlabs_enabled": bool(self.elevenlabs_api_key),
            "edge_tts_enabled": bool(edge_tts),
            "google_tts_enabled": bool(self.google_tts_api_key),
            "available": self.is_available,
            "default_voice": self.DEFAULT_VOICE,
        }

    async def text_to_speech(
        self, text: str, voice: Optional[str] = None, return_base64: bool = True
    ) -> Dict[str, Any]:
        """
        Convert text to speech audio. -> ElevenLabs -> Edge TTS -> Google TTS
        """
        if not text or not text.strip():
            return {"success": False, "error": "No text provided"}

        # Clean text for voice (remove markdown, limit length)
        clean_text = self._clean_text_for_voice(text)

        # Use default voice if not specified
        if not voice:
            voice = self.DEFAULT_VOICE

        if len(clean_text) > 5000:
            clean_text = clean_text[:5000] + "..."
            logger.warning("Text truncated to 5000 chars for TTS")

        # 1. Try ElevenLabs
        elevenlabs_error = None
        if self.elevenlabs_api_key:
            logger.info(f"Attempting ElevenLabs TTS with voice: {voice}")
            result = await self._elevenlabs_tts(clean_text, voice, return_base64)
            if result.get("success"):
                logger.info(f"✅ Served audio via ElevenLabs ({voice})")
                return result
            elevenlabs_error = result.get("error", "Unknown ElevenLabs error")
            logger.warning(
                f"❌ ElevenLabs failed: {elevenlabs_error}. Trying Edge TTS..."
            )
        else:
            logger.warning("No ElevenLabs API key - skipping to core providers")

        # 2. Try Edge TTS (High Quality Free Fallback)
        edge_error = None
        if edge_tts:
            result = await self._edge_tts_generate(clean_text, voice, return_base64)
            if result.get("success"):
                logger.info("✅ Served audio via Edge TTS fallback")
                return result
            edge_error = result.get("error")
            logger.warning(f"Edge TTS failed: {edge_error}. Trying Google...")

        # 3. Fallback to Google TTS
        if self.google_tts_api_key:
            return await self._google_tts(clean_text, return_base64)

        # Return relevant error
        final_error = elevenlabs_error or edge_error or "No TTS providers available"
        return {"success": False, "error": f"All TTS failed. Last error: {final_error}"}

    async def _edge_tts_generate(
        self, text: str, voice: str, return_base64: bool
    ) -> Dict[str, Any]:
        """Generate speech using Microsoft Edge TTS (Free, high quality)."""
        try:
            # Map simplified voice name to Edge voice ID
            edge_voice = self.EDGE_VOICES.get(voice.lower(), "en-US-GuyNeural")
            communicate = edge_tts.Communicate(text, edge_voice)

            # Accumulate audio bytes
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if return_base64:
                b64_audio = base64.b64encode(audio_data).decode("utf-8")
                return {
                    "success": True,
                    "audio_base64": b64_audio,
                    "content_type": "audio/mpeg",  # Edge returns mp3 by default
                    "provider": "edge-tts",
                }
            return {"success": True, "audio": audio_data, "content_type": "audio/mpeg"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _clean_text_for_voice(self, text: str) -> str:
        """Remove markdown and format text for natural speech."""
        import re

        # Remove markdown formatting
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # Bold
        text = re.sub(r"\*([^*]+)\*", r"\1", text)  # Italic
        text = re.sub(r"`([^`]+)`", r"\1", text)  # Code
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # Links
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)  # Headers
        text = re.sub(r"^[-*]\s*", "", text, flags=re.MULTILINE)  # Bullets
        text = re.sub(r"\n{2,}", ". ", text)  # Multiple newlines
        text = re.sub(r"\n", " ", text)  # Single newlines

        return text.strip()

    async def _elevenlabs_tts(
        self, text: str, voice: str, return_base64: bool
    ) -> Dict[str, Any]:
        """Generate speech using ElevenLabs SDK."""
        if not self.client:
            return {
                "success": False,
                "error": "ElevenLabs SDK not initialized or key missing",
            }

        # Try to map name to ID, otherwise assume it's a direct ID
        voice_id = self.VOICES.get(voice.lower())
        if not voice_id:
            voice_id = voice  # Use provided string as direct ID

        logger.info(
            f"🎤 TTS Generation: voice_requested='{voice}', voice_id_used='{voice_id}'"
        )

        try:
            try:
                # IMPORTANT: convert() returns an async generator, do NOT await the call itself
                audio_stream = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )

                # Consume the async generator to get full audio bytes
                audio_data = b""
                async for chunk in audio_stream:
                    audio_data += chunk

            except Exception as e:
                logger.warning(
                    f"ElevenLabs Multilingual V2 failed ({e}), falling back to Monolingual V1"
                )
                # Fallback to standard model
                # Do NOT await the generator creation
                audio_stream = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice_id,
                    model_id="eleven_monolingual_v1",
                    output_format="mp3_44100_128",
                )

                audio_data = b""
                async for chunk in audio_stream:
                    audio_data += chunk

            if return_base64:
                audio_b64 = base64.b64encode(audio_data).decode("utf-8")
                return {
                    "success": True,
                    "audio_base64": audio_b64,
                    "content_type": "audio/mpeg",
                    "provider": "elevenlabs",
                    "voice": voice,
                }
            return {
                "success": True,
                "audio_bytes": audio_data,
                "content_type": "audio/mpeg",
                "provider": "elevenlabs",
            }

        except Exception as e:
            logger.error(f"ElevenLabs SDK request failed: {e}")
            return {"success": False, "error": str(e)}

    async def _google_tts(self, text: str, return_base64: bool) -> Dict[str, Any]:
        """Generate speech using Google Cloud TTS API (fallback)."""
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.google_tts_api_key}"

        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-US",
                "name": "en-US-Neural2-D",  # Premium male voice (matches Josh persona)
                "ssmlGender": "MALE",
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": 1.0,
                "pitch": 0.0,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    audio_b64 = data.get("audioContent", "")

                    if return_base64:
                        return {
                            "success": True,
                            "audio_base64": audio_b64,
                            "content_type": "audio/mpeg",
                            "provider": "google",
                        }
                    else:
                        audio_bytes = base64.b64decode(audio_b64)
                        return {
                            "success": True,
                            "audio_bytes": audio_bytes,
                            "content_type": "audio/mpeg",
                            "provider": "google",
                        }
                else:
                    error_text = response.text[:200]
                    logger.error(
                        f"Google TTS error {response.status_code}: {error_text}"
                    )
                    return {
                        "success": False,
                        "error": f"Google TTS API error: {response.status_code}",
                    }

        except Exception as e:
            logger.error(f"Google TTS request failed: {e}")
            return {"success": False, "error": str(e)}


# Voice-optimized system prompt for Pinnacle AI (NO PRICING - services only)
VOICE_SYSTEM_PROMPT = """You are the AI Voice Assistant for Pinnacle AI Solutions, a premier firm specializing in enterprise-grade AI agents, websites, and automation.

VOICE INTERACTION RULES:
- Keep responses SHORT and conversational (2-4 sentences ideal)
- Speak naturally like a helpful technical consultant
- Avoid long lists - summarize instead
- No markdown formatting (**, [], etc.) - plain text only
- Use contractions (we're, you'll, that's)

CORE SERVICES:
1. Website Development (Next.js, FastAPI)
2. AI Chatbot Integrations (RAG, Multi-modal)
3. AI Agents (Workflow Automation)
4. Data Extraction & Scrapers (Scalable)

CONTACT: futureai4all@gmail.com

For inquiries: Get the project details and user contact info, then confirm we'll reach out within 24 business hours.

Be professional, intelligent, and conversational. No bullet points or lists in spoken responses."""
