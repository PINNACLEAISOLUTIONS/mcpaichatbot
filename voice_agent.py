"""
Voice Agent Module for Miami Loves Green Landscaping
TTS: ElevenLabs (primary) with Google TTS fallback
Designed for Render deployment with environment variables
"""

import os
import logging
import base64
from typing import Dict, Any
import httpx

# Import ElevenLabs SDK
try:
    from elevenlabs.client import AsyncElevenLabs
except ImportError:
    AsyncElevenLabs = None

logger = logging.getLogger(__name__)


class VoiceAgent:
    """Text-to-Speech agent with ElevenLabs primary and Google fallback."""

    # ElevenLabs voice IDs (free tier compatible)
    VOICES = {
        "miami": "s3TPKV1kjDlVtZbl4Ksh",  # Custom Miami Loves Green voice
        "rachel": "21m00Tcm4TlvDq8ikWAM",  # Warm, professional female
        "josh": "TxGEqnHWrfWFTfGW9XjX",  # Friendly male
        "bella": "EXAVITQu4vr4xnSDxMaL",  # Young female
        "adam": "pNInz6obpgDQGcFmaJgB",  # Deep male
        "antoni": "ErXwobaYiN019PkySvjV",  # Antoni (Deep, well rounded)
    }
    DEFAULT_VOICE = "miami"

    def __init__(self):
        """Initialize voice agent with API keys from environment."""
        # Load API keys from Render environment
        self.elevenlabs_api_key = (
            os.getenv("ELEVENLABS_API_KEY")
            or "sk_067a9530fadd6b203cf48003655fea83e4c0566b806ae77e"
        )
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

        if self.google_tts_api_key:
            logger.info("✅ Google TTS/Gemini key loaded (fallback ready)")
        else:
            logger.warning("⚠️ No Google/ElevenLabs keys found for server-side TTS")

    @property
    def is_available(self) -> bool:
        """Check if any TTS service is available."""
        return bool(self.elevenlabs_api_key or self.google_tts_api_key)

    def get_status(self) -> Dict[str, Any]:
        """Return TTS service status."""
        return {
            "elevenlabs_enabled": bool(self.elevenlabs_api_key),
            "google_tts_enabled": bool(self.google_tts_api_key),
            "available": self.is_available,
            "default_voice": self.DEFAULT_VOICE,
        }

    async def text_to_speech(
        self, text: str, voice: str = "josh", return_base64: bool = True
    ) -> Dict[str, Any]:
        """
        Convert text to speech audio.

        Args:
            text: Text to convert to speech
            voice: Voice ID or name (rachel, josh, bella, adam)
            return_base64: If True, return base64 encoded audio

        Returns:
            Dict with success status and audio data or error
        """
        if not text or not text.strip():
            return {"success": False, "error": "No text provided"}

        # Clean text for voice (remove markdown, limit length)
        clean_text = self._clean_text_for_voice(text)

        if len(clean_text) > 5000:
            clean_text = clean_text[:5000] + "..."
            logger.warning("Text truncated to 5000 chars for TTS")

        # Try ElevenLabs first
        elevenlabs_error = None
        if self.elevenlabs_api_key:
            result = await self._elevenlabs_tts(clean_text, voice, return_base64)
            if result.get("success"):
                return result
            elevenlabs_error = result.get("error", "Unknown ElevenLabs error")
            logger.warning(f"ElevenLabs failed: {elevenlabs_error}. Trying Google...")

        # Fallback to Google TTS
        if self.google_tts_api_key:
            return await self._google_tts(clean_text, return_base64)

        # Return actual error from ElevenLabs if available
        if elevenlabs_error:
            return {"success": False, "error": f"ElevenLabs failed: {elevenlabs_error}"}

        return {"success": False, "error": "No TTS API keys configured"}

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
                audio_stream = await self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
            except Exception as e:
                logger.warning(
                    f"ElevenLabs Multilingual V2 failed ({e}), falling back to Monolingual V1"
                )
                # Fallback to standard model
                audio_stream = await self.client.text_to_speech.convert(
                    text=text,
                    voice_id=voice_id,
                    model_id="eleven_monolingual_v1",
                    output_format="mp3_44100_128",
                )

            # Consume the async generator to get full audio bytes
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


# Voice-optimized system prompt for Miami Loves Green (NO PRICING - services only)
VOICE_SYSTEM_PROMPT = """You are the AI Voice Assistant for Miami Loves Green Landscaping, a Miami-based company specializing in premium tropical landscaping and garden maintenance.

VOICE INTERACTION RULES:
- Keep responses SHORT and conversational (2-4 sentences ideal)
- Speak naturally like a helpful phone agent
- Avoid long lists - summarize instead
- No markdown formatting (**, [], etc.) - plain text only
- Use contractions (we're, you'll, that's)

CORE SERVICES:
1. Landscape Design & 3D Renderings
2. Garden Maintenance (Weekly/Bi-weekly)
3. Irrigation Systems & Repairs
4. Hardscaping (Patios, Walkways)
5. Tree Care & Palm Maintenance
6. Outdoor Lighting Systems

CONTACT: (786) 570-3215 | miamilovesgreenlandscaping@gmail.com

For quotes: Get name, email, phone, and project details, then confirm 24hr callback.

Be warm, helpful, and conversational. No bullet points or lists in spoken responses."""
