"""
Voice Agent Module for Pinnacle AI Solutions & Miami Loves Green
TTS: ElevenLabs (primary flagship) with Edge TTS (neural fallback) and Google TTS
Engineered for ultra-realistic conversational audio and seamless voice mode
"""

import os
import re
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

    # Top ElevenLabs male voices
    # ADAM is universally celebrated as ElevenLabs' gold-standard male voice:
    # Deep, warm, smooth, natural, charismatic, and perfectly paced for conversational AI.
    VOICES = {
        # Flagship Voices
        "adam": "pNInz6obpgDQGcFmaJgB",      # Adam (ElevenLabs #1 Flagship male voice)
        "antoni": "ErXwobaYiN019PkySvjV",    # Antoni (Crisp, modern American tech male)
        "brian": "nPczCjzI2devNBz1zQrb",     # Brian (Deep, resonant American male)
        "eric": "cjVigY5qzO86Huf0OWal",      # Eric (Friendly, conversational American male)
        "daniel": "onwK4e9ZLuTAKqWW03F9",    # Daniel (Authoritative British male)
        "chris": "iP95p4xoKVk53GoZ742B",     # Chris (Casual, charming American male)
        "george": "JBFqnCBsd6RMkjVDRZzb",    # George (Warm, raspy British male)
        "liam": "TX3LPaxmHKxFdv7VOQHJ",      # Liam (Young, energetic)
        "will": "bIHbv24MWmeRgasZH58o",      # Will (Friendly, conversational)
        "roger": "CwhRBWXzGAHq8TQ4Fs17",     # Roger (Confident, deep)
        "charlie": "IKne3meq5aSn9XLyUdCD",   # Charlie (Casual, Australian)
        # Female voices
        "rachel": "21m00Tcm4TlvDq8ikWAM",    # Rachel (Professional, warm)
        "bella": "EXAVITQu4vr4xnSDxMaL",     # Bella (Young, upbeat)
        # Aliases
        "pinnacle": "pNInz6obpgDQGcFmaJgB",  # Default Pinnacle: Adam
        "miami": "pNInz6obpgDQGcFmaJgB",     # Default Miami: Adam
        "josh": "pNInz6obpgDQGcFmaJgB",      # Legacy josh mapped to Adam
    }
    DEFAULT_VOICE = "adam"

    # Edge TTS Voice Map - Microsoft's highest fidelity neural voices
    EDGE_VOICES = {
        "adam": "en-US-AndrewNeural",        # Microsoft's top conversational male voice
        "pinnacle": "en-US-AndrewNeural",
        "miami": "en-US-AndrewNeural",
        "antoni": "en-US-AndrewNeural",
        "eric": "en-US-EricNeural",
        "brian": "en-US-BrianNeural",
        "daniel": "en-GB-RyanNeural",
        "guy": "en-US-GuyNeural",
        "josh": "en-US-GuyNeural",
        "rachel": "en-US-AriaNeural",
        "bella": "en-US-MichelleNeural",
    }

    # Best-practice ElevenLabs voice settings for lifelike conversational speech
    VOICE_SETTINGS = {
        "stability": 0.50,          # 0.50 allows natural inflection and emotional cadence
        "similarity_boost": 0.82,   # 0.82 preserves rich voice timbre and clarity
        "style": 0.05,              # 0.05 subtle expressiveness
        "use_speaker_boost": True   # Enhances volume consistency and fidelity
    }

    def __init__(self):
        """Initialize voice agent with API keys from environment."""
        raw_key = os.getenv("ELEVENLABS_API_KEY")
        self.elevenlabs_api_key = raw_key.strip() if raw_key else None
        
        # Check custom voice overrides
        self.custom_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip() or None
        self.pinnacle_voice_id = os.getenv("ELEVENLABS_VOICE_ID_PINNACLE", "").strip() or self.custom_voice_id or self.VOICES["adam"]
        self.miami_voice_id = os.getenv("ELEVENLABS_VOICE_ID_MIAMI", "").strip() or self.custom_voice_id or self.VOICES["adam"]

        if self.custom_voice_id:
            logger.info(f"🎤 Custom ElevenLabs Voice ID detected: {self.custom_voice_id}")
            self.VOICES["custom"] = self.custom_voice_id
        
        self.VOICES["pinnacle"] = self.pinnacle_voice_id
        self.VOICES["miami"] = self.miami_voice_id

        # Google TTS fallback key
        self.google_tts_api_key = os.getenv("GOOGLE_TTS_API_KEY") or os.getenv("GEMINI_API_KEY")

        if self.elevenlabs_api_key:
            if AsyncElevenLabs:
                self.client = AsyncElevenLabs(api_key=self.elevenlabs_api_key)
                logger.info("✅ ElevenLabs SDK client initialized with Adam/Antoni voices")
            else:
                self.client = None
                logger.info("ℹ️ ElevenLabs REST API mode active (direct HTTP)")
        else:
            self.client = None
            logger.warning("⚠️ ElevenLabs API key NOT found. Fallback providers active.")

        if edge_tts:
            logger.info("✅ Edge TTS initialized (High-quality AndrewNeural fallback ready)")
        else:
            logger.warning("⚠️ Edge TTS not found.")

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
            "pinnacle_voice": self.pinnacle_voice_id,
            "miami_voice": self.miami_voice_id
        }

    async def text_to_speech(
        self, text: str, voice: Optional[str] = None, brand_name: Optional[str] = None, return_base64: bool = True
    ) -> Dict[str, Any]:
        """
        Convert text to speech audio: ElevenLabs -> Edge TTS -> Google TTS
        """
        if not text or not text.strip():
            return {"success": False, "error": "No text provided"}

        # Clean text for natural speech
        clean_text = self._clean_text_for_voice(text)

        # Brand-specific voice resolution
        if not voice:
            b = (brand_name or "").lower()
            if "miami" in b or "green" in b:
                voice = "miami"
            else:
                voice = "pinnacle"

        if len(clean_text) > 5000:
            clean_text = clean_text[:5000] + "..."
            logger.warning("Text truncated to 5000 chars for TTS")

        # 1. Try ElevenLabs (Highest Quality)
        elevenlabs_error = None
        if self.elevenlabs_api_key:
            logger.info(f"Attempting ElevenLabs TTS with voice '{voice}'...")
            result = await self._elevenlabs_tts(clean_text, voice, return_base64)
            if result.get("success"):
                logger.info(f"✅ Served audio via ElevenLabs ({voice})")
                return result
            elevenlabs_error = result.get("error", "Unknown ElevenLabs error")
            logger.warning(f"❌ ElevenLabs failed: {elevenlabs_error}. Falling back to Edge TTS...")
        else:
            logger.info("ElevenLabs key not present; using Edge TTS fallback")

        # 2. Try Edge TTS (High-Quality AndrewNeural)
        edge_error = None
        if edge_tts:
            result = await self._edge_tts_generate(clean_text, voice, return_base64)
            if result.get("success"):
                logger.info("✅ Served audio via Edge TTS AndrewNeural fallback")
                return result
            edge_error = result.get("error")
            logger.warning(f"Edge TTS failed: {edge_error}. Trying Google...")

        # 3. Fallback to Google TTS
        if self.google_tts_api_key:
            return await self._google_tts(clean_text, return_base64)

        final_error = elevenlabs_error or edge_error or "No TTS providers available"
        return {"success": False, "error": f"All TTS failed. Last error: {final_error}"}

    async def _edge_tts_generate(
        self, text: str, voice: str, return_base64: bool
    ) -> Dict[str, Any]:
        """Generate speech using Microsoft Edge TTS (Free, high quality)."""
        try:
            edge_voice = self.EDGE_VOICES.get(voice.lower(), "en-US-AndrewNeural")
            communicate = edge_tts.Communicate(text, edge_voice)

            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if return_base64:
                b64_audio = base64.b64encode(audio_data).decode("utf-8")
                return {
                    "success": True,
                    "audio_base64": b64_audio,
                    "content_type": "audio/mpeg",
                    "provider": "edge-tts",
                }
            return {"success": True, "audio": audio_data, "content_type": "audio/mpeg", "provider": "edge-tts"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _clean_text_for_voice(self, text: str) -> str:
        """Remove markdown, URLs, symbols, and format numbers/acronyms for seamless speech."""
        # Remove markdown links, keep anchor text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove images
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
        # Remove code blocks and inline code
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Remove markdown headers and bullets
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        # Remove bold, italics, strikethrough
        text = re.sub(r"[*_~]{1,3}([^*_~]+)[*_~]{1,3}", r"\1", text)
        # Remove raw URLs
        text = re.sub(r"https?://\S+", "", text)
        # Format phone numbers so TTS speaks them with natural pacing: "(904) 686-6593" -> "904, 686, 6593"
        text = re.sub(r"\((\d{3})\)\s*(\d{3})-(\d{4})", r"\1, \2, \3", text)
        text = re.sub(r"(\d{3})-(\d{3})-(\d{4})", r"\1, \2, \3", text)
        # Normalize whitespace
        text = re.sub(r"\n{2,}", ". ", text)
        text = re.sub(r"\n", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def _elevenlabs_tts(
        self, text: str, voice: str, return_base64: bool
    ) -> Dict[str, Any]:
        """
        Generate speech using ElevenLabs.
        Tries low-latency Flash v2.5 first, then Turbo v2.5, then Multilingual v2.
        Supports both SDK and direct REST API for maximum reliability.
        """
        if not self.elevenlabs_api_key:
            return {"success": False, "error": "ElevenLabs API key missing"}

        # Resolve voice ID
        voice_id = self.VOICES.get(voice.lower(), voice)
        if not voice_id or len(voice_id) < 5:
            voice_id = self.VOICES["adam"]

        models_to_try = ["eleven_flash_v2_5", "eleven_turbo_v2_5", "eleven_multilingual_v2"]

        # Strategy 1: Direct REST API (Ultra reliable, exact latency params, no SDK version issues)
        headers = {
            "xi-api-key": self.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }

        async with httpx.AsyncClient(timeout=25.0) as http_client:
            for model_id in models_to_try:
                try:
                    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?optimize_streaming_latency=3&output_format=mp3_44100_128"
                    payload = {
                        "text": text,
                        "model_id": model_id,
                        "voice_settings": self.VOICE_SETTINGS
                    }
                    response = await http_client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        audio_data = response.content
                        if return_base64:
                            return {
                                "success": True,
                                "audio_base64": base64.b64encode(audio_data).decode("utf-8"),
                                "content_type": "audio/mpeg",
                                "provider": "elevenlabs",
                                "voice": voice,
                                "model": model_id
                            }
                        return {
                            "success": True,
                            "audio_bytes": audio_data,
                            "content_type": "audio/mpeg",
                            "provider": "elevenlabs",
                            "voice": voice,
                            "model": model_id
                        }
                    else:
                        logger.warning(f"ElevenLabs REST {model_id} returned {response.status_code}: {response.text[:160]}")
                except Exception as e:
                    logger.warning(f"ElevenLabs REST attempt ({model_id}) error: {e}")

        # Strategy 2: ElevenLabs SDK (if initialized)
        if self.client:
            for model_id in models_to_try:
                try:
                    audio_stream = self.client.text_to_speech.convert(
                        text=text,
                        voice_id=voice_id,
                        model_id=model_id,
                        output_format="mp3_44100_128"
                    )
                    audio_data = b""
                    async for chunk in audio_stream:
                        audio_data += chunk

                    if audio_data:
                        if return_base64:
                            return {
                                "success": True,
                                "audio_base64": base64.b64encode(audio_data).decode("utf-8"),
                                "content_type": "audio/mpeg",
                                "provider": "elevenlabs",
                                "voice": voice
                            }
                        return {
                            "success": True,
                            "audio_bytes": audio_data,
                            "content_type": "audio/mpeg",
                            "provider": "elevenlabs",
                            "voice": voice
                        }
                except Exception as e:
                    logger.warning(f"ElevenLabs SDK ({model_id}) error: {e}")

        return {"success": False, "error": "All ElevenLabs models failed"}

    async def _google_tts(self, text: str, return_base64: bool) -> Dict[str, Any]:
        """Generate speech using Google Cloud TTS API (tertiary fallback)."""
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.google_tts_api_key}"

        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-US",
                "name": "en-US-Neural2-D",
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
                            "provider": "google-tts",
                        }
                    return {
                        "success": True,
                        "audio": base64.b64decode(audio_b64),
                        "content_type": "audio/mpeg",
                        "provider": "google-tts",
                    }
                return {"success": False, "error": f"Google TTS error: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
